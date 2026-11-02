from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import (
    FinanceAccount,
    FinanceCoachDiscrepancy,
    FinanceCoachEarningAdjustment,
    FinanceCoachSettlement,
    FinanceJournal,
    FinanceJournalLine,
)
from tests.api.routes.test_finance_coach_agreements import make_coach
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def paid_and_vested(
    client: TestClient,
    owner: dict[str, str],
    customer: str,
    coach_id: str,
    *,
    amount: int = 1_000_000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    invoice = coached_invoice(client, owner, customer, coach_id, amount=amount)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=amount, allocations=[(invoice["id"], amount)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    earning = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    ).json()["data"][0]
    vested = client.post(
        f"/api/v1/finance/coach-earnings/{earning['id']}/vest",
        headers=owner,
        json={"reason": "delivered"},
    )
    assert vested.status_code == 200, vested.text
    return invoice, vested.json()


def refund(
    client: TestClient, owner: dict[str, str], customer: str, invoice_id: str, amount: int
) -> dict[str, Any]:
    requested = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice_id,
            "amount_irr": amount,
            "reason": "customer cancellation",
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
        json={"posting_date": "2026-11-07"},
    )
    assert recorded.status_code == 200, recorded.text
    return recorded.json()


def test_refund_reverses_unsettled_coach_share_and_posts_balanced_journal(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund Coach Gym")
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
    invoice, earning = paid_and_vested(client, owner, customer, coach_id)
    refund(client, owner, customer, invoice["id"], 200_000)

    adjustment = db_session.exec(
        select(FinanceCoachEarningAdjustment).where(
            FinanceCoachEarningAdjustment.earning_id == uuid.UUID(earning["id"])
        )
    ).one()
    assert adjustment.amount_irr == 60_000
    assert adjustment.applied_irr == 60_000
    assert adjustment.discrepancy_irr == 0

    journal = db_session.get(FinanceJournal, adjustment.journal_id)
    assert journal is not None
    lines = db_session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == journal.id
        )
    ).all()
    accounts = {
        line.account_id: (line.debit_irr, line.credit_irr) for line in lines
    }
    payable = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "2100",
        )
    ).one()
    expense = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "5100",
        )
    ).one()
    assert accounts[payable.id] == (60_000, 0)
    assert accounts[expense.id] == (0, 60_000)

    row = client.get(
        f"/api/v1/finance/coach-earnings/{earning['id']}", headers=owner
    ).json()
    assert row["adjusted_irr"] == 60_000
    assert row["eligible_irr"] == 240_000
    discrepancies = client.get(
        "/api/v1/finance/coach-discrepancies", headers=owner
    ).json()
    assert discrepancies["count"] == 0
    journal_list = client.get("/api/v1/finance/journal?limit=50", headers=owner)
    assert journal_list.status_code == 200, journal_list.text
    assert any(
        entry["event_type"] == "COACH_ADJUSTMENT"
        for entry in journal_list.json()["data"]
    )


def test_overpaid_refund_creates_a_manual_discrepancy_not_a_clawback(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Refund Discrepancy Gym"
    )
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
    invoice, earning = paid_and_vested(client, owner, customer, coach_id)
    settled = client.post(
        "/api/v1/finance/coach-settlements",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "coach_user_id": coach_id,
            "amount_irr": 300_000,
            "method": "TRANSFER",
            "paid_on": "2026-11-06",
        },
    )
    assert settled.status_code == 200, settled.text
    confirmed = client.post(
        f"/api/v1/finance/coach-settlements/{settled.json()['id']}/confirm",
        headers=owner,
    )
    assert confirmed.status_code == 200

    refund(client, owner, customer, invoice["id"], 200_000)

    discrepancy = db_session.exec(
        select(FinanceCoachDiscrepancy).where(
            FinanceCoachDiscrepancy.earning_id == uuid.UUID(earning["id"])
        )
    ).one()
    assert discrepancy.amount_irr == 60_000
    assert discrepancy.status == "OPEN"

    # The recorded payout is unchanged: no automatic negative transfer.
    settlement = db_session.get(
        FinanceCoachSettlement, uuid.UUID(settled.json()["id"])
    )
    assert settlement is not None
    assert settlement.amount_irr == 300_000
    assert settlement.status == "CONFIRMED"

    listed = client.get(
        "/api/v1/finance/coach-discrepancies?status=OPEN", headers=owner
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] == 1

    resolved = client.post(
        f"/api/v1/finance/coach-discrepancies/{discrepancy.id}/resolve",
        headers=owner,
        json={"resolution_note": "coach agreed to offset next cycle"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolution_note"] == "coach agreed to offset next cycle"
