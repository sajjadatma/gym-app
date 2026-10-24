from __future__ import annotations

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_and_publish_program,
    create_athlete,
    create_gym,
    first_exercise_id,
    gym_headers,
    program_payload,
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


def test_archive_requires_admin_and_wrong_gym_mutations_do_not_change_target(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym_a, owner_a, coach_a, _coach_member_a, athlete = _setup(
        client, superuser_headers
    )
    _gym_b, owner_b, _coach_b, _coach_member_b, _email_b = _setup(
        client, superuser_headers
    )
    version = create_and_publish_program(client, coach_a, athlete["user_id"])
    detail_url = f"/api/v1/athletes/{athlete['user_id']}"
    version_url = f"/api/v1/program-versions/{version['id']}"
    before = client.get(detail_url, headers=owner_a).json()
    before_version = client.get(version_url, headers=owner_a).json()

    coach_archive = client.post(f"{detail_url}/archive", headers=coach_a)
    assert coach_archive.status_code == 403
    assert coach_archive.json()["detail"] == "gym_admin_required"
    for method, path in (
        ("post", f"{detail_url}/archive"),
        ("post", f"{detail_url}/restore"),
        ("delete", detail_url),
    ):
        response = getattr(client, method)(path, headers=owner_b)
        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "athlete_not_found"

    after = client.get(detail_url, headers=owner_a).json()
    assert after["profile"]["is_archived"] is False
    assert after["profile"] == before["profile"]
    assert client.get(version_url, headers=owner_a).json() == before_version


def test_delete_in_one_gym_preserves_other_gym_profile_program_and_file(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym_a, owner_a, coach_a, coach_member_a, _email_a = _setup(
        client, superuser_headers
    )
    _gym_b, owner_b, coach_b, coach_member_b, _email_b = _setup(
        client, superuser_headers
    )
    email = unique_email("shared-cross-gym")
    athlete_a = create_athlete(
        client,
        coach_a,
        email=email,
        coach_user_id=coach_member_a["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        coach_b,
        email=email,
        coach_user_id=coach_member_b["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    assert athlete_a["user_id"] == athlete_b["user_id"]
    assert athlete_a["gym_id"] != athlete_b["gym_id"]
    version_a = create_and_publish_program(client, coach_a, athlete_a["user_id"])
    version_b = create_and_publish_program(client, coach_b, athlete_b["user_id"])
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    file_a = client.post(
        f"/api/v1/athletes/{athlete_a['user_id']}/body-files",
        headers=owner_a,
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )
    file_b = client.post(
        f"/api/v1/athletes/{athlete_b['user_id']}/body-files",
        headers=owner_b,
        files={"file": ("b.pdf", pdf, "application/pdf")},
    )
    assert file_a.status_code == 200, file_a.text
    assert file_b.status_code == 200, file_b.text
    b_detail_before = client.get(
        f"/api/v1/athletes/{athlete_b['user_id']}", headers=owner_b
    ).json()
    b_version_before = client.get(
        f"/api/v1/program-versions/{version_b['id']}", headers=owner_b
    ).json()
    b_file_before = client.get(
        f"/api/v1/athletes/{athlete_b['user_id']}/body-files/{file_b.json()['id']}/download",
        headers=owner_b,
    )

    assert (
        client.post(
            f"/api/v1/athletes/{athlete_a['user_id']}/archive", headers=owner_a
        ).status_code
        == 200
    )
    deleted = client.delete(
        f"/api/v1/athletes/{athlete_a['user_id']}", headers=owner_a
    )
    assert deleted.status_code == 200, deleted.text
    assert (
        client.get(
            f"/api/v1/athletes/{athlete_a['user_id']}", headers=owner_a
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/athletes/{athlete_a['user_id']}/body-files/{file_a.json()['id']}/download",
            headers=owner_a,
        ).status_code
        == 404
    )

    b_detail_after = client.get(
        f"/api/v1/athletes/{athlete_b['user_id']}", headers=owner_b
    ).json()
    assert b_detail_after == b_detail_before
    assert b_detail_after["profile"]["user_id"] == athlete_b["user_id"]
    assert b_detail_after["profile"]["gym_id"] == athlete_b["gym_id"]
    assert (
        client.get(
            f"/api/v1/program-versions/{version_b['id']}", headers=owner_b
        ).json()
        == b_version_before
    )
    b_file_after = client.get(
        f"/api/v1/athletes/{athlete_b['user_id']}/body-files/{file_b.json()['id']}/download",
        headers=owner_b,
    )
    assert b_file_after.status_code == 200
    assert b_file_after.content == b_file_before.content == pdf
    assert (
        client.get(
            f"/api/v1/program-versions/{version_a['id']}", headers=owner_a
        ).status_code
        == 404
    )
    assert version_a["program_id"] != version_b["program_id"]


def test_archive_restore_cuts_off_and_restores_coach_access_without_duplicate_assignment(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner, coach, _coach_member, athlete = _setup(client, superuser_headers)
    detail_url = f"/api/v1/athletes/{athlete['user_id']}"
    version = create_and_publish_program(client, coach, athlete["user_id"])
    version_url = f"/api/v1/program-versions/{version['id']}"
    before = client.get(detail_url, headers=owner).json()
    before_version = client.get(version_url, headers=owner).json()
    assert client.get(detail_url, headers=coach).status_code == 200
    assert client.post(f"{detail_url}/archive", headers=owner).status_code == 200
    assert client.get(detail_url, headers=coach).status_code == 404

    first_restore = client.post(f"{detail_url}/restore", headers=owner)
    assert first_restore.status_code == 200
    assert client.get(detail_url, headers=coach).status_code == 200
    second_restore = client.post(f"{detail_url}/restore", headers=owner)
    assert second_restore.status_code == 200

    detail = second_restore.json()
    assignments = detail["assignments"]
    assert sum(1 for row in assignments if row["ended_at"] is None) == 1
    assert sum(1 for row in assignments if row["ended_at"] is not None) == 1
    assert detail["profile"]["user_id"] == before["profile"]["user_id"]
    assert detail["profile"]["gym_id"] == before["profile"]["gym_id"]
    assert client.get(version_url, headers=owner).json() == before_version


def test_archived_athlete_profile_and_program_authoring_are_read_only(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner, coach, _coach_member, athlete = _setup(client, superuser_headers)
    version = create_and_publish_program(client, coach, athlete["user_id"])
    detail_url = f"/api/v1/athletes/{athlete['user_id']}"
    version_url = f"/api/v1/program-versions/{version['id']}"
    before = client.get(detail_url, headers=owner).json()
    before_version = client.get(version_url, headers=owner).json()
    assert (
        client.post(f"{detail_url}/archive", headers=owner).status_code == 200
    )

    patch = client.patch(detail_url, headers=owner, json={"phone": "09120000000"})
    assert patch.status_code == 409, patch.text
    assert patch.json()["detail"] == "athlete_archived"
    create = client.post(
        f"{detail_url}/programs", headers=owner, json={"title": "Blocked"}
    )
    assert create.status_code == 409, create.text
    assert create.json()["detail"] == "athlete_archived"
    exercise_id = first_exercise_id(client, owner)
    update = client.put(
        version_url, headers=owner, json=program_payload(exercise_id)
    )
    assert update.status_code == 409, update.text
    assert update.json()["detail"] == "athlete_archived"
    new_draft = client.post(f"{version_url}/new-draft", headers=owner)
    assert new_draft.status_code == 409, new_draft.text
    assert new_draft.json()["detail"] == "athlete_archived"
    archive_version = client.post(f"{version_url}/archive", headers=owner)
    assert archive_version.status_code == 409, archive_version.text
    assert archive_version.json()["detail"] == "athlete_archived"
    save_template = client.post(
        f"{version_url}/save-as-template",
        headers=owner,
        json={"name": "Blocked"},
    )
    assert save_template.status_code == 409, save_template.text
    assert save_template.json()["detail"] == "athlete_archived"

    after = client.get(detail_url, headers=owner)
    assert after.status_code == 200
    assert after.json()["profile"]["is_archived"] is True
    assert after.json()["profile"]["phone"] == before["profile"]["phone"]
    assert after.json()["profile"]["full_name"] == before["profile"]["full_name"]
    assert client.get(version_url, headers=owner).json() == before_version

    _other_gym, other_owner, _other_coach, _other_member, _other_athlete = _setup(
        client, superuser_headers
    )
    cross_patch = client.patch(
        detail_url, headers=other_owner, json={"phone": "09121111111"}
    )
    assert cross_patch.status_code == 404
    assert cross_patch.json()["detail"] == "athlete_not_found"
    coach_patch = client.patch(
        detail_url, headers=coach, json={"phone": "09122222222"}
    )
    assert coach_patch.status_code == 404
    cross_program = client.post(
        f"{detail_url}/programs", headers=other_owner, json={"title": "Cross"}
    )
    assert cross_program.status_code == 404

    assert client.post(f"{detail_url}/restore", headers=owner).status_code == 200
    restored_patch = client.patch(
        detail_url, headers=owner, json={"phone": "09123333333"}
    )
    assert restored_patch.status_code == 200, restored_patch.text
    assert restored_patch.json()["profile"]["phone"] == "09123333333"
    restored_program = client.post(
        f"{detail_url}/programs", headers=owner, json={"title": "Allowed"}
    )
    assert restored_program.status_code == 200, restored_program.text


def test_deleting_owner_as_athlete_keeps_account_and_gym_ownership(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("owner-athlete")
    gym = create_gym(
        client,
        superuser_headers,
        name="Owner Athlete Gym",
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
    owner = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=unique_email("owner-athlete-coach"),
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    athlete = create_athlete(
        client,
        owner,
        email=owner_email,
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]

    deleted = client.delete(
        f"/api/v1/athletes/{athlete['user_id']}", headers=owner
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["message"] == "athlete_deleted"
    assert (
        client.get(
            f"/api/v1/athletes/{athlete['user_id']}", headers=owner
        ).status_code
        == 404
    )

    owner_again = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    gyms = client.get("/api/v1/gyms/", headers=owner_again)
    assert gyms.status_code == 200
    assert any(
        row["id"] == gym["id"] and row["is_owner"] for row in gyms.json()["data"]
    )
    members = client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers=owner_again
    )
    assert members.status_code == 200
    row = next(
        item
        for item in members.json()["data"]
        if item["user_id"] == athlete["user_id"]
    )
    assert row["is_owner"] is True
    assert row["is_active"] is True
    assert "ATHLETE" not in row["roles"]


def test_deleting_athlete_of_other_gym_owner_keeps_account_and_other_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    first_owner_email = unique_email("shared-owner")
    first_gym = create_gym(
        client,
        superuser_headers,
        name="First Owner Gym",
        owner_email=first_owner_email,
        password="first-owner-pass-123",
    )["gym"]
    raw_first = auth_headers(client, first_owner_email, "first-owner-pass-123")
    change_password(
        client,
        raw_first,
        current_password="first-owner-pass-123",
        new_password="first-owner-pass-456",
    )
    first_owner = gym_headers(
        client,
        email=first_owner_email,
        password="first-owner-pass-456",
        gym_id=first_gym["id"],
    )
    _second_gym, second_owner, _coach, coach_member, _athlete = _setup(
        client, superuser_headers
    )
    shared = create_athlete(
        client,
        second_owner,
        email=first_owner_email,
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    first_members_before = client.get(
        f"/api/v1/gyms/{first_gym['id']}/members", headers=first_owner
    )
    assert first_members_before.status_code == 200

    deleted = client.delete(
        f"/api/v1/athletes/{shared['user_id']}", headers=second_owner
    )
    assert deleted.status_code == 200, deleted.text
    assert (
        client.get(
            f"/api/v1/athletes/{shared['user_id']}", headers=second_owner
        ).status_code
        == 404
    )

    first_owner_again = gym_headers(
        client,
        email=first_owner_email,
        password="first-owner-pass-456",
        gym_id=first_gym["id"],
    )
    gyms = client.get("/api/v1/gyms/", headers=first_owner_again)
    assert gyms.status_code == 200
    assert any(
        row["id"] == first_gym["id"] and row["is_owner"]
        for row in gyms.json()["data"]
    )
    first_members_after = client.get(
        f"/api/v1/gyms/{first_gym['id']}/members", headers=first_owner_again
    )
    assert first_members_after.status_code == 200
    assert (
        first_members_after.json()["count"]
        == first_members_before.json()["count"]
    )
