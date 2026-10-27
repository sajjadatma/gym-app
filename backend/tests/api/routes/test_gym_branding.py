from __future__ import annotations

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_gym,
    unique_email,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"brand" * 8


def _owner(
    client: TestClient, superuser_headers: dict[str, str], name: str
) -> tuple[dict, dict[str, str]]:
    email = unique_email("brand-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=name,
        owner_email=email,
        password="owner-pass-123",
    )["gym"]
    raw = auth_headers(client, email, "owner-pass-123")
    change_password(
        client,
        raw,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    headers = auth_headers(client, email, "owner-pass-456")
    headers["X-Gym-ID"] = gym["id"]
    return gym, headers


def test_gym_admin_can_set_branding_colors(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Branding Colors Gym")

    response = client.patch(
        f"/api/v1/gyms/{gym['id']}",
        headers=owner,
        json={"brand_primary_color": "#AA33CC", "brand_accent_color": "#112233"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["brand_primary_color"] == "#aa33cc"
    assert response.json()["brand_accent_color"] == "#112233"
    assert response.json()["logo_url"] is None

    invalid = client.patch(
        f"/api/v1/gyms/{gym['id']}",
        headers=owner,
        json={"brand_primary_color": "purple"},
    )
    assert invalid.status_code == 422


def test_non_admin_cannot_change_branding(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Branding Auth Gym")
    coach = add_member(
        client,
        owner,
        gym["id"],
        email=unique_email("brand-coach"),
        roles=["COACH"],
    )["member"]
    coach_raw = auth_headers(client, coach["email"], "member-pass-123")
    change_password(
        client,
        coach_raw,
        current_password="member-pass-123",
        new_password="coach-pass-456",
    )
    coach_headers = auth_headers(client, coach["email"], "coach-pass-456")
    coach_headers["X-Gym-ID"] = gym["id"]

    response = client.patch(
        f"/api/v1/gyms/{gym['id']}",
        headers=coach_headers,
        json={"brand_primary_color": "#123456"},
    )
    logo = client.post(
        f"/api/v1/gyms/{gym['id']}/branding/logo",
        headers=coach_headers,
        files={"file": ("logo.png", PNG, "image/png")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "gym_admin_required"
    assert logo.status_code == 403


def test_logo_upload_read_and_delete(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Branding Logo Gym")

    upload = client.post(
        f"/api/v1/gyms/{gym['id']}/branding/logo",
        headers=owner,
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    logo_url = upload.json()["logo_url"]
    assert logo_url and "/branding/logo?v=" in logo_url

    download = client.get(f"/api/v1/gyms/{gym['id']}/branding/logo", headers=owner)
    assert download.status_code == 200, download.text
    assert download.content == PNG
    assert download.headers["content-type"].startswith("image/png")

    _other_gym, other_owner = _owner(
        client, superuser_headers, "Branding Logo Other"
    )
    outsider = client.get(
        f"/api/v1/gyms/{gym['id']}/branding/logo", headers=other_owner
    )
    assert outsider.status_code == 404

    removed = client.delete(
        f"/api/v1/gyms/{gym['id']}/branding/logo", headers=owner
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["logo_url"] is None
    assert (
        client.get(
            f"/api/v1/gyms/{gym['id']}/branding/logo", headers=owner
        ).status_code
        == 404
    )


def test_logo_validation_and_gym_isolation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Branding Scope A")
    gym_b, _owner_b = _owner(client, superuser_headers, "Branding Scope B")

    wrong_type = client.post(
        f"/api/v1/gyms/{gym_a['id']}/branding/logo",
        headers=owner_a,
        files={"file": ("logo.svg", b"<svg/>", "image/svg+xml")},
    )
    too_large = client.post(
        f"/api/v1/gyms/{gym_a['id']}/branding/logo",
        headers=owner_a,
        files={"file": ("logo.png", PNG + b"x" * (512 * 1024), "image/png")},
    )
    cross_gym = client.post(
        f"/api/v1/gyms/{gym_b['id']}/branding/logo",
        headers=owner_a,
        files={"file": ("logo.png", PNG, "image/png")},
    )

    assert wrong_type.status_code == 400
    assert too_large.status_code == 413
    assert cross_gym.status_code == 404
    assert gym_a["id"] != gym_b["id"]
