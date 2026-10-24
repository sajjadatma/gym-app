from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.core import security
from app.core.config import settings
from tests.utils.helpers import (
    auth_headers,
    change_password,
    create_gym,
    unique_email,
)


def _create_owner(
    client: TestClient, superuser_headers: dict[str, str], prefix: str
) -> str:
    email = unique_email(prefix)
    create_gym(
        client,
        superuser_headers,
        name=f"Token Gym {email}",
        owner_email=email,
        password="owner-pass-123",
    )
    return email


def _request_reset_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, email: str
) -> str:
    outbox: list[str] = []

    def fake_send_email(
        *, email_to: str = "", subject: str = "", html_content: str = ""
    ) -> None:
        _ = (email_to, subject)
        outbox.append(html_content)

    monkeypatch.setattr("app.api.routes.login.send_email", fake_send_email)
    response = client.post(f"/api/v1/password-recovery/{email}")
    assert response.status_code == 200
    assert len(outbox) == 1
    match = re.search(r"reset-password\?token=([^\"&<]+)", outbox[0])
    assert match
    return match.group(1)


def _reset(client: TestClient, token: str, new_password: str) -> Response:
    return client.post(
        "/api/v1/reset-password/",
        json={"token": token, "new_password": new_password},
    )


def test_reset_token_cannot_be_redeemed_twice(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    email = _create_owner(client, superuser_headers, "reset-replay")
    token = _request_reset_token(client, monkeypatch, email)

    first = _reset(client, token, "recovered-pass-123")
    assert first.status_code == 200, first.text

    replay = _reset(client, token, "replayed-pass-123")
    assert replay.status_code == 400
    assert replay.json()["detail"] == "invalid_token"

    assert auth_headers(client, email, "recovered-pass-123")
    rejected = client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": "replayed-pass-123"},
    )
    assert rejected.status_code == 400
    assert token not in caplog.text


def test_reset_token_is_invalidated_by_password_change(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _create_owner(client, superuser_headers, "reset-after-change")
    token = _request_reset_token(client, monkeypatch, email)
    raw_headers = auth_headers(client, email, "owner-pass-123")

    change_password(
        client,
        raw_headers,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )

    stale_reset = _reset(client, token, "stale-reset-pass-123")
    assert stale_reset.status_code == 400
    assert stale_reset.json()["detail"] == "invalid_token"
    assert auth_headers(client, email, "owner-pass-456")


def test_access_token_is_rejected_after_password_change(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    email = _create_owner(client, superuser_headers, "stale-change")
    old_headers = auth_headers(client, email, "owner-pass-123")
    assert client.get("/api/v1/users/me", headers=old_headers).status_code == 200

    change_password(
        client,
        old_headers,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )

    stale = client.get("/api/v1/users/me", headers=old_headers)
    assert stale.status_code == 401
    assert stale.json()["detail"] == "invalid_credentials"

    fresh_headers = auth_headers(client, email, "owner-pass-456")
    assert client.get("/api/v1/users/me", headers=fresh_headers).status_code == 200


def test_each_password_change_invalidates_the_previous_generation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    email = _create_owner(client, superuser_headers, "rotation")
    first_headers = auth_headers(client, email, "owner-pass-123")

    change_password(
        client,
        first_headers,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    second_headers = auth_headers(client, email, "owner-pass-456")
    assert client.get("/api/v1/users/me", headers=second_headers).status_code == 200

    change_password(
        client,
        second_headers,
        current_password="owner-pass-456",
        new_password="owner-pass-789",
    )
    assert client.get("/api/v1/users/me", headers=first_headers).status_code == 401
    assert client.get("/api/v1/users/me", headers=second_headers).status_code == 401
    assert auth_headers(client, email, "owner-pass-789")


def test_access_token_is_rejected_after_password_reset(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _create_owner(client, superuser_headers, "stale-reset")
    old_headers = auth_headers(client, email, "owner-pass-123")
    token = _request_reset_token(client, monkeypatch, email)

    reset = _reset(client, token, "recovered-pass-123")
    assert reset.status_code == 200, reset.text

    stale = client.get("/api/v1/users/me", headers=old_headers)
    assert stale.status_code == 401
    assert stale.json()["detail"] == "invalid_credentials"

    fresh_headers = auth_headers(client, email, "recovered-pass-123")
    assert client.get("/api/v1/users/me", headers=fresh_headers).status_code == 200


@pytest.mark.parametrize(
    "token_kind",
    ["malformed", "expired", "wrong-purpose", "future-version", "missing-subject"],
)
def test_invalid_reset_tokens_are_rejected(
    client: TestClient,
    superuser_headers: dict[str, str],
    token_kind: str,
) -> None:
    email = _create_owner(client, superuser_headers, "invalid-reset")
    if token_kind == "malformed":
        token = "not-a-token"
    else:
        claims: dict[str, object] = {
            "exp": (datetime.now(UTC) + timedelta(hours=1)).timestamp(),
            "sub": email,
            "purpose": "reset_password",
            "token_version": 0,
        }
        if token_kind == "expired":
            claims["exp"] = (datetime.now(UTC) - timedelta(minutes=1)).timestamp()
        elif token_kind == "wrong-purpose":
            claims["purpose"] = "invitation"
        elif token_kind == "future-version":
            claims["token_version"] = 1
        elif token_kind == "missing-subject":
            claims.pop("sub")
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm=security.ALGORITHM)

    response = _reset(client, token, "invalid-reset-pass-123")
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_token"


def test_legacy_tokens_without_version_claim_are_version_zero(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    email = _create_owner(client, superuser_headers, "legacy-token")
    issued = auth_headers(client, email, "owner-pass-123")["Authorization"]
    token = issued.removeprefix("Bearer ")
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
    claims.pop("token_version", None)
    legacy_token = jwt.encode(
        claims, settings.SECRET_KEY, algorithm=security.ALGORITHM
    )
    legacy_headers = {"Authorization": f"Bearer {legacy_token}"}
    assert client.get("/api/v1/users/me", headers=legacy_headers).status_code == 200

    change_password(
        client,
        legacy_headers,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    assert client.get("/api/v1/users/me", headers=legacy_headers).status_code == 401


def test_concurrent_reset_redemption_succeeds_at_most_once(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _create_owner(client, superuser_headers, "concurrent-reset")
    token = _request_reset_token(client, monkeypatch, email)

    def redeem(password: str) -> int:
        return _reset(client, token, password).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(redeem, ["concurrent-pass-a", "concurrent-pass-b"]))

    assert statuses == [200, 400]
