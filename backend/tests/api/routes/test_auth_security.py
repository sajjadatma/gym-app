from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes.utils import readiness_check
from app.core.config import Settings, settings
from app.core.rate_limit import reset_rate_limits
from app.utils import render_email_template
from tests.utils.helpers import TEST_SUPERUSER_PASSWORD


def _login_with_cookie(client: TestClient):
    response = client.post(
        "/api/v1/login/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": TEST_SUPERUSER_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    cookies = response.headers.get("set-cookie", "")
    assert "gym_access_token=" in cookies
    assert "gym_csrf_token=" in cookies
    csrf = client.cookies.get("gym_csrf_token")
    assert csrf
    return response.json()["access_token"], csrf, response


def test_login_sets_httponly_cookie_and_csrf_protects_mutation(
    client: TestClient,
) -> None:
    token, csrf, login = _login_with_cookie(client)
    set_cookie = login.headers.get_list("set-cookie")
    auth_cookie = next(value for value in set_cookie if value.startswith("gym_access_token="))
    csrf_cookie = next(value for value in set_cookie if value.startswith("gym_csrf_token="))
    assert "HttpOnly" in auth_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in auth_cookie

    # Cookie-authenticated unsafe requests require the double-submit header.
    missing_header = client.post("/api/v1/auth/logout")
    assert missing_header.status_code == 403
    assert missing_header.json()["detail"] == "csrf_failed"

    logged_out = client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
    )
    assert logged_out.status_code == 200, logged_out.text

    # Both the cookie and the old bearer token are now revoked.
    assert client.get("/api/v1/users/me").status_code == 401
    assert (
        client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 401
    )


def test_login_rate_limit_returns_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_WINDOW_SECONDS", 60)
    reset_rate_limits()
    email = "rate-limit-login@example.com"
    for _ in range(2):
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": email, "password": "wrong-password"},
        )
        assert response.status_code == 400
    limited = client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": "wrong-password"},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == "too_many_attempts"
    assert limited.headers["Retry-After"]


def test_login_ip_rate_limit_applies_across_usernames(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", 100)
    monkeypatch.setattr(settings, "LOGIN_IP_RATE_LIMIT", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_WINDOW_SECONDS", 60)
    reset_rate_limits()
    for index in range(2):
        response = client.post(
            "/api/v1/login/access-token",
            data={
                "username": f"spray-{index}@example.com",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 400
    limited = client.post(
        "/api/v1/login/access-token",
        data={
            "username": "spray-third@example.com",
            "password": "wrong-password",
        },
    )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_recovery_ip_rate_limit_applies_across_emails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RECOVERY_RATE_LIMIT", 100)
    monkeypatch.setattr(settings, "RECOVERY_IP_RATE_LIMIT", 2)
    monkeypatch.setattr(settings, "RECOVERY_RATE_WINDOW_SECONDS", 60)
    reset_rate_limits()
    for index in range(2):
        assert (
            client.post(
                f"/api/v1/password-recovery/spray-{index}@example.com"
            ).status_code
            == 200
        )
    limited = client.post(
        "/api/v1/password-recovery/spray-third@example.com"
    )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_recovery_rate_limit_returns_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RECOVERY_RATE_LIMIT", 2)
    monkeypatch.setattr(settings, "RECOVERY_RATE_WINDOW_SECONDS", 60)
    reset_rate_limits()
    email = "rate-limit-recovery@example.com"
    for _ in range(2):
        assert (
            client.post(f"/api/v1/password-recovery/{email}").status_code
            == 200
        )
    limited = client.post(f"/api/v1/password-recovery/{email}")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/utils/health-check/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert (
        response.headers["Referrer-Policy"]
        == "strict-origin-when-cross-origin"
    )
    policy = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database(client: TestClient) -> None:
    assert client.get("/api/v1/utils/ready/").status_code == 200

    class BrokenSession:
        def exec(self, _statement: object) -> object:
            raise RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as exc:
        readiness_check(BrokenSession())  # type: ignore[arg-type]
    assert exc.value.status_code == 503


def test_oversized_json_is_rejected_before_handlers(client: TestClient) -> None:
    response = client.post(
        "/api/v1/templates",
        content=b"x" * (settings.MAX_JSON_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request_too_large"


def test_email_templates_escape_user_html() -> None:
    html = render_email_template(
        template_name="invitation.html",
        context={
            "project_name": "Gym",
            "gym_name": '<img src=x onerror="alert(1)">',
            "full_name": "<b>Injected</b>",
            "link": "http://localhost/accept?token=x",
            "valid_hours": 72,
        },
    )
    assert '<img src=x onerror="alert(1)">' not in html
    assert "&lt;img" in html
    assert "&lt;b&gt;Injected&lt;/b&gt;" in html


def test_production_mode_requires_secure_cookies() -> None:
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(
            FASTAPI_ENV="production",
            COOKIE_SECURE=False,
            SECRET_KEY="x" * 64,
            FIRST_SUPERUSER=settings.FIRST_SUPERUSER,
            FIRST_SUPERUSER_PASSWORD="not-a-default-password",
            DATABASE_URL=settings.DATABASE_URL,
        )


def _request_with(headers: list[tuple[str, str]], peer: str = "127.0.0.1"):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(key.encode(), value.encode()) for key, value in headers],
            "client": (peer, 1234),
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )


def test_client_ip_ignores_forwarded_headers_when_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.rate_limit import client_ip

    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    request = _request_with([("x-forwarded-for", "1.2.3.4, 5.6.7.8")])
    assert client_ip(request) == "127.0.0.1"


def test_client_ip_uses_only_proxy_appended_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.rate_limit import client_ip

    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    request = _request_with([("x-forwarded-for", "9.9.9.9, 203.0.113.7")])
    # A client-supplied prefix must not become the rate-limit identity.
    assert client_ip(request) == "203.0.113.7"


def test_client_ip_falls_back_on_malformed_forwarded_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.rate_limit import client_ip

    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    request = _request_with([("x-forwarded-for", "1.2.3.4, not-an-ip")])
    assert client_ip(request) == "127.0.0.1"


def _base_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "SECRET_KEY": "x" * 64,
        "COOKIE_SECURE": True,
        "FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
        "FIRST_SUPERUSER_PASSWORD": "not-a-default-password",
        "DATABASE_URL": settings.DATABASE_URL,
    }
    values.update(overrides)
    return values


def test_staging_requires_email_sandbox_when_smtp_is_enabled() -> None:
    with pytest.raises(ValueError, match="EMAIL_REDIRECT_TO"):
        Settings(
            **_base_settings(
                FASTAPI_ENV="staging",
                SMTP_HOST="smtp.example.test",
            )
        )


def test_production_rejects_email_redirection() -> None:
    with pytest.raises(ValueError, match="EMAIL_REDIRECT_TO"):
        Settings(
            **_base_settings(
                FASTAPI_ENV="production",
                EMAIL_REDIRECT_TO="sandbox@example.test",
            )
        )


def test_staging_email_is_redirected_to_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import emails

    from app.utils import send_email

    captured: dict[str, object] = {}

    class FakeMessage:
        def __init__(self, **kwargs: object) -> None:
            captured["message"] = kwargs

        def send(self, *, to: str, smtp: dict[str, object]) -> object:
            captured["to"] = to
            captured["smtp"] = smtp
            return SimpleNamespace(status_code=250)

    monkeypatch.setattr(emails.message, "Message", FakeMessage)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "no-reply@example.test")
    monkeypatch.setattr(settings, "EMAIL_REDIRECT_TO", "sandbox@example.test")
    monkeypatch.setattr(settings, "FASTAPI_ENV", "staging")

    send_email(email_to="real-user@example.test", subject="Invitation", html_content="ok")

    assert captured["to"] == "sandbox@example.test"
    message = captured["message"]
    assert isinstance(message, dict)
    assert str(message["subject"]).startswith("[staging]")
