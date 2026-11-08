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
    PlatformInvoice,
    PlatformInvoiceLine,
    PlatformReceivable,
)
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
) -> uuid.UUID:
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
        due_on=issued_on + timedelta(days=30),
        status="ISSUED",
        discount_irr=0,
        total_irr=receivable.amount_irr,
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
        credit_irr=0,
        amount_irr=receivable.amount_irr,
        paid_irr=0,
    )
    db_session.add(line)
    receivable.status = "INVOICED"
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
        assert metrics_b["recognized_revenue_irr"] == detail_b["recognized_revenue_irr"]
        assert metrics_b["collected_fees_irr"] == detail_b["collected_fees_irr"]
        assert metrics_b["receivable_irr"] == detail_b["receivable_irr"]
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
