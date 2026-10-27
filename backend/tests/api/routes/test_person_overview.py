from __future__ import annotations

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_and_publish_program,
    create_athlete,
    create_gym,
    gym_headers,
    unique_email,
)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _owner_headers(
    client: TestClient,
    superuser_headers: dict[str, str],
    gym_name: str,
) -> tuple[dict, dict[str, str]]:
    email = unique_email("owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=gym_name,
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
    return gym, gym_headers(
        client,
        email=email,
        password="owner-pass-456",
        gym_id=gym["id"],
    )


def _add_coach(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    email: str,
) -> tuple[dict, dict[str, str]]:
    member = add_member(
        client,
        owner,
        gym_id,
        email=email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    raw = auth_headers(client, email, "coach-pass-123")
    change_password(
        client,
        raw,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    return member, gym_headers(
        client,
        email=email,
        password="coach-pass-456",
        gym_id=gym_id,
    )


def _overview(
    client: TestClient,
    headers: dict[str, str],
    *,
    user_id: str,
    gym_id: str,
    kind: str,
):
    return client.get(
        f"/api/v1/people/{user_id}/overview",
        headers=headers,
        params={"gym_id": gym_id, "kind": kind},
    )


def test_athlete_overview_contains_every_stored_record(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(client, superuser_headers, "Overview Athlete")
    coach_one_member, coach_one = _add_coach(
        client, owner, gym["id"], unique_email("coach-one")
    )
    coach_two_member, _coach_two = _add_coach(
        client, owner, gym["id"], unique_email("coach-two")
    )
    athlete_email = unique_email("overview-athlete")
    athlete = create_athlete(
        client,
        owner,
        email=athlete_email,
        coach_user_id=coach_one_member["user_id"],
        phone="09123334444",
        full_name="Athlete Overview",
    )["athlete"]["profile"]
    client.patch(
        f"/api/v1/athletes/{athlete['user_id']}",
        headers=owner,
        json={
            "internal_coach_note": "private note",
            "training_goal": "قدرت",
            "limitations": "knee",
        },
    )
    version = create_and_publish_program(
        client, coach_one, athlete["user_id"]
    )
    upload = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=owner,
        files={"file": ("analysis.pdf", PDF, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]
    reassigned = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/reassign-coach",
        headers=owner,
        json={"coach_user_id": coach_two_member["user_id"]},
    )
    assert reassigned.status_code == 200, reassigned.text

    response = _overview(
        client,
        superuser_headers,
        user_id=athlete["user_id"],
        gym_id=gym["id"],
        kind="ATHLETE",
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["kind"] == "ATHLETE"
    assert data["focus_gym_id"] == gym["id"]
    assert data["focus_gym_name"] == "Overview Athlete"
    assert data["account"]["email"] == athlete_email
    assert data["account"]["phone"] == "09123334444"
    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["roles"] == ["ATHLETE"]
    assert data["stats"]["program_versions"] == 1
    assert data["stats"]["active_program_versions"] == 1
    assert data["stats"]["body_files"] == 1
    assert data["stats"]["assignments"] == 2
    assert data["stats"]["active_assignments"] == 1

    section = data["athlete"]
    assert section["profile"]["full_name"] == "Athlete Overview"
    assert section["profile"]["height_cm"] == 180
    assert section["profile"]["training_goal"] == "قدرت"
    assert section["profile"]["limitations"] == "knee"
    assert section["internal_coach_note"] == "private note"
    assert section["current_coach"]["user_id"] == coach_two_member["user_id"]
    assert len(section["assignments"]) == 2
    assert sum(1 for item in section["assignments"] if item["ended_at"]) == 1
    assert len(section["programs"]) == 1
    program = section["programs"][0]
    assert program["id"] == version["id"]
    assert program["gym_id"] == gym["id"]
    assert program["athlete_name"] == "Athlete Overview"
    assert program["days"][0]["exercises"][0]["sets"][0]["weight_kg"] == 40
    assert len(section["body_files"]) == 1
    assert section["body_files"][0]["id"] == file_id
    assert section["body_files"][0]["gym_id"] == gym["id"]

    events = {event["event"] for event in data["history"]}
    assert {
        "account.created",
        "membership.joined",
        "athlete.profile_created",
        "assignment.started",
        "assignment.ended",
        "program.version_created",
        "program.version_published",
        "athlete.body_file_uploaded",
    } <= events
    timestamps = [event["occurred_at"] for event in data["history"]]
    assert timestamps == sorted(timestamps, reverse=True)

    serialized = response.text
    assert "hashed_password" not in serialized
    assert "token_version" not in serialized
    assert "must_change_password" not in serialized
    assert "stored_name" not in serialized

    owner_download = client.get(
        f"/api/v1/people/{athlete['user_id']}/body-files/{file_id}",
        headers=owner,
        params={"gym_id": gym["id"]},
    )
    assert owner_download.status_code == 200
    assert owner_download.content == PDF

    download = client.get(
        f"/api/v1/people/{athlete['user_id']}/body-files/{file_id}",
        headers=superuser_headers,
        params={"gym_id": gym["id"]},
    )
    assert download.status_code == 200
    assert download.content == PDF

    wrong_user = client.get(
        f"/api/v1/people/{coach_one_member['user_id']}/body-files/{file_id}",
        headers=superuser_headers,
        params={"gym_id": gym["id"]},
    )
    assert wrong_user.status_code == 404


def test_coach_overview_lists_assignments_and_authored_programs(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(client, superuser_headers, "Overview Coach")
    coach_member, coach = _add_coach(
        client, owner, gym["id"], unique_email("overview-coach")
    )
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("coach-athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    version = create_and_publish_program(client, coach, athlete["user_id"])

    response = _overview(
        client,
        superuser_headers,
        user_id=coach_member["user_id"],
        gym_id=gym["id"],
        kind="COACH",
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["kind"] == "COACH"
    assert data["athlete"] is None
    section = data["coach"]
    assert section["roles"] == ["COACH"]
    assert section["is_active"] is True
    assert len(section["assignments"]) == 1
    assert section["assignments"][0]["athlete_name"]
    assert len(section["authored_programs"]) == 1
    assert section["authored_programs"][0]["id"] == version["id"]
    assert data["stats"]["assignments"] == 1
    assert data["stats"]["active_assignments"] == 1
    assert data["stats"]["program_versions"] == 1
    assert data["stats"]["body_files"] == 0

    missing_kind = _overview(
        client,
        superuser_headers,
        user_id=athlete["user_id"],
        gym_id=gym["id"],
        kind="COACH",
    )
    assert missing_kind.status_code == 404
    assert missing_kind.json()["detail"] == "coach_not_found"


def test_overview_enforces_admin_scope_and_tenant_isolation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = _owner_headers(client, superuser_headers, "Scope A")
    gym_b, owner_b = _owner_headers(client, superuser_headers, "Scope B")
    coach_member, coach = _add_coach(
        client, owner_a, gym_a["id"], unique_email("scope-coach")
    )
    coach_b_member, _coach_b = _add_coach(
        client, owner_b, gym_b["id"], unique_email("scope-coach-b")
    )
    athlete = create_athlete(
        client,
        owner_a,
        email=unique_email("scope-athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        owner_b,
        email=unique_email("scope-athlete-b"),
        coach_user_id=coach_b_member["user_id"],
    )["athlete"]["profile"]

    allowed = _overview(
        client,
        owner_a,
        user_id=athlete["user_id"],
        gym_id=gym_a["id"],
        kind="ATHLETE",
    )
    assert allowed.status_code == 200, allowed.text

    coach_denied = _overview(
        client,
        coach,
        user_id=athlete["user_id"],
        gym_id=gym_a["id"],
        kind="ATHLETE",
    )
    assert coach_denied.status_code == 403

    athlete_raw = auth_headers(
        client, athlete["email"], "athlete-pass-123"
    )
    athlete_denied = _overview(
        client,
        athlete_raw,
        user_id=athlete["user_id"],
        gym_id=gym_a["id"],
        kind="ATHLETE",
    )
    assert athlete_denied.status_code == 403

    cross_gym = _overview(
        client,
        owner_a,
        user_id=athlete_b["user_id"],
        gym_id=gym_b["id"],
        kind="ATHLETE",
    )
    assert cross_gym.status_code == 403

    outside_scope = _overview(
        client,
        owner_a,
        user_id=athlete_b["user_id"],
        gym_id=gym_a["id"],
        kind="ATHLETE",
    )
    assert outside_scope.status_code == 404
    assert outside_scope.json()["detail"] == "person_not_found"

    superuser_cross = _overview(
        client,
        superuser_headers,
        user_id=athlete_b["user_id"],
        gym_id=gym_b["id"],
        kind="ATHLETE",
    )
    assert superuser_cross.status_code == 200, superuser_cross.text


def test_overview_keeps_archived_athletes_and_empty_coaches_visible(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(client, superuser_headers, "Overview Archived")
    coach_member, _coach = _add_coach(
        client, owner, gym["id"], unique_email("idle-coach")
    )
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("archived-athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    archived = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner
    )
    assert archived.status_code == 200, archived.text

    athlete_overview = _overview(
        client,
        owner,
        user_id=athlete["user_id"],
        gym_id=gym["id"],
        kind="ATHLETE",
    )
    assert athlete_overview.status_code == 200, athlete_overview.text
    assert athlete_overview.json()["athlete"]["profile"]["is_archived"] is True

    coach_overview = _overview(
        client,
        owner,
        user_id=coach_member["user_id"],
        gym_id=gym["id"],
        kind="COACH",
    )
    assert coach_overview.status_code == 200, coach_overview.text
    data = coach_overview.json()
    assert len(data["coach"]["assignments"]) == 1
    assert data["coach"]["assignments"][0]["ended_at"] is not None
    assert data["coach"]["authored_programs"] == []
    assert data["stats"]["program_versions"] == 0
    assert any(
        event["event"] == "membership.joined" for event in data["history"]
    )
