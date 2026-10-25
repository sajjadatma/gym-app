from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import CoachAssignment, GymMembership, User
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
    client: TestClient,
    owner: dict[str, str],
    gym: dict,
    email: str | None = None,
    roles: list[str] | None = None,
    phone: str = "09120000000",
) -> dict:
    return add_member(
        client,
        owner,
        gym["id"],
        email=email or unique_email("coach"),
        roles=roles or ["COACH"],
        phone=phone,
    )["member"]


def _create_coach(
    client: TestClient,
    superuser_headers: dict[str, str],
    gym_id: str,
    email: str,
    phone: str,
) -> dict:
    response = client.post(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        json={
            "gym_id": gym_id,
            "email": email,
            "full_name": email,
            "phone": phone,
            "activation_method": "password",
            "initial_password": "CoachPass123!",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_superuser_coach_list_is_authorized_and_cross_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Coach List A")
    coach_a_email = unique_email("coach-a")
    _coach(client, owner_a, gym_a, email=coach_a_email, phone="09121111111")
    gym_b, owner_b = _owner(client, superuser_headers, "Coach List B")
    coach_b_email = unique_email("coach-b")
    _coach(client, owner_b, gym_b, email=coach_b_email, phone="09122222222")

    assert (
        client.get("/api/v1/superuser/coaches", headers=owner_a).status_code
        == 403
    )
    assert (
        client.delete(
            "/api/v1/superuser/coaches/00000000-0000-0000-0000-000000000000",
            headers=owner_a,
        ).status_code
        == 403
    )

    listing = client.get("/api/v1/superuser/coaches", headers=superuser_headers)
    assert listing.status_code == 200, listing.text
    rows = listing.json()["data"]
    by_email = {row["email"]: row for row in rows}
    assert by_email[coach_a_email]["gym_name"] == "Coach List A"
    assert by_email[coach_a_email]["phone"] == "09121111111"
    assert by_email[coach_b_email]["gym_name"] == "Coach List B"

    filtered = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"q": coach_a_email},
    )
    assert [row["email"] for row in filtered.json()["data"]] == [coach_a_email]

    by_gym = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"gym_id": gym_b["id"]},
    )
    assert [row["email"] for row in by_gym.json()["data"]] == [coach_b_email]


def test_superuser_create_coach_requires_phone_and_reuses_account(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, _owner_a = _owner(client, superuser_headers, "Coach Create A")
    gym_b, _owner_b = _owner(client, superuser_headers, "Coach Create B")
    email = unique_email("created-coach")

    blank = client.post(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        json={
            "gym_id": gym_a["id"],
            "email": email,
            "full_name": email,
            "phone": "   ",
        },
    )
    assert blank.status_code == 400, blank.text
    assert blank.json()["detail"] == "coach_phone_required"

    first = _create_coach(
        client, superuser_headers, gym_a["id"], email, "09123333333"
    )
    assert first["coach"]["phone"] == "09123333333"
    assert first["coach"]["gym_name"] == "Coach Create A"

    second = _create_coach(
        client, superuser_headers, gym_b["id"], email, "09124444444"
    )
    assert second["coach"]["user_id"] == first["coach"]["user_id"]
    assert second["coach"]["phone"] == "09123333333"
    assert db_session.exec(
        select(func.count()).select_from(User).where(User.email == email)
    ).one() == 1

    duplicate = client.post(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        json={
            "gym_id": gym_a["id"],
            "email": email,
            "full_name": email,
            "phone": "09123333333",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"] == "coach_already_exists"


def test_superuser_archive_ends_assignments_and_restore_keeps_history(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = _owner(client, superuser_headers, "Coach Archive Gym")
    coach_email = unique_email("archive-coach")
    coach = _coach(client, owner, gym, email=coach_email)
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("archive-athlete"),
        coach_user_id=coach["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]

    archived = client.post(
        f"/api/v1/superuser/coaches/{coach['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text

    membership = db_session.get(GymMembership, coach["membership_id"])
    assert membership and membership.is_active is False
    assignments = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym["id"],
            CoachAssignment.coach_user_id == coach["user_id"],
        )
    ).all()
    assert assignments and all(row.ended_at is not None for row in assignments)

    detail = client.get(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    ).json()
    assert detail["coach_user_id"] is None

    active_list = client.get(
        "/api/v1/superuser/coaches", headers=superuser_headers
    ).json()["data"]
    assert all(row["membership_id"] != coach["membership_id"] for row in active_list)
    archived_list = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"include_archived": True},
    ).json()["data"]
    assert any(row["membership_id"] == coach["membership_id"] for row in archived_list)

    restored = client.post(
        f"/api/v1/superuser/coaches/{coach['membership_id']}/restore",
        headers=superuser_headers,
    )
    assert restored.status_code == 200, restored.text
    db_session.refresh(membership)
    assert membership.is_active is True
    still_unassigned = client.get(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    ).json()
    assert still_unassigned["coach_user_id"] is None


def test_superuser_archive_protects_owner_and_multi_role_memberships(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = _owner(client, superuser_headers, "Coach Protection Gym")
    # The owner account already owns the membership; add the COACH role to it.
    owner_members = client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers=owner
    ).json()["data"]
    owner_row = next(row for row in owner_members if row["is_owner"])
    added = add_member(
        client,
        owner,
        gym["id"],
        email=owner_row["email"],
        roles=["COACH"],
    )["member"]
    assert added["membership_id"] == owner_row["membership_id"]

    owner_archive = client.post(
        f"/api/v1/superuser/coaches/{owner_row['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert owner_archive.status_code == 409, owner_archive.text
    assert owner_archive.json()["detail"] == "coach_archive_not_allowed"

    owner_role_removed = client.delete(
        f"/api/v1/superuser/coaches/{owner_row['membership_id']}",
        headers=superuser_headers,
    )
    assert owner_role_removed.status_code == 200, owner_role_removed.text
    owner_membership = db_session.get(
        GymMembership, owner_row["membership_id"]
    )
    assert owner_membership is not None
    owner_row_after = next(
        row
        for row in client.get(
            f"/api/v1/gyms/{gym['id']}/members", headers=owner
        ).json()["data"]
        if row["membership_id"] == owner_row["membership_id"]
    )
    assert "COACH" not in owner_row_after["roles"]
    assert (
        client.get(f"/api/v1/gyms/{gym['id']}", headers=owner).status_code
        == 200
    )

    admin_coach = _coach(
        client,
        owner,
        gym,
        email=unique_email("admin-coach"),
        roles=["COACH", "GYM_ADMIN"],
    )
    admin_archive = client.post(
        f"/api/v1/superuser/coaches/{admin_coach['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert admin_archive.status_code == 409, admin_archive.text
    assert admin_archive.json()["detail"] == "coach_archive_not_allowed"


def test_superuser_delete_coach_is_club_scoped_and_preserves_access(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Coach Delete A")
    gym_b, owner_b = _owner(client, superuser_headers, "Coach Delete B")
    email = unique_email("multi-coach")
    coach_a = _coach(
        client,
        owner_a,
        gym_a,
        email=email,
        roles=["COACH", "GYM_ADMIN"],
        phone="09125555555",
    )
    coach_b = _coach(client, owner_b, gym_b, email=email, phone="09125555555")
    athlete_a = create_athlete(
        client,
        owner_a,
        email=unique_email("delete-coach-athlete"),
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]

    removed = client.delete(
        f"/api/v1/superuser/coaches/{coach_a['membership_id']}",
        headers=superuser_headers,
    )
    assert removed.status_code == 200, removed.text

    membership_a = db_session.get(GymMembership, coach_a["membership_id"])
    membership_b = db_session.get(GymMembership, coach_b["membership_id"])
    assert membership_a is not None
    assert membership_b is not None and membership_b.is_active is True
    members_a = client.get(
        f"/api/v1/gyms/{gym_a['id']}/members", headers=owner_a
    ).json()["data"]
    row_a = next(
        row for row in members_a if row["membership_id"] == coach_a["membership_id"]
    )
    assert "COACH" not in row_a["roles"]
    assert "GYM_ADMIN" in row_a["roles"]
    assert (
        client.get(
            f"/api/v1/gyms/{gym_b['id']}/coaches", headers=owner_b
        ).json()["count"]
        == 1
    )
    ended = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_a["id"],
            CoachAssignment.coach_user_id == coach_a["user_id"],
        )
    ).all()
    assert ended and all(row.ended_at is not None for row in ended)
    still_present = client.get(
        f"/api/v1/athletes/{athlete_a['user_id']}", headers=owner_a
    )
    assert still_present.status_code == 200, still_present.text

    sole_coach = _coach(
        client,
        owner_a,
        gym_a,
        email=unique_email("sole-coach"),
        phone="09126666666",
    )
    deleted = client.delete(
        f"/api/v1/superuser/coaches/{sole_coach['membership_id']}",
        headers=superuser_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert db_session.get(GymMembership, sole_coach["membership_id"]) is None
    # The account itself is preserved even when the last membership is removed.
    login = client.post(
        "/api/v1/login/access-token",
        data={
            "username": sole_coach["email"],
            "password": "member-pass-123",
        },
    )
    assert login.status_code == 200


def test_superuser_archive_only_ends_assignments_in_that_club(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Coach Scope A")
    gym_b, owner_b = _owner(client, superuser_headers, "Coach Scope B")
    email = unique_email("scoped-coach")
    coach_a = _coach(client, owner_a, gym_a, email=email)
    coach_b = _coach(client, owner_b, gym_b, email=email)
    athlete_a = create_athlete(
        client,
        owner_a,
        email=unique_email("scope-athlete-a"),
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        owner_b,
        email=unique_email("scope-athlete-b"),
        coach_user_id=coach_b["user_id"],
    )["athlete"]["profile"]

    archived = client.post(
        f"/api/v1/superuser/coaches/{coach_a['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text

    for athlete, coach, expected_ended in (
        (athlete_a, coach_a, True),
        (athlete_b, coach_b, False),
    ):
        assignment = db_session.exec(
            select(CoachAssignment).where(
                CoachAssignment.athlete_user_id == athlete["user_id"],
                CoachAssignment.coach_user_id == coach["user_id"],
            )
        ).one()
        assert (assignment.ended_at is not None) is expected_ended


def test_superuser_coach_with_athlete_profile_cannot_be_archived(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Coach Athlete Profile Gym")
    email = unique_email("coach-profile")
    coach = _coach(client, owner, gym, email=email)
    create_athlete(
        client,
        owner,
        email=email,
        coach_user_id=coach["user_id"],
    )

    listing = client.get(
        "/api/v1/superuser/coaches", headers=superuser_headers
    ).json()["data"]
    row = next(
        item for item in listing if item["membership_id"] == coach["membership_id"]
    )
    assert row["can_archive"] is False

    archived = client.post(
        f"/api/v1/superuser/coaches/{coach['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 409, archived.text
    assert archived.json()["detail"] == "coach_archive_not_allowed"


def test_all_coach_management_routes_reject_non_superusers(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Coach Forbidden Gym")
    membership_id = uuid.uuid4()
    calls = [
        ("get", "/api/v1/superuser/coaches", None),
        (
            "post",
            "/api/v1/superuser/coaches",
            {
                "gym_id": gym["id"],
                "email": unique_email("forbidden-create"),
                "full_name": "Forbidden",
                "phone": "09120000000",
            },
        ),
        (
            "post",
            f"/api/v1/superuser/coaches/{membership_id}/archive",
            None,
        ),
        (
            "post",
            f"/api/v1/superuser/coaches/{membership_id}/restore",
            None,
        ),
        ("delete", f"/api/v1/superuser/coaches/{membership_id}", None),
    ]
    for method, url, body in calls:
        request = getattr(client, method)
        response = (
            request(url, headers=owner, json=body)
            if body is not None
            else request(url, headers=owner)
        )
        assert response.status_code == 403, (method, url, response.text)


def test_superuser_cannot_archive_own_coach_membership(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    me = client.get("/api/v1/users/me", headers=superuser_headers)
    assert me.status_code == 200, me.text
    gym, owner = _owner(client, superuser_headers, "Coach Self Gym")
    coach = add_member(
        client,
        owner,
        gym["id"],
        email=me.json()["email"],
        roles=["COACH"],
        phone="09120000000",
    )["member"]

    listing = client.get(
        "/api/v1/superuser/coaches", headers=superuser_headers
    ).json()["data"]
    row = next(
        item for item in listing if item["membership_id"] == coach["membership_id"]
    )
    assert row["can_archive"] is False

    archived = client.post(
        f"/api/v1/superuser/coaches/{coach['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 409, archived.text
    assert archived.json()["detail"] == "coach_archive_not_allowed"
