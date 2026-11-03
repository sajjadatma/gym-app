from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_platform_invoices import (
    accrue,
    subscription_agreement,
)


def platform_invoice(
    client: TestClient,
    headers: dict[str, str],
    *,
    gym_id: str,
    due_on: date | None = None,
):
    return client.post(
        "/api/v1/platform/invoices",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_id,
            "period_start": "2026-11-01",
            "period_end": "2026-12-31",
            "due_on": (due_on or date.today()).isoformat(),
        },
    )


def test_overdue_stage_progresses_and_superuser_authority_is_unchanged(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Dues Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    accrued = accrue(client, superuser_headers, agreement["id"])
    assert accrued.status_code == 200, accrued.text
    issued = platform_invoice(
        client, superuser_headers, gym_id=gym_id, due_on=date.today()
    )
    assert issued.status_code == 200, issued.text

    for offset, expected in ((0, "DUE"), (1, "DUE"), (9, "GRACE"), (22, "RESTRICTED")):
        standing = client.get(
            f"/api/v1/platform/dues/{gym_id}",
            headers=superuser_headers,
            params={"as_of": (date.today() + timedelta(days=offset)).isoformat()},
        )
        assert standing.status_code == 200, standing.text
        assert standing.json()["stage"] == expected
        if offset:
            assert standing.json()["overdue_irr"] == 500_000
        else:
            assert standing.json()["overdue_irr"] == 0
            assert standing.json()["open_irr"] == 500_000
        if offset:
            assert standing.json()["informational_restrictions"]

    # A restricted standing never blocks a Superuser write.
    created = client.post(
        "/api/v1/platform/agreements",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_id,
            "mode": "FREE",
            "effective_from": "2026-12-01",
            "terms": [],
        },
    )
    assert created.status_code == 200, created.text


def test_platform_reminders_are_in_app_only_and_list_due_and_overdue(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Reminder Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    assert platform_invoice(
        client, superuser_headers, gym_id=gym_id, due_on=date.today()
    ).status_code == 200
    due_soon = client.get(
        "/api/v1/platform/reminders",
        headers=superuser_headers,
        params={"as_of": date.today().isoformat(), "within_days": 7},
    )
    assert due_soon.status_code == 200, due_soon.text
    assert due_soon.json()["due_soon"]
    reminders = client.get(
        "/api/v1/platform/reminders",
        headers=superuser_headers,
        params={
            "as_of": (date.today() + timedelta(days=1)).isoformat(),
            "within_days": 7,
        },
    )
    assert reminders.status_code == 200, reminders.text
    body = reminders.json()
    assert body["delivery_scope"] == "IN_APP_ONLY"
    assert body["overdue"]
    # The approved proactive delivery requirement remains outstanding.
    assert body["delivery_scope"] != "PROACTIVE"


def test_gym_summary_separates_cashflow_and_accrual_profit(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    import uuid

    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import (
        issued_invoice,
        receipt_payload,
        record_receipt,
    )
    from tests.api.routes.test_platform_fees import commission_agreement

    gym, owner = make_owner(client, superuser_headers, name="Summary Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    commission_agreement(client, superuser_headers, gym_id, percent_bp=1000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    expense = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "اجاره",
            "counterparty": "مالک",
            "amount_irr": 50_000,
            "spent_on": "2026-11-02",
            "paid": True,
            "method": "TRANSFER",
        },
    )
    assert expense.status_code == 200, expense.text
    summary = client.get(
        "/api/v1/finance/reports/summary",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["sales_irr"] == 1_000_000
    assert body["cash_collected_irr"] == 400_000
    assert body["cash_expenses_paid_irr"] == 50_000
    assert body["net_cashflow_irr"] == 350_000
    assert body["recognized_revenue_irr"] == 1_000_000
    assert body["recognized_expenses_irr"] == 90_000
    assert body["estimated_operating_profit_irr"] == 910_000
    assert body["estimated_operating_profit_irr"] != body["net_cashflow_irr"]


def test_platform_overview_separates_cash_from_recognized_revenue(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    import uuid

    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import (
        issued_invoice,
        receipt_payload,
        record_receipt,
    )
    from tests.api.routes.test_platform_fees import commission_agreement

    gym, owner = make_owner(client, superuser_headers, name="Platform Report Gym")
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
    cost = client.post(
        "/api/v1/platform/costs",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_id,
            "category": "hosting",
            "amount_irr": 10_000,
            "incurred_on": "2026-11-03",
        },
    )
    assert cost.status_code == 200, cost.text
    overview = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["zero_plan_mode"] is True
    assert body["mrr_irr"] == 0
    assert body["collected_fees_irr"] == 0
    assert body["recognized_platform_revenue_irr"] == 100_000
    assert body["recorded_platform_costs_irr"] == 10_000
    assert body["estimated_operating_profit_irr"] == 90_000
    assert body["by_gym"][0]["contribution_irr"] == 90_000

    platform_invoice = client.post(
        "/api/v1/platform/invoices",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": gym_id,
            "period_start": "2026-11-01",
            "period_end": "2026-12-31",
            "due_on": "2027-01-15",
        },
    )
    assert platform_invoice.status_code == 200, platform_invoice.text
    payment = client.post(
        f"/api/v1/platform/invoices/{platform_invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 100_000,
            "method": "TRANSFER",
            "received_on": "2026-12-01",
        },
    )
    assert payment.status_code == 200, payment.text
    after = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after["collected_fees_irr"] == 100_000
    assert after["recognized_platform_revenue_irr"] == 100_000


def test_csv_exports_are_tenant_safe_and_keep_history(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:

    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import issued_invoice

    gym, owner = make_owner(client, superuser_headers, name="Export Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    invoice = issued_invoice(client, owner, customer, amount=100_000)
    assert invoice["id"]
    export = client.get(
        "/api/v1/finance/reports/export",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert export.status_code == 200, export.text
    assert export.headers["content-type"].startswith("text/csv")
    assert "BILLING" in export.text
    offboarding = client.get(
        "/api/v1/finance/reports/offboarding-export", headers=owner
    )
    assert offboarding.status_code == 200, offboarding.text
    assert "invoice" in offboarding.text
    denied = client.get(
        "/api/v1/platform/reports/export",
        headers=owner,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert denied.status_code == 403
    allowed = client.get(
        "/api/v1/platform/reports/export",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    )
    assert allowed.status_code == 200, allowed.text
    assert "CASHFLOW" in allowed.text


def test_coach_summary_aggregates_own_gyms_only(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    from tests.api.routes.test_finance_coach_agreements import make_coach
    from tests.api.routes.test_finance_coach_allocations import (
        active_agreement,
        coached_invoice,
    )
    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import receipt_payload, record_receipt

    gym, owner = make_owner(client, superuser_headers, name="Coach Summary Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, coach_headers = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    summary = client.get("/api/v1/finance/my/coach-summary", headers=coach_headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["calculated_irr"] == 300_000
    assert body["reserved_irr"] == 0
    assert body["per_gym"][0]["gym_id"] == gym_id


def test_platform_receivables_and_by_gym_reconcile_after_credit_and_cancel(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    import uuid

    from tests.api.routes.test_finance_coach_refunds import refund
    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import (
        issued_invoice,
        receipt_payload,
        record_receipt,
    )
    from tests.api.routes.test_platform_fees import commission_agreement
    from tests.api.routes.test_platform_invoices import issue_platform_invoice

    gym, owner = make_owner(client, superuser_headers, name="Credit Reconcile Gym")
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
    refund(client, owner, customer, invoice["id"], 300_000)

    def gym_summary() -> dict[str, object]:
        response = client.get(
            "/api/v1/finance/reports/summary",
            headers=owner,
            params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
        )
        assert response.status_code == 200, response.text
        return response.json()

    before = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert before["recognized_platform_revenue_irr"] == 70_000
    assert before["receivable_irr"] == 70_000
    assert before["by_gym"][0]["recognized_revenue_irr"] == 70_000
    assert before["by_gym"][0]["receivable_irr"] == 70_000
    assert before["by_gym"][0]["recognized_revenue_irr"] == before[
        "recognized_platform_revenue_irr"
    ]
    assert gym_summary()["platform_payable_irr"] == 70_000

    first_invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert first_invoice.status_code == 200, first_invoice.text
    assert first_invoice.json()["total_irr"] == 70_000
    assert first_invoice.json()["lines"][0]["credit_irr"] == 30_000
    after_issue = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after_issue["receivable_irr"] == 70_000
    assert gym_summary()["platform_payable_irr"] == 70_000

    cancelled = client.post(
        f"/api/v1/platform/invoices/{first_invoice.json()['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "reissue"},
    )
    assert cancelled.status_code == 200, cancelled.text
    after_cancel = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after_cancel["receivable_irr"] == 70_000
    assert after_cancel["by_gym"][0]["receivable_irr"] == 70_000
    # The replacement credit for the cancelled invoice must not be
    # subtracted from recognized revenue a second time.
    assert after_cancel["recognized_platform_revenue_irr"] == 70_000
    assert after_cancel["by_gym"][0]["recognized_revenue_irr"] == 70_000
    assert after_cancel["invoiced_fees_irr"] == 0
    assert gym_summary()["platform_payable_irr"] == 70_000

    second_invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert second_invoice.status_code == 200, second_invoice.text
    partial = client.post(
        f"/api/v1/platform/invoices/{second_invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 40_000,
            "method": "CASH",
            "received_on": "2026-12-01",
        },
    )
    assert partial.status_code == 200, partial.text
    after_partial = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after_partial["receivable_irr"] == 30_000
    assert gym_summary()["platform_payable_irr"] == 30_000
    final = client.post(
        f"/api/v1/platform/invoices/{second_invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 30_000,
            "method": "CASH",
            "received_on": "2026-12-02",
        },
    )
    assert final.status_code == 200, final.text
    after_final = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after_final["receivable_irr"] == 0
    assert after_final["invoiced_fees_irr"] == 70_000
    assert gym_summary()["platform_payable_irr"] == 0


def test_platform_overview_does_not_cross_net_credit_between_gyms(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    from sqlmodel import select

    from app.platform_models import PlatformReceivable
    from tests.api.routes.test_finance_coach_refunds import refund
    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import (
        issued_invoice,
        receipt_payload,
        record_receipt,
    )
    from tests.api.routes.test_platform_fees import commission_agreement
    from tests.api.routes.test_platform_invoices import issue_platform_invoice

    # Gym A: settle its platform invoice, then refund the athlete fee so it
    # holds unused credit with no open receivable.
    gym_a, owner_a = make_owner(client, superuser_headers, name="Credit A Gym")
    gym_a_id = str(gym_a["id"])
    customer_a = make_customer(client, owner_a, gym_a_id)
    commission_agreement(client, superuser_headers, gym_a_id, percent_bp=1000)
    athlete_invoice_a = issued_invoice(client, owner_a, customer_a, amount=1_000_000)
    receipt_a = record_receipt(
        client,
        owner_a,
        receipt_payload(
            customer_a,
            amount=1_000_000,
            allocations=[(athlete_invoice_a["id"], 1_000_000)],
        ),
    )
    assert receipt_a.status_code == 200, receipt_a.text
    platform_invoice_a = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_a_id
    )
    assert platform_invoice_a.status_code == 200, platform_invoice_a.text
    assert platform_invoice_a.json()["total_irr"] == 100_000
    settled = client.post(
        f"/api/v1/platform/invoices/{platform_invoice_a.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 100_000,
            "method": "CASH",
            "received_on": date.today().isoformat(),
        },
    )
    assert settled.status_code == 200, settled.text
    refund(client, owner_a, customer_a, athlete_invoice_a["id"], 300_000)

    # Gym B has an overdue open receivable and no credit.
    gym_b, owner_b = make_owner(client, superuser_headers, name="Credit B Gym")
    gym_b_id = str(gym_b["id"])
    customer_b = make_customer(client, owner_b, gym_b_id)
    commission_agreement(client, superuser_headers, gym_b_id, percent_bp=1000)
    athlete_invoice_b = issued_invoice(client, owner_b, customer_b, amount=1_000_000)
    receipt_b = record_receipt(
        client,
        owner_b,
        receipt_payload(
            customer_b,
            amount=1_000_000,
            allocations=[(athlete_invoice_b["id"], 1_000_000)],
        ),
    )
    assert receipt_b.status_code == 200, receipt_b.text
    receivable_b = db_session.exec(
        select(PlatformReceivable).where(
            PlatformReceivable.gym_id == uuid.UUID(gym_b_id)
        )
    ).one()
    receivable_b.due_on = date.today() - timedelta(days=5)
    db_session.add(receivable_b)
    db_session.commit()

    overview = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    by_gym = {row["gym_id"]: row for row in overview["by_gym"]}
    assert by_gym[gym_a_id]["receivable_irr"] == 0
    assert by_gym[gym_b_id]["receivable_irr"] == 100_000
    assert by_gym[gym_b_id]["overdue_irr"] == 100_000
    assert overview["receivable_irr"] == 100_000
    assert overview["overdue_irr"] == 100_000
    assert overview["receivable_irr"] == sum(
        row["receivable_irr"] for row in overview["by_gym"]
    )
    assert overview["overdue_irr"] == sum(
        row["overdue_irr"] for row in overview["by_gym"]
    )


def test_platform_standing_is_current_when_credit_covers_overdue_invoice(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    from tests.api.routes.test_finance_coach_refunds import refund
    from tests.api.routes.test_finance_foundation import make_owner
    from tests.api.routes.test_finance_invoices import make_customer
    from tests.api.routes.test_finance_receipts import (
        issued_invoice,
        receipt_payload,
        record_receipt,
    )
    from tests.api.routes.test_platform_fees import commission_agreement

    gym, owner = make_owner(client, superuser_headers, name="Standing Credit Gym")
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
    issued = platform_invoice(
        client, superuser_headers, gym_id=gym_id, due_on=date.today()
    )
    assert issued.status_code == 200, issued.text
    refund(client, owner, customer, invoice["id"], 1_000_000)

    standing = client.get(
        f"/api/v1/platform/dues/{gym_id}",
        headers=superuser_headers,
        params={"as_of": (date.today() + timedelta(days=22)).isoformat()},
    )
    assert standing.status_code == 200, standing.text
    body = standing.json()
    assert body["open_irr"] == 0
    assert body["overdue_irr"] == 0
    assert body["stage"] == "CURRENT"
    assert body["informational_restrictions"] == []


def test_group_volume_discount_reconciles_gym_and_platform_reports(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
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
    from tests.api.routes.test_platform_fees import commission_agreement
    from tests.api.routes.test_platform_invoices import (
        activate,
        issue_platform_invoice,
    )

    gym, owner = make_owner(client, superuser_headers, name="Discount Gym")
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
    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Discount Group",
            "members": [{"gym_id": gym_id, "allocation_bp": 10000}],
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
    body = issued.json()
    assert body["discount_irr"] == 5_000
    assert body["total_irr"] == 95_000
    overview = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert overview["recognized_platform_revenue_irr"] == 95_000
    assert overview["by_gym"][0]["recognized_revenue_irr"] == 95_000
    assert overview["invoiced_fees_irr"] == 95_000

    cancelled = client.post(
        f"/api/v1/platform/invoices/{body['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "discount reissue"},
    )
    assert cancelled.status_code == 200, cancelled.text
    after = client.get(
        "/api/v1/platform/reports/overview",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-12-31"},
    ).json()
    assert after["recognized_platform_revenue_irr"] == 100_000
    assert after["by_gym"][0]["recognized_revenue_irr"] == 100_000
    assert after["invoiced_fees_irr"] == 0
