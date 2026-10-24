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


def _setup(client: TestClient, superuser_headers: dict[str, str]):
    owner_email = unique_email("owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Lifecycle Gym",
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
    owner = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    coach_email = unique_email("coach")
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    coach_raw = auth_headers(client, coach_email, "coach-pass-123")
    change_password(
        client,
        coach_raw,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    coach = gym_headers(
        client, email=coach_email, password="coach-pass-456", gym_id=gym["id"]
    )
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    return gym, owner, coach, coach_member, athlete


def test_restore_and_permanent_delete_archived_athlete(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner, coach, coach_member, athlete = _setup(client, superuser_headers)
    create_and_publish_program(client, coach, athlete["user_id"])

    archived = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner
    )
    assert archived.status_code == 200, archived.text

    archived_list = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"q": athlete["email"], "include_archived": True},
    )
    assert archived_list.status_code == 200
    assert [row["email"] for row in archived_list.json()["data"]] == [
        athlete["email"]
    ]

    restored = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/restore", headers=owner
    )
    assert restored.status_code == 200, restored.text
    restored_body = restored.json()
    assert restored_body["profile"]["is_archived"] is False
    assert restored_body["coach_user_id"] == coach_member["user_id"]
    assert restored_body["coach_name"]

    active_list = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"q": athlete["email"]},
    )
    assert active_list.status_code == 200
    assert [row["email"] for row in active_list.json()["data"]] == [
        athlete["email"]
    ]

    archived_again = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner
    )
    assert archived_again.status_code == 200

    deleted = client.delete(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["message"] == "athlete_deleted"

    missing = client.get(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    )
    assert missing.status_code == 404
    all_athletes = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"q": athlete["email"], "include_archived": True},
    )
    assert all_athletes.status_code == 200
    assert all_athletes.json()["count"] == 0


def test_restore_and_delete_require_owner_or_admin(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner, coach, _coach_member, athlete = _setup(client, superuser_headers)
    client.post(f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner)

    restore = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/restore", headers=coach
    )
    assert restore.status_code == 403
    delete = client.delete(
        f"/api/v1/athletes/{athlete['user_id']}", headers=coach
    )
    assert delete.status_code == 403

    restored = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/restore", headers=owner
    )
    assert restored.status_code == 200
