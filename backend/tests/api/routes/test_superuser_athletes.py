from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AthleteProfile, CoachAssignment, GymMembership
from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    unique_email,
)


def _owner(
    client: TestClient, superuser_headers: dict[str, str], name: str
) -> tuple[dict, dict[str, str]]:
    email = unique_email("owner")
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


def _coach(
    client: TestClient, owner: dict[str, str], gym: dict, email: str | None = None
) -> dict:
    return add_member(
        client,
        owner,
        gym["id"],
        email=email or unique_email("coach"),
        roles=["COACH"],
        phone="09120000000",
    )["member"]


def test_superuser_athlete_list_is_authorized_and_cross_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete List A")
    coach_a = _coach(client, owner_a, gym_a)
    email_a = unique_email("athlete-a")
    create_athlete(
        client,
        owner_a,
        email=email_a,
        coach_user_id=coach_a["user_id"],
        phone="09121111111",
    )
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete List B")
    coach_b = _coach(client, owner_b, gym_b)
    email_b = unique_email("athlete-b")
    create_athlete(
        client,
        owner_b,
        email=email_b,
        coach_user_id=coach_b["user_id"],
        phone="09122222222",
    )

    assert (
        client.get("/api/v1/superuser/athletes", headers=owner_a).status_code
        == 403
    )

    listing = client.get("/api/v1/superuser/athletes", headers=superuser_headers)
    assert listing.status_code == 200, listing.text
    rows = listing.json()["data"]
    by_email = {row["email"]: row for row in rows}
    assert by_email[email_a]["gym_name"] == "Athlete List A"
    assert by_email[email_a]["phone"] == "09121111111"
    assert by_email[email_a]["coach_name"]
    assert by_email[email_b]["gym_name"] == "Athlete List B"

    filtered = client.get(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        params={"q": email_a},
    )
    assert [row["email"] for row in filtered.json()["data"]] == [email_a]

    by_gym = client.get(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        params={"gym_id": gym_b["id"]},
    )
    assert [row["email"] for row in by_gym.json()["data"]] == [email_b]


def test_superuser_create_athlete_requires_coach(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Athlete Create Gym")
    coach = _coach(client, owner, gym)
    email = unique_email("created-athlete")

    missing = client.post(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        json={
            "gym_id": gym["id"],
            "email": email,
            "full_name": email,
            "phone": "09123333333",
            "activation_method": "password",
            "initial_password": "AthletePass123!",
        },
    )
    assert missing.status_code == 400, missing.text
    assert missing.json()["detail"] == "coach_required"

    created = client.post(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        json={
            "gym_id": gym["id"],
            "coach_user_id": coach["user_id"],
            "email": email,
            "full_name": email,
            "phone": "09123333333",
            "activation_method": "password",
            "initial_password": "AthletePass123!",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["athlete"]["profile"]["email"] == email

    listing = client.get(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        params={"q": email},
    ).json()["data"]
    assert listing[0]["gym_name"] == "Athlete Create Gym"
    assert listing[0]["coach_user_id"] == coach["user_id"]
    assert listing[0]["is_archived"] is False


def test_superuser_athlete_archive_restore_and_delete_are_club_scoped(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Scope A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Scope B")
    coach_a = _coach(client, owner_a, gym_a)
    coach_b = _coach(client, owner_b, gym_b)
    email = unique_email("multi-athlete")
    athlete_a = create_athlete(
        client,
        owner_a,
        email=email,
        coach_user_id=coach_a["user_id"],
        phone="09124444444",
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        owner_b,
        email=email,
        coach_user_id=coach_b["user_id"],
        phone="09124444444",
    )["athlete"]["profile"]

    archived = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text
    profile_a = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_a["id"],
            AthleteProfile.user_id == athlete_a["user_id"],
        )
    ).one()
    profile_b = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_b["id"],
            AthleteProfile.user_id == athlete_b["user_id"],
        )
    ).one()
    assert profile_a.is_archived is True
    assert profile_b.is_archived is False
    assignment_a = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_a["id"],
            CoachAssignment.athlete_user_id == athlete_a["user_id"],
        )
    ).one()
    assignment_b = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_b["id"],
            CoachAssignment.athlete_user_id == athlete_b["user_id"],
        )
    ).one()
    assert assignment_a.ended_at is not None
    assert assignment_b.ended_at is None

    restored = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}/restore",
        headers=superuser_headers,
        json={"coach_user_id": coach_a["user_id"]},
    )
    assert restored.status_code == 200, restored.text
    db_session.refresh(profile_a)
    assert profile_a.is_archived is False

    deleted = client.delete(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}",
        headers=superuser_headers,
    )
    assert deleted.status_code == 200, deleted.text
    remaining_b = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_b["id"],
            AthleteProfile.user_id == athlete_b["user_id"],
        )
    ).first()
    assert remaining_b is not None
    memberships = db_session.exec(
        select(GymMembership).where(
            GymMembership.user_id == athlete_a["user_id"]
        )
    ).all()
    assert len(memberships) == 1
    assert str(memberships[0].gym_id) == gym_b["id"]


def test_superuser_athlete_delete_preserves_other_staff_roles(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = _owner(client, superuser_headers, "Athlete Roles Gym")
    email = unique_email("staff-athlete")
    coach_member = _coach(client, owner, gym, email=email)
    athlete = create_athlete(
        client,
        owner,
        email=email,
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]

    deleted = client.delete(
        f"/api/v1/superuser/athletes/{gym['id']}/{athlete['user_id']}",
        headers=superuser_headers,
    )
    assert deleted.status_code == 200, deleted.text

    membership = db_session.get(GymMembership, coach_member["membership_id"])
    assert membership is not None
    members = client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers=owner
    ).json()["data"]
    row = next(
        item for item in members if item["membership_id"] == str(membership.id)
    )
    assert "COACH" in row["roles"]
    assert "ATHLETE" not in row["roles"]
