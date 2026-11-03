from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.finance_models import FinanceSettings
from app.models import User
from app.platform_models import (
    PlatformInvoice,
    PlatformInvoiceLine,
    PlatformReceivable,
)
from app.services import finance as finance_service
from app.services import platform as platform_service
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import (
    create_draft,
    invoice_payload,
    issue,
    make_customer,
    void,
)
from tests.api.routes.test_finance_journal import post_opening
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)
from tests.api.routes.test_platform_agreements import (
    create_agreement as create_platform_agreement,
)
from tests.api.routes.test_platform_invoices import (
    accrue,
    activate,
    subscription_agreement,
)
from tests.api.routes.test_platform_reports import platform_invoice

pytestmark = pytest.mark.usefixtures("client")


def test_effective_due_date_uses_first_unpaid_installment(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Effective Due Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    payload = invoice_payload(
        customer,
        installments=[
            {"due_date": "2026-10-01", "amount_irr": 400_000},
            {"due_date": "2026-12-15", "amount_irr": 600_000},
        ],
    )
    payload["due_date"] = "2026-12-31"
    draft = create_draft(client, owner, payload)
    assert draft.status_code == 200, draft.text
    issued = issue(client, owner, draft.json()["id"])
    assert issued.status_code == 200, issued.text
    invoice = issued.json()

    due_on, amount = finance_service.effective_due(
        db_session, finance_service._get_invoice(
            db_session, gym_id=uuid.UUID(gym_id), invoice_id=uuid.UUID(invoice["id"])
        )
    )
    assert due_on == date(2026, 10, 1)
    assert amount == 400_000

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=400_000,
            allocations=[(invoice["id"], 400_000)],
        ),
    )
    assert receipt.status_code == 200, receipt.text

    refreshed = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["overdue"] is False
    assert refreshed.json()["due_date"] == "2026-12-31"

    reminders = client.get(
        "/api/v1/finance/reminders",
        headers=owner,
        params={"within_days": 90},
    )
    assert reminders.status_code == 200, reminders.text
    reminder = next(
        row
        for row in reminders.json()["installments"]
        if row["invoice_id"] == invoice["id"]
    )
    assert reminder["due_date"] == "2026-12-15"
    assert reminder["amount_irr"] == 600_000
    assert reminder["overdue"] is False


def test_platform_historical_standing_and_reminders_use_as_of_events(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Historical Platform Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    issued = platform_invoice(
        client,
        superuser_headers,
        gym_id=gym_id,
        due_on=platform_service.platform_today(),
    )
    assert issued.status_code == 200, issued.text

    today = platform_service.platform_today()
    before = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": today.isoformat()},
    )
    assert before.status_code == 200, before.text
    assert before.json()["open_irr"] == 500_000

    payment = client.post(
        f"/api/v1/platform/invoices/{issued.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 500_000,
            "method": "TRANSFER",
            "reference": "FUTURE-PAYMENT",
            "received_on": (today + timedelta(days=1)).isoformat(),
        },
    )
    assert payment.status_code == 200, payment.text

    still_before = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": today.isoformat()},
    )
    assert still_before.status_code == 200, still_before.text
    assert still_before.json()["open_irr"] == 500_000

    after = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": (today + timedelta(days=1)).isoformat()},
    )
    assert after.status_code == 200, after.text
    assert after.json()["open_irr"] == 0

    historical_reminders = client.get(
        "/api/v1/platform/reminders",
        headers=superuser_headers,
        params={
            "as_of": (today - timedelta(days=1)).isoformat(),
            "within_days": 7,
        },
    )
    assert historical_reminders.status_code == 200, historical_reminders.text
    assert historical_reminders.json()["overdue"] == []
    assert historical_reminders.json()["due_soon"] == []


def test_platform_billed_unbilled_split_and_owner_consistency(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Billed Unbilled Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=700_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200

    dues = client.get("/api/v1/finance/platform/dues", headers=owner)
    assert dues.status_code == 200, dues.text
    assert dues.json()["open_irr"] == 0
    assert dues.json()["unbilled_open_irr"] == 700_000
    assert dues.json()["total_exposure_irr"] == 700_000
    assert dues.json()["stage"] == "CURRENT"

    overview = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["billed_receivable_irr"] == 0
    assert overview.json()["unbilled_receivable_irr"] == 700_000
    assert overview.json()["receivable_irr"] == 700_000

    summary = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["platform_payable_irr"] == 700_000

    issued = platform_invoice(
        client,
        superuser_headers,
        gym_id=gym_id,
        due_on=platform_service.platform_today(),
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["issued_on"] == platform_service.platform_today().isoformat()

    billed = client.get("/api/v1/finance/platform/dues", headers=owner)
    assert billed.status_code == 200, billed.text
    assert billed.json()["open_irr"] == 700_000
    assert billed.json()["unbilled_open_irr"] == 0
    assert billed.json()["total_exposure_irr"] == 700_000


def test_revenue_recognition_aligns_with_journal_for_boundary_range(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Revenue Boundary Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
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
    assert accrue(client, superuser_headers, agreement.json()["id"]).status_code == 200

    invoice = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            lines=[
                {
                    "kind": "PROGRAM",
                    "description": "Boundary sale",
                    "quantity": 1,
                    "unit_price_irr": 1_000_000,
                }
            ],
        ),
    )
    assert invoice.status_code == 200, invoice.text
    issued = issue(client, owner, invoice.json()["id"])
    assert issued.status_code == 200, issued.text
    receipt_payload_data = receipt_payload(
        customer,
        amount=1_000_000,
        allocations=[(issued.json()["id"], 1_000_000)],
    )
    receipt_payload_data["received_on"] = "2026-11-01"
    receipt = record_receipt(client, owner, receipt_payload_data)
    assert receipt.status_code == 200, receipt.text

    boundary = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-11-01"},
    )
    assert boundary.status_code == 200, boundary.text
    body = boundary.json()
    assert body["recognized_platform_revenue_irr"] == 600_000
    assert sum(
        row["recognized_revenue_irr"] for row in body["by_gym"]
    ) == 600_000

    later = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-03", "to_date": "2026-11-03"},
    )
    assert later.status_code == 200, later.text
    assert later.json()["recognized_platform_revenue_irr"] == 0
    assert sum(
        row["recognized_revenue_irr"] for row in later.json()["by_gym"]
    ) == 0


def test_void_preserves_original_period_and_reverses_in_void_period(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Void Boundary Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    draft = create_draft(client, owner, invoice_payload(customer))
    assert draft.status_code == 200, draft.text
    issued = issue(
        client, owner, draft.json()["id"], posting_date="2026-11-02"
    )
    assert issued.status_code == 200, issued.text

    original = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-02", "to_date": "2026-11-02"},
    )
    assert original.status_code == 200, original.text
    assert original.json()["sales_irr"] == 1_000_000
    assert original.json()["recognized_revenue_irr"] == 1_000_000

    voided = void(client, owner, issued.json()["id"])
    assert voided.status_code == 200, voided.text

    unchanged = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-02", "to_date": "2026-11-02"},
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["sales_irr"] == 1_000_000
    assert unchanged.json()["recognized_revenue_irr"] == 1_000_000

    void_period = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-03", "to_date": "2026-11-03"},
    )
    assert void_period.status_code == 200, void_period.text
    assert void_period.json()["sales_irr"] == -1_000_000
    assert void_period.json()["recognized_revenue_irr"] == -1_000_000


def test_closed_period_rejects_backdated_posting(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Closed Period Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    opened = post_opening(client, owner)
    assert opened.status_code == 200, opened.text
    closed = client.post("/api/v1/finance/periods/close", headers=owner)
    assert closed.status_code == 200, closed.text

    draft = create_draft(client, owner, invoice_payload(customer))
    assert draft.status_code == 200, draft.text
    backdated = issue(
        client, owner, draft.json()["id"], posting_date="2026-11-02"
    )
    assert backdated.status_code == 400, backdated.text
    assert backdated.json()["detail"] == "finance_posting_outside_open_period"

    current = issue(
        client,
        owner,
        draft.json()["id"],
        posting_date=finance_service.gym_today(
            db_session, uuid.UUID(str(gym["id"]))
        ).isoformat(),
    )
    assert current.status_code == 200, current.text


def test_gym_today_uses_gym_timezone(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gym, _owner = make_owner(client, superuser_headers, name="Timezone Gym")
    gym_id = uuid.UUID(str(gym["id"]))
    db_session.add(FinanceSettings(gym_id=gym_id, timezone="Asia/Tehran"))
    db_session.commit()

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(2026, 11, 3, 21, 0, tzinfo=UTC)

    monkeypatch.setattr(finance_service, "datetime", FixedDateTime)
    assert finance_service.gym_today(db_session, gym_id) == date(2026, 11, 4)

    class EarlierDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(2026, 11, 3, 20, 0, tzinfo=UTC)

    monkeypatch.setattr(finance_service, "datetime", EarlierDateTime)
    assert finance_service.gym_today(db_session, gym_id) == date(2026, 11, 3)


def test_refund_posts_in_recorded_period_not_request_period(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    from tests.api.routes.test_finance_coach_refunds import refund

    gym, owner = make_owner(client, superuser_headers, name="Refund Period Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = create_draft(client, owner, invoice_payload(customer))
    assert invoice.status_code == 200, invoice.text
    issued = issue(client, owner, invoice.json()["id"])
    assert issued.status_code == 200, issued.text
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=1_000_000,
            allocations=[(issued.json()["id"], 1_000_000)],
        ),
    )
    assert receipt.status_code == 200, receipt.text
    refund(client, owner, customer, issued.json()["id"], 100_000)

    request_period = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-03", "to_date": "2026-11-03"},
    )
    assert request_period.status_code == 200, request_period.text
    assert request_period.json()["cash_refunded_irr"] == 0

    recorded_period = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-07", "to_date": "2026-11-07"},
    )
    assert recorded_period.status_code == 200, recorded_period.text
    assert recorded_period.json()["cash_refunded_irr"] == 100_000

    recorded_export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={"from_date": "2026-11-07", "to_date": "2026-11-07"},
    )
    assert recorded_export.status_code == 200, recorded_export.text
    assert ",refund," in recorded_export.text
    assert "2026-11-07,100000" in recorded_export.text
    requested_refund = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": issued.json()["id"],
            "amount_irr": 50_000,
            "reason": "rejected refund",
        },
    )
    assert requested_refund.status_code == 200, requested_refund.text
    rejected = client.post(
        f"/api/v1/finance/refunds/{requested_refund.json()['id']}/reject",
        headers=owner,
        json={"reason": "synthetic rejection"},
    )
    assert rejected.status_code == 200, rejected.text
    request_export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={"from_date": "2026-11-03", "to_date": "2026-11-03"},
    )
    assert request_export.status_code == 200, request_export.text
    assert ",refund," not in request_export.text


def test_platform_cancellation_does_not_rewrite_original_period(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Cancel Period Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    accrued = accrue(client, superuser_headers, agreement["id"])
    assert accrued.status_code == 200, accrued.text
    receivable = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_id)
        )
    ).one()
    today = platform_service.platform_today()
    issued_on = today - timedelta(days=1)
    next_number = int(
        db_session.exec(
            select(func.coalesce(func.max(PlatformInvoice.invoice_number), 0))
        ).one()
    ) + 1
    invoice = PlatformInvoice(
        gym_id=uuid.UUID(gym_id),
        group_id=None,
        invoice_number=next_number,
        period_start=issued_on,
        period_end=issued_on,
        issued_on=issued_on,
        due_on=today,
        status="ISSUED",
        discount_irr=0,
        total_irr=500_000,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PlatformInvoiceLine(
            invoice_id=invoice.id,
            gym_id=uuid.UUID(gym_id),
            receivable_id=receivable.id,
            source_key=receivable.source_key,
            description="synthetic cancellation boundary",
            gross_irr=500_000,
            discount_irr=0,
            credit_irr=0,
            amount_irr=500_000,
            paid_irr=0,
        )
    )
    db_session.commit()

    original = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={
            "from_date": issued_on.isoformat(),
            "to_date": issued_on.isoformat(),
        },
    )
    assert original.status_code == 200, original.text
    assert original.json()["invoiced_fees_irr"] == 500_000

    cancelled = client.post(
        f"/api/v1/platform/invoices/{invoice.id}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "synthetic cancellation boundary"},
    )
    assert cancelled.status_code == 200, cancelled.text

    unchanged = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={
            "from_date": issued_on.isoformat(),
            "to_date": issued_on.isoformat(),
        },
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["invoiced_fees_irr"] == 500_000

    cancel_period = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": today.isoformat(), "to_date": today.isoformat()},
    )
    assert cancel_period.status_code == 200, cancel_period.text
    assert cancel_period.json()["invoiced_fees_irr"] == -500_000

    historical = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": issued_on.isoformat()},
    )
    assert historical.status_code == 200, historical.text
    assert historical.json()["open_irr"] == 500_000


def test_closed_synthetic_month_reconciles_with_zero_delta(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Closed Month Reconciliation Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
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
    assert accrue(client, superuser_headers, agreement.json()["id"]).status_code == 200

    invoice = create_draft(client, owner, invoice_payload(customer))
    assert invoice.status_code == 200, invoice.text
    issued = issue(
        client, owner, invoice.json()["id"], posting_date="2026-11-01"
    )
    assert issued.status_code == 200, issued.text
    receipt_payload_data = receipt_payload(
        customer,
        amount=1_000_000,
        allocations=[(issued.json()["id"], 1_000_000)],
    )
    receipt_payload_data["received_on"] = "2026-11-01"
    receipt = record_receipt(client, owner, receipt_payload_data)
    assert receipt.status_code == 200, receipt.text

    overview = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-11-01"},
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    by_gym_total = sum(row["recognized_revenue_irr"] for row in body["by_gym"])
    assert body["recognized_platform_revenue_irr"] == 600_000
    assert by_gym_total == 600_000
    assert body["recognized_platform_revenue_irr"] - by_gym_total == 0

    summary = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-11-01"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["recognized_revenue_irr"] == 1_000_000
    assert summary.json()["cash_collected_irr"] == 1_000_000
    assert summary.json()["platform_payable_irr"] == 600_000

    closed = client.post("/api/v1/finance/periods/close", headers=owner)
    assert closed.status_code == 200, closed.text
    after_close = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-11-01"},
    )
    assert after_close.status_code == 200, after_close.text
    assert after_close.json()["recognized_platform_revenue_irr"] == 600_000
    assert sum(
        row["recognized_revenue_irr"]
        for row in after_close.json()["by_gym"]
    ) == 600_000

    from app.finance_models import FinanceJournal, FinanceJournalLine
    from app.platform_models import PlatformJournal, PlatformJournalLine

    finance_unbalanced = db_session.exec(
        select(FinanceJournal.id)
        .join(
            FinanceJournalLine,
            FinanceJournalLine.journal_id == FinanceJournal.id,
        )
        .group_by(FinanceJournal.id)
        .having(
            func.sum(FinanceJournalLine.debit_irr)
            != func.sum(FinanceJournalLine.credit_irr)
        )
    ).all()
    platform_unbalanced = db_session.exec(
        select(PlatformJournal.id)
        .join(
            PlatformJournalLine,
            PlatformJournalLine.journal_id == PlatformJournal.id,
        )
        .group_by(PlatformJournal.id)
        .having(
            func.sum(PlatformJournalLine.debit_irr)
            != func.sum(PlatformJournalLine.credit_irr)
        )
    ).all()
    assert finance_unbalanced == []
    assert platform_unbalanced == []


def test_platform_historical_unbilled_ignores_future_payment(
    client: TestClient,
    superuser_headers: dict[str, str],
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Unbilled As Of Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    today = platform_service.platform_today()
    issued = platform_invoice(
        client, superuser_headers, gym_id=gym_id, due_on=today
    )
    assert issued.status_code == 200, issued.text
    payment = client.post(
        f"/api/v1/platform/invoices/{issued.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 500_000,
            "method": "TRANSFER",
            "reference": "UNBILLED-FUTURE",
            "received_on": (today + timedelta(days=1)).isoformat(),
        },
    )
    assert payment.status_code == 200, payment.text

    historical = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": (today - timedelta(days=1)).isoformat()},
    )
    assert historical.status_code == 200, historical.text
    assert historical.json()["unbilled_open_irr"] == 500_000
    assert historical.json()["total_exposure_irr"] == 500_000


def test_platform_discount_cancellation_is_period_stable(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Discount Cancellation Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    receivable = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_id)
        )
    ).one()
    today = platform_service.platform_today()
    issued_on = today - timedelta(days=1)
    next_number = int(
        db_session.exec(
            select(func.coalesce(func.max(PlatformInvoice.invoice_number), 0))
        ).one()
    ) + 1
    invoice = PlatformInvoice(
        gym_id=uuid.UUID(gym_id),
        group_id=None,
        invoice_number=next_number,
        period_start=issued_on,
        period_end=issued_on,
        issued_on=issued_on,
        due_on=today,
        status="ISSUED",
        discount_irr=5_000,
        total_irr=495_000,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PlatformInvoiceLine(
            invoice_id=invoice.id,
            gym_id=uuid.UUID(gym_id),
            receivable_id=receivable.id,
            source_key=receivable.source_key,
            description="synthetic discount boundary",
            gross_irr=500_000,
            discount_irr=5_000,
            credit_irr=0,
            amount_irr=495_000,
            paid_irr=0,
        )
    )
    actor = db_session.exec(
        select(User).where(User.is_superuser == True)  # noqa: E712
    ).first()
    assert actor is not None
    platform_service.post_platform_journal(
        db_session,
        actor=actor,
        posting_date=issued_on,
        event_type="PLATFORM_FEE_REVERSAL",
        description="synthetic discount boundary",
        lines=[
            ("4100", 5_000, 0, "discount"),
            ("1100", 0, 5_000, "discount"),
        ],
        source_type="platform_invoice",
        source_id=invoice.id,
    )
    db_session.commit()

    original = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={
            "from_date": "2026-11-01",
            "to_date": issued_on.isoformat(),
        },
    )
    assert original.status_code == 200, original.text
    original_body = original.json()
    assert original_body["recognized_platform_revenue_irr"] == 495_000
    assert sum(
        row["recognized_revenue_irr"] for row in original_body["by_gym"]
    ) == 495_000

    cancelled = client.post(
        f"/api/v1/platform/invoices/{invoice.id}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "synthetic discount cancellation"},
    )
    assert cancelled.status_code == 200, cancelled.text

    unchanged = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={
            "from_date": "2026-11-01",
            "to_date": issued_on.isoformat(),
        },
    )
    assert unchanged.status_code == 200, unchanged.text
    unchanged_body = unchanged.json()
    assert unchanged_body["recognized_platform_revenue_irr"] == 495_000
    assert sum(
        row["recognized_revenue_irr"] for row in unchanged_body["by_gym"]
    ) == 495_000

    cancel_day = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": today.isoformat(), "to_date": today.isoformat()},
    )
    assert cancel_day.status_code == 200, cancel_day.text
    assert cancel_day.json()["recognized_platform_revenue_irr"] == 5_000
    assert sum(
        row["recognized_revenue_irr"] for row in cancel_day.json()["by_gym"]
    ) == 5_000


def test_void_receivable_uses_void_posting_date(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Void Receivable Gym"
    )
    gym_id = uuid.UUID(str(gym["id"]))
    customer = make_customer(client, owner, str(gym_id))
    today = finance_service.gym_today(db_session, gym_id)
    draft = create_draft(client, owner, invoice_payload(customer))
    assert draft.status_code == 200, draft.text
    issued = issue(
        client, owner, draft.json()["id"], posting_date=today.isoformat()
    )
    assert issued.status_code == 200, issued.text
    future = today + timedelta(days=2)
    voided = client.post(
        f"/api/v1/finance/invoices/{issued.json()['id']}/void",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "future void", "posting_date": future.isoformat()},
    )
    assert voided.status_code == 200, voided.text

    current = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": today.isoformat(), "to_date": today.isoformat()},
    )
    assert current.status_code == 200, current.text
    assert current.json()["sales_irr"] == 1_000_000
    assert current.json()["receivable_irr"] == 1_000_000

    future_period = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": future.isoformat(), "to_date": future.isoformat()},
    )
    assert future_period.status_code == 200, future_period.text
    assert future_period.json()["sales_irr"] == -1_000_000
    assert future_period.json()["receivable_irr"] == 0


def test_paid_expense_export_uses_paid_journal_date(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Expense Export Gym"
    )
    gym_id = uuid.UUID(str(gym["id"]))
    today = finance_service.gym_today(db_session, gym_id)
    spent_on = today - timedelta(days=2)
    created = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "Acceptance",
            "amount_irr": 1_000,
            "spent_on": spent_on.isoformat(),
        },
    )
    assert created.status_code == 200, created.text
    paid = client.post(
        f"/api/v1/finance/expenses/{created.json()['id']}/pay",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"paid_on": today.isoformat(), "method": "TRANSFER"},
    )
    assert paid.status_code == 200, paid.text

    paid_export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={"from_date": today.isoformat(), "to_date": today.isoformat()},
    )
    assert paid_export.status_code == 200, paid_export.text
    assert ",expense," in paid_export.text
    assert f"{today.isoformat()},1000" in paid_export.text

    spent_export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={
            "from_date": spent_on.isoformat(),
            "to_date": spent_on.isoformat(),
        },
    )
    assert spent_export.status_code == 200, spent_export.text
    assert ",expense," not in spent_export.text
