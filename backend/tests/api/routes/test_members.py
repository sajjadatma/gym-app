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
