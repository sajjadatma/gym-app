from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

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
            "paid": False,
        },
    )
    assert expense.status_code == 200, expense.text
    paid = client.post(
        f"/api/v1/finance/expenses/{expense.json()['id']}/pay",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"paid_on": "2026-11-03", "method": "TRANSFER"},
    )
    assert paid.status_code == 200, paid.text
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
