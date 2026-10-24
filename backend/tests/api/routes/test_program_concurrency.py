from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.services import programs as programs_service
from tests.api.routes.test_programs import _add_coach, _owner_headers
from tests.utils.helpers import (
    create_and_publish_program,
    create_athlete,
    first_exercise_id,
    program_payload,
    unique_email,
)


def _setup_program(
    client: TestClient, superuser_headers: dict[str, str]
) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    gym, owner = _owner_headers(
        client, superuser_headers, "Concurrency Gym", unique_email("owner")
    )
    coach_member, coach = _add_coach(client, owner, gym["id"], unique_email("coach"))
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    created = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Concurrent program"},
    )
    assert created.status_code == 200, created.text
    return coach, created.json(), athlete


def test_stale_program_version_update_is_rejected_and_retry_works(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    coach, version, athlete = _setup_program(client, superuser_headers)
    exercise_id = first_exercise_id(client, coach)
    version_url = f"/api/v1/program-versions/{version['id']}"

    first = client.put(
        version_url,
        headers=coach,
        json={
            **program_payload(exercise_id),
            "title": "Editor A",
            "expected_revision": version["revision"],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == version["revision"] + 1

    stale = client.put(
        version_url,
        headers=coach,
        json={
            **program_payload(exercise_id),
            "title": "Editor B stale",
            "expected_revision": version["revision"],
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "program_version_conflict"

    current = client.get(version_url, headers=coach)
    assert current.status_code == 200, current.text
    assert current.json()["title"] == "Editor A"
    assert current.json()["revision"] == first.json()["revision"]

    retried = client.put(
        version_url,
        headers=coach,
        json={
            **program_payload(exercise_id),
            "title": "Editor B after reload",
            "expected_revision": current.json()["revision"],
        },
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["title"] == "Editor B after reload"
    assert retried.json()["revision"] == current.json()["revision"] + 1

    listed = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/programs", headers=coach
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"][0]["revision"] == retried.json()["revision"]


def test_active_program_version_stays_editable_and_publishable_with_revision(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Active Revision Gym", unique_email("owner")
    )
    coach_member, coach = _add_coach(client, owner, gym["id"], unique_email("coach"))
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    active = create_and_publish_program(client, coach, athlete["user_id"])
    exercise_id = first_exercise_id(client, coach)
    version_url = f"/api/v1/program-versions/{active['id']}"

    assert active["status"] == "ACTIVE"
    edited = client.put(
        version_url,
        headers=coach,
        json={
            **program_payload(exercise_id),
            "title": "Active edited",
            "expected_revision": active["revision"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "ACTIVE"
    assert edited.json()["revision"] == active["revision"] + 1

    stale = client.put(
        version_url,
        headers=coach,
        json={
            **program_payload(exercise_id),
            "title": "Active stale",
            "expected_revision": active["revision"],
        },
    )
    assert stale.status_code == 409, stale.text

    republished = client.post(f"{version_url}/publish", headers=coach)
    assert republished.status_code == 400
    assert republished.json()["detail"] == "only_drafts_can_be_published"


def test_update_without_expected_revision_still_succeeds_and_bumps_revision(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    """Deliberate back-compat: clients that do not send expected_revision can
    still save. They skip the stale-write guard and always bump revision. The
    current UI always sends expected_revision; this pin only protects older
    clients. Remove only with an approved breaking-change decision."""
    coach, version, _athlete = _setup_program(client, superuser_headers)
    exercise_id = first_exercise_id(client, coach)
    version_url = f"/api/v1/program-versions/{version['id']}"

    first = client.put(
        version_url,
        headers=coach,
        json={**program_payload(exercise_id), "title": "Legacy client A"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["title"] == "Legacy client A"
    assert first.json()["revision"] == version["revision"] + 1

    second = client.put(
        version_url,
        headers=coach,
        json={**program_payload(exercise_id), "title": "Legacy client B"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["title"] == "Legacy client B"
    assert second.json()["revision"] == first.json()["revision"] + 1


def test_new_draft_retries_version_number_collision(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach, version, _athlete = _setup_program(client, superuser_headers)
    original = programs_service.next_version_number
    calls = {"count": 0}

    def colliding_once(*args: object, **kwargs: object) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            return version["version_number"]
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(programs_service, "next_version_number", colliding_once)

    draft = client.post(
        f"/api/v1/program-versions/{version['id']}/new-draft", headers=coach
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["version_number"] == version["version_number"] + 1
    assert calls["count"] >= 2


def test_exhausted_version_number_collision_returns_409(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach, version, athlete = _setup_program(client, superuser_headers)

    def always_colliding(*_args: object, **_kwargs: object) -> int:
        return version["version_number"]

    monkeypatch.setattr(programs_service, "next_version_number", always_colliding)

    draft = client.post(
        f"/api/v1/program-versions/{version['id']}/new-draft", headers=coach
    )
    assert draft.status_code == 409, draft.text
    assert draft.json()["detail"] == "program_version_conflict"

    remaining = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/programs", headers=coach
    )
    assert remaining.status_code == 200
    assert remaining.json()["count"] == 1


def test_concurrent_new_drafts_get_unique_version_numbers(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach, version, athlete = _setup_program(client, superuser_headers)
    original = programs_service.next_version_number
    barrier = threading.Barrier(2, timeout=15)
    lock = threading.Lock()
    calls = {"count": 0}

    def synchronized_allocation(*args: object, **kwargs: object) -> int:
        allocated = original(*args, **kwargs)  # type: ignore[arg-type]
        with lock:
            calls["count"] += 1
            wait = calls["count"] <= 2
        if wait:
            barrier.wait()
        return allocated

    monkeypatch.setattr(
        programs_service, "next_version_number", synchronized_allocation
    )
    url = f"/api/v1/program-versions/{version['id']}/new-draft"

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _index: client.post(url, headers=coach), range(2))
        )

    assert [response.status_code for response in responses] == [200, 200], [
        response.text for response in responses
    ]
    numbers = sorted(response.json()["version_number"] for response in responses)
    assert numbers == [version["version_number"] + 1, version["version_number"] + 2]

    listed = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/programs", headers=coach
    )
    assert listed.status_code == 200
    all_numbers = [item["version_number"] for item in listed.json()["data"]]
    assert len(all_numbers) == len(set(all_numbers)) == 3
