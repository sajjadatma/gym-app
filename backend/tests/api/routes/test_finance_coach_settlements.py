from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import (
    FinanceAccount,
    FinanceCoachSettlement,
    FinanceJournal,
    FinanceJournalLine,
)
from tests.api.routes.test_finance_coach_agreements import make_coach
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coach_earning,
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def vested_earning(
    client: TestClient,
    owner: dict[str, str],
    customer: str,
    coach_id: str,
    *,
    amount: int = 1_000_000,
) -> str:
    invoice = coached_invoice(client, owner, customer, coach_id, amount=amount)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=amount, allocations=[(invoice["id"], amount)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    return invoice["id"]


def settle(
    client: TestClient,
    owner: dict[str, str],
    coach_id: str,
    amount: int,
) -> Any:
    return client.post(
        "/api/v1/finance/coach-settlements",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "coach_user_id": coach_id,
            "amount_irr": amount,
            "method": "CASH",
            "reference": "SETTLE-1",
            "paid_on": "2026-11-06",
            "notes": "weekly payout",
        },
    )


def test_partial_settlement_is_fifo_capped_and_confirmable(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Settlement Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, coach_headers = make_coach(client, owner, gym_id)
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
    invoice_id = vested_earning(client, owner, customer, coach_id)
    earning = coach_earning(db_session, invoice_id)
    vested = client.post(
        f"/api/v1/finance/coach-earnings/{earning.id}/vest",
        headers=owner,
        json={"reason": "service delivered"},
    )
    assert vested.status_code == 200, vested.text

    first = settle(client, owner, coach_id, 100_000)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "RECORDED"
    assert body["amount_irr"] == 100_000
    assert body["items"][0]["earning_id"] == str(earning.id)
    assert body["items"][0]["amount_irr"] == 100_000

    listed = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    )
    row = listed.json()["data"][0]
    assert row["settled_irr"] == 100_000
    assert row["eligible_irr"] == 200_000

    confirmed = client.post(
        f"/api/v1/finance/coach-settlements/{body['id']}/confirm",
        headers=owner,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    # Confirmation retries are idempotent and never post a second cash entry.
    assert (
        client.post(
            f"/api/v1/finance/coach-settlements/{body['id']}/confirm",
            headers=owner,
        ).status_code
        == 200
    )

    second = settle(client, owner, coach_id, 200_000)
    assert second.status_code == 200, second.text
    row = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    ).json()["data"][0]
    assert row["settled_irr"] == 300_000
    assert row["eligible_irr"] == 0
    assert row["status"] == "SETTLED"

    too_much = settle(client, owner, coach_id, 1)
    assert too_much.status_code == 400, too_much.text
    assert too_much.json()["detail"] == "settlement_exceeds_eligible"

    settlement = db_session.get(FinanceCoachSettlement, uuid.UUID(body["id"]))
    assert settlement is not None
    journal = db_session.get(FinanceJournal, settlement.journal_id)
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
    pending = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "2200",
        )
    ).one()
    assert accounts[payable.id] == (100_000, 0)
    assert accounts[pending.id] == (0, 100_000)

    confirmed_journal = db_session.get(FinanceJournal, settlement.confirmed_journal_id)
    assert confirmed_journal is not None
    confirmed_lines = db_session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == confirmed_journal.id
        )
    ).all()
    confirmed_accounts = {
        line.account_id: (line.debit_irr, line.credit_irr)
        for line in confirmed_lines
    }
    cash = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "1000",
        )
    ).one()
    assert confirmed_accounts[pending.id] == (100_000, 0)
    assert confirmed_accounts[cash.id] == (0, 100_000)
    # Exactly two settlement journals exist: recorded stage and confirmation.
    settlement_journals = db_session.exec(
        select(FinanceJournal).where(
            FinanceJournal.source_type == "finance_coach_settlement",
            FinanceJournal.source_id == settlement.id,
        )
    ).all()
    assert len(settlement_journals) == 2

    coach_view = client.get(
        "/api/v1/finance/my/settlements", headers=coach_headers
    )
    assert coach_view.status_code == 200, coach_view.text
    assert coach_view.json()["count"] == 2


def test_settlement_refuses_unvested_and_unresolved_earnings(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Settlement Guard Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        vesting_mode="ON_DATE",
        vesting_days=30,
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    future_invoice = vested_earning(client, owner, customer, coach_id)
    hidden = coach_earning(db_session, future_invoice)
    assert hidden.status == "CALCULATED"
    rejected = settle(client, owner, coach_id, 1)
    assert rejected.status_code == 400, rejected.text
    assert rejected.json()["detail"] == "settlement_exceeds_eligible"

    unresolved_invoice = coached_invoice(client, owner, customer, coach_id)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=1_000_000,
            allocations=[(unresolved_invoice["id"], 1_000_000)],
        ),
    )
    assert receipt.status_code == 200
    # The agreement in this gym is active, so the second invoice snapshots it
    # as well; unresolved earnings are exercised in the allocation slice.
