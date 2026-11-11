from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import WorkoutDay, WorkoutExercise, WorkoutSet
from tests.api.routes.test_finance_plans import (
    coach_headers,
    create_plan,
    make_athlete,
    purchase,
)
from tests.api.routes.test_finance_sandbox import (
    create_coach_contract,
    create_default_contract,
    make_finance_gym,
)
from tests.conftest import test_engine


@pytest.fixture()
def env(client: TestClient, superuser_headers: dict[str, str]) -> dict[str, Any]:
    data = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    create_coach_contract(
        client,
        data["owner"],
        data["gym_id"],
        data["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    data["coach"] = coach_headers(client, data)
    data["athlete_id"], data["athlete"] = make_athlete(client, data)
    data["plan"] = create_plan(
        client, data["owner"], data["gym_id"], coach_user_id=data["coach_id"]
    )
    return data


def buy(client: TestClient, env: dict[str, Any]) -> dict[str, Any]:
    response = purchase(client, env["athlete"], env["gym_id"], env["plan"]["id"])
    assert response.status_code == 200, response.text
    return response.json()


def draft(client: TestClient, env: dict[str, Any], request_id: str) -> Any:
    return client.post(
        f"/api/v1/athletes/{env['athlete_id']}/programs",
        headers=env["coach"],
        json={"title": "Purchased program", "purchase_request_id": request_id},
    )


def request_status(client: TestClient, env: dict[str, Any], request_id: str) -> str:
    rows = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/program-requests",
        headers=env["athlete"],
    ).json()
    return next(row["status"] for row in rows if row["id"] == request_id)


def publishable(version_id: str) -> dict[str, str]:
    with Session(test_engine) as db:
        from app.models import Exercise

        exercise = db.exec(select(Exercise)).first()
        assert exercise is not None
        day = WorkoutDay(
            version_id=uuid.UUID(version_id), day_number=1, title="Workout day"
        )
        db.add(day)
        db.flush()
        movement = WorkoutExercise(
            day_id=day.id,
            exercise_id=exercise.id,
            exercise_name=exercise.name_fa,
            muscle_group=exercise.muscle_group,
            order_index=0,
        )
        db.add(movement)
        db.flush()
        target = WorkoutSet(
            workout_exercise_id=movement.id,
            set_number=1,
            reps_min=8,
            reps_max=12,
            weight_kg=20,
        )
        db.add(target)
        db.commit()
        return {"day_id": str(day.id), "set_id": str(target.id)}


def test_purchase_releases_deleted_draft_and_only_delivers_on_publish(
    client: TestClient, env: dict[str, Any]
) -> None:
    bought = buy(client, env)
    rid = bought["request"]["id"]
    first = draft(client, env, rid)
    assert first.status_code == 200
    assert request_status(client, env, rid) == "IN_PROGRESS"
    assert draft(client, env, rid).status_code == 409
    visible = client.get(
        f"/api/v1/athletes/{env['athlete_id']}/programs", headers=env["athlete"]
    ).json()["data"]
    assert all(row["id"] != first.json()["id"] for row in visible)
    assert (
        client.delete(
            f"/api/v1/program-versions/{first.json()['id']}", headers=env["coach"]
        ).status_code
        == 200
    )
    assert request_status(client, env, rid) == "REQUESTED"
    second = draft(client, env, rid)
    assert second.status_code == 200
    publishable(second.json()["id"])
    published = client.post(
        f"/api/v1/program-versions/{second.json()['id']}/publish", headers=env["coach"]
    )
    assert published.status_code == 200, published.text
    assert request_status(client, env, rid) == "FULFILLED"


def test_price_changes_require_new_confirmation_and_retry_is_idempotent(
    client: TestClient, env: dict[str, Any]
) -> None:
    path = f"/api/v1/finance/gyms/{env['gym_id']}"
    offer = client.get(path + "/athlete/training-offer", headers=env["athlete"]).json()
    body = {
        "plan_id": env["plan"]["id"],
        "quote_token": offer["quote_token"],
        "idempotency_key": uuid.uuid4().hex,
    }
    changed = client.put(
        path + f"/coach-plans/{env['plan']['id']}",
        headers=env["coach"],
        json={"title": "Changed", "base_price_irr": 2_000_000},
    )
    assert changed.status_code == 200
    rejected = client.post(
        path + "/athlete/training-purchases", headers=env["athlete"], json=body
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"] == "training_quote_changed"
    assert (
        client.get(path + "/athlete/program-requests", headers=env["athlete"]).json()
        == []
    )
    body["quote_token"] = client.get(
        path + "/athlete/training-offer", headers=env["athlete"]
    ).json()["quote_token"]
    first = client.post(
        path + "/athlete/training-purchases", headers=env["athlete"], json=body
    )
    again = client.post(
        path + "/athlete/training-purchases", headers=env["athlete"], json=body
    )
    assert first.status_code == again.status_code == 200
    assert first.json()["payment"]["id"] == again.json()["payment"]["id"]
    missing = {key: value for key, value in body.items() if key != "quote_token"}
    assert (
        client.post(
            path + "/athlete/training-purchases", headers=env["athlete"], json=missing
        ).status_code
        == 422
    )


def test_receipts_are_private_and_exclude_allocation_shares(
    client: TestClient, env: dict[str, Any]
) -> None:
    bought = buy(client, env)
    path = f"/api/v1/gyms/{env['gym_id']}/athlete/purchases/{bought['sale']['id']}/document"
    doc = client.get(path, headers=env["athlete"])
    assert doc.status_code == 200, doc.text
    assert doc.json()["payments"][0]["amount_irr"] == bought["payment"]["amount_irr"]
    assert "platform_bp" not in doc.json() and "allocations" not in doc.json()
    _, other = make_athlete(client, env)
    assert client.get(path, headers=other).status_code == 404
    assert client.get(path, headers=env["coach"]).status_code == 403


def test_statement_contains_only_current_coach_and_tasks_are_scoped(
    client: TestClient, env: dict[str, Any]
) -> None:
    bought = buy(client, env)
    path = f"/api/v1/gyms/{env['gym_id']}"
    statement = client.get(path + "/coach/statement", headers=env["coach"])
    assert statement.status_code == 200, statement.text
    assert statement.json()["earned_irr"] == bought["sale"]["coach_amount_irr"]
    assert "platform_amount_irr" not in statement.text
    owner = client.get(path + "/coach/statement", headers=env["owner"])
    assert owner.json()["earned_irr"] == 0
    assert (
        client.get(path + "/coach/statement", headers=env["athlete"]).status_code == 403
    )
    tasks = client.get(path + "/tasks", headers=env["coach"])
    assert tasks.status_code == 200, tasks.text
    assert tasks.json()["requested_count"] == 1
    draft(client, env, bought["request"]["id"])
    assert (
        client.get(path + "/tasks", headers=env["coach"]).json()["in_progress_count"]
        == 1
    )
    assert client.get(path + "/tasks", headers=env["athlete"]).status_code == 403


def test_actual_workout_is_private_validated_and_snapshotted(
    client: TestClient, env: dict[str, Any]
) -> None:
    bought = buy(client, env)
    created = draft(client, env, bought["request"]["id"]).json()
    structure = publishable(created["id"])
    assert (
        client.post(
            f"/api/v1/program-versions/{created['id']}/publish", headers=env["coach"]
        ).status_code
        == 200
    )
    public = client.get(
        f"/api/v1/program-versions/{created['id']}", headers=env["athlete"]
    ).json()
    assert public["days"][0]["id"] == structure["day_id"]
    assert public["days"][0]["exercises"][0]["sets"][0]["id"] == structure["set_id"]
    path = f"/api/v1/athletes/{env['athlete_id']}/workout-sessions"
    body = {
        "version_id": created["id"],
        "day_id": structure["day_id"],
        "performed_on": date.today().isoformat(),
        "completed": True,
        "effort": 7,
        "note": "Felt stronger",
        "idempotency_key": str(uuid.uuid4()),
        "sets": [
            {
                "set_id": structure["set_id"],
                "completed": True,
                "reps": 10,
                "weight_kg": 22.5,
            }
        ],
    }
    first = client.post(path, headers=env["athlete"], json=body)
    assert first.status_code == 200, first.text
    again = client.post(path, headers=env["athlete"], json=body)
    assert again.json()["id"] == first.json()["id"]
    assert first.json()["sets"][0]["target_weight_kg"] == 20
    assert client.get(path, headers=env["coach"]).json()[0]["note"] == "Felt stronger"
    assert client.post(path, headers=env["coach"], json=body).status_code == 403
    _, other = make_athlete(client, env)
    assert client.get(path, headers=other).status_code == 404
    invalid = {
        **body,
        "idempotency_key": str(uuid.uuid4()),
        "sets": [{**body["sets"][0], "weight_kg": -1}],
    }
    assert client.post(path, headers=env["athlete"], json=invalid).status_code == 422
    invalid = {
        **body,
        "idempotency_key": str(uuid.uuid4()),
        "performed_on": (date.today() + timedelta(days=2)).isoformat(),
    }
    assert client.post(path, headers=env["athlete"], json=invalid).status_code == 400
    invalid = {
        **body,
        "idempotency_key": str(uuid.uuid4()),
        "sets": [{**body["sets"][0], "set_id": str(uuid.uuid4())}],
    }
    assert client.post(path, headers=env["athlete"], json=invalid).status_code == 400
    with Session(test_engine) as db:
        target = db.get(WorkoutSet, uuid.UUID(structure["set_id"]))
        assert target is not None
        target.weight_kg = 50
        db.add(target)
        db.commit()
    assert (
        client.get(path, headers=env["athlete"]).json()[0]["sets"][0][
            "target_weight_kg"
        ]
        == 20
    )


def test_quote_rejects_expired_or_forged_tokens(
    client: TestClient, env: dict[str, Any]
) -> None:
    from datetime import UTC, datetime

    import jwt

    from app.core.config import settings
    from app.core.security import ALGORITHM

    path = f"/api/v1/finance/gyms/{env['gym_id']}/athlete"
    offer = client.get(path + "/training-offer", headers=env["athlete"]).json()
    claims = jwt.decode(
        offer["quote_token"], settings.SECRET_KEY, algorithms=[ALGORITHM]
    )
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    expired = jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)
    for quote in [expired, "forged-quote"]:
        response = client.post(
            path + "/training-purchases",
            headers=env["athlete"],
            json={
                "plan_id": env["plan"]["id"],
                "quote_token": quote,
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        assert response.status_code == 409, response.text
    assert client.get(path + "/program-requests", headers=env["athlete"]).json() == []


def test_workout_history_survives_program_deletion_and_rejects_reused_keys(
    client: TestClient, env: dict[str, Any]
) -> None:
    bought = buy(client, env)
    created = draft(client, env, bought["request"]["id"]).json()
    structure = publishable(created["id"])
    assert (
        client.post(
            f"/api/v1/program-versions/{created['id']}/publish", headers=env["coach"]
        ).status_code
        == 200
    )
    path = f"/api/v1/athletes/{env['athlete_id']}/workout-sessions"
    body = {
        "version_id": created["id"],
        "day_id": structure["day_id"],
        "performed_on": date.today().isoformat(),
        "idempotency_key": str(uuid.uuid4()),
        "sets": [
            {
                "set_id": structure["set_id"],
                "completed": True,
                "reps": 8,
                "weight_kg": 25,
            }
        ],
    }
    saved = client.post(path, headers=env["athlete"], json=body)
    assert saved.status_code == 200, saved.text
    changed = {**body, "note": "different payload"}
    assert client.post(path, headers=env["athlete"], json=changed).status_code == 409
    assert (
        client.delete(
            f"/api/v1/program-versions/{created['id']}", headers=env["coach"]
        ).status_code
        == 200
    )
    history = client.get(path, headers=env["athlete"]).json()
    assert history[0]["version_id"] is None
    assert history[0]["sets"][0]["weight_kg"] == 25
    assert request_status(client, env, bought["request"]["id"]) == "FULFILLED"


def test_new_views_do_not_cross_gyms(
    client: TestClient, env: dict[str, Any], superuser_headers: dict[str, str]
) -> None:
    other = make_finance_gym(client, superuser_headers)
    path = f"/api/v1/gyms/{other['gym_id']}"
    for endpoint in ["/tasks", "/coach/statement"]:
        response = client.get(
            path + endpoint, headers={**env["coach"], "X-Gym-ID": other["gym_id"]}
        )
        assert response.status_code in {403, 404}
    bought = buy(client, env)
    doc = f"/api/v1/gyms/{other['gym_id']}/athlete/purchases/{bought['sale']['id']}/document"
    assert client.get(doc, headers=env["athlete"]).status_code == 403
