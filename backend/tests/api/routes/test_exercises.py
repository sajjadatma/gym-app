from __future__ import annotations

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    gym_headers,
    program_payload,
    unique_email,
)


def _gym_with_coach(client: TestClient, superuser_headers: dict[str, str], label: str):
    owner_email = unique_email(f"{label}-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=f"{label} Gym",
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
    coach_email = unique_email(f"{label}-coach")
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
    athlete = create_athlete(
        client,
        coach,
        email=unique_email(f"{label}-athlete"),
        coach_user_id=coach_member["user_id"],
    )["athlete"]["profile"]
    return gym, owner, coach, athlete


def test_custom_exercise_is_gym_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a, coach_a, _athlete_a = _gym_with_coach(
        client, superuser_headers, "exercise-a"
    )
    gym_b, owner_b, coach_b, athlete_b = _gym_with_coach(
        client, superuser_headers, "exercise-b"
    )

    created = client.post(
        "/api/v1/exercises",
        headers=coach_a,
        json={
            "name_fa": "حرکت اختصاصی تست",
            "muscle_group": "تمام بدن",
            "description": "فقط برای باشگاه اول",
        },
    )
    assert created.status_code == 200, created.text
    exercise_id = created.json()["id"]

    list_a = client.get("/api/v1/exercises", headers=coach_a)
    assert list_a.status_code == 200
    assert any(item["id"] == exercise_id for item in list_a.json()["data"])
    list_b = client.get("/api/v1/exercises", headers=coach_b)
    assert list_b.status_code == 200
    assert all(item["id"] != exercise_id for item in list_b.json()["data"])

    program = client.post(
        f"/api/v1/athletes/{athlete_b['user_id']}/programs",
        headers=coach_b,
        json={"title": "Cross gym exercise"},
    )
    assert program.status_code == 200
    version_id = program.json()["id"]
    invalid = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=coach_b,
        json=program_payload(exercise_id),
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "invalid_exercise"

    admin_list = client.get("/api/v1/exercises", headers=owner_a)
    assert admin_list.status_code == 200
    assert any(item["id"] == exercise_id for item in admin_list.json()["data"])
    assert gym_a["id"] != gym_b["id"]
