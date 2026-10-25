from __future__ import annotations

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    unique_email,
)


def test_athlete_membership_cannot_be_deactivated(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("members-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Members Gym",
        owner_email=owner_email,
        password="owner-pass-123",
    )["gym"]
    raw_owner = auth_headers(client, owner_email, "owner-pass-123")
    change_password(
        client,
        raw_owner,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    owner = auth_headers(client, owner_email, "owner-pass-456")
    owner["X-Gym-ID"] = gym["id"]
    coach_email = unique_email("members-coach")
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    athlete_email = unique_email("members-athlete")
    athlete = create_athlete(
        client,
        owner,
        email=athlete_email,
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]

    members = client.get(f"/api/v1/gyms/{gym['id']}/members", headers=owner)
    assert members.status_code == 200, members.text
    membership = next(
        item for item in members.json()["data"] if item["email"] == athlete_email
    )

    deactivated = client.patch(
        f"/api/v1/gyms/{gym['id']}/members/{membership['membership_id']}",
        headers=owner,
        json={"is_active": False},
    )
    assert deactivated.status_code == 400, deactivated.text
    assert (
        deactivated.json()["detail"]
        == "athlete_membership_cannot_be_deactivated"
    )

    still_visible = client.get(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    )
    assert still_visible.status_code == 200, still_visible.text


def _owner_headers(
    client: TestClient, superuser_headers: dict[str, str], name: str
) -> tuple[dict, dict[str, str]]:
    owner_email = unique_email("owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=name,
        owner_email=owner_email,
        password="owner-pass-123",
    )["gym"]
    raw = auth_headers(client, owner_email, "owner-pass-123")
    change_password(
        client,
        raw,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    headers = auth_headers(client, owner_email, "owner-pass-456")
    headers["X-Gym-ID"] = gym["id"]
    return gym, headers


def _member_payload(email: str, roles: list[str], phone: str | None = None) -> dict:
    body: dict = {
        "email": email,
        "full_name": email,
        "roles": roles,
        "activation_method": "password",
        "initial_password": "member-pass-123",
    }
    if phone is not None:
        body["phone"] = phone
    return body


def test_coach_creation_requires_phone(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(client, superuser_headers, "Phone Gym")
    missing = client.post(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        json=_member_payload(unique_email("phone-coach"), ["COACH"]),
    )
    assert missing.status_code == 400, missing.text
    assert missing.json()["detail"] == "coach_phone_required"

    created = client.post(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        json=_member_payload(
            unique_email("phone-coach"), ["COACH"], "09121234567"
        ),
    )
    assert created.status_code == 200, created.text
    assert created.json()["member"]["phone"] == "09121234567"


def test_coach_phone_fills_empty_account_without_overwriting(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    email = unique_email("shared-coach")
    gym_a, owner_a = _owner_headers(client, superuser_headers, "Phone Gym A")
    admin = client.post(
        f"/api/v1/gyms/{gym_a['id']}/members",
        headers=owner_a,
        json=_member_payload(email, ["GYM_ADMIN"]),
    )
    assert admin.status_code == 200, admin.text
    assert admin.json()["member"]["phone"] is None

    gym_b, owner_b = _owner_headers(client, superuser_headers, "Phone Gym B")
    filled = client.post(
        f"/api/v1/gyms/{gym_b['id']}/members",
        headers=owner_b,
        json=_member_payload(email, ["COACH"], "09120000001"),
    )
    assert filled.status_code == 200, filled.text
    assert filled.json()["member"]["phone"] == "09120000001"

    gym_c, owner_c = _owner_headers(client, superuser_headers, "Phone Gym C")
    kept = client.post(
        f"/api/v1/gyms/{gym_c['id']}/members",
        headers=owner_c,
        json=_member_payload(email, ["COACH"], "09120000002"),
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["member"]["phone"] == "09120000001"


def test_account_phone_is_returned_by_me(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(client, superuser_headers, "Phone Profile Gym")
    coach_email = unique_email("phone-profile-coach")
    created = client.post(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        json=_member_payload(coach_email, ["COACH"], "09127770000"),
    )
    assert created.status_code == 200, created.text

    headers = auth_headers(client, coach_email, "member-pass-123")
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    # The profile editor seeds its form from this value; an empty response
    # would clear the stored phone on the next profile save.
    assert me.json()["phone"] == "09127770000"

    saved = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={
            "full_name": coach_email,
            "email": coach_email,
            "phone": "09127770000",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["phone"] == "09127770000"
