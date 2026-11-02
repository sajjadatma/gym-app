from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import (
    FinanceAccount,
    FinanceCoachEarning,
    FinanceJournal,
    FinanceJournalLine,
)
from tests.api.routes.test_finance_coach_agreements import (
    agreement_payload,
    make_coach,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import (
    create_draft,
    invoice_payload,
    issue,
    make_customer,
)
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def active_agreement(
    client: TestClient, owner: dict[str, str], coach_id: str, **overrides: Any
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(coach_id, **overrides),
    )
    assert created.status_code == 200, created.text
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{created.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


def coached_invoice(
    client: TestClient,
    owner: dict[str, str],
    customer: str,
    coach_id: str | None,
    *,
    amount: int = 1_000_000,
    discount: int = 0,
    funding: str = "GYM",
    second_line: bool = False,
) -> dict[str, Any]:
    lines: list[dict[str, Any]] = [
        {
            "kind": "PROGRAM",
            "description": "coached program",
            "quantity": 1,
            "unit_price_irr": amount,
        }
    ]
    if coach_id is not None:
        lines[0]["coach_user_id"] = coach_id
    if second_line:
        lines.append(
            {
                "kind": "PRODUCT",
                "description": "gym product",
                "quantity": 1,
                "unit_price_irr": 200_000,
            }
        )
    payload = invoice_payload(customer, lines=lines, discount=discount)
    payload["discount_funding"] = funding
    draft = create_draft(client, owner, payload)
    assert draft.status_code == 200, draft.text
    issued = issue(client, owner, draft.json()["id"])
    assert issued.status_code == 200, issued.text
    return issued.json()


def coach_earning(
    db_session: Session, invoice_id: str
) -> FinanceCoachEarning:
    return db_session.exec(
        select(FinanceCoachEarning).where(
            FinanceCoachEarning.invoice_id == uuid.UUID(invoice_id)
        )
    ).one()


def test_partial_receipt_allocates_only_confirmed_collections(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Allocation Engine Gym")
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
    invoice = coached_invoice(
        client, owner, customer, coach_id, second_line=True
    )

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=600_000, allocations=[(invoice["id"], 600_000)]),
    )
    assert receipt.status_code == 200, receipt.text

    earning = coach_earning(db_session, invoice["id"])
    assert earning.base_irr == 500_000
    assert earning.discount_irr == 0
    assert earning.coach_share_irr == 150_000
    assert earning.platform_share_irr == 0
    assert earning.gym_share_irr == 350_000
    assert earning.status == "CALCULATED"
    assert earning.agreement_version == 1

    journal = db_session.get(FinanceJournal, earning.journal_id)
    assert journal is not None
    lines = db_session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == journal.id
        )
    ).all()
    accounts = {
        line.account_id: (line.debit_irr, line.credit_irr) for line in lines
    }
    expense = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "5100",
        )
    ).one()
    payable = db_session.exec(
        select(FinanceAccount).where(
            FinanceAccount.gym_id == gym["id"],
            FinanceAccount.code == "2100",
        )
    ).one()
    assert accounts[expense.id] == (150_000, 0)
    assert accounts[payable.id] == (0, 150_000)
    assert sum(debit for debit, _ in accounts.values()) == sum(
        credit for _, credit in accounts.values()
    )


@pytest.mark.parametrize(
    ("funding", "coach", "platform", "gym"),
    [
        ("GYM", 300_000, 100_000, 500_000),
        ("COACH", 200_000, 100_000, 600_000),
        ("ASCORA", 300_000, 0, 600_000),
        ("MIXED", 270_000, 90_000, 540_000),
    ],
)
def test_discount_funding_is_deterministic_and_mixed_splits_pro_rata(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
    funding: str,
    coach: int,
    platform: int,
    gym: int,
) -> None:
    owner_gym, owner = make_owner(
        client, superuser_headers, name=f"Funding {funding} Gym"
    )
    gym_id = str(owner_gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "ASCORA", "basis": "PERCENT", "percent_bp": 1000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 6000},
        ],
    )
    invoice = coached_invoice(
        client,
        owner,
        customer,
        coach_id,
        discount=100_000,
        funding=funding,
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=900_000,
            allocations=[(invoice["id"], 900_000)],
        ),
    )
    assert receipt.status_code == 200, receipt.text
    earning = coach_earning(db_session, invoice["id"])
    assert earning.base_irr == 1_000_000
    assert earning.discount_irr == 100_000
    assert earning.coach_share_irr == coach
    assert earning.platform_share_irr == platform
    assert earning.gym_share_irr == gym
    assert (
        earning.coach_share_irr
        + earning.platform_share_irr
        + earning.gym_share_irr
        == 900_000
    )


def test_missing_agreement_keeps_intake_working_but_leaves_share_unresolved(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Unresolved Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    invoice = coached_invoice(client, owner, customer, coach_id)

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    earning = coach_earning(db_session, invoice["id"])
    assert earning.status == "UNRESOLVED"
    assert earning.unresolved_reason == "coach_agreement_missing"
    assert earning.coach_share_irr == 0
    assert earning.journal_id is None


def test_applied_customer_advance_also_creates_coach_earnings(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Advance Allocation Gym")
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
    first = coached_invoice(client, owner, customer, None, amount=100_000)
    overpaid = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=200_000, allocations=[(first["id"], 100_000)]
        ),
    )
    assert overpaid.status_code == 200, overpaid.text

    second = coached_invoice(client, owner, customer, coach_id, amount=500_000)
    applied = client.post(
        "/api/v1/finance/credits/apply",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "invoice_id": second["id"],
            "amount_irr": 100_000,
            "received_on": "2026-11-06",
        },
    )
    assert applied.status_code == 200, applied.text
    earning = coach_earning(db_session, second["id"])
    assert earning.base_irr == 100_000
    assert earning.coach_share_irr == 30_000
    assert earning.status == "CALCULATED"


def test_fixed_compensation_is_not_reapplied_on_partial_receipts(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fixed Cap Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    created = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            mode="WATERFALL",
            terms=[
                {"recipient": "COACH", "basis": "FIXED", "fixed_irr": 250_000},
                {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 10000},
            ],
        ),
    )
    assert created.status_code == 200, created.text
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{created.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    for _ in range(2):
        receipt = record_receipt(
            client,
            owner,
            receipt_payload(
                customer, amount=500_000, allocations=[(invoice["id"], 500_000)]
            ),
        )
        assert receipt.status_code == 200, receipt.text
    rows = db_session.exec(
        select(FinanceCoachEarning).where(
            FinanceCoachEarning.invoice_id == uuid.UUID(invoice["id"])
        )
    ).all()
    assert sum(row.coach_share_irr for row in rows) == 250_000
