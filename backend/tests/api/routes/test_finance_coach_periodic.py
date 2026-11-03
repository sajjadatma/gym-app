from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import (
    FinanceAccount,
    FinanceExpense,
    FinanceJournal,
    FinanceJournalLine,
)
from tests.api.routes.test_finance_coach_agreements import (
    agreement_payload,
    make_coach,
)
from tests.api.routes.test_finance_foundation import make_owner

pytestmark = pytest.mark.usefixtures("client")


def test_periodic_fixed_coach_payable_without_a_sale(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Periodic Coach Gym")
    gym_id = str(gym["id"])
    coach_id, _ = make_coach(client, owner, gym_id)
    agreement = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            periodic_fixed_irr=200_000,
            periodic_interval="MONTHLY",
        ),
    )
    assert agreement.status_code == 200, agreement.text
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200

    key = uuid.uuid4().hex
    accrued = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/accrue-period",
        headers={**owner, "Idempotency-Key": key},
        json={"period": "2026-11"},
    )
    assert accrued.status_code == 200, accrued.text
    expense = accrued.json()
    assert expense["status"] == "UNPAID"
    assert expense["amount_irr"] == 200_000
    assert expense["category"] == "حقوق ثابت مربی"
    assert expense["counterparty"] is not None

    again = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/accrue-period",
        headers={**owner, "Idempotency-Key": key},
        json={"period": "2026-11"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == expense["id"]
    duplicate = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/accrue-period",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"period": "2026-11"},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"] == "expense_recurrence_exists"

    other_period = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/accrue-period",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"period": "2026-12"},
    )
    assert other_period.status_code == 200

    outside = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/accrue-period",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"period": "2026-10"},
    )
    assert outside.status_code == 400, outside.text
    assert outside.json()["detail"] == "coach_period_outside_agreement"

    db_expense = db_session.get(FinanceExpense, uuid.UUID(expense["id"]))
    assert db_expense is not None
    journal = db_session.get(FinanceJournal, db_expense.journal_id)
    assert journal is not None
    lines = db_session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == journal.id
        )
    ).all()
    accounts = {
        line.account_id: (line.debit_irr, line.credit_irr) for line in lines
    }
    expense_account = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "5000",
        )
    ).one()
    payable = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "2000",
        )
    ).one()
    assert accounts[expense_account.id] == (200_000, 0)
    assert accounts[payable.id] == (0, 200_000)
