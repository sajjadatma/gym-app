from __future__ import annotations

import csv
import io
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.platform_models import (
    PlatformCredit,
    PlatformCreditApplication,
    PlatformInvoice,
    PlatformInvoiceLine,
    PlatformReceivable,
)
from app.services.platform import platform_today
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_platform_invoices import (
    accrue,
    subscription_agreement,
)

pytestmark = pytest.mark.usefixtures("client")


def csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


def insert_invoice_for_receivable(
    db_session: Session,
    *,
    gym_id: str,
    receivable: PlatformReceivable,
    issued_on: date,
    credit: int = 0,
    paid: int = 0,
) -> uuid.UUID:
    next_number = int(
        db_session.exec(
            select(func.coalesce(func.max(PlatformInvoice.invoice_number), 0))
        ).one()
    ) + 1
    net_amount = receivable.amount_irr - credit
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
        description="synthetic per-gym history",
        gross_irr=receivable.amount_irr,
        discount_irr=0,
        credit_irr=credit,
        amount_irr=net_amount,
        paid_irr=paid,
    )
    db_session.add(line)
    db_session.flush()
    if credit:
        platform_credit = PlatformCredit(
            gym_id=uuid.UUID(gym_id),
            source_type="REFUND",
            source_id=None,
            source_key=f"synthetic-credit:{uuid.uuid4().hex}",
            amount_irr=credit,
            recognized_on=issued_on,
            reason="synthetic per-gym credit",
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
    receivable.paid_irr = paid
    receivable.status = "PARTIAL" if paid else "INVOICED"
    db_session.add(receivable)
    db_session.commit()
    return invoice.id


def receivable_for_period(
    db_session: Session, *, gym_id: str, period: str
) -> PlatformReceivable:
    return db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_id),
            PlatformReceivable.source_type == "SUBSCRIPTION",
            PlatformReceivable.source_key.like(f"%:{period}"),
        )
    ).one()


def gym_report(
    client: TestClient,
    headers: dict[str, str],
    *,
    gym_id: str,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/platform/reports/gyms/{gym_id}",
        headers=headers,
        params={"from_date": from_date, "to_date": to_date},
    )
    assert response.status_code == 200, response.text
    return response.json()


def overview(
    client: TestClient,
    headers: dict[str, str],
    *,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    response = client.get(
        "/api/v1/platform/reports/overview",
        headers=headers,
        params={"from_date": from_date, "to_date": to_date},
    )
    assert response.status_code == 200, response.text
    return response.json()


def export_detail(
    client: TestClient,
    headers: dict[str, str],
    *,
    gym_id: str,
    from_date: str,
    to_date: str,
) -> tuple[list[list[str]], dict[str, int]]:
    response = client.get(
        f"/api/v1/platform/gyms/{gym_id}/export",
        headers=headers,
        params={"from_date": from_date, "to_date": to_date},
    )
    assert response.status_code == 200, response.text
    rows = csv_rows(response.text)
    assert rows[0][-1] == "date_basis"
    metrics = {
        row[1]: int(row[2])
        for row in rows[1:]
        if len(row) >= 4 and row[1] not in {"metric_family"}
    }
    return rows, metrics


def test_platform_per_gym_report_and_export_reconcile_across_periods(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym_a, owner_a = make_owner(
        client, superuser_headers, name="History Platform A"
    )
    gym_b, _owner_b = make_owner(
        client, superuser_headers, name="History Platform B"
    )
    gym_a_id = str(gym_a["id"])
    gym_b_id = str(gym_b["id"])
    agreement_a = subscription_agreement(
        client, superuser_headers, gym_a_id, amount=500_000
    )
    agreement_b = subscription_agreement(
        client, superuser_headers, gym_b_id, amount=300_000
    )
    for agreement in (agreement_a, agreement_b):
        for period in ("2026-11", "2026-12"):
            assert (
                accrue(
                    client,
                    superuser_headers,
                    agreement["id"],
                    period,
                ).status_code
                == 200
            )

    nov_a = receivable_for_period(db_session, gym_id=gym_a_id, period="2026-11")
    dec_a = receivable_for_period(db_session, gym_id=gym_a_id, period="2026-12")
    nov_b = receivable_for_period(db_session, gym_id=gym_b_id, period="2026-11")
    dec_b = receivable_for_period(db_session, gym_id=gym_b_id, period="2026-12")
    invoice_nov_a = insert_invoice_for_receivable(
        db_session,
        gym_id=gym_a_id,
        receivable=nov_a,
        issued_on=date(2026, 11, 5),
    )
    insert_invoice_for_receivable(
        db_session,
        gym_id=gym_a_id,
        receivable=dec_a,
        issued_on=date(2026, 12, 5),
    )
    insert_invoice_for_receivable(
        db_session,
        gym_id=gym_b_id,
        receivable=nov_b,
        issued_on=date(2026, 11, 5),
    )
    invoice_dec_b = insert_invoice_for_receivable(
        db_session,
        gym_id=gym_b_id,
        receivable=dec_b,
        issued_on=date(2026, 12, 5),
    )

    payment_a = client.post(
        f"/api/v1/platform/invoices/{invoice_nov_a}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 200_000,
            "method": "TRANSFER",
            "received_on": "2026-11-20",
        },
    )
    assert payment_a.status_code == 200, payment_a.text
    payment_b = client.post(
        f"/api/v1/platform/invoices/{invoice_dec_b}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 100_000,
            "method": "TRANSFER",
            "received_on": "2026-12-10",
        },
    )
    assert payment_b.status_code == 200, payment_b.text

    cost_a = client.post(
        "/api/v1/platform/costs",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_a_id,
            "category": "hosting",
            "amount_irr": 50_000,
            "incurred_on": "2026-11-15",
        },
    )
    assert cost_a.status_code == 200, cost_a.text
    cost_b = client.post(
        "/api/v1/platform/costs",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_b_id,
            "category": "hosting",
            "amount_irr": 20_000,
            "incurred_on": "2026-12-05",
        },
    )
    assert cost_b.status_code == 200, cost_b.text

    ranges = (
        ("2026-11-01", "2026-11-30"),
        ("2026-12-01", "2026-12-31"),
        ("2026-11-01", "2026-12-31"),
    )
    for from_date, to_date in ranges:
        platform = overview(
            client,
            superuser_headers,
            from_date=from_date,
            to_date=to_date,
        )
        by_gym = {str(row["gym_id"]): row for row in platform["by_gym"]}
        detail_a = gym_report(
            client,
            superuser_headers,
            gym_id=gym_a_id,
            from_date=from_date,
            to_date=to_date,
        )
        detail_b = gym_report(
            client,
            superuser_headers,
            gym_id=gym_b_id,
            from_date=from_date,
            to_date=to_date,
        )
        assert detail_a == by_gym[gym_a_id]
        assert detail_b == by_gym[gym_b_id]
        assert platform["recognized_platform_revenue_irr"] == sum(
            row["recognized_revenue_irr"] for row in platform["by_gym"]
        )
        assert platform["collected_fees_irr"] == sum(
            row["collected_fees_irr"] for row in platform["by_gym"]
        )
        assert platform["receivable_irr"] == sum(
            row["receivable_irr"] for row in platform["by_gym"]
        )
        assert platform["overdue_irr"] == sum(
            row["overdue_irr"] for row in platform["by_gym"]
        )
        assert platform["recorded_platform_costs_irr"] == sum(
            row["recorded_cost_irr"] for row in platform["by_gym"]
        )

        rows_a, metrics_a = export_detail(
            client,
            superuser_headers,
            gym_id=gym_a_id,
            from_date=from_date,
            to_date=to_date,
        )
        rows_b, metrics_b = export_detail(
            client,
            superuser_headers,
            gym_id=gym_b_id,
            from_date=from_date,
            to_date=to_date,
        )
        assert metrics_a["recognized_revenue_irr"] == detail_a["recognized_revenue_irr"]
        assert metrics_a["collected_fees_irr"] == detail_a["collected_fees_irr"]
        assert metrics_a["receivable_irr"] == detail_a["receivable_irr"]
        assert metrics_a["overdue_irr"] == detail_a["overdue_irr"]
        assert metrics_a["recorded_cost_irr"] == detail_a["recorded_cost_irr"]
        assert metrics_a["contribution_irr"] == detail_a["contribution_irr"]
        assert metrics_b["recognized_revenue_irr"] == detail_b["recognized_revenue_irr"]
        assert metrics_b["collected_fees_irr"] == detail_b["collected_fees_irr"]
        assert metrics_b["receivable_irr"] == detail_b["receivable_irr"]
        assert metrics_b["overdue_irr"] == detail_b["overdue_irr"]
        assert metrics_b["recorded_cost_irr"] == detail_b["recorded_cost_irr"]
        assert metrics_b["contribution_irr"] == detail_b["contribution_irr"]
        assert rows_a[0][-1] == "date_basis"
        assert rows_b[0][-1] == "date_basis"
        assert {
            row[1]: row[3]
            for row in rows_a[1:]
            if len(row) >= 4
        }["recognized_revenue_irr"] == "range"
        assert {
            row[1]: row[3]
            for row in rows_a[1:]
            if len(row) >= 4
        }["receivable_irr"] == "as_of_to_date"

        platform_export = client.get(
            "/api/v1/platform/reports/export",
            headers=superuser_headers,
            params={"from_date": from_date, "to_date": to_date},
        )
        assert platform_export.status_code == 200, platform_export.text
        platform_rows = csv_rows(platform_export.text)
        assert platform_rows[0][-1] == "date_basis"
        contribution = next(
            row
            for row in platform_rows[1:]
            if row[1] == "gym"
            and row[2] == gym_a_id
            and row[3] == "contribution_irr"
        )
        assert int(contribution[4]) == detail_a["contribution_irr"]
        assert contribution[5] == "range"
        balance = next(
            row for row in platform_rows[1:] if row[3] == "receivable_irr"
        )
        assert balance[5] == "as_of_to_date"

        # A's collected cash must never appear in B's per-gym row.
        if (from_date, to_date) == ("2026-11-01", "2026-11-30"):
            assert detail_a["recognized_revenue_irr"] == 500_000
            assert detail_b["recognized_revenue_irr"] == 300_000
            assert detail_a["collected_fees_irr"] == 200_000
            assert detail_b["collected_fees_irr"] == 0
            assert detail_a["recorded_cost_irr"] == 50_000
            assert detail_b["recorded_cost_irr"] == 0
            assert detail_a["receivable_irr"] == 300_000
            assert detail_b["receivable_irr"] == 300_000
        if (from_date, to_date) == ("2026-12-01", "2026-12-31"):
            assert detail_a["recognized_revenue_irr"] == 500_000
            assert detail_b["recognized_revenue_irr"] == 300_000
            assert detail_a["collected_fees_irr"] == 0
            assert detail_b["collected_fees_irr"] == 100_000
            assert detail_a["recorded_cost_irr"] == 0
            assert detail_b["recorded_cost_irr"] == 20_000
            assert detail_a["receivable_irr"] == 800_000
            assert detail_b["receivable_irr"] == 500_000
        if (from_date, to_date) == ("2026-11-01", "2026-12-31"):
            assert detail_a["recognized_revenue_irr"] == 1_000_000
            assert detail_b["recognized_revenue_irr"] == 600_000
            assert detail_a["collected_fees_irr"] == 200_000
            assert detail_b["collected_fees_irr"] == 100_000
            assert detail_a["receivable_irr"] == 800_000
            assert detail_b["receivable_irr"] == 500_000


def test_platform_per_gym_cancellation_and_credit_as_of(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    cancel_gym, _ = make_owner(
        client, superuser_headers, name="History Cancel Per Gym"
    )
    cancel_gym_id = str(cancel_gym["id"])
    cancel_agreement = subscription_agreement(
        client, superuser_headers, cancel_gym_id, amount=500_000
    )
    assert (
        accrue(client, superuser_headers, cancel_agreement["id"]).status_code
        == 200
    )
    cancel_receivable = receivable_for_period(
        db_session, gym_id=cancel_gym_id, period="2026-11"
    )
    insert_invoice_for_receivable(
        db_session,
        gym_id=cancel_gym_id,
        receivable=cancel_receivable,
        issued_on=date(2026, 11, 5),
    )
    invoice_id = db_session.exec(
        select(PlatformInvoice.id).where(
            PlatformInvoice.gym_id == uuid.UUID(cancel_gym_id)
        )
    ).one()
    cancelled = client.post(
        f"/api/v1/platform/invoices/{invoice_id}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "synthetic per-gym cancellation"},
    )
    assert cancelled.status_code == 200, cancelled.text

    before = gym_report(
        client,
        superuser_headers,
        gym_id=cancel_gym_id,
        from_date="2026-11-01",
        to_date=(platform_today() - timedelta(days=1)).isoformat(),
    )
    after = gym_report(
        client,
        superuser_headers,
        gym_id=cancel_gym_id,
        from_date="2026-11-01",
        to_date="2026-11-30",
    )
    assert before["recognized_revenue_irr"] == 500_000
    assert before["receivable_irr"] == 500_000
    assert after["recognized_revenue_irr"] == 500_000
    assert after["receivable_irr"] == 500_000
    overview_after = overview(
        client,
        superuser_headers,
        from_date="2026-11-01",
        to_date="2026-11-30",
    )
    by_gym_after = {
        str(row["gym_id"]): row for row in overview_after["by_gym"]
    }
    assert after == by_gym_after[cancel_gym_id]

    credit_gym, _ = make_owner(
        client, superuser_headers, name="History Credit Per Gym"
    )
    credit_gym_id = str(credit_gym["id"])
    credit_agreement = subscription_agreement(
        client, superuser_headers, credit_gym_id, amount=300_000
    )
    assert (
        accrue(client, superuser_headers, credit_agreement["id"]).status_code
        == 200
    )
    credit_receivable = receivable_for_period(
        db_session, gym_id=credit_gym_id, period="2026-11"
    )
    insert_invoice_for_receivable(
        db_session,
        gym_id=credit_gym_id,
        receivable=credit_receivable,
        issued_on=date(2026, 11, 10),
        credit=100_000,
        paid=100_000,
    )

    before_credit = gym_report(
        client,
        superuser_headers,
        gym_id=credit_gym_id,
        from_date="2026-11-01",
        to_date="2026-11-09",
    )
    credit_period = gym_report(
        client,
        superuser_headers,
        gym_id=credit_gym_id,
        from_date="2026-11-10",
        to_date="2026-11-30",
    )
    combined_credit = gym_report(
        client,
        superuser_headers,
        gym_id=credit_gym_id,
        from_date="2026-11-01",
        to_date="2026-11-30",
    )
    assert before_credit["recognized_revenue_irr"] == 300_000
    assert before_credit["receivable_irr"] == 300_000
    # The credit posts in its own period, so that period contains only the
    # negative adjustment; the combined period nets to the expected revenue.
    assert credit_period["recognized_revenue_irr"] == -100_000
    assert credit_period["receivable_irr"] == 200_000
    assert combined_credit["recognized_revenue_irr"] == 200_000
    assert combined_credit["receivable_irr"] == 200_000
    overview_credit = overview(
        client,
        superuser_headers,
        from_date="2026-11-01",
        to_date="2026-11-30",
    )
    by_gym_credit = {
        str(row["gym_id"]): row for row in overview_credit["by_gym"]
    }
    assert combined_credit == by_gym_credit[credit_gym_id]
