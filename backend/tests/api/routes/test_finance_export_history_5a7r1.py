from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.finance_models import FinanceRefund
from app.platform_models import (
    PlatformCredit,
    PlatformCreditApplication,
    PlatformInvoice,
    PlatformInvoiceLine,
    PlatformReceivable,
)
from app.services import finance as finance_service
from app.services.platform import platform_today
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)
from tests.api.routes.test_platform_invoices import (
    accrue,
    issue_platform_invoice,
    subscription_agreement,
)

pytestmark = pytest.mark.usefixtures("client")


def csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


def export_rows(
    client: TestClient,
    headers: dict[str, str],
    *,
    from_date: str,
    to_date: str,
    offboarding: bool = False,
) -> list[list[str]]:
    path = (
        "/api/v1/finance/reports/offboarding-export"
        if offboarding
        else "/api/v1/finance/reports/export"
    )
    params = {} if offboarding else {"from_date": from_date, "to_date": to_date}
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    rows = csv_rows(response.text)
    assert rows[0][-1] == "date_basis"
    return rows


def summary_row(rows: list[list[str]], field: str) -> list[str]:
    return next(
        row
        for row in rows[1:]
        if row[1] == "summary" and row[2] == field
    )


def test_gym_export_has_explicit_date_basis_and_matches_summary_as_of(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Export History Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)

    first = receipt_payload(
        customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
    )
    first["received_on"] = "2026-11-05"
    assert record_receipt(client, owner, first).status_code == 200
    later = receipt_payload(
        customer, amount=300_000, allocations=[(invoice["id"], 300_000)]
    )
    later["received_on"] = "2026-12-05"
    assert record_receipt(client, owner, later).status_code == 200

    summary = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-11-30"},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()

    november = export_rows(
        client, owner, from_date="2026-11-01", to_date="2026-11-30"
    )
    receivable = summary_row(november, "receivable_irr")
    assert int(receivable[4]) == body["receivable_irr"] == 600_000
    assert receivable[3] == "2026-11-30"
    assert receivable[6] == "as_of_to_date"
    assert int(summary_row(november, "cash_collected_irr")[4]) == 400_000
    assert summary_row(november, "cash_collected_irr")[6] == "range"
    assert int(summary_row(november, "sales_irr")[4]) == 1_000_000
    assert summary_row(november, "sales_irr")[6] == "range"
    assert summary_row(november, "renewals_due")[6] == "as_of_to_date"

    november_receipts = [
        row for row in november[1:] if row[1] == "receipt"
    ]
    assert len(november_receipts) == 1
    assert november_receipts[0][3] == "2026-11-05"
    assert november_receipts[0][6] == "received_on"

    december = export_rows(
        client, owner, from_date="2026-12-01", to_date="2026-12-31"
    )
    assert int(summary_row(december, "receivable_irr")[4]) == 300_000
    december_receipts = [
        row for row in december[1:] if row[1] == "receipt"
    ]
    assert [row[3] for row in december_receipts] == ["2026-12-05"]


def _insert_platform_invoice(
    db_session: Session,
    *,
    gym_id: str,
    receivable: PlatformReceivable,
    gross_amount: int,
    issued_on: date,
    credit: int = 0,
    paid: int = 0,
) -> uuid.UUID:
    next_number = int(
        db_session.exec(
            select(func.coalesce(func.max(PlatformInvoice.invoice_number), 0))
        ).one()
    ) + 1
    net_amount = gross_amount - credit
    invoice = PlatformInvoice(
        gym_id=uuid.UUID(gym_id),
        group_id=None,
        invoice_number=next_number,
        period_start=issued_on,
        period_end=issued_on,
        issued_on=issued_on,
        due_on=issued_on + timedelta(days=30),
        status="ISSUED",
        discount_irr=0,
        total_irr=net_amount,
    )
    db_session.add(invoice)
    db_session.flush()
    line = PlatformInvoiceLine(
        invoice_id=invoice.id,
        gym_id=uuid.UUID(gym_id),
        receivable_id=receivable.id,
        source_key=receivable.source_key,
        description="synthetic export history",
        gross_irr=gross_amount,
        discount_irr=0,
        credit_irr=credit,
        amount_irr=net_amount,
        paid_irr=paid,
    )
    db_session.add(line)
    receivable.paid_irr = paid
    receivable.status = "PARTIAL" if paid else "INVOICED"
    db_session.add(receivable)
    db_session.flush()
    if credit:
        platform_credit = PlatformCredit(
            gym_id=uuid.UUID(gym_id),
            source_type="MANUAL",
            source_id=None,
            source_key=f"synthetic-credit:{uuid.uuid4().hex}",
            amount_irr=credit,
            recognized_on=issued_on,
            reason="synthetic export credit",
        )
        db_session.add(platform_credit)
        db_session.flush()
        db_session.add(
            PlatformCreditApplication(
                credit_id=platform_credit.id,
                invoice_line_id=line.id,
                amount_irr=credit,
            )
        )
    db_session.commit()
    return line.id


def test_platform_balance_rows_use_as_of_payments_credits_and_cancellation(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Platform Export Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    invoice = issue_platform_invoice(client, superuser_headers, gym_id=gym_id)
    assert invoice.status_code == 200, invoice.text
    payment = client.post(
        f"/api/v1/platform/invoices/{invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 200_000,
            "method": "TRANSFER",
            "received_on": "2026-11-20",
        },
    )
    assert payment.status_code == 200, payment.text

    before = export_rows(
        client, owner, from_date="2026-11-01", to_date="2026-11-19"
    )
    before_receivable = next(
        row for row in before[1:] if row[1] == "platform_receivable"
    )
    before_line = next(
        row for row in before[1:] if row[1] == "platform_invoice_line"
    )
    assert int(before_receivable[4]) == 500_000
    assert before_receivable[6] == "recognized_on;as_of_to_date"
    assert int(before_line[4]) == 500_000
    assert before_line[6] == "issued_on;as_of_to_date"
    assert not [
        row for row in before[1:] if row[1] == "platform_payment_allocation"
    ]

    after = export_rows(
        client, owner, from_date="2026-11-20", to_date="2026-11-30"
    )
    after_receivable = next(
        row for row in after[1:] if row[1] == "platform_receivable"
    )
    after_line = next(
        row for row in after[1:] if row[1] == "platform_invoice_line"
    )
    allocation = next(
        row for row in after[1:] if row[1] == "platform_payment_allocation"
    )
    assert int(after_receivable[4]) == 300_000
    assert int(after_line[4]) == 300_000
    assert int(allocation[4]) == 200_000

    # A later cancellation must not rewrite the earlier exported period.
    cancel_gym, cancel_owner = make_owner(
        client, superuser_headers, name="Cancellation Export Gym"
    )
    cancel_gym_id = str(cancel_gym["id"])
    cancel_agreement = subscription_agreement(
        client, superuser_headers, cancel_gym_id, amount=400_000
    )
    assert (
        accrue(client, superuser_headers, cancel_agreement["id"]).status_code
        == 200
    )
    receivable = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(cancel_gym_id)
        )
    ).one()
    _insert_platform_invoice(
        db_session,
        gym_id=cancel_gym_id,
        receivable=receivable,
        gross_amount=400_000,
        issued_on=date(2026, 11, 1),
    )
    cancelled = client.post(
        f"/api/v1/platform/invoices/{db_session.exec(select(PlatformInvoice).where(PlatformInvoice.gym_id == uuid.UUID(cancel_gym_id))).one().id}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "synthetic later cancellation"},
    )
    assert cancelled.status_code == 200, cancelled.text
    today = platform_today().isoformat()
    before_cancel = export_rows(
        client,
        cancel_owner,
        from_date="2026-11-01",
        to_date=(platform_today() - timedelta(days=1)).isoformat(),
    )
    assert [
        row for row in before_cancel[1:] if row[1] == "platform_invoice_line"
    ]
    after_cancel = export_rows(
        client,
        cancel_owner,
        from_date=today,
        to_date=today,
    )
    assert not [
        row for row in after_cancel[1:] if row[1] == "platform_invoice_line"
    ]

    # Credit applied at issuance is visible only from the invoice issue date.
    credit_gym, credit_owner = make_owner(
        client, superuser_headers, name="Credit Export Gym"
    )
    credit_gym_id = str(credit_gym["id"])
    credit_agreement = subscription_agreement(
        client, superuser_headers, credit_gym_id, amount=300_000
    )
    assert (
        accrue(client, superuser_headers, credit_agreement["id"]).status_code
        == 200
    )
    credit_receivable = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(credit_gym_id)
        )
    ).one()
    _insert_platform_invoice(
        db_session,
        gym_id=credit_gym_id,
        receivable=credit_receivable,
        gross_amount=300_000,
        issued_on=date(2026, 11, 10),
        credit=100_000,
        paid=100_000,
    )
    before_issue = export_rows(
        client, credit_owner, from_date="2026-11-01", to_date="2026-11-09"
    )
    before_credit_receivable = next(
        row for row in before_issue[1:] if row[1] == "platform_receivable"
    )
    assert int(before_credit_receivable[4]) == 300_000
    assert not [
        row for row in before_issue[1:] if row[1] == "platform_invoice_line"
    ]
    after_issue = export_rows(
        client, credit_owner, from_date="2026-11-10", to_date="2026-11-30"
    )
    after_credit_receivable = next(
        row for row in after_issue[1:] if row[1] == "platform_receivable"
    )
    after_credit_line = next(
        row for row in after_issue[1:] if row[1] == "platform_invoice_line"
    )
    assert int(after_credit_receivable[4]) == 200_000
    assert int(after_credit_line[4]) == 200_000


def test_offboarding_export_labels_balances_as_of_export(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Offboarding Export Gym")
    gym_id = uuid.UUID(str(gym["id"]))
    customer = make_customer(client, owner, str(gym_id))
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    receipt = receipt_payload(
        customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
    )
    receipt["received_on"] = "2026-11-05"
    assert record_receipt(client, owner, receipt).status_code == 200

    rows = export_rows(client, owner, from_date="", to_date="", offboarding=True)
    receivable = summary_row(rows, "receivable_irr")
    assert int(receivable[4]) == 600_000
    assert receivable[3] == finance_service.gym_today(db_session, gym_id).isoformat()
    assert receivable[6] == "as_of_export"
    assert summary_row(rows, "cash_collected_irr")[6] == "range"


def test_export_uses_business_dates_for_refunds_and_expenses(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Business Date Export Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    receipt = receipt_payload(
        customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
    )
    receipt["received_on"] = "2026-11-05"
    assert record_receipt(client, owner, receipt).status_code == 200

    requested = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 100_000,
            "reason": "synthetic export refund",
        },
    )
    assert requested.status_code == 200, requested.text
    assert (
        client.post(
            f"/api/v1/finance/refunds/{requested.json()['id']}/approve",
            headers=owner,
        ).status_code
        == 200
    )
    recorded = client.post(
        f"/api/v1/finance/refunds/{requested.json()['id']}/record",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"posting_date": "2026-11-10"},
    )
    assert recorded.status_code == 200, recorded.text
    stored_refund = db_session.get(FinanceRefund, uuid.UUID(recorded.json()["id"]))
    assert stored_refund is not None
    stored_refund.created_at = datetime(2026, 11, 8, tzinfo=UTC)
    db_session.add(stored_refund)
    db_session.commit()

    expense = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "synthetic",
            "amount_irr": 50_000,
            "spent_on": "2026-11-02",
        },
    )
    assert expense.status_code == 200, expense.text
    paid = client.post(
        f"/api/v1/finance/expenses/{expense.json()['id']}/pay",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"paid_on": "2026-11-10", "method": "CASH"},
    )
    assert paid.status_code == 200, paid.text

    before = export_rows(
        client, owner, from_date="2026-11-01", to_date="2026-11-09"
    )
    before_refund = next(row for row in before[1:] if row[1] == "refund")
    assert before_refund[0] == "BALANCE"
    assert before_refund[3] == "2026-11-08"
    assert before_refund[6] == "created_at_local"
    assert not [row for row in before[1:] if row[1] == "expense"]

    after = export_rows(
        client, owner, from_date="2026-11-10", to_date="2026-11-30"
    )
    refund_row = next(row for row in after[1:] if row[1] == "refund")
    assert refund_row[3] == "2026-11-10"
    assert refund_row[6] == "posting_date"
    after_expense = next(row for row in after[1:] if row[1] == "expense")
    assert after_expense[0] == "CASHFLOW"
    assert after_expense[3] == "2026-11-10"
    assert after_expense[6] == "posting_date"
