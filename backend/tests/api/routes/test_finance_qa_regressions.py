from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from threading import Barrier
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import (
    FinanceCoachContract,
    FinancePayment,
    FinancePlatformContract,
    FinancePlatformRate,
    FinanceProgramRequest,
    FinanceRefund,
    FinanceRefundAdjustment,
    FinanceSale,
    FinanceSettlement,
)
from app.main import app
from app.models import GymMembership, User
from app.services import finance as svc
from tests.api.routes.test_finance_plans import (
    create_plan,
    make_athlete,
    purchase,
)
from tests.api.routes.test_finance_sandbox import (
    create_coach_contract,
    create_default_contract,
    create_sale,
    create_vat,
    make_finance_gym,
    pay,
    platform_rates,
)
from tests.conftest import test_engine


@pytest.fixture()
def env(client: TestClient, superuser_headers: dict[str, str]) -> dict[str, Any]:
    environment = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    return environment


def paid_membership(
    client: TestClient,
    env: dict[str, Any],
    *,
    amount: int = 1_000_000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        category="MEMBERSHIP",
        base_amount_irr=amount,
    )
    response = pay(client, env["owner"], env["gym_id"], sale["id"])
    assert response.status_code == 200, response.text
    return sale, response.json()


def paid_training(
    client: TestClient,
    env: dict[str, Any],
    *,
    amount: int = 1_000_000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        category="TRAINING",
        base_amount_irr=amount,
        coach_id=env["coach_id"],
    )
    response = pay(client, env["owner"], env["gym_id"], sale["id"])
    assert response.status_code == 200, response.text
    return sale, response.json()


def report_for(
    client: TestClient,
    env: dict[str, Any],
    *,
    category: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    end_date = end or svc.finance_today().isoformat()
    params: dict[str, Any] = {
        "gym_id": env["gym_id"],
        "from_date": end_date,
        "to_date": end_date,
    }
    if category is not None:
        params["category"] = category
    response = client.get(
        "/api/v1/finance/reports",
        headers=env["owner"],
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def payment_for_sale(
    client: TestClient, env: dict[str, Any], sale_id: str
) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments",
        headers=env["owner"],
    )
    assert response.status_code == 200, response.text
    return next(
        row
        for row in response.json()
        if row["sale_id"] == sale_id and row["status"] == "SUCCEEDED"
    )


def refund(
    client: TestClient,
    env: dict[str, Any],
    payment: dict[str, Any],
    amount: int,
    *,
    key: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments/{payment['id']}/refunds",
        headers=env["owner"],
        json={
            "amount_irr": amount,
            "reason": "QA regression refund",
            "idempotency_key": key or uuid.uuid4().hex,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_qa_category_filter_excludes_other_payments(
    client: TestClient, env: dict[str, Any]
) -> None:
    paid_membership(client, env)

    training = report_for(client, env, category="TRAINING")
    assert training["activity"]["total_payments_irr"] == 0
    assert training["activity"]["platform_share_irr"] == 0
    assert training["activity"]["gym_share_irr"] == 0
    assert training["as_of"]["unsettled_platform_irr"] == 0
    assert training["as_of"]["unsettled_gym_irr"] == 0

    membership = report_for(client, env, category="MEMBERSHIP")
    assert membership["activity"]["total_payments_irr"] == 1_000_000
    assert membership["activity"]["platform_share_irr"] == 100_000
    assert membership["activity"]["gym_share_irr"] == 900_000


def test_qa_category_filter_is_consistent_for_mixed_settlements(
    client: TestClient, env: dict[str, Any]
) -> None:
    paid_membership(client, env)
    paid_training(client, env)
    settlement = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 1_300_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert settlement.status_code == 200, settlement.text

    training = report_for(client, env, category="TRAINING")
    membership = report_for(client, env, category="MEMBERSHIP")
    everything = report_for(client, env)
    assert training["as_of"]["pending_settlements_irr"] == 400_000
    assert membership["as_of"]["pending_settlements_irr"] == 900_000
    assert (
        training["as_of"]["pending_settlements_irr"]
        + membership["as_of"]["pending_settlements_irr"]
        == everything["as_of"]["pending_settlements_irr"]
    )


def test_qa_repeated_partial_refunds_do_not_exceed_party_allocation(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale, _ = paid_membership(client, env, amount=100)
    payment = payment_for_sale(client, env, sale["id"])

    refund(client, env, payment, 55)
    refund(client, env, payment, 45)

    updated = payment_for_sale(client, env, sale["id"])
    allocations = {row["party"]: row for row in updated["allocations"]}
    assert allocations["PLATFORM"]["amount_irr"] == 10
    assert allocations["GYM"]["amount_irr"] == 90
    assert allocations["PLATFORM"]["refunded_irr"] == 10
    assert allocations["GYM"]["refunded_irr"] == 90
    assert all(
        row["refunded_irr"] == row["amount_irr"] for row in updated["allocations"]
    )


@pytest.mark.parametrize("action", ["complete", "cancel"])
def test_qa_historical_pending_is_preserved(
    client: TestClient,
    env: dict[str, Any],
    db_session: Session,
    action: str,
) -> None:
    sale, payment = paid_membership(client, env)
    settlement_response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 900_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert settlement_response.status_code == 200, settlement_response.text
    settlement = settlement_response.json()

    yesterday_date = svc.finance_today() - timedelta(days=1)
    yesterday = datetime.combine(yesterday_date, time(12, 0), tzinfo=UTC)
    payment_row = db_session.get(FinancePayment, uuid.UUID(payment["id"]))
    settlement_row = db_session.get(FinanceSettlement, uuid.UUID(settlement["id"]))
    assert payment_row is not None
    assert settlement_row is not None
    payment_row.paid_at = yesterday
    settlement_row.requested_at = yesterday
    db_session.add(payment_row)
    db_session.add(settlement_row)
    db_session.commit()

    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{settlement['id']}/{action}",
        headers=env["owner"],
    )
    assert response.status_code == 200, response.text

    historical = report_for(client, env, end=yesterday_date.isoformat())
    assert historical["as_of"]["pending_settlements_irr"] == 900_000
    assert historical["as_of"]["unsettled_gym_irr"] == 0


def test_qa_concurrent_settlements_do_not_overreserve(
    client: TestClient, env: dict[str, Any]
) -> None:
    paid_membership(client, env)
    with Session(test_engine) as db:
        actor_id = db.exec(
            select(User.id).where(User.email == env["owner_email"])
        ).one()
    barrier = Barrier(2)

    def worker(index: int) -> dict[str, Any]:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                return svc.create_settlement(
                    db,
                    actor=actor,
                    gym_id=uuid.UUID(env["gym_id"]),
                    party="GYM",
                    party_user_id=None,
                    amount_irr=900_000,
                    idempotency_key=f"concurrent-settlement-{index}",
                )
            except HTTPException as exc:
                assert exc.status_code in (400, 409)
                return {"error": exc.detail}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    successful = [row for row in results if "id" in row]
    assert len(successful) == 1, results
    completed = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{successful[0]['id']}/complete",
        headers=env["owner"],
    )
    assert completed.status_code == 200, completed.text
    with Session(test_engine) as db:
        rows = db.exec(
            select(FinanceSettlement).where(
                FinanceSettlement.gym_id == uuid.UUID(env["gym_id"]),
                FinanceSettlement.party == "GYM",
                FinanceSettlement.status == "COMPLETED",
            )
        ).all()
    assert sum(row.amount_irr for row in rows) == 900_000


def test_qa_refunded_purchase_cannot_be_fulfilled(
    client: TestClient, env: dict[str, Any]
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    athlete_id, athlete_headers = make_athlete(client, env)
    bought = purchase(client, athlete_headers, env["gym_id"], plan["id"]).json()
    refund(
        client,
        env,
        bought["payment"],
        bought["payment"]["amount_irr"],
    )

    response = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=env["owner"],
        json={
            "title": "Refunded purchase",
            "purchase_request_id": bought["request"]["id"],
        },
    )
    assert response.status_code in (400, 409), response.text
    assert response.json()["detail"] in {
        "program_request_cancelled",
        "program_purchase_refunded",
    }


def test_qa_partial_refund_does_not_cancel_purchase_request(
    client: TestClient, env: dict[str, Any]
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    athlete_id, athlete_headers = make_athlete(client, env)
    bought = purchase(client, athlete_headers, env["gym_id"], plan["id"]).json()
    refund(client, env, bought["payment"], 100)

    response = client.post(
        f"/api/v1/athletes/{athlete_id}/programs",
        headers=env["owner"],
        json={
            "title": "Partially refunded purchase",
            "purchase_request_id": bought["request"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["origin"] == "PURCHASED"


def test_qa_normal_large_sale_is_supported(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        category="MEMBERSHIP",
        base_amount_irr=3_000_000_000,
    )
    payment = pay(client, env["owner"], env["gym_id"], sale["id"])
    assert payment.status_code == 200, payment.text
    body = payment.json()
    assert body["amount_irr"] == 3_000_000_000
    assert sum(row["amount_irr"] for row in body["allocations"]) == 3_000_000_000
    settlement = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 2_700_000_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert settlement.status_code == 200, settlement.text
    completed = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{settlement.json()['id']}/complete",
        headers=env["owner"],
    )
    assert completed.status_code == 200, completed.text
    refund(client, env, body, 1_000_000)
    report = report_for(client, env)
    assert report["activity"]["total_payments_irr"] == 3_000_000_000
    assert report["activity"]["completed_settlements_irr"] == 2_700_000_000


def test_qa_amount_plus_tax_over_supported_range_is_rejected(
    client: TestClient, env: dict[str, Any], superuser_headers: dict[str, str]
) -> None:
    vat = create_vat(client, superuser_headers)
    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales/preview",
        headers=env["owner"],
        json={
            "category": "MEMBERSHIP",
            "description": "Too large",
            "base_amount_irr": 10**15,
            "tax_ids": [vat["id"]],
            "coach_user_id": None,
            "sold_on": svc.finance_today().isoformat(),
        },
    )
    assert response.status_code == 422 or response.status_code == 400
    if response.status_code == 400:
        assert response.json()["detail"] == "amount_out_of_range"


def test_qa_departed_coach_can_receive_existing_earnings(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    paid_training(client, env)
    membership = db_session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == uuid.UUID(env["gym_id"]),
            GymMembership.user_id == uuid.UUID(env["coach_id"]),
        )
    ).one()
    membership.is_active = False
    db_session.add(membership)
    db_session.commit()

    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "COACH",
            "party_user_id": env["coach_id"],
            "amount_irr": 500_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert response.status_code == 200, response.text


def test_qa_refund_idempotency_cannot_return_another_payment(
    client: TestClient, env: dict[str, Any]
) -> None:
    _, first_payment = paid_membership(client, env)
    _, second_payment = paid_membership(client, env)
    refund(client, env, first_payment, 100, key="same-refund-key")

    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments/{second_payment['id']}/refunds",
        headers=env["owner"],
        json={
            "amount_irr": 200,
            "reason": "QA regression refund",
            "idempotency_key": "same-refund-key",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "idempotency_key_reused"


def test_qa_concurrent_duplicate_refund_is_idempotent(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale, payment = paid_membership(client, env)
    with Session(test_engine) as db:
        actor_id = db.exec(
            select(User.id).where(User.email == env["owner_email"])
        ).one()
    barrier = Barrier(2)
    key = "duplicate-refund-key"

    def worker(_index: int) -> str:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            result = svc.create_refund(
                db,
                actor=actor,
                gym_id=uuid.UUID(env["gym_id"]),
                payment_id=uuid.UUID(payment["id"]),
                amount_irr=100,
                idempotency_key=key,
                reason="QA concurrent refund",
            )
            return str(result["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    assert results[0] == results[1]
    with Session(test_engine) as db:
        refunds = db.exec(
            select(FinanceRefund).where(
                FinanceRefund.payment_id == uuid.UUID(payment["id"])
            )
        ).all()
        adjustments = db.exec(
            select(FinanceRefundAdjustment).where(
                FinanceRefundAdjustment.refund_id == uuid.UUID(results[0])
            )
        ).all()
    assert len(refunds) == 1
    assert sum(row.amount_irr for row in adjustments) == 100


def test_qa_contract_update_preserves_backdated_sale_policy(
    client: TestClient,
    env: dict[str, Any],
    superuser_headers: dict[str, str],
) -> None:
    old_date = svc.finance_today() - timedelta(days=2)
    old = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "Old contract",
            "scope": "DEFAULT",
            "effective_from": old_date.isoformat(),
            "rates": platform_rates(),
        },
    )
    assert old.status_code == 200, old.text
    old_id = old.json()["id"]

    before = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": old_date.isoformat(),
        },
    )
    assert before.status_code == 200, before.text

    new = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "New contract",
            "scope": "DEFAULT",
            "effective_from": svc.finance_today().isoformat(),
            "rates": platform_rates(2000),
        },
    )
    assert new.status_code == 200, new.text

    after = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": old_date.isoformat(),
        },
    )
    assert after.status_code == 200, after.text
    assert after.json()["contract_id"] == old_id
    assert after.json()["platform_bp"] == 1000

    sale = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales",
        headers=env["owner"],
        json={
            "category": "MEMBERSHIP",
            "description": "Backdated sale",
            "base_amount_irr": 1_000_000,
            "tax_ids": [],
            "coach_user_id": None,
            "sold_on": old_date.isoformat(),
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["platform_bp"] == 1000


def test_qa_coach_contract_historical_resolution_after_rebase(
    client: TestClient,
    env: dict[str, Any],
    superuser_headers: dict[str, str],
) -> None:
    old_date = svc.finance_today() - timedelta(days=2)
    old = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "Old contract",
            "scope": "DEFAULT",
            "effective_from": old_date.isoformat(),
            "rates": platform_rates(training_bp=1000),
        },
    )
    assert old.status_code == 200, old.text
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
        effective_from=old_date.isoformat(),
    )
    new = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "New contract",
            "scope": "DEFAULT",
            "effective_from": svc.finance_today().isoformat(),
            "rates": platform_rates(2000),
        },
    )
    assert new.status_code == 200, new.text

    with Session(test_engine) as db:
        historical = svc.resolve_coach_contract(
            db,
            gym_id=uuid.UUID(env["gym_id"]),
            coach_user_id=uuid.UUID(env["coach_id"]),
            category="TRAINING",
            on_date=old_date,
        )
    assert historical is not None
    assert historical.platform_bp == 1000
    assert historical.gym_bp == 4000
    assert historical.coach_bp == 5000


def test_qa_concurrent_settlement_and_refund_never_overlap(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale, payment = paid_membership(client, env)
    with Session(test_engine) as db:
        actor_id = db.exec(
            select(User.id).where(User.email == env["owner_email"])
        ).one()
    barrier = Barrier(2)

    def settle_worker() -> dict[str, Any]:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                row = svc.create_settlement(
                    db,
                    actor=actor,
                    gym_id=uuid.UUID(env["gym_id"]),
                    party="GYM",
                    party_user_id=None,
                    amount_irr=900_000,
                    idempotency_key="race-settlement",
                )
                return {"kind": "settlement", "id": row["id"]}
            except HTTPException as exc:
                return {"kind": "error", "detail": exc.detail}

    def refund_worker() -> dict[str, Any]:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                row = svc.create_refund(
                    db,
                    actor=actor,
                    gym_id=uuid.UUID(env["gym_id"]),
                    payment_id=uuid.UUID(payment["id"]),
                    amount_irr=payment["amount_irr"],
                    idempotency_key="race-refund",
                    reason="QA race refund",
                )
                return {"kind": "refund", "id": row["id"]}
            except HTTPException as exc:
                return {"kind": "error", "detail": exc.detail}

    with ThreadPoolExecutor(max_workers=2) as pool:
        settlement_future = pool.submit(settle_worker)
        refund_future = pool.submit(refund_worker)
        settlement_result = settlement_future.result(timeout=30)
        refund_result = refund_future.result(timeout=30)

    successes = [
        row for row in (settlement_result, refund_result) if row["kind"] != "error"
    ]
    assert len(successes) == 1, (settlement_result, refund_result)
    with Session(test_engine) as db:
        settlements = db.exec(
            select(FinanceSettlement).where(
                FinanceSettlement.gym_id == uuid.UUID(env["gym_id"])
            )
        ).all()
        refunds = db.exec(
            select(FinanceRefund).where(
                FinanceRefund.gym_id == uuid.UUID(env["gym_id"])
            )
        ).all()
    if successes[0]["kind"] == "settlement":
        assert len(refunds) == 0
        completed = client.post(
            f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{successes[0]['id']}/complete",
            headers=env["owner"],
        )
        assert completed.status_code == 200, completed.text
        assert sum(row.amount_irr for row in settlements) == 900_000
    else:
        assert len(settlements) == 0
        assert sum(row.amount_irr for row in refunds) == payment["amount_irr"]


def test_qa_concurrent_auto_settle_does_not_overpay(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale, _ = paid_membership(client, env)
    with Session(test_engine) as db:
        actor_id = db.exec(
            select(User.id).where(User.email == env["owner_email"])
        ).one()
    barrier = Barrier(2)

    def worker(_index: int) -> list[dict[str, Any]]:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            return svc.auto_settle(db, actor=actor, gym_id=uuid.UUID(env["gym_id"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    with Session(test_engine) as db:
        completed = db.exec(
            select(FinanceSettlement).where(
                FinanceSettlement.gym_id == uuid.UUID(env["gym_id"]),
                FinanceSettlement.status == "COMPLETED",
            )
        ).all()
    assert sum(row.amount_irr for row in completed) == sale["total_amount_irr"]
    assert sum(len(rows) for rows in results) <= 2


def test_qa_settlement_idempotency_rejects_payload_change(
    client: TestClient, env: dict[str, Any]
) -> None:
    paid_membership(client, env)
    first = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 100_000,
            "idempotency_key": "settlement-payload-key",
        },
    )
    assert first.status_code == 200, first.text
    retry = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 200_000,
            "idempotency_key": "settlement-payload-key",
        },
    )
    assert retry.status_code == 409, retry.text
    assert retry.json()["detail"] == "idempotency_key_reused"


def test_qa_purchase_idempotency_rejects_different_plan(
    client: TestClient, env: dict[str, Any]
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    first_plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
        title="First",
    )
    _, athlete_headers = make_athlete(client, env)
    key = "purchase-payload-key"
    first = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-purchases",
        headers=athlete_headers,
        json={
            "plan_id": first_plan["id"],
            "quote_token": client.get(
                f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-offer",
                headers=athlete_headers,
            ).json()["quote_token"],
            "note": None,
            "idempotency_key": key,
            "outcome": "SUCCESS",
        },
    )
    assert first.status_code == 200, first.text
    second_plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
        title="Second",
    )
    second = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-purchases",
        headers=athlete_headers,
        json={
            "plan_id": second_plan["id"],
            "quote_token": client.get(
                f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-offer",
                headers=athlete_headers,
            ).json()["quote_token"],
            "note": None,
            "idempotency_key": key,
            "outcome": "SUCCESS",
        },
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "idempotency_key_reused"


def test_qa_concurrent_different_refunds_respect_remaining(
    client: TestClient, env: dict[str, Any]
) -> None:
    sale, payment = paid_membership(client, env, amount=100)
    with Session(test_engine) as db:
        actor_id = db.exec(
            select(User.id).where(User.email == env["owner_email"])
        ).one()
    barrier = Barrier(2)

    def worker(index: int) -> dict[str, Any]:
        with Session(test_engine) as db:
            actor = db.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                row = svc.create_refund(
                    db,
                    actor=actor,
                    gym_id=uuid.UUID(env["gym_id"]),
                    payment_id=uuid.UUID(payment["id"]),
                    amount_irr=60,
                    idempotency_key=f"different-refund-{index}",
                    reason="QA concurrent different refund",
                )
                return {"id": row["id"], "amount": row["amount_irr"]}
            except HTTPException as exc:
                return {"error": exc.detail}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    with Session(test_engine) as db:
        refunds = db.exec(
            select(FinanceRefund).where(
                FinanceRefund.payment_id == uuid.UUID(payment["id"])
            )
        ).all()
    assert sum(row.amount_irr for row in refunds) <= 100
    assert len([row for row in results if "id" in row]) == 1


def test_qa_auto_settle_pays_departed_coach(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    paid_training(client, env)
    membership = db_session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == uuid.UUID(env["gym_id"]),
            GymMembership.user_id == uuid.UUID(env["coach_id"]),
        )
    ).one()
    membership.is_active = False
    db_session.add(membership)
    db_session.commit()

    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/auto",
        headers=env["owner"],
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert any(row["party"] == "COACH" and row["amount_irr"] == 500_000 for row in rows)


def test_qa_completed_settlement_and_refund_category_totals(
    client: TestClient, env: dict[str, Any]
) -> None:
    membership_sale, membership_payment = paid_membership(client, env)
    training_sale, _training_payment = paid_training(client, env)
    settlement = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "party_user_id": None,
            "amount_irr": 1_300_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert settlement.status_code == 200, settlement.text
    completed = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{settlement.json()['id']}/complete",
        headers=env["owner"],
    )
    assert completed.status_code == 200, completed.text
    refund(client, env, membership_payment, 100_000)

    training = report_for(client, env, category="TRAINING")
    membership = report_for(client, env, category="MEMBERSHIP")
    everything = report_for(client, env)
    assert training["activity"]["refunds_irr"] == 0
    assert membership["activity"]["refunds_irr"] == 100_000
    assert training["activity"]["completed_settlements_irr"] == 400_000
    assert membership["activity"]["completed_settlements_irr"] == 900_000
    assert (
        training["activity"]["completed_settlements_irr"]
        + membership["activity"]["completed_settlements_irr"]
        == everything["activity"]["completed_settlements_irr"]
    )
    assert training_sale["total_amount_irr"] == 1_000_000
    assert membership_sale["total_amount_irr"] == 1_000_000


def test_qa_coach_selector_includes_departed_coach_with_balance(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    paid_training(client, env)
    membership = db_session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == uuid.UUID(env["gym_id"]),
            GymMembership.user_id == uuid.UUID(env["coach_id"]),
        )
    ).one()
    membership.is_active = False
    db_session.add(membership)
    db_session.commit()

    default = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coaches",
        headers=env["owner"],
    )
    assert default.status_code == 200, default.text
    assert all(row["user_id"] != env["coach_id"] for row in default.json())

    with_balance = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coaches",
        headers=env["owner"],
        params={"with_balance": True},
    )
    assert with_balance.status_code == 200, with_balance.text
    row = next(row for row in with_balance.json() if row["user_id"] == env["coach_id"])
    assert row["is_active"] is False
    assert row["has_balance"] is True


def test_qa_tax_update_rejects_explicit_null_percent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/finance/taxes",
        headers=superuser_headers,
        json={
            "name": "QA null percent",
            "calculation": "PERCENT",
            "percent_bp": 1000,
            "is_active": True,
        },
    )
    assert created.status_code == 200, created.text
    tax_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/finance/taxes/{tax_id}",
        headers=superuser_headers,
        json={"calculation": "PERCENT", "percent_bp": None},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "invalid_tax_value"
    current = client.get(
        "/api/v1/finance/taxes",
        headers=superuser_headers,
        params={"include_inactive": True},
    )
    assert current.status_code == 200
    row = next(item for item in current.json() if item["id"] == tax_id)
    assert row["percent_bp"] == 1000


def test_qa_global_report_and_csv_match_gym_report(
    client: TestClient,
    env: dict[str, Any],
    superuser_headers: dict[str, str],
) -> None:
    paid_membership(client, env)
    today = svc.finance_today().isoformat()
    gym_report = report_for(client, env, category="MEMBERSHIP")
    global_response = client.get(
        "/api/v1/finance/reports",
        headers=superuser_headers,
        params={
            "from_date": today,
            "to_date": today,
            "category": "MEMBERSHIP",
        },
    )
    assert global_response.status_code == 200, global_response.text
    global_report = global_response.json()
    gym_row = next(
        row for row in global_report["by_gym"] if row["gym_id"] == env["gym_id"]
    )
    assert gym_row["activity"] == gym_report["activity"]
    assert gym_row["as_of"] == gym_report["as_of"]
    assert global_report["activity"]["total_payments_irr"] >= 1_000_000

    csv_response = client.get(
        "/api/v1/finance/reports/export",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "from_date": today,
            "to_date": today,
            "category": "MEMBERSHIP",
        },
    )
    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "total_payments_irr" in csv_response.text
    assert "1000000" in csv_response.text


def test_qa_legacy_archived_override_does_not_apply_today(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    actor = db_session.exec(select(User).where(User.email == env["owner_email"])).one()
    today = svc.finance_today()
    legacy = FinancePlatformContract(
        name="Legacy archived override",
        scope="GYM",
        gym_id=uuid.UUID(env["gym_id"]),
        version=99,
        status="ARCHIVED",
        effective_from=today - timedelta(days=2),
        effective_to=None,
        archived_at=None,
        created_by_id=actor.id,
    )
    db_session.add(legacy)
    db_session.flush()
    for rate in platform_rates(3000, 3000, 3000):
        db_session.add(FinancePlatformRate(contract_id=legacy.id, **rate))
    db_session.commit()

    response = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={"gym_id": env["gym_id"], "category": "MEMBERSHIP"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "PLATFORM_DEFAULT"
    assert response.json()["platform_bp"] == 1000

    sale = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales",
        headers=env["owner"],
        json={
            "category": "MEMBERSHIP",
            "description": "Legacy override must not apply",
            "base_amount_irr": 1_000_000,
            "tax_ids": [],
            "coach_user_id": None,
            "sold_on": today.isoformat(),
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["platform_bp"] == 1000


def test_qa_legacy_archived_override_with_explicit_end_is_historical(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    actor = db_session.exec(select(User).where(User.email == env["owner_email"])).one()
    today = svc.finance_today()
    legacy = FinancePlatformContract(
        name="Legacy archived override with end",
        scope="GYM",
        gym_id=uuid.UUID(env["gym_id"]),
        version=99,
        status="ARCHIVED",
        effective_from=today - timedelta(days=3),
        effective_to=today - timedelta(days=1),
        archived_at=None,
        created_by_id=actor.id,
    )
    db_session.add(legacy)
    db_session.flush()
    for rate in platform_rates(3000, 3000, 3000):
        db_session.add(FinancePlatformRate(contract_id=legacy.id, **rate))
    db_session.commit()

    historical = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": (today - timedelta(days=2)).isoformat(),
        },
    )
    assert historical.status_code == 200, historical.text
    assert historical.json()["source"] == "GYM_OVERRIDE"
    assert historical.json()["platform_bp"] == 3000

    current = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={"gym_id": env["gym_id"], "category": "MEMBERSHIP"},
    )
    assert current.status_code == 200, current.text
    assert current.json()["source"] == "PLATFORM_DEFAULT"
    assert current.json()["platform_bp"] == 1000


def test_qa_legacy_archived_coach_contract_does_not_authorize_new_sale(
    client: TestClient, env: dict[str, Any], db_session: Session
) -> None:
    actor = db_session.exec(select(User).where(User.email == env["owner_email"])).one()
    policy = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={"gym_id": env["gym_id"], "category": "TRAINING"},
    )
    assert policy.status_code == 200, policy.text
    legacy = FinanceCoachContract(
        gym_id=uuid.UUID(env["gym_id"]),
        coach_user_id=uuid.UUID(env["coach_id"]),
        category="TRAINING",
        version=99,
        status="ARCHIVED",
        effective_from=svc.finance_today() - timedelta(days=2),
        effective_to=None,
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
        platform_contract_id=uuid.UUID(policy.json()["contract_id"]),
        platform_source=policy.json()["source"],
        archived_at=None,
        created_by_id=actor.id,
    )
    db_session.add(legacy)
    db_session.commit()

    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales",
        headers=env["owner"],
        json={
            "category": "TRAINING",
            "description": "Legacy coach contract must not apply",
            "base_amount_irr": 1_000_000,
            "tax_ids": [],
            "coach_user_id": env["coach_id"],
            "sold_on": svc.finance_today().isoformat(),
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "coach_contract_missing"


def test_qa_concurrent_purchase_retry_is_atomic(
    client: TestClient, env: dict[str, Any]
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    athlete_id, _athlete_headers = make_athlete(client, env)
    barrier = Barrier(2)

    def worker(_index: int) -> dict[str, Any]:
        with Session(test_engine) as db:
            db.connection().exec_driver_sql("SET statement_timeout = '15000'")
            actor = db.get(User, uuid.UUID(athlete_id))
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                result = svc.purchase_training_plan(
                    db,
                    actor=actor,
                    gym_id=uuid.UUID(env["gym_id"]),
                    athlete_user_id=uuid.UUID(athlete_id),
                    coach_user_id=uuid.UUID(env["coach_id"]),
                    plan_id=uuid.UUID(plan["id"]),
                    note="same purchase",
                    idempotency_key="same-purchase-retry",
                    outcome="SUCCESS",
                )
                return {
                    "sale": result["sale"]["id"],
                    "payment": result["payment"]["id"],
                    "request": result["request"]["id"],
                }
            except HTTPException as exc:
                return {"error": exc.detail, "status": exc.status_code}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    assert all("sale" in row for row in results), results
    assert results[0] == results[1]
    with Session(test_engine) as db:
        sales = db.exec(
            select(FinanceSale).where(FinanceSale.gym_id == uuid.UUID(env["gym_id"]))
        ).all()
        payments = db.exec(
            select(FinancePayment).where(
                FinancePayment.gym_id == uuid.UUID(env["gym_id"])
            )
        ).all()
        requests = db.exec(
            select(FinanceProgramRequest).where(
                FinanceProgramRequest.gym_id == uuid.UUID(env["gym_id"])
            )
        ).all()
    assert len(sales) == len(payments) == len(requests) == 1


def test_qa_http_concurrent_purchase_retry_is_idempotent(
    client: TestClient, env: dict[str, Any]
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    _athlete_id, athlete_headers = make_athlete(client, env)
    key = "http-same-purchase-retry"
    payload = {
        "plan_id": plan["id"],
        "quote_token": client.get(
            f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-offer",
            headers=athlete_headers,
        ).json()["quote_token"],
        "note": "same http purchase",
        "idempotency_key": key,
        "outcome": "SUCCESS",
    }
    barrier = Barrier(2)

    def worker(_index: int) -> dict[str, Any]:
        barrier.wait(timeout=10)
        with TestClient(app) as http:
            response = http.post(
                f"/api/v1/finance/gyms/{env['gym_id']}/athlete/training-purchases",
                headers=athlete_headers,
                json=payload,
            )
            assert response.status_code == 200, response.text
            return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    assert results[0]["sale"]["id"] == results[1]["sale"]["id"]
    assert results[0]["payment"]["id"] == results[1]["payment"]["id"]
    assert results[0]["request"]["id"] == results[1]["request"]["id"]
    with Session(test_engine) as db:
        assert (
            len(
                db.exec(
                    select(FinanceSale).where(
                        FinanceSale.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 1
        )
        assert (
            len(
                db.exec(
                    select(FinancePayment).where(
                        FinancePayment.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 1
        )
        assert (
            len(
                db.exec(
                    select(FinanceProgramRequest).where(
                        FinanceProgramRequest.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 1
        )


def test_qa_purchase_failure_rolls_back_and_retry_recovers(
    client: TestClient, env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=4000,
        coach_bp=5000,
    )
    plan = create_plan(
        client,
        env["owner"],
        env["gym_id"],
        coach_user_id=env["coach_id"],
    )
    athlete_id, _athlete_headers = make_athlete(client, env)
    original = svc._create_program_request_after_payment

    def fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("injected request failure")

    with Session(test_engine) as db:
        actor = db.get(User, uuid.UUID(athlete_id))
        assert actor is not None
        monkeypatch.setattr(svc, "_create_program_request_after_payment", fail)
        with pytest.raises(RuntimeError, match="injected request failure"):
            svc.purchase_training_plan(
                db,
                actor=actor,
                gym_id=uuid.UUID(env["gym_id"]),
                athlete_user_id=uuid.UUID(athlete_id),
                coach_user_id=uuid.UUID(env["coach_id"]),
                plan_id=uuid.UUID(plan["id"]),
                note="fails after payment",
                idempotency_key="failing-purchase",
                outcome="SUCCESS",
            )
    with Session(test_engine) as db:
        assert (
            len(
                db.exec(
                    select(FinanceSale).where(
                        FinanceSale.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 0
        )
        assert (
            len(
                db.exec(
                    select(FinancePayment).where(
                        FinancePayment.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 0
        )

    monkeypatch.setattr(svc, "_create_program_request_after_payment", original)
    with Session(test_engine) as db:
        actor = db.get(User, uuid.UUID(athlete_id))
        assert actor is not None
        result = svc.purchase_training_plan(
            db,
            actor=actor,
            gym_id=uuid.UUID(env["gym_id"]),
            athlete_user_id=uuid.UUID(athlete_id),
            coach_user_id=uuid.UUID(env["coach_id"]),
            plan_id=uuid.UUID(plan["id"]),
            note="retry succeeds",
            idempotency_key="failing-purchase",
            outcome="SUCCESS",
        )
    assert result["request"] is not None
    with Session(test_engine) as db:
        assert (
            len(
                db.exec(
                    select(FinanceSale).where(
                        FinanceSale.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 1
        )
        assert (
            len(
                db.exec(
                    select(FinanceProgramRequest).where(
                        FinanceProgramRequest.gym_id == uuid.UUID(env["gym_id"])
                    )
                ).all()
            )
            == 1
        )
