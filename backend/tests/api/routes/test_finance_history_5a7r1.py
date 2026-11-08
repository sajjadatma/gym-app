from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.finance_models import FinanceMembership
from app.services import finance as finance_service
from tests.api.routes.test_finance_coach_agreements import make_coach
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_memberships import create_membership
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def summary_as_of(
    client: TestClient,
    owner: dict[str, str],
    *,
    as_of: str,
) -> dict[str, Any]:
    response = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": as_of},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_gym_summary_renewals_are_reconstructed_at_the_requested_date(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Historical Renewals Gym")
    gym_id = str(gym["id"])
    athlete = make_customer(client, owner, gym_id, prefix="renewal")
    created = create_membership(
        client,
        owner,
        athlete,
        start="2026-11-01",
        end="2026-12-31",
    )
    assert created.status_code == 200, created.text
    membership_id = created.json()["id"]

    assert summary_as_of(client, owner, as_of="2026-10-31")["renewals_due"] == 0
    assert summary_as_of(client, owner, as_of="2026-11-15")["renewals_due"] == 0
    assert summary_as_of(client, owner, as_of="2026-12-05")["renewals_due"] == 1

    frozen = client.post(
        f"/api/v1/finance/memberships/{membership_id}/freeze",
        headers=owner,
        json={"frozen_on": "2026-12-10"},
    )
    assert frozen.status_code == 200, frozen.text
    resumed = client.post(
        f"/api/v1/finance/memberships/{membership_id}/resume",
        headers=owner,
        json={"resume_on": "2027-01-05"},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["end_date"] == "2027-01-26"

    # The current end date is now outside the 30-day window, but as of
    # 2026-12-05 the membership still ended on 2026-12-31.
    assert summary_as_of(client, owner, as_of="2026-12-05")["renewals_due"] == 1
    assert summary_as_of(client, owner, as_of="2027-01-10")["renewals_due"] == 1

    cancelled = client.post(
        f"/api/v1/finance/memberships/{membership_id}/cancel",
        headers=owner,
        json={"cancelled_on": "2027-01-15", "reason": "historical boundary"},
    )
    assert cancelled.status_code == 200, cancelled.text

    assert summary_as_of(client, owner, as_of="2026-12-05")["renewals_due"] == 1
    assert summary_as_of(client, owner, as_of="2027-01-16")["renewals_due"] == 0


def _coached_earning(
    client: TestClient,
    owner: dict[str, str],
    *,
    customer: str,
    coach_id: str,
    received_on: str,
    amount: int = 1_000_000,
) -> dict[str, Any]:
    invoice = coached_invoice(
        client,
        owner,
        customer,
        coach_id,
        amount=amount,
    )
    payload = receipt_payload(
        customer,
        amount=amount,
        allocations=[(invoice["id"], amount)],
    )
    payload["received_on"] = received_on
    receipt = record_receipt(client, owner, payload)
    assert receipt.status_code == 200, receipt.text
    earnings = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    )
    assert earnings.status_code == 200, earnings.text
    return earnings.json()["data"][0]


def test_gym_summary_coach_payable_uses_receipt_and_settlement_dates(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Historical Coach Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        vesting_mode="MANUAL",
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    earning = _coached_earning(
        client,
        owner,
        customer=customer,
        coach_id=coach_id,
        received_on="2026-11-05",
    )
    assert earning["coach_share_irr"] == 300_000

    assert summary_as_of(client, owner, as_of="2026-11-04")["coach_payable_irr"] == 0
    assert (
        summary_as_of(client, owner, as_of="2026-11-05")["coach_payable_irr"]
        == 300_000
    )

    vested = client.post(
        f"/api/v1/finance/coach-earnings/{earning['id']}/vest",
        headers=owner,
        json={"reason": "delivered"},
    )
    assert vested.status_code == 200, vested.text
    settlement = client.post(
        "/api/v1/finance/coach-settlements",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "coach_user_id": coach_id,
            "amount_irr": 100_000,
            "method": "CASH",
            "paid_on": "2026-11-06",
        },
    )
    assert settlement.status_code == 200, settlement.text

    assert (
        summary_as_of(client, owner, as_of="2026-11-05")["coach_payable_irr"]
        == 300_000
    )
    assert (
        summary_as_of(client, owner, as_of="2026-11-06")["coach_payable_irr"]
        == 200_000
    )


def test_gym_summary_coach_payable_excludes_later_refund_adjustment(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Historical Refund Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    payload = receipt_payload(
        customer,
        amount=1_000_000,
        allocations=[(invoice["id"], 1_000_000)],
    )
    payload["received_on"] = "2026-11-05"
    receipt = record_receipt(client, owner, payload)
    assert receipt.status_code == 200, receipt.text

    requested = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 100_000,
            "reason": "historical refund boundary",
        },
    )
    assert requested.status_code == 200, requested.text
    approved = client.post(
        f"/api/v1/finance/refunds/{requested.json()['id']}/approve",
        headers=owner,
    )
    assert approved.status_code == 200, approved.text
    recorded = client.post(
        f"/api/v1/finance/refunds/{requested.json()['id']}/record",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"posting_date": "2026-11-10"},
    )
    assert recorded.status_code == 200, recorded.text

    assert (
        summary_as_of(client, owner, as_of="2026-11-09")["coach_payable_irr"]
        == 300_000
    )
    assert (
        summary_as_of(client, owner, as_of="2026-11-10")["coach_payable_irr"]
        == 270_000
    )


def test_gym_summary_coach_payable_restores_cancelled_settlement_after_cancel_date(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Historical Cancel Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        vesting_mode="MANUAL",
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    earning = _coached_earning(
        client,
        owner,
        customer=customer,
        coach_id=coach_id,
        received_on="2026-11-05",
    )
    vested = client.post(
        f"/api/v1/finance/coach-earnings/{earning['id']}/vest",
        headers=owner,
        json={"reason": "delivered"},
    )
    assert vested.status_code == 200, vested.text
    settlement = client.post(
        "/api/v1/finance/coach-settlements",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "coach_user_id": coach_id,
            "amount_irr": 100_000,
            "method": "CASH",
            "paid_on": "2026-11-06",
        },
    )
    assert settlement.status_code == 200, settlement.text
    cancel_date = client.get(
        "/api/v1/finance/settings", headers=owner
    )
    assert cancel_date.status_code == 200, cancel_date.text
    today = finance_service.gym_today(db_session, uuid.UUID(gym_id)).isoformat()
    assert (
        summary_as_of(client, owner, as_of="2026-11-07")["coach_payable_irr"]
        == 200_000
    )

    cancelled = client.post(
        f"/api/v1/finance/coach-settlements/{settlement.json()['id']}/cancel",
        headers=owner,
        json={"reason": "historical reversal"},
    )
    assert cancelled.status_code == 200, cancelled.text

    assert (
        summary_as_of(client, owner, as_of="2026-11-07")["coach_payable_irr"]
        == 200_000
    )
    assert (
        summary_as_of(client, owner, as_of=today)["coach_payable_irr"] == 300_000
    )


def test_gym_summary_fails_closed_on_incomplete_membership_freeze_history(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Incomplete Lifecycle Gym"
    )
    gym_id = str(gym["id"])
    athlete = make_customer(client, owner, gym_id, prefix="incomplete")
    created = create_membership(
        client,
        owner,
        athlete,
        start="2026-11-01",
        end="2026-12-31",
    )
    assert created.status_code == 200, created.text
    membership = db_session.get(
        FinanceMembership, uuid.UUID(created.json()["id"])
    )
    assert membership is not None
    membership.frozen_days = 5
    db_session.add(membership)
    db_session.commit()

    response = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-05"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "membership_history_incomplete"
