from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_sandbox import (
    create_coach_contract,
    create_default_contract,
    create_sale,
    create_vat,
    make_finance_gym,
)
from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    gym_headers,
    unique_email,
)

pytestmark = pytest.mark.usefixtures("client")


def coach_headers(client: TestClient, env: dict[str, Any]) -> dict[str, str]:
    raw = auth_headers(client, env["coach_email"], "member-pass-123")
    change_password(
        client,
        raw,
        current_password="member-pass-123",
        new_password="member-pass-456",
    )
    return gym_headers(
        client,
        email=env["coach_email"],
        password="member-pass-456",
        gym_id=env["gym_id"],
    )


def athlete_headers(
    client: TestClient, env: dict[str, Any], email: str
) -> dict[str, str]:
    raw = auth_headers(client, email, "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    return gym_headers(
        client,
        email=email,
        password="athlete-pass-456",
        gym_id=env["gym_id"],
    )


def create_plan(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    *,
    coach_user_id: str | None,
    title: str = "پلن تمرینی اختصاصی",
    price_irr: int = 1_000_000,
    active: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "description": "برنامه اختصاصی بر اساس پرونده ورزشکار",
        "base_price_irr": price_irr,
        "is_active": active,
    }
    if coach_user_id is not None:
        body["coach_user_id"] = coach_user_id
    response = client.post(
        f"/api/v1/finance/gyms/{gym_id}/coach-plans",
        headers=headers,
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_athlete(client: TestClient, env: dict[str, Any]) -> tuple[str, dict[str, str]]:
    email = unique_email("finance-athlete")
    created = create_athlete(
        client,
        env["owner"],
        email=email,
        coach_user_id=env["coach_id"],
        full_name="ورزشکار مالی",
        phone="09123334444",
    )
    return (
        created["athlete"]["profile"]["user_id"],
        athlete_headers(client, env, email),
    )


def purchase(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    plan_id: str,
    *,
    key: str | None = None,
    outcome: str = "SUCCESS",
    note: str | None = "برنامه برای عضویت باشگاه",
) -> Any:
    offer = client.get(
        f"/api/v1/finance/gyms/{gym_id}/athlete/training-offer", headers=headers
    )
    assert offer.status_code == 200, offer.text
    return client.post(
        f"/api/v1/finance/gyms/{gym_id}/athlete/training-purchases",
        headers=headers,
        json={
            "plan_id": plan_id,
            "quote_token": (offer.json() or {}).get("quote_token", "invalid-quote"),
            "note": note,
            "idempotency_key": key or uuid.uuid4().hex,
            "outcome": outcome,
        },
    )


def test_coach_plan_is_unique_per_coach_and_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    first = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
        title="پلن اول",
        price_irr=900_000,
    )
    second = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
        title="پلن دوم",
        price_irr=1_200_000,
    )
    plans = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-plans",
        headers=env["owner"],
    ).json()
    active = [row for row in plans if row["is_active"]]
    assert [row["id"] for row in active] == [second["id"]]
    assert next(row for row in plans if row["id"] == first["id"])["is_active"] is False

    coach = coach_headers(client, env)
    own = create_plan(
        client,
        coach,
        env["gym_id"],
        coach_user_id=None,
        title="پلن مربی",
        price_irr=1_500_000,
    )
    assert own["coach_user_id"] == env["coach_id"]
    coach_list = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-plans",
        headers=coach,
    ).json()
    assert [row["id"] for row in coach_list if row["is_active"]] == [own["id"]]

    other_coach = add_member(
        client,
        env["owner"],
        env["gym_id"],
        email=unique_email("other-coach"),
        roles=["COACH"],
        phone="09125556666",
    )
    forbidden = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-plans",
        headers=coach,
        json={
            "coach_user_id": other_coach["member"]["user_id"],
            "title": "پلن غیرمجاز",
            "base_price_irr": 100_000,
            "is_active": True,
        },
    )
    assert forbidden.status_code == 403


def test_athlete_buys_only_current_coach_plan_and_request_is_idempotent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    create_vat(client, superuser_headers)
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
        price_irr=1_000_000,
    )
    athlete_id, athlete = make_athlete(client, env)

    offer = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-offer",
        headers=athlete,
    )
    assert offer.status_code == 200, offer.text
    assert offer.json()["plan"]["id"] == plan["id"]
    assert offer.json()["tax_amount_irr"] == 100_000
    assert offer.json()["total_amount_irr"] == 1_100_000
    assert offer.json()["platform_amount_irr"] == 110_000
    assert offer.json()["gym_amount_irr"] == 440_000
    assert offer.json()["coach_amount_irr"] == 550_000

    key = uuid.uuid4().hex
    purchased = purchase(client, athlete, env["gym_id"], plan["id"], key=key)
    assert purchased.status_code == 200, purchased.text
    body = purchased.json()
    assert body["payment"]["status"] == "SUCCEEDED"
    assert body["request"]["status"] == "REQUESTED"
    assert body["sale"]["coach_plan_id"] == plan["id"]
    assert body["sale"]["athlete_user_id"] == athlete_id
    request_id = body["request"]["id"]

    duplicate = purchase(client, athlete, env["gym_id"], plan["id"], key=key)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["request"]["id"] == request_id

    requests = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/program-requests",
        headers=athlete,
    )
    assert requests.status_code == 200
    assert [row["id"] for row in requests.json()] == [request_id]
    coach_requests = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/program-requests",
        headers=coach_headers(client, env),
    )
    assert coach_requests.status_code == 200
    assert [row["id"] for row in coach_requests.json()] == [request_id]

    failed = purchase(
        client,
        athlete,
        env["gym_id"],
        plan["id"],
        outcome="FAILURE",
        note="پرداخت ناموفق",
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["request"] is None
    requests = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/program-requests",
        headers=athlete,
    ).json()
    assert len(requests) == 1


def test_athlete_cannot_buy_another_coachs_plan(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    other = add_member(
        client,
        env["owner"],
        env["gym_id"],
        email=unique_email("other-plan-coach"),
        roles=["COACH"],
        phone="09126667777",
    )
    other_id = other["member"]["user_id"]
    # A second coach needs a training contract for the offer preview to exist.
    second = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": other_id,
            "category": "TRAINING",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1000,
            "gym_bp": 4000,
            "coach_bp": 5000,
        },
    )
    assert second.status_code == 200, second.text
    other_plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=other_id,
        title="پلن مربی دیگر",
    )
    _, athlete = make_athlete(client, env)
    denied = purchase(client, athlete, env["gym_id"], other_plan["id"])
    assert denied.status_code == 404
    assert denied.json()["detail"] == "training_plan_not_available"


def test_program_creation_requires_purchase_or_tracked_free_exception(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    create_vat(client, superuser_headers)
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    athlete_id, athlete = make_athlete(client, env)
    coach = coach_headers(client, env)

    missing = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=coach,
        json={"title": "برنامه بدون خرید"},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "program_purchase_required"

    free = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=coach,
        json={"title": "برنامه رایگان", "free_reason": "هدیه افتتاحیه"},
    )
    assert free.status_code == 200, free.text
    assert free.json()["origin"] == "FREE"
    assert free.json()["free_reason"] == "هدیه افتتاحیه"

    purchased = purchase(client, athlete, env["gym_id"], plan["id"])
    assert purchased.status_code == 200, purchased.text
    request_id = purchased.json()["request"]["id"]
    created = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=coach,
        json={
            "title": "برنامه خریداری‌شده",
            "purchase_request_id": request_id,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["origin"] == "PURCHASED"
    assert created.json()["purchase_request_id"] == request_id

    reused = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=coach,
        json={
            "title": "استفاده دوباره",
            "purchase_request_id": request_id,
        },
    )
    assert reused.status_code == 409
    assert reused.json()["detail"] == "program_request_already_fulfilled"

    copy_without_source = client.post(
        f"/api/v1/program-versions/{created.json()['id']}/new-draft",
        headers=coach,
    )
    assert copy_without_source.status_code == 400
    assert copy_without_source.json()["detail"] == "program_purchase_required"

    copy_free = client.post(
        f"/api/v1/program-versions/{created.json()['id']}/new-draft",
        headers=coach,
        json={"free_reason": "اصلاح استثنایی"},
    )
    assert copy_free.status_code == 200, copy_free.text
    assert copy_free.json()["origin"] == "FREE"


def test_membership_has_no_coach_share(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    forbidden_contract = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": env["coach_id"],
            "category": "MEMBERSHIP",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1000,
            "gym_bp": 4000,
            "coach_bp": 5000,
        },
    )
    assert forbidden_contract.status_code == 400
    assert forbidden_contract.json()["detail"] == "membership_coach_forbidden"

    forbidden_sale = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales",
        headers=env["owner"],
        json={
            "category": "MEMBERSHIP",
            "description": "فروش عضویت با مربی",
            "base_amount_irr": 1_000_000,
            "tax_ids": [],
            "coach_user_id": env["coach_id"],
            "sold_on": date.today().isoformat(),
        },
    )
    assert forbidden_sale.status_code == 400
    assert forbidden_sale.json()["detail"] == "membership_coach_forbidden"

    membership = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        base_amount_irr=1_000_000,
        category="MEMBERSHIP",
    )
    assert membership["coach_bp"] == 0
    assert membership["coach_amount_irr"] == 0
    assert membership["platform_amount_irr"] == 100_000
    assert membership["gym_amount_irr"] == 900_000
