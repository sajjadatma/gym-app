from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.main import app
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


def test_private_coach_note_is_never_exposed_to_athlete(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("privacy-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Privacy Gym",
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
    coach_email = unique_email("coach")
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    raw_coach = auth_headers(client, coach_email, "coach-pass-123")
    change_password(
        client,
        raw_coach,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    coach = gym_headers(
        client, email=coach_email, password="coach-pass-456", gym_id=gym["id"]
    )
    athlete_email = unique_email("athlete")
    athlete = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    note = "PRIVATE-NOTE-DO-NOT-LEAK-9f26"
    updated = client.patch(
        f"/api/v1/athletes/{athlete['user_id']}",
        headers=coach,
        json={"internal_coach_note": note, "limitations": "knee", "equipment": "Dumbbells"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["internal_coach_note"] == note
    staff_view = client.get(f"/api/v1/athletes/{athlete['user_id']}", headers=coach)
    assert staff_view.json()["internal_coach_note"] == note

    raw_athlete = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        raw_athlete,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete_email,
        password="athlete-pass-456",
        gym_id=gym["id"],
    )
    self_view = client.get("/api/v1/athletes/me", headers=athlete_headers)
    assert self_view.status_code == 200
    assert note not in self_view.text
    assert "internal_coach_note" not in self_view.json()

    injection = client.patch(
        "/api/v1/athletes/me",
        headers=athlete_headers,
        json={
            "training_goal": "استقامت",
            "training_days_count": 3,
            "internal_coach_note": "OVERWRITTEN",
            "limitations": "changed",
        },
    )
    assert injection.status_code == 200
    assert injection.json()["profile"]["training_goal"] == "استقامت"
    assert injection.json()["profile"]["training_days_count"] == 3
    assert injection.json()["profile"]["training_days"] == []
    staff_again = client.get(f"/api/v1/athletes/{athlete['user_id']}", headers=coach)
    assert staff_again.json()["internal_coach_note"] == note
    assert staff_again.json()["profile"]["equipment"] == "Dumbbells"

    program = create_and_publish_program(client, coach, athlete["user_id"])
    athlete_program = client.get(
        f"/api/v1/program-versions/{program['id']}", headers=athlete_headers
    )
    assert athlete_program.status_code == 200
    assert note not in athlete_program.text

    listed = client.get("/api/v1/athletes", headers=coach)
    assert note not in listed.text


def test_body_analysis_file_is_private_and_validated(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("file-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="File Gym",
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
    coach_email = unique_email("file-coach")
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    raw_coach = auth_headers(client, coach_email, "coach-pass-123")
    change_password(
        client,
        raw_coach,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    coach = gym_headers(
        client, email=coach_email, password="coach-pass-456", gym_id=gym["id"]
    )
    athlete_email = unique_email("file-athlete")
    other_email = unique_email("other-athlete")
    athlete = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    other = create_athlete(
        client,
        coach,
        email=other_email,
        coach_user_id=coach_member["user_id"],
        password="other-pass-123",
    )["athlete"]["profile"]
    raw_athlete = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        raw_athlete,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete_email,
        password="athlete-pass-456",
        gym_id=gym["id"],
    )
    raw_other = auth_headers(client, other_email, "other-pass-123")
    change_password(
        client,
        raw_other,
        current_password="other-pass-123",
        new_password="other-pass-456",
    )
    other_headers = gym_headers(
        client, email=other_email, password="other-pass-456", gym_id=gym["id"]
    )

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    upload = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=athlete_headers,
        files={"file": ("analysis.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]
    assert upload.json()["original_name"] == "analysis.pdf"

    download = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/body-files/{file_id}/download",
        headers=athlete_headers,
    )
    assert download.status_code == 200
    assert download.content == pdf
    assert "attachment" in download.headers["content-disposition"]

    cross = client.get(
        f"/api/v1/athletes/{other['user_id']}/body-files/{file_id}/download",
        headers=other_headers,
    )
    assert cross.status_code == 404
    cross_list = client.get(
        f"/api/v1/athletes/{other['user_id']}/body-files", headers=other_headers
    )
    assert cross_list.json() == []

    wrong_extension = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=athlete_headers,
        files={"file": ("analysis.txt", b"hello", "text/plain")},
    )
    assert wrong_extension.status_code == 400
    wrong_magic = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=athlete_headers,
        files={"file": ("analysis.pdf", b"not a pdf", "application/pdf")},
    )
    assert wrong_magic.status_code == 400
    too_large = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 10)
    oversized = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=athlete_headers,
        files={"file": ("large.pdf", too_large, "application/pdf")},
    )
    assert oversized.status_code == 413

    archived = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner
    )
    assert archived.status_code == 200
    coach_after = client.get(f"/api/v1/athletes/{athlete['user_id']}", headers=coach)
    assert coach_after.status_code == 404
    self_after = client.get("/api/v1/athletes/me", headers=athlete_headers)
    assert self_after.status_code in {403, 404}


def _fail_commit(_session: Session) -> None:
    raise RuntimeError("simulated commit failure")


def _file_lifecycle_setup(
    client: TestClient, superuser_headers: dict[str, str]
) -> tuple[dict[str, str], dict[str, object]]:
    owner_email = unique_email("lifecycle-file-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Lifecycle File Gym",
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
        email=unique_email("lifecycle-file-coach"),
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    athlete = create_athlete(
        client,
        owner,
        email=unique_email("lifecycle-file-athlete"),
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    return owner, athlete


def test_delete_commit_failure_preserves_body_file_row_and_file(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, athlete = _file_lifecycle_setup(client, superuser_headers)
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    upload = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/body-files",
        headers=owner,
        files={"file": ("kept.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]
    stored_files_before = set(settings.BODY_ANALYSIS_DIR.iterdir())
    download_url = (
        f"/api/v1/athletes/{athlete['user_id']}/body-files/{file_id}/download"
    )
    before = client.get(download_url, headers=owner)
    assert before.status_code == 200
    assert before.content == pdf
    assert (
        client.post(
            f"/api/v1/athletes/{athlete['user_id']}/archive", headers=owner
        ).status_code
        == 200
    )

    with monkeypatch.context() as patch:  # type: ignore[attr-defined]
        patch.setattr(Session, "commit", _fail_commit)
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.delete(
                f"/api/v1/athletes/{athlete['user_id']}", headers=owner
            )
    assert response.status_code == 500

    assert set(settings.BODY_ANALYSIS_DIR.iterdir()) == stored_files_before
    detail = client.get(f"/api/v1/athletes/{athlete['user_id']}", headers=owner)
    assert detail.status_code == 200, detail.text
    assert detail.json()["profile"]["is_archived"] is True
    listed = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/body-files", headers=owner
    )
    assert [row["id"] for row in listed.json()] == [file_id]
    after = client.get(download_url, headers=owner)
    assert after.status_code == 200
    assert after.content == pdf


def test_failed_upload_commit_does_not_leave_orphan_file(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, athlete = _file_lifecycle_setup(client, superuser_headers)
    stored_files_before = set(settings.BODY_ANALYSIS_DIR.iterdir())
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

    with monkeypatch.context() as patch:  # type: ignore[attr-defined]
        patch.setattr(Session, "commit", _fail_commit)
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post(
                f"/api/v1/athletes/{athlete['user_id']}/body-files",
                headers=owner,
                files={"file": ("orphan.pdf", pdf, "application/pdf")},
            )
    assert response.status_code == 500

    assert set(settings.BODY_ANALYSIS_DIR.iterdir()) == stored_files_before
    listed = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/body-files", headers=owner
    )
    assert listed.status_code == 200
    assert listed.json() == []
