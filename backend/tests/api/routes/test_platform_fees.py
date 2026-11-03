from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.platform_models import (
    PlatformJournal,
    PlatformJournalLine,
    PlatformReceivable,
)
from tests.api.routes.test_finance_coach_agreements import agreement_payload, make_coach
from tests.api.routes.test_finance_coach_allocations import (
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)
from tests.api.routes.test_platform_agreements import (
    create_agreement as create_platform_agreement,
)


def activate_platform_agreement(
    client: TestClient,
    headers: dict[str, str],
    agreement_id: str,
) -> None:
    activated = client.post(
        f"/api/v1/platform/agreements/{agreement_id}/activate",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert activated.status_code == 200, activated.text


def commission_agreement(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    *,
    percent_bp: int = 1000,
    kind: str = "ANY",
    source: str = "ANY",
) -> dict[str, object]:
    created = create_platform_agreement(
        client,
        headers,
        gym_id=gym_id,
        mode="COMMISSION",
        terms=[
            {
                "kind": kind,
                "acquisition_source": source,
                "basis": "PERCENT",
                "percent_bp": percent_bp,
            }
        ],
        effective_from="2026-11-01",
    )
    assert created.status_code == 200, created.text
    activate_platform_agreement(client, headers, created.json()["id"])
    return created.json()


def fixed_agreement(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    *,
    fixed_irr: int,
) -> dict[str, object]:
    created = create_platform_agreement(
        client,
        headers,
        gym_id=gym_id,
        mode="COMMISSION",
        terms=[
            {
                "kind": "ANY",
                "acquisition_source": "ANY",
                "basis": "FIXED",
                "fixed_irr": fixed_irr,
            }
        ],
        effective_from="2026-11-01",
    )
    assert created.status_code == 200, created.text
    activate_platform_agreement(client, headers, created.json()["id"])
    return created.json()


def test_commission_only_accrues_on_confirmed_collection_from_issue_snapshot(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fee Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    commission_agreement(client, superuser_headers, str(gym["id"]), percent_bp=1000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    line = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()["lines"][0]
    assert line["platform_allocation_status"] == "SNAPSHOTTED"
    assert line["platform_fee_irr"] == 100_000

    draft = client.post(
        "/api/v1/finance/invoices",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "lines": [
                {
                    "kind": "PROGRAM",
                    "description": "Draft",
                    "quantity": 1,
                    "unit_price_irr": 100_000,
                }
            ],
        },
    )
    assert draft.status_code == 200, draft.text
    draft_line = client.get(
        f"/api/v1/finance/invoices/{draft.json()['id']}", headers=owner
    ).json()["lines"][0]
    assert draft_line["platform_allocation_status"] == "NOT_APPLICABLE"

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    receivables = client.get(
        f"/api/v1/platform/receivables?gym_id={gym['id']}",
        headers=superuser_headers,
    ).json()["data"]
    assert sum(row["amount_irr"] for row in receivables) == 40_000


def test_commission_uses_issue_snapshot_after_agreement_replacement(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Snapshot Fee Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    commission_agreement(client, superuser_headers, str(gym["id"]), percent_bp=1000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)

    replacement = create_platform_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="COMMISSION",
        terms=[
            {
                "kind": "ANY",
                "acquisition_source": "ANY",
                "basis": "PERCENT",
                "percent_bp": 2000,
            }
        ],
        effective_from="2026-11-02",
    )
    assert replacement.status_code == 200, replacement.text
    activate_platform_agreement(
        client, superuser_headers, replacement.json()["id"]
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    receivables = client.get(
        f"/api/v1/platform/receivables?gym_id={gym['id']}",
        headers=superuser_headers,
    ).json()["data"]
    assert sum(row["amount_irr"] for row in receivables) == 100_000


def test_fixed_fee_is_proportional_across_installments_and_capped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fixed Fee Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    fixed_agreement(client, superuser_headers, str(gym["id"]), fixed_irr=100_000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    first = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
        ),
    )
    assert first.status_code == 200, first.text
    second = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=600_000, allocations=[(invoice["id"], 600_000)]
        ),
    )
    assert second.status_code == 200, second.text
    receivables = client.get(
        f"/api/v1/platform/receivables?gym_id={gym['id']}",
        headers=superuser_headers,
    ).json()["data"]
    assert sum(row["amount_irr"] for row in receivables) == 100_000


def test_ascora_coach_share_and_platform_commission_are_recognized_exactly_once(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Single Recognition")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    coach_agreement = client.post(
        "/api/v1/finance/coach-agreements",
        headers={**superuser_headers, "X-Gym-ID": gym_id},
        json=agreement_payload(
            coach_id,
            terms=[
                {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 2000},
                {"recipient": "ASCORA", "basis": "PERCENT", "percent_bp": 1000},
                {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
            ],
        ),
    )
    assert coach_agreement.status_code == 200, coach_agreement.text
    activated_coach = client.post(
        f"/api/v1/finance/coach-agreements/{coach_agreement.json()['id']}/activate",
        headers={**superuser_headers, "X-Gym-ID": gym_id},
    )
    assert activated_coach.status_code == 200, activated_coach.text
    commission_agreement(
        client, superuser_headers, gym_id, percent_bp=500
    )
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    line = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()["lines"][0]
    assert line["platform_allocation_status"] == "COACH_ASCORA_TERM"
    assert line["platform_ascora_term_share_irr"] == 100_000

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    receivables = db_session.exec(
        select(PlatformReceivable).where(PlatformReceivable.gym_id == gym["id"])
    ).all()
    assert [row.source_type for row in receivables] == ["COACH_ASCORA_SHARE"]
    assert sum(row.amount_irr for row in receivables) == 100_000
    journal = db_session.exec(select(PlatformJournal)).one()
    lines = db_session.exec(
        select(PlatformJournalLine).where(
            PlatformJournalLine.journal_id == journal.id
        )
    ).all()
    revenue = sum(
        line.credit_irr
        for line in lines
        if line.account_code in ("4100", "4200")
    )
    assert revenue == 100_000


def test_free_and_unmatched_source_do_not_accrue_and_replay_is_idempotent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="No Fee Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    free = create_platform_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="FREE",
        effective_from="2026-11-01",
    )
    assert free.status_code == 200, free.text
    activate_platform_agreement(client, superuser_headers, free.json()["id"])
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    line = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()["lines"][0]
    assert line["platform_allocation_status"] == "NOT_APPLICABLE"
    key = uuid.uuid4().hex
    payload = receipt_payload(
        customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
    )
    first = record_receipt(client, owner, payload, key=key)
    assert first.status_code == 200, first.text
    second = record_receipt(client, owner, payload, key=key)
    assert second.status_code == 200, second.text
    receivables = client.get(
        f"/api/v1/platform/receivables?gym_id={gym['id']}",
        headers=superuser_headers,
    ).json()["data"]
    assert receivables == []


def test_fixed_ascora_coach_share_is_capped_at_issue_snapshot(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fixed ASCORA Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    coach_agreement = client.post(
        "/api/v1/finance/coach-agreements",
        headers={**superuser_headers, "X-Gym-ID": gym_id},
        json=agreement_payload(
            coach_id,
            terms=[
                {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 2000},
                {"recipient": "ASCORA", "basis": "FIXED", "fixed_irr": 100_000},
                {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 8000},
            ],
        ),
    )
    assert coach_agreement.status_code == 200, coach_agreement.text
    assert (
        client.post(
            f"/api/v1/finance/coach-agreements/{coach_agreement.json()['id']}/activate",
            headers={**superuser_headers, "X-Gym-ID": gym_id},
        ).status_code
        == 200
    )
    commission_agreement(client, superuser_headers, gym_id, percent_bp=500)
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    first = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
        ),
    )
    assert first.status_code == 200, first.text
    second = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=600_000, allocations=[(invoice["id"], 600_000)]
        ),
    )
    assert second.status_code == 200, second.text
    rows = client.get(
        f"/api/v1/platform/receivables?gym_id={gym_id}",
        headers=superuser_headers,
    ).json()["data"]
    assert [row["source_type"] for row in rows] == ["COACH_ASCORA_SHARE"]
    assert sum(row["amount_irr"] for row in rows) == 100_000


def test_snapshot_is_audited_and_subscription_or_unmatched_source_adds_no_fee(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    from app.platform_models import PlatformAudit

    gym, owner = make_owner(client, superuser_headers, name="Audit / No Fee Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)

    subscription = create_platform_agreement(
        client,
        superuser_headers,
        gym_id=gym_id,
        mode="SUBSCRIPTION",
        subscription_amount_irr=500_000,
        terms=[],
    )
    assert subscription.status_code == 200, subscription.text
    activate_platform_agreement(
        client, superuser_headers, subscription.json()["id"]
    )
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    line = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()["lines"][0]
    assert line["platform_allocation_status"] == "NOT_APPLICABLE"
    assert (
        db_session.exec(
            select(PlatformAudit).where(
                PlatformAudit.action == "platform.ascora_source.snapshotted"
            )
        ).first()
        is not None
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    assert (
        client.get(
            f"/api/v1/platform/receivables?gym_id={gym_id}",
            headers=superuser_headers,
        ).json()["data"]
        == []
    )


def test_invoice_refund_appends_platform_credit_without_mutating_receivable(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    from app.platform_models import PlatformCredit, PlatformJournalLine
    from tests.api.routes.test_finance_coach_refunds import refund

    gym, owner = make_owner(client, superuser_headers, name="Refund Platform Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    commission_agreement(client, superuser_headers, gym_id, percent_bp=1000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    before = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_id)
        )
    ).all()
    assert sum(row.amount_irr for row in before) == 100_000

    refund(client, owner, customer, invoice["id"], 300_000)
    db_session.expire_all()
    after = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_id)
        )
    ).all()
    assert [(row.id, row.amount_irr) for row in after] == [
        (row.id, row.amount_irr) for row in before
    ]
    credit = db_session.exec(select(PlatformCredit)).one()
    assert credit.amount_irr == 30_000
    assert credit.source_type == "REFUND"
    reversal = db_session.exec(
        select(PlatformJournalLine).where(
            PlatformJournalLine.account_code == "4100",
            PlatformJournalLine.debit_irr == 30_000,
        )
    ).first()
    assert reversal is not None
