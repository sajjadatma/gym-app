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


def _owner_headers(
    client: TestClient,
    superuser_headers: dict[str, str],
    gym_name: str,
    owner_email: str,
):
    gym = create_gym(
        client,
        superuser_headers,
        name=gym_name,
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
    headers = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    return gym, headers


def _add_coach(
    client: TestClient,
    owner_headers: dict[str, str],
    gym_id: str,
    email: str,
):
    member = add_member(
        client,
        owner_headers,
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
        client, email=email, password="coach-pass-456", gym_id=gym_id
    )


def test_coach_reassignment_preserves_history_and_moves_access(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Reassign Gym", unique_email("owner")
    )
    coach1_email = unique_email("coach1")
    coach2_email = unique_email("coach2")
    coach1_member, coach1 = _add_coach(client, owner, gym["id"], coach1_email)
    coach2_member, coach2 = _add_coach(client, owner, gym["id"], coach2_email)
    athlete_email = unique_email("athlete")
    athlete = create_athlete(
        client,
        coach1,
        email=athlete_email,
        coach_user_id=coach1_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]

    old_version = create_and_publish_program(client, coach1, athlete["user_id"])

    reassigned = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/reassign-coach",
        headers=owner,
        json={"coach_user_id": coach2_member["user_id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assignments = reassigned.json()["assignments"]
    assert len(assignments) == 2
    assert sum(1 for item in assignments if item["ended_at"] is None) == 1

    assert client.get("/api/v1/athletes", headers=coach1).json()["count"] == 0
    assert (
        client.get(f"/api/v1/athletes/{athlete['user_id']}", headers=coach1).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/program-versions/{old_version['id']}", headers=coach1
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/program-versions/{old_version['id']}/new-draft",
            headers=coach1,
        ).status_code
        == 404
    )

    new_coach_list = client.get("/api/v1/athletes", headers=coach2)
    assert new_coach_list.status_code == 200
    assert new_coach_list.json()["data"][0]["coach_user_id"] == coach2_member["user_id"]
    visible = client.get(
        f"/api/v1/program-versions/{old_version['id']}", headers=coach2
    )
    assert visible.status_code == 200
    assert visible.json()["coach_name"] == coach1_email
    assert visible.json()["status"] == "ACTIVE"

    draft = client.post(
        f"/api/v1/program-versions/{old_version['id']}/new-draft", headers=coach2
    )
    assert draft.status_code == 200, draft.text
    new_version = draft.json()
    assert new_version["version_number"] == 2
    assert new_version["days"][0]["exercises"][0]["sets"][0]["weight_kg"] == 40.0

    payload = program_payload(new_version["days"][0]["exercises"][0]["exercise_id"])
    payload["days"][0]["exercises"][0]["sets"][1]["weight_kg"] = 55
    saved = client.put(
        f"/api/v1/program-versions/{new_version['id']}",
        headers=coach2,
        json=payload,
    )
    assert saved.status_code == 200, saved.text
    published = client.post(
        f"/api/v1/program-versions/{new_version['id']}/publish", headers=coach2
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "ACTIVE"

    old_again = client.get(
        f"/api/v1/program-versions/{old_version['id']}", headers=coach2
    )
    assert old_again.json()["status"] == "ARCHIVED"
    assert old_again.json()["days"][0]["exercises"][0]["sets"][1]["weight_kg"] == 45.0

    all_versions = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/programs", headers=coach2
    ).json()["data"]
    assert len(all_versions) == 2
    assert sum(1 for item in all_versions if item["status"] == "ACTIVE") == 1

    athlete_raw = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        athlete_raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete_email,
        password="athlete-pass-456",
        gym_id=gym["id"],
    )
    athlete_versions = client.get(
        f"/api/v1/athletes/{athlete['user_id']}/programs", headers=athlete_headers
    )
    assert athlete_versions.status_code == 200
    assert all(item["status"] != "DRAFT" for item in athlete_versions.json()["data"])
    assert athlete_versions.json()["count"] == 2


def test_versioning_editable_active_and_templates(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Version Gym", unique_email("owner")
    )
    coach_member, coach = _add_coach(client, owner, gym["id"], unique_email("coach"))
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    exercise_id = first_exercise_id(client, coach)

    created = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Versioned", "goal": "قدرت"},
    )
    version_id = created.json()["id"]
    saved = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json=program_payload(exercise_id),
    )
    assert saved.status_code == 200
    assert saved.json()["days"][0]["exercises"][0]["sets"][1]["weight_kg"] == 45.0
    published = client.post(
        f"/api/v1/program-versions/{version_id}/publish", headers=coach
    )
    assert published.status_code == 200
    active_edit = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json=program_payload(exercise_id),
    )
    assert active_edit.status_code == 200
    assert active_edit.json()["status"] == "ACTIVE"
    assert active_edit.json()["published_at"] == published.json()["published_at"]
    invalid_edit = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json={**program_payload(exercise_id), "title": "Rejected", "days": []},
    )
    assert invalid_edit.status_code == 400
    preserved = client.get(
        f"/api/v1/program-versions/{version_id}", headers=coach
    ).json()
    assert preserved["title"] == active_edit.json()["title"]
    assert len(preserved["days"]) == 1

    template_days = program_payload(exercise_id)["days"]
    template = client.post(
        "/api/v1/templates",
        headers=coach,
        json={
            "name": "Reusable Strength",
            "goal": "قدرت",
            "notes": "template notes",
            "days": template_days,
        },
    )
    assert template.status_code == 200, template.text
    template_id = template.json()["id"]
    assert template.json()["day_count"] == 1

    applied = client.post(
        f"/api/v1/templates/{template_id}/apply",
        headers=coach,
        json={"athlete_user_id": athlete["user_id"]},
    )
    assert applied.status_code == 200, applied.text
    applied_version = applied.json()
    assert applied_version["status"] == "DRAFT"
    applied_weight = applied_version["days"][0]["exercises"][0]["sets"][1]["weight_kg"]
    assert applied_weight == 45.0

    updated_template = client.put(
        f"/api/v1/templates/{template_id}",
        headers=coach,
        json={
            "name": "Reusable Strength 2",
            "goal": "قدرت",
            "notes": "changed",
            "days": [
                {
                    **template_days[0],
                    "title": "Changed day",
                    "exercises": [
                        {
                            **template_days[0]["exercises"][0],
                            "sets": [
                                {
                                    **template_days[0]["exercises"][0]["sets"][0],
                                    "weight_kg": 99,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert updated_template.status_code == 200
    applied_again = client.get(
        f"/api/v1/program-versions/{applied_version['id']}", headers=coach
    )
    assert applied_again.json()["days"][0]["title"] == "Day 1"
    assert (
        applied_again.json()["days"][0]["exercises"][0]["sets"][1]["weight_kg"] == 45.0
    )

    no_access = client.get(f"/api/v1/templates/{template_id}", headers=owner)
    assert no_access.status_code == 200
    other_gym, other_owner = _owner_headers(
        client, superuser_headers, "Other Version Gym", unique_email("other-owner")
    )
    other_coach_member, other_coach = _add_coach(
        client, other_owner, other_gym["id"], unique_email("other-coach")
    )
    cross = client.get(f"/api/v1/templates/{template_id}", headers=other_coach)
    assert cross.status_code == 404
    assert client.get("/api/v1/templates", headers=other_coach).json()["count"] == 0


def test_publish_requires_days_exercises_and_sets(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Validation Gym", unique_email("owner")
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
        json={"title": "Empty"},
    )
    version_id = created.json()["id"]
    published = client.post(
        f"/api/v1/program-versions/{version_id}/publish", headers=coach
    )
    assert published.status_code == 400
    assert published.json()["detail"] == "program_is_empty"

    exercise_id = first_exercise_id(client, coach)
    payload = program_payload(exercise_id)
    payload["days"][0]["exercises"][0]["sets"] = []
    saved = client.put(
        f"/api/v1/program-versions/{version_id}", headers=coach, json=payload
    )
    assert saved.status_code == 200
    publish_empty_sets = client.post(
        f"/api/v1/program-versions/{version_id}/publish", headers=coach
    )
    assert publish_empty_sets.status_code == 400
    assert publish_empty_sets.json()["detail"] == "program_exercise_has_no_sets"

    payload["days"][0]["exercises"][0]["sets"] = [
        {"set_number": 1, "reps_min": 10, "reps_max": 5}
    ]
    invalid = client.put(
        f"/api/v1/program-versions/{version_id}", headers=coach, json=payload
    )
    assert invalid.status_code == 422


def test_program_days_cannot_exceed_athlete_training_days(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Weekday Cap Gym", unique_email("owner")
    )
    coach_member, coach = _add_coach(client, owner, gym["id"], unique_email("coach"))
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]

    patched = client.patch(
        f"/api/v1/athletes/{athlete['user_id']}",
        headers=coach,
        json={"training_days_count": 1},
    )
    assert patched.status_code == 200, patched.text

    exercise_id = first_exercise_id(client, coach)
    created = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Capped"},
    )
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]
    payload = program_payload(exercise_id)
    rejected = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json={
            **payload,
            "days": [
                payload["days"][0],
                {**payload["days"][0], "day_number": 2, "title": "Day 2"},
            ],
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert rejected.json()["detail"] == "program_too_many_days"

    allowed = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json={**payload, "days": [{**payload["days"][0], "weekday": "sat"}]},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["days"][0]["weekday"] == "sat"


def test_program_weekday_must_be_unique_and_valid(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner_headers(
        client, superuser_headers, "Weekday Gym", unique_email("owner")
    )
    coach_member, coach = _add_coach(client, owner, gym["id"], unique_email("coach"))
    athlete = create_athlete(
        client,
        coach,
        email=unique_email("athlete"),
        coach_user_id=coach_member["user_id"],
        password="athlete-pass-123",
    )["athlete"]["profile"]
    exercise_id = first_exercise_id(client, coach)
    created = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Weekdays"},
    )
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]
    payload = program_payload(exercise_id)
    day_one = payload["days"][0]

    duplicate = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json={
            **payload,
            "days": [
                {**day_one, "weekday": "sat"},
                {**day_one, "day_number": 2, "title": "Day 2", "weekday": "sat"},
            ],
        },
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["detail"] == "invalid_weekday"

    unknown = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach,
        json={**payload, "days": [{**day_one, "weekday": "sunday"}]},
    )
    assert unknown.status_code == 400, unknown.text
    assert unknown.json()["detail"] == "invalid_weekday"
