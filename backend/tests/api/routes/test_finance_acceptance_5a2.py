from __future__ import annotations

import csv
import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.finance_models import (
    FinanceAccount,
    FinanceJournal,
    FinanceJournalLine,
)
from app.platform_models import PlatformJournal, PlatformJournalLine
from tests.api.routes.test_finance_coach_agreements import (
    make_coach,
)
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coached_invoice,
)
from tests.api.routes.test_finance_coach_refunds import refund
from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_invoices import (
    create_draft,
    invoice_payload,
    issue,
    make_customer,
)
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)
from tests.api.routes.test_platform_agreements import (
    create_agreement as create_platform_agreement,
)
from tests.api.routes.test_platform_fees import commission_agreement
from tests.api.routes.test_platform_invoices import (
    accrue,
    activate,
    issue_platform_invoice,
)
from tests.utils.helpers import (
    auth_headers,
    change_password,
    create_athlete,
    gym_headers,
    unique_email,
)

pytestmark = pytest.mark.usefixtures("client")


def _finance_lines(
    session: Session,
    *,
    gym_id: uuid.UUID,
    event_type: str,
    source_id: uuid.UUID | None = None,
) -> list[tuple[str, int, int]]:
    statement = select(FinanceJournal).where(
        FinanceJournal.gym_id == gym_id,
        FinanceJournal.event_type == event_type,
    )
    if source_id is not None:
        statement = statement.where(FinanceJournal.source_id == source_id)
    journal = session.exec(
        statement.order_by(FinanceJournal.entry_number.desc())
    ).first()
    assert journal is not None, (event_type, source_id)
    rows = session.exec(
        select(FinanceJournalLine, FinanceAccount.code)
        .join(
            FinanceAccount,
            FinanceJournalLine.account_id == FinanceAccount.id,
        )
        .where(FinanceJournalLine.journal_id == journal.id)
    ).all()
    lines = sorted(
        (code, line.debit_irr, line.credit_irr) for line, code in rows
    )
    assert sum(line[1] for line in lines) == sum(line[2] for line in lines)
    return lines


def _platform_lines(
    session: Session,
    *,
    event_type: str,
    source_id: uuid.UUID | None = None,
) -> list[tuple[str, int, int]]:
    statement = select(PlatformJournal).where(
        PlatformJournal.event_type == event_type
    )
    if source_id is not None:
        statement = statement.where(PlatformJournal.source_id == source_id)
    journal = session.exec(
        statement.order_by(PlatformJournal.entry_number.desc())
    ).first()
    assert journal is not None, (event_type, source_id)
    rows = session.exec(
        select(PlatformJournalLine).where(
            PlatformJournalLine.journal_id == journal.id
        )
    ).all()
    lines = sorted(
        (line.account_code, line.debit_irr, line.credit_irr) for line in rows
    )
    assert sum(line[1] for line in lines) == sum(line[2] for line in lines)
    return lines


def _count_finance_journals(session: Session, *, gym_id: uuid.UUID) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(FinanceJournal)
            .where(FinanceJournal.gym_id == gym_id)
        ).one()
    )


def _count_finance_events(
    session: Session,
    *,
    gym_id: uuid.UUID,
    event_type: str,
    source_id: uuid.UUID | None = None,
) -> int:
    statement = select(func.count()).select_from(FinanceJournal).where(
        FinanceJournal.gym_id == gym_id,
        FinanceJournal.event_type == event_type,
    )
    if source_id is not None:
        statement = statement.where(FinanceJournal.source_id == source_id)
    return int(session.exec(statement).one())


def _count_platform_events(
    session: Session,
    *,
    event_type: str,
    source_id: uuid.UUID | None = None,
) -> int:
    statement = select(func.count()).select_from(PlatformJournal).where(
        PlatformJournal.event_type == event_type
    )
    if source_id is not None:
        statement = statement.where(PlatformJournal.source_id == source_id)
    return int(session.exec(statement).one())


def _csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


def test_gym_sales_installments_receipts_refund_credit_and_failures(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Acceptance Sales Gym"
    )
    gym_id = uuid.UUID(str(gym["id"]))
    customer = make_customer(client, owner, str(gym_id))

    draft = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            installments=[
                {"due_date": "2026-11-15", "amount_irr": 400_000},
                {"due_date": "2026-12-15", "amount_irr": 600_000},
            ],
        ),
    )
    assert draft.status_code == 200, draft.text
    issue_key = uuid.uuid4().hex
    issued = issue(client, owner, draft.json()["id"], key=issue_key)
    assert issued.status_code == 200, issued.text
    invoice = issued.json()
    assert invoice["total_irr"] == 1_000_000
    assert [row["amount_irr"] for row in invoice["installments"]] == [
        400_000,
        600_000,
    ]
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="INVOICE_ISSUED",
        source_id=uuid.UUID(invoice["id"]),
    ) == [("1100", 1_000_000, 0), ("4000", 0, 1_000_000)]
    issue_replay = issue(client, owner, draft.json()["id"], key=issue_key)
    assert issue_replay.status_code == 200, issue_replay.text
    assert issue_replay.json()["id"] == invoice["id"]
    assert (
        _count_finance_events(
            db_session,
            gym_id=gym_id,
            event_type="INVOICE_ISSUED",
            source_id=uuid.UUID(invoice["id"]),
        )
        == 1
    )

    first = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=400_000,
            allocations=[(invoice["id"], 400_000)],
        ),
        key="acceptance-receipt-1",
    )
    assert first.status_code == 200, first.text
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="RECEIPT_CONFIRMED",
        source_id=uuid.UUID(first.json()["id"]),
    ) == [("1000", 400_000, 0), ("1100", 0, 400_000)]

    replay = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=400_000,
            allocations=[(invoice["id"], 400_000)],
        ),
        key="acceptance-receipt-1",
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert (
        _count_finance_events(
            db_session,
            gym_id=gym_id,
            event_type="RECEIPT_CONFIRMED",
            source_id=uuid.UUID(first.json()["id"]),
        )
        == 1
    )

    second = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=600_000,
            allocations=[(invoice["id"], 600_000)],
        ),
    )
    assert second.status_code == 200, second.text
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="RECEIPT_CONFIRMED",
        source_id=uuid.UUID(second.json()["id"]),
    ) == [("1000", 600_000, 0), ("1100", 0, 600_000)]

    refunded = refund(client, owner, customer, invoice["id"], 100_000)
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="REFUND_RECORDED",
        source_id=uuid.UUID(refunded["id"]),
    ) == [("1000", 0, 100_000), ("4100", 100_000, 0)]

    before_failure = _count_finance_journals(db_session, gym_id=gym_id)
    over_allocated = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=100_000,
            allocations=[(invoice["id"], 100_000)],
        ),
    )
    assert over_allocated.status_code == 400
    assert _count_finance_journals(db_session, gym_id=gym_id) == before_failure

    retry_invoice = issued_invoice(client, owner, customer, amount=100_000)
    retry_receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=100_000,
            allocations=[(retry_invoice["id"], 100_000)],
        ),
    )
    assert retry_receipt.status_code == 200, retry_receipt.text

    advance_invoice = issued_invoice(client, owner, customer, amount=500_000)
    advance_receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=600_000,
            allocations=[(advance_invoice["id"], 500_000)],
        ),
    )
    assert advance_receipt.status_code == 200, advance_receipt.text
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="RECEIPT_CONFIRMED",
        source_id=uuid.UUID(advance_receipt.json()["id"]),
    ) == [
        ("1000", 600_000, 0),
        ("1100", 0, 500_000),
        ("2000", 0, 100_000),
    ]

    credits_before = client.get("/api/v1/finance/credits", headers=owner)
    assert credits_before.status_code == 200, credits_before.text
    before_row = next(
        row
        for row in credits_before.json()["data"]
        if row["customer_user_id"] == customer
    )
    assert before_row["balance_irr"] == 100_000

    credit_invoice = issued_invoice(client, owner, customer, amount=300_000)
    applied = client.post(
        "/api/v1/finance/credits/apply",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "invoice_id": credit_invoice["id"],
            "amount_irr": 100_000,
            "received_on": "2026-11-08",
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["balance_irr"] == 200_000
    assert _finance_lines(
        db_session,
        gym_id=gym_id,
        event_type="ADVANCE_APPLIED",
        source_id=uuid.UUID(credit_invoice["id"]),
    ) == [("1100", 0, 100_000), ("2000", 100_000, 0)]
    credits_after = client.get("/api/v1/finance/credits", headers=owner)
    assert credits_after.status_code == 200, credits_after.text
    assert customer not in {
        row["customer_user_id"] for row in credits_after.json()["data"]
    }
    second_apply = client.post(
        "/api/v1/finance/credits/apply",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "invoice_id": credit_invoice["id"],
            "amount_irr": 100_000,
            "received_on": "2026-11-08",
        },
    )
    assert second_apply.status_code == 400
    assert second_apply.json()["detail"] == "insufficient_customer_credit"


def test_coach_commission_subscription_settlement_and_platform_payment(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Acceptance Coach Platform Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _coach_headers = make_coach(client, owner, gym_id)
    active_agreement(client, owner, coach_id, vesting_mode="MANUAL")
    agreement = create_platform_agreement(
        client,
        superuser_headers,
        gym_id=gym_id,
        mode="HYBRID",
        subscription_amount_irr=500_000,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 1000}],
        effective_from="2026-11-01",
    )
    assert agreement.status_code == 200, agreement.text
    activate(client, superuser_headers, agreement.json()["id"])
    accrual_key = uuid.uuid4().hex
    accrued = accrue(
        client, superuser_headers, agreement.json()["id"], key=accrual_key
    )
    assert accrued.status_code == 200, accrued.text
    accrual_replay = accrue(
        client, superuser_headers, agreement.json()["id"], key=accrual_key
    )
    assert accrual_replay.status_code == 200, accrual_replay.text
    assert accrual_replay.json()["id"] == accrued.json()["id"]
    assert (
        _count_platform_events(
            db_session,
            event_type="PLATFORM_FEE",
            source_id=uuid.UUID(agreement.json()["id"]),
        )
        == 1
    )

    invoice = coached_invoice(
        client, owner, customer, coach_id, amount=1_000_000
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text

    earning = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    ).json()["data"][0]
    assert earning["coach_share_irr"] == 300_000
    assert _finance_lines(
        db_session,
        gym_id=uuid.UUID(gym_id),
        event_type="COACH_ALLOCATION",
        source_id=uuid.UUID(earning["id"]),
    ) == [("2100", 0, 300_000), ("5100", 300_000, 0)]

    assert _platform_lines(
        db_session,
        event_type="PLATFORM_FEE",
        source_id=uuid.UUID(receipt.json()["id"]),
    ) == [("1100", 100_000, 0), ("4100", 0, 100_000)]
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_FEE",
        source_id=uuid.UUID(agreement.json()["id"]),
    ) == [("1100", 500_000, 0), ("4000", 0, 500_000)]

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
            "amount_irr": 300_000,
            "method": "CASH",
            "reference": "ACCEPTANCE-SETTLE",
            "paid_on": "2026-11-06",
        },
    )
    assert settlement.status_code == 200, settlement.text
    settlement_id = settlement.json()["id"]
    assert _finance_lines(
        db_session,
        gym_id=uuid.UUID(gym_id),
        event_type="COACH_SETTLEMENT",
        source_id=uuid.UUID(settlement_id),
    ) == [("2100", 300_000, 0), ("2200", 0, 300_000)]

    confirmed = client.post(
        f"/api/v1/finance/coach-settlements/{settlement_id}/confirm",
        headers=owner,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert _finance_lines(
        db_session,
        gym_id=uuid.UUID(gym_id),
        event_type="COACH_SETTLED",
        source_id=uuid.UUID(settlement_id),
    ) == [("1000", 0, 300_000), ("2200", 300_000, 0)]
    confirm_replay = client.post(
        f"/api/v1/finance/coach-settlements/{settlement_id}/confirm",
        headers=owner,
    )
    assert confirm_replay.status_code == 200, confirm_replay.text
    assert confirm_replay.json()["id"] == settlement_id
    assert (
        _count_finance_events(
            db_session,
            gym_id=uuid.UUID(gym_id),
            event_type="COACH_SETTLED",
            source_id=uuid.UUID(settlement_id),
        )
        == 1
    )

    platform_invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert platform_invoice.status_code == 200, platform_invoice.text
    assert platform_invoice.json()["total_irr"] == 600_000
    platform_lines = platform_invoice.json()["lines"]
    subscription_line = next(
        line
        for line in platform_lines
        if line["source_key"].startswith("subscription:")
    )
    commission_line = next(
        line
        for line in platform_lines
        if line["source_key"].startswith("receipt:")
    )
    assert subscription_line["amount_irr"] == 500_000
    assert commission_line["amount_irr"] == 100_000
    assert len(platform_lines) == 2
    payment = client.post(
        f"/api/v1/platform/invoices/{platform_invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 600_000,
            "method": "TRANSFER",
            "reference": "ACCEPTANCE-PLATFORM",
            "received_on": "2026-11-09",
        },
    )
    assert payment.status_code == 200, payment.text
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_PAYMENT",
        source_id=uuid.UUID(payment.json()["id"]),
    ) == [("1000", 600_000, 0), ("1100", 0, 600_000)]

    owner_payments = client.get(
        "/api/v1/finance/platform/payments", headers=owner
    )
    assert owner_payments.status_code == 200, owner_payments.text
    owner_payment = next(
        row
        for row in owner_payments.json()["data"]
        if row["id"] == payment.json()["id"]
    )
    assert owner_payment["amount_irr"] == 600_000
    assert owner_payment["method"] == "TRANSFER"
    assert owner_payment["reference"] == "ACCEPTANCE-PLATFORM"
    export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert export.status_code == 200, export.text
    assert "ACCRUAL" in export.text
    assert "platform_payment_allocation" in export.text


def test_group_contract_discount_cancellation_payment_and_exports(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gyms: list[dict[str, Any]] = []
    owners: list[dict[str, str]] = []
    for index in range(2):
        gym, owner = make_owner(
            client, superuser_headers, name=f"Acceptance Group Gym {index}"
        )
        gyms.append(gym)
        owners.append(owner)
        gym_id = str(gym["id"])
        customer = make_customer(client, owner, gym_id)
        commission_agreement(client, superuser_headers, gym_id, percent_bp=1000)
        invoice = issued_invoice(client, owner, customer, amount=1_000_000)
        receipt = record_receipt(
            client,
            owner,
            receipt_payload(
                customer,
                amount=1_000_000,
                allocations=[(invoice["id"], 1_000_000)],
            ),
        )
        assert receipt.status_code == 200, receipt.text

    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Acceptance Group",
            "members": [
                {"gym_id": str(gyms[0]["id"]), "allocation_bp": 5000},
                {"gym_id": str(gyms[1]["id"]), "allocation_bp": 5000},
            ],
        },
    )
    assert group.status_code == 200, group.text
    group_agreement = create_platform_agreement(
        client,
        superuser_headers,
        group_id=group.json()["id"],
        mode="COMMISSION",
        volume_discount_bp=500,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 0}],
    )
    assert group_agreement.status_code == 200, group_agreement.text
    activate(client, superuser_headers, group_agreement.json()["id"])

    issued = issue_platform_invoice(
        client, superuser_headers, group_id=group.json()["id"]
    )
    assert issued.status_code == 200, issued.text
    invoice = issued.json()
    assert invoice["discount_irr"] == 10_000
    assert invoice["total_irr"] == 190_000
    assert len(invoice["lines"]) == 2
    lines_by_gym = {line["gym_id"]: line for line in invoice["lines"]}
    assert set(lines_by_gym) == {str(gym["id"]) for gym in gyms}
    for gym in gyms:
        line = lines_by_gym[str(gym["id"])]
        assert line["gross_irr"] == 100_000
        assert line["discount_irr"] == 5_000
        assert line["amount_irr"] == 95_000
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_FEE_REVERSAL",
        source_id=uuid.UUID(invoice["id"]),
    ) == [
        ("1100", 0, 5_000),
        ("1100", 0, 5_000),
        ("4100", 5_000, 0),
        ("4100", 5_000, 0),
    ]

    cancelled = client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "acceptance reissue"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    cancel_replay = client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "acceptance reissue"},
    )
    assert cancel_replay.status_code == 200, cancel_replay.text
    assert cancel_replay.json()["id"] == invoice["id"]
    assert cancel_replay.json()["status"] == "CANCELLED"
    after_cancel = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert after_cancel.status_code == 200, after_cancel.text
    assert after_cancel.json()["invoiced_fees_irr"] == 0
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_INVOICE_CANCEL",
        source_id=uuid.UUID(invoice["id"]),
    ) == [
        ("1100", 5_000, 0),
        ("1100", 5_000, 0),
        ("4100", 0, 5_000),
        ("4100", 0, 5_000),
    ]

    reissued = issue_platform_invoice(
        client, superuser_headers, group_id=group.json()["id"]
    )
    assert reissued.status_code == 200, reissued.text
    assert reissued.json()["total_irr"] == 190_000
    first_gym_line = next(
        line
        for line in reissued.json()["lines"]
        if line["gym_id"] == str(gyms[0]["id"])
    )
    payment_key = uuid.uuid4().hex
    payment_payload = {
        "amount_irr": 90_000,
        "method": "TRANSFER",
        "reference": "ACCEPTANCE-GROUP",
        "received_on": "2026-11-10",
        "allocations": [
            {
                "invoice_line_id": first_gym_line["id"],
                "amount_irr": 90_000,
            }
        ],
    }
    payment = client.post(
        f"/api/v1/platform/invoices/{reissued.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": payment_key},
        json=payment_payload,
    )
    assert payment.status_code == 200, payment.text
    replay = client.post(
        f"/api/v1/platform/invoices/{reissued.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": payment_key},
        json=payment_payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == payment.json()["id"]
    assert (
        _count_platform_events(
            db_session,
            event_type="PLATFORM_PAYMENT",
            source_id=uuid.UUID(payment.json()["id"]),
        )
        == 1
    )
    changed = client.post(
        f"/api/v1/platform/invoices/{reissued.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": payment_key},
        json={**payment_payload, "amount_irr": 1},
    )
    assert changed.status_code == 409
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_PAYMENT",
        source_id=uuid.UUID(payment.json()["id"]),
    ) == [("1000", 90_000, 0), ("1100", 0, 90_000)]

    platform_export = client.get(
        "/api/v1/platform/reports/export",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert platform_export.status_code == 200, platform_export.text
    platform_metrics = {
        (row[0], row[3]): int(row[4])
        for row in _csv_rows(platform_export.text)[1:]
        if len(row) >= 5
    }
    assert platform_metrics[("ACCRUAL", "recognized_platform_revenue_irr")] == 190_000
    assert platform_metrics[("CASHFLOW", "collected_fees_irr")] == 90_000
    assert platform_metrics[("BALANCE", "receivable_irr")] == 100_000

    owner_export = client.get(
        "/api/v1/finance/reports/export",
        headers=owners[0],
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert owner_export.status_code == 200, owner_export.text
    owner_rows = _csv_rows(owner_export.text)
    allocation_rows = [
        row
        for row in owner_rows[1:]
        if len(row) >= 6 and row[1] == "platform_payment_allocation"
    ]
    assert len(allocation_rows) == 1
    assert int(allocation_rows[0][4]) == 90_000
    owner_summary = {
        row[2]: int(row[4])
        for row in owner_rows[1:]
        if len(row) >= 6 and row[1] == "summary"
    }
    assert owner_summary["sales_irr"] == 1_000_000
    assert owner_summary["platform_payable_irr"] == 5_000

    owner_payments = client.get(
        "/api/v1/finance/platform/payments", headers=owners[0]
    )
    assert owner_payments.status_code == 200, owner_payments.text
    owner_payment = next(
        row
        for row in owner_payments.json()["data"]
        if row["id"] == payment.json()["id"]
    )
    assert owner_payment["amount_irr"] == 90_000
    assert owner_payment["method"] == "TRANSFER"
    assert owner_payment["reference"] == "ACCEPTANCE-GROUP"


def test_role_authorization_matrix_for_local_acceptance(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym_a, owner_a = make_owner(
        client, superuser_headers, name="Acceptance Role Gym A"
    )
    gym_b, owner_b = make_owner(
        client, superuser_headers, name="Acceptance Role Gym B"
    )
    gym_a_id = str(gym_a["id"])
    gym_b_id = str(gym_b["id"])
    customer_a = make_customer(client, owner_a, gym_a_id)
    customer_b = make_customer(client, owner_b, gym_b_id)
    invoice_b = issued_invoice(client, owner_b, customer_b, amount=100_000)
    staff = add_staff(client, owner_a, gym_a_id, roles=["FINANCE_STAFF"])
    coach_email = unique_email("acceptance-coach")
    add_staff(
        client, owner_a, gym_a_id, roles=["COACH"], email=coach_email
    )
    coach = gym_headers(
        client,
        email=coach_email,
        password="staff-pass-456",
        gym_id=gym_a_id,
    )
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    athlete_email = unique_email("acceptance-athlete")
    create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_id,
        password="athlete-pass-123",
    )
    raw_athlete = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        raw_athlete,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete_email,
        password="athlete-pass-456",
        gym_id=gym_a_id,
    )

    assert client.get("/api/v1/finance/settings", headers=owner_a).status_code == 200
    assert (
        client.get(
            "/api/v1/finance/reports/summary",
            headers=owner_a,
            params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/finance/reports/summary",
            headers={**owner_a, "X-Gym-ID": gym_b_id},
            params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
        ).status_code
        in {403, 404}
    )
    assert client.get("/api/v1/platform/plans", headers=owner_a).status_code == 403

    assert client.get("/api/v1/finance/settings", headers=staff).status_code == 200
    assert client.get("/api/v1/athletes", headers=staff).status_code == 403
    assert client.get("/api/v1/platform/plans", headers=staff).status_code == 403
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    denied_invoice = client.post(
        "/api/v1/finance/invoices",
        headers={**staff, "Idempotency-Key": uuid.uuid4().hex},
        json=invoice_payload(customer_a),
    )
    assert denied_invoice.status_code == 403
    granted = client.put(
        f"/api/v1/finance/grants/{staff_id}",
        headers=owner_a,
        json={"grants": [{"permission": "finance.expense.manage"}]},
    )
    assert granted.status_code == 200, granted.text
    allowed_expense = client.post(
        "/api/v1/finance/expenses",
        headers={**staff, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "Acceptance",
            "amount_irr": 1_000,
            "spent_on": "2026-11-03",
        },
    )
    assert allowed_expense.status_code == 200, allowed_expense.text
    cross_gym_staff = client.get(
        "/api/v1/finance/settings",
        headers={**staff, "X-Gym-ID": gym_b_id},
    )
    assert cross_gym_staff.status_code in {403, 404}

    assert client.get("/api/v1/finance/settings", headers=coach).status_code == 403
    denied_coach = client.post(
        "/api/v1/finance/invoices",
        headers={**coach, "Idempotency-Key": uuid.uuid4().hex},
        json=invoice_payload(customer_a),
    )
    assert denied_coach.status_code == 403
    assert client.get("/api/v1/finance/my/earnings", headers=coach).status_code == 200

    assert (
        client.get("/api/v1/finance/my/account", headers=athlete_headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/finance/settings", headers=athlete_headers).status_code
        == 403
    )
    assert (
        client.get("/api/v1/platform/plans", headers=athlete_headers).status_code
        == 403
    )
    denied_athlete = client.post(
        "/api/v1/finance/invoices",
        headers={**athlete_headers, "Idempotency-Key": uuid.uuid4().hex},
        json=invoice_payload(customer_a),
    )
    assert denied_athlete.status_code == 403
    cross_gym_invoice = client.get(
        f"/api/v1/finance/invoices/{invoice_b['id']}", headers=owner_a
    )
    assert cross_gym_invoice.status_code == 404

    assert (
        client.get("/api/v1/platform/plans", headers=superuser_headers).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/finance/settings",
            headers={**superuser_headers, "X-Gym-ID": gym_a_id},
        ).status_code
        == 200
    )


def test_coached_invoice_refund_posts_coach_adjustment_and_platform_reversal(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Acceptance Coach Refund Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _coach_headers = make_coach(client, owner, gym_id)
    active_agreement(client, owner, coach_id, vesting_mode="MANUAL")
    commission_agreement(client, superuser_headers, gym_id, percent_bp=1000)

    invoice = coached_invoice(
        client, owner, customer, coach_id, amount=1_000_000
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text

    refunded = refund(client, owner, customer, invoice["id"], 100_000)
    assert _finance_lines(
        db_session,
        gym_id=uuid.UUID(gym_id),
        event_type="COACH_ADJUSTMENT",
        source_id=uuid.UUID(refunded["id"]),
    ) == [("2100", 30_000, 0), ("5100", 0, 30_000)]
    assert _platform_lines(
        db_session,
        event_type="PLATFORM_FEE_REVERSAL",
        source_id=uuid.UUID(refunded["id"]),
    ) == [("1100", 0, 10_000), ("4100", 10_000, 0)]
