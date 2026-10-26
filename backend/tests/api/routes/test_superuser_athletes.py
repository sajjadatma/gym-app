from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    AthleteProfile,
    BodyAnalysisFile,
    CoachAssignment,
    Gym,
    GymMembership,
    GymMembershipRole,
    WorkoutDay,
    WorkoutProgram,
    WorkoutProgramVersion,
)
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


def test_superuser_can_edit_athlete_profile_and_reassign_same_gym_coach(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = _owner(client, superuser_headers, "Athlete Edit Gym")
    original_coach = _coach(client, owner, gym)
    replacement_coach = _coach(client, owner, gym)
    email = unique_email("editable-athlete")
    athlete = create_athlete(
        client,
        owner,
        email=email,
        coach_user_id=original_coach["user_id"],
        phone="09121112222",
    )["athlete"]["profile"]
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Edit Other Gym")
    coach_b = _coach(client, owner_b, gym_b)
    athlete_b = create_athlete(
        client,
        owner_b,
        email=email,
        coach_user_id=coach_b["user_id"],
        phone="09125556666",
    )["athlete"]["profile"]

    response = client.patch(
        f"/api/v1/superuser/athletes/{gym['id']}/{athlete['user_id']}",
        headers=superuser_headers,
        json={
            "full_name": "Updated Athlete",
            "phone": "09123334444",
            "coach_user_id": replacement_coach["user_id"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == athlete["user_id"]
    assert response.json()["full_name"] == "Updated Athlete"
    assert response.json()["phone"] == "09123334444"
    assert response.json()["coach_user_id"] == replacement_coach["user_id"]
    other_profile = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_b["id"],
            AthleteProfile.user_id == athlete_b["user_id"],
        )
    ).one()
    assert other_profile.phone == "09125556666"
    assignments = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym["id"],
            CoachAssignment.athlete_user_id == athlete["user_id"],
        )
    ).all()
    assert sum(assignment.ended_at is None for assignment in assignments) == 1
    assert str(next(
        assignment
        for assignment in assignments
        if assignment.ended_at is None
    ).coach_user_id) == replacement_coach["user_id"]


def test_superuser_athlete_edit_rejects_cross_gym_coach_and_profile_scope(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Edit Scope A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Edit Scope B")
    coach_a = _coach(client, owner_a, gym_a)
    coach_b = _coach(client, owner_b, gym_b)
    email = unique_email("multi-gym-edit-athlete")
    athlete_a = create_athlete(
        client,
        owner_a,
        email=email,
        coach_user_id=coach_a["user_id"],
        phone="09121112222",
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        owner_b,
        email=unique_email("other-gym-athlete"),
        coach_user_id=coach_b["user_id"],
        phone="09125556666",
    )["athlete"]["profile"]

    cross_gym_coach = client.patch(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}",
        headers=superuser_headers,
        json={"phone": "09120000001", "coach_user_id": coach_b["user_id"]},
    )
    coach_b_row = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"gym_id": gym_b["id"], "q": coach_b["email"]},
    ).json()["data"][0]
    archived_coach = client.post(
        f"/api/v1/superuser/coaches/{coach_b_row['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived_coach.status_code == 200, archived_coach.text
    inactive_coach = client.patch(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}",
        headers=superuser_headers,
        json={"phone": "09120000003", "coach_user_id": coach_b["user_id"]},
    )
    mismatched_profile = client.patch(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_b['user_id']}",
        headers=superuser_headers,
        json={"phone": "09120000002"},
    )

    assert cross_gym_coach.status_code == 400, cross_gym_coach.text
    assert inactive_coach.status_code == 400, inactive_coach.text
    assert mismatched_profile.status_code == 404, mismatched_profile.text
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
    assert profile_a.phone == "09121112222"
    assert profile_b.phone == "09125556666"


def test_superuser_athlete_edit_rejects_null_coach_without_partial_update(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = _owner(client, superuser_headers, "Athlete Edit Validation Gym")
    coach = _coach(client, owner, gym)
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("athlete-edit-validation"),
        coach_user_id=coach["user_id"],
        phone="09121112222",
    )["athlete"]["profile"]

    response = client.patch(
        f"/api/v1/superuser/athletes/{gym['id']}/{athlete['user_id']}",
        headers=superuser_headers,
        json={"full_name": "Must Not Persist", "coach_user_id": None},
    )

    assert response.status_code == 400
    profile = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym["id"],
            AthleteProfile.user_id == athlete["user_id"],
        )
    ).one()
    assert profile.phone == "09121112222"


def test_non_superuser_cannot_edit_athlete(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Athlete Edit Auth Gym")
    coach = _coach(client, owner, gym)
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("auth-edit-athlete"),
        coach_user_id=coach["user_id"],
    )["athlete"]["profile"]

    response = client.patch(
        f"/api/v1/superuser/athletes/{gym['id']}/{athlete['user_id']}",
        headers=owner,
        json={"phone": "09120009999"},
    )

    assert response.status_code == 403


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


def test_superuser_can_transfer_athlete_with_profile_program_and_files(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Transfer A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Transfer B")
    source_coach = _coach(client, owner_a, gym_a)
    destination_coach = _coach(client, owner_b, gym_b)
    email = unique_email("transfer-athlete")
    athlete = create_athlete(
        client,
        owner_a,
        email=email,
        coach_user_id=source_coach["user_id"],
        phone="09121112222",
    )["athlete"]["profile"]
    program = WorkoutProgram(
        gym_id=uuid.UUID(gym_a["id"]),
        athlete_user_id=uuid.UUID(athlete["user_id"]),
        created_by_id=uuid.UUID(source_coach["user_id"]),
    )
    db_session.add(program)
    db_session.flush()
    version = WorkoutProgramVersion(
        program_id=program.id,
        version_number=1,
        status="ACTIVE",
        title="Transferred program",
    )
    db_session.add(version)
    db_session.flush()
    day = WorkoutDay(version_id=version.id, day_number=1, title="Transferred day")
    body_file = BodyAnalysisFile(
        gym_id=uuid.UUID(gym_a["id"]),
        athlete_user_id=uuid.UUID(athlete["user_id"]),
        original_name="analysis.pdf",
        stored_name=f"{uuid.uuid4().hex}.pdf",
        content_type="application/pdf",
        size_bytes=10,
    )
    db_session.add_all([day, body_file])
    db_session.commit()
    program_id = program.id
    version_id = version.id
    day_id = day.id
    body_file_id = body_file.id
    source_membership = db_session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_a["id"],
            GymMembership.user_id == athlete["user_id"],
        )
    ).one()
    source_membership_id = source_membership.id

    response = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete['user_id']}/transfer",
        headers=superuser_headers,
        json={
            "gym_id": gym_b["id"],
            "coach_user_id": destination_coach["user_id"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == athlete["user_id"]
    assert response.json()["gym_id"] == gym_b["id"]
    assert response.json()["gym_name"] == "Athlete Transfer B"
    assert response.json()["phone"] == "09121112222"
    assert response.json()["coach_user_id"] == destination_coach["user_id"]
    assert response.json()["coach_name"]

    db_session.expire_all()
    assert db_session.get(GymMembership, source_membership_id) is None
    destination_membership = db_session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_b["id"],
            GymMembership.user_id == athlete["user_id"],
        )
    ).one()
    assert "ATHLETE" in {
        row.role
        for row in db_session.exec(
            select(GymMembershipRole).where(
                GymMembershipRole.membership_id == destination_membership.id
            )
        ).all()
    }
    profile = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_b["id"],
            AthleteProfile.user_id == athlete["user_id"],
        )
    ).one()
    assert profile.phone == "09121112222"
    moved_program = db_session.get(WorkoutProgram, program_id)
    assert moved_program is not None
    assert str(moved_program.gym_id) == gym_b["id"]
    moved_version = db_session.get(WorkoutProgramVersion, version_id)
    assert moved_version is not None
    assert moved_version.program_id == program_id
    moved_day = db_session.get(WorkoutDay, day_id)
    assert moved_day is not None
    assert moved_day.version_id == version_id
    moved_file = db_session.get(BodyAnalysisFile, body_file_id)
    assert moved_file is not None
    assert str(moved_file.gym_id) == gym_b["id"]
    source_assignment = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_a["id"],
            CoachAssignment.athlete_user_id == athlete["user_id"],
        )
    ).one()
    destination_assignment = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_b["id"],
            CoachAssignment.athlete_user_id == athlete["user_id"],
        )
    ).one()
    assert source_assignment.ended_at is not None
    assert destination_assignment.ended_at is None
    assert str(destination_assignment.coach_user_id) == destination_coach["user_id"]

    assert (
        client.get(
            "/api/v1/superuser/athletes",
            headers=superuser_headers,
            params={"gym_id": gym_a["id"], "q": email},
        ).json()["count"]
        == 0
    )
    assert (
        client.get(
            "/api/v1/superuser/athletes",
            headers=superuser_headers,
            params={"gym_id": gym_b["id"], "q": email},
        ).json()["count"]
        == 1
    )


def test_athlete_transfer_rejects_invalid_destination_coach_and_same_gym(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Transfer Guard A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Transfer Guard B")
    source_coach = _coach(client, owner_a, gym_a)
    cross_gym_coach = _coach(client, owner_a, gym_a)
    archived_coach = _coach(client, owner_b, gym_b)
    athlete = create_athlete(
        client,
        owner_a,
        email=unique_email("athlete-transfer-guard"),
        coach_user_id=source_coach["user_id"],
    )["athlete"]["profile"]
    url = f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete['user_id']}/transfer"

    same_gym = client.post(
        url,
        headers=superuser_headers,
        json={"gym_id": gym_a["id"], "coach_user_id": source_coach["user_id"]},
    )
    wrong_gym_coach = client.post(
        url,
        headers=superuser_headers,
        json={
            "gym_id": gym_b["id"],
            "coach_user_id": cross_gym_coach["user_id"],
        },
    )
    archived_row = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"gym_id": gym_b["id"], "q": archived_coach["email"]},
    ).json()["data"][0]
    archived = client.post(
        f"/api/v1/superuser/coaches/{archived_row['membership_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text
    inactive_coach = client.post(
        url,
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": archived_coach["user_id"]},
    )

    assert same_gym.status_code == 400, same_gym.text
    assert same_gym.json()["detail"] == "gym_unchanged"
    assert wrong_gym_coach.status_code == 400, wrong_gym_coach.text
    assert wrong_gym_coach.json()["detail"] == "invalid_coach"
    assert inactive_coach.status_code == 400, inactive_coach.text
    assert inactive_coach.json()["detail"] == "invalid_coach"
    profile = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_a["id"],
            AthleteProfile.user_id == athlete["user_id"],
        )
    ).one()
    assert profile is not None
    assignment = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_a["id"],
            CoachAssignment.athlete_user_id == athlete["user_id"],
        )
    ).one()
    assert assignment.ended_at is None
    assert str(assignment.coach_user_id) == source_coach["user_id"]


def test_athlete_transfer_rejects_collisions_archived_and_staff_roles(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Transfer Collision A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Transfer Collision B")
    coach_a = _coach(client, owner_a, gym_a)
    coach_b = _coach(client, owner_b, gym_b)
    email = unique_email("multi-gym-transfer-athlete")
    athlete_a = create_athlete(
        client,
        owner_a,
        email=email,
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        owner_b,
        email=email,
        coach_user_id=coach_b["user_id"],
    )["athlete"]["profile"]
    collision = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete_a['user_id']}/transfer",
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )
    assert collision.status_code == 409, collision.text
    assert collision.json()["detail"] == "athlete_already_member"

    archived_athlete = create_athlete(
        client,
        owner_a,
        email=unique_email("transfer-archived-athlete"),
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]
    archived = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{archived_athlete['user_id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text
    archived_transfer = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/"
        f"{archived_athlete['user_id']}/transfer",
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )
    assert archived_transfer.status_code == 409, archived_transfer.text
    assert archived_transfer.json()["detail"] == "athlete_archived"

    staff_email = unique_email("transfer-staff-athlete")
    staff_member = _coach(client, owner_a, gym_a, email=staff_email)
    staff_athlete = create_athlete(
        client,
        owner_a,
        email=staff_email,
        coach_user_id=staff_member["user_id"],
    )["athlete"]["profile"]
    staff_transfer = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/"
        f"{staff_athlete['user_id']}/transfer",
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )
    assert staff_transfer.status_code == 409, staff_transfer.text
    assert staff_transfer.json()["detail"] == "athlete_has_other_roles"

    db_session.expire_all()
    profiles = db_session.exec(
        select(AthleteProfile).where(AthleteProfile.user_id == athlete_a["user_id"])
    ).all()
    assert {str(profile.gym_id) for profile in profiles} == {
        gym_a["id"],
        gym_b["id"],
    }
    assert athlete_b["user_id"] == athlete_a["user_id"]


def test_athlete_transfer_requires_superuser_and_correct_profile_scope(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Transfer Auth A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Transfer Auth B")
    coach_a = _coach(client, owner_a, gym_a)
    coach_b = _coach(client, owner_b, gym_b)
    athlete = create_athlete(
        client,
        owner_a,
        email=unique_email("athlete-transfer-auth"),
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]

    forbidden = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete['user_id']}/transfer",
        headers=owner_a,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )
    mismatched = client.post(
        f"/api/v1/superuser/athletes/{gym_b['id']}/{athlete['user_id']}/transfer",
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )

    assert forbidden.status_code == 403
    assert mismatched.status_code == 404, mismatched.text


def test_athlete_transfer_rejects_gym_owner_membership(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = _owner(client, superuser_headers, "Athlete Transfer Owner A")
    gym_b, owner_b = _owner(client, superuser_headers, "Athlete Transfer Owner B")
    coach_a = _coach(client, owner_a, gym_a)
    coach_b = _coach(client, owner_b, gym_b)
    athlete = create_athlete(
        client,
        owner_a,
        email=unique_email("owner-athlete"),
        coach_user_id=coach_a["user_id"],
    )["athlete"]["profile"]
    gym = db_session.get(Gym, uuid.UUID(gym_a["id"]))
    assert gym is not None
    gym.owner_id = uuid.UUID(athlete["user_id"])
    db_session.add(gym)
    db_session.commit()

    response = client.post(
        f"/api/v1/superuser/athletes/{gym_a['id']}/{athlete['user_id']}/transfer",
        headers=superuser_headers,
        json={"gym_id": gym_b["id"], "coach_user_id": coach_b["user_id"]},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "athlete_transfer_not_allowed"
    db_session.expire_all()
    profile = db_session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_a["id"],
            AthleteProfile.user_id == athlete["user_id"],
        )
    ).one()
    assert profile is not None
    assignment = db_session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_a["id"],
            CoachAssignment.athlete_user_id == athlete["user_id"],
        )
    ).one()
    assert assignment.ended_at is None


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
