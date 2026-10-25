from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi.testclient import TestClient

TEST_SUPERUSER_PASSWORD = "test-only-superuser-password"


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def superuser_headers(client: TestClient, email: str) -> dict[str, str]:
    return auth_headers(client, email, TEST_SUPERUSER_PASSWORD)


def create_gym(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    owner_email: str,
    password: str = "owner-pass-123",
    method: str = "password",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/gyms/",
        headers=headers,
        json={
            "name": name,
            "owner_email": owner_email,
            "owner_full_name": f"Owner {name}",
            "activation_method": method,
            "initial_password": password if method == "password" else None,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_member(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    *,
    email: str,
    roles: list[str],
    password: str = "member-pass-123",
    method: str = "password",
    full_name: str | None = None,
    phone: str | None = "09120000000",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/gyms/{gym_id}/members",
        headers=headers,
        json={
            "email": email,
            "full_name": full_name or email,
            "roles": roles,
            "activation_method": method,
            "initial_password": password if method == "password" else None,
            "phone": phone,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_athlete(
    client: TestClient,
    headers: dict[str, str],
    *,
    email: str,
    coach_user_id: str | None,
    password: str = "athlete-pass-123",
    method: str = "password",
    full_name: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/athletes",
        headers=headers,
        json={
            "email": email,
            "full_name": full_name or email,
            "phone": phone,
            "coach_user_id": coach_user_id,
            "activation_method": method,
            "initial_password": password if method == "password" else None,
            "height_cm": 180,
            "weight_kg": 80,
            "training_goal": "قدرت",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def change_password(
    client: TestClient,
    headers: dict[str, str],
    *,
    current_password: str,
    new_password: str,
) -> None:
    response = client.post(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": current_password,
            "new_password": new_password,
        },
    )
    assert response.status_code == 200, response.text


def gym_headers(
    client: TestClient,
    *,
    email: str,
    password: str,
    gym_id: str,
) -> dict[str, str]:
    headers = auth_headers(client, email, password)
    headers["X-Gym-ID"] = gym_id
    return headers


def first_exercise_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/api/v1/exercises", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"][0]["id"]


def program_payload(exercise_id: str) -> dict[str, Any]:
    return {
        "title": "Program",
        "goal": "Strength",
        "notes": "notes",
        "days": [
            {
                "day_number": 1,
                "title": "Day 1",
                "notes": "day notes",
                "exercises": [
                    {
                        "exercise_id": exercise_id,
                        "order_index": 0,
                        "notes": "exercise notes",
                        "sets": [
                            {
                                "set_number": 1,
                                "reps_min": 8,
                                "reps_max": 10,
                                "weight_kg": 40,
                                "rest_seconds": 60,
                                "intensity": "RPE 7",
                                "note": "first",
                            },
                            {
                                "set_number": 2,
                                "reps_min": 6,
                                "reps_max": 6,
                                "weight_kg": 45,
                                "rest_seconds": 90,
                                "duration_seconds": 30,
                                "note": "second",
                            },
                        ],
                    }
                ],
            }
        ],
    }


def create_and_publish_program(
    client: TestClient,
    headers: dict[str, str],
    athlete_id: str,
) -> dict[str, Any]:
    exercise_id = first_exercise_id(client, headers)
    created = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=headers,
        json={"title": "Program"},
    )
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]
    saved = client.put(
        f"/api/v1/program-versions/{version_id}",
        headers=headers,
        json=program_payload(exercise_id),
    )
    assert saved.status_code == 200, saved.text
    published = client.post(
        f"/api/v1/program-versions/{version_id}/publish", headers=headers
    )
    assert published.status_code == 200, published.text
    return published.json()


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def extract_invitation_token(html_content: str) -> str:
    match = re.search(r"accept-invitation\?token=([^\"&<]+)", html_content)
    assert match, "invitation token not found"
    return match.group(1)
