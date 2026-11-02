from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_invoices import (
    make_customer,
)
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def refund_request(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    key: str | None = None,
) -> Any:
    return client.post(
        "/api/v1/finance/refunds",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json=payload,
    )


def refund_transition(
    client: TestClient,
    headers: dict[str, str],
    refund_id: str,
    action: str,
    *,
    body: dict[str, Any] | None = None,
    key: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/finance/refunds/{refund_id}/{action}",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json=body or {},
    )


def test_invoice_refund_records_a_linked_reversal_of_collected_money(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund Invoice Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    assert (
        record_receipt(
            client,
            owner,
            receipt_payload(
                customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
            ),
        ).status_code
        == 200
    )

    requested = refund_request(
        client,
        owner,
        {
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 300_000,
            "reason": "Customer cancelled one session",
        },
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "REQUESTED"
    assert requested.json()["method"] == "CASH"
    assert requested.json()["original_method"] == "CASH"
    assert requested.json()["method_override_reason"] is None

    approved = refund_transition(client, owner, requested.json()["id"], "approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    recorded = refund_transition(
        client,
        owner,
        requested.json()["id"],
        "record",
        body={"posting_date": "2026-11-10"},
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["status"] == "RECORDED"

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(
        item for item in entries if item["event_type"] == "REFUND_RECORDED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("4100", 300_000, 0), ("1000", 0, 300_000)}

    # The refundable ceiling is the collected amount minus recorded refunds.
    too_much = refund_request(
        client,
        owner,
        {
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 800_000,
            "method": "CASH",
            "reason": "Over refund",
        },
    )
    assert too_much.status_code == 400, too_much.text
    assert too_much.json()["detail"] == "refund_exceeds_refundable"


def test_advance_refund_reduces_the_customer_advance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund Advance Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)
    record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=700_000, allocations=[(invoice["id"], 500_000)]),
    )

    requested = refund_request(
        client,
        owner,
        {
            "source": "ADVANCE",
            "customer_user_id": customer,
            "amount_irr": 200_000,
            "method": "CASH",
            "reason": "Unused deposit returned",
        },
    )
    assert requested.status_code == 200, requested.text
    assert refund_transition(client, owner, requested.json()["id"], "approve").status_code == 200
    recorded = refund_transition(
        client,
        owner,
        requested.json()["id"],
        "record",
        body={"posting_date": "2026-11-11"},
    )
    assert recorded.status_code == 200, recorded.text

    assert client.get("/api/v1/finance/credits", headers=owner).json()["count"] == 0
    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(
        item for item in entries if item["event_type"] == "REFUND_RECORDED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("2000", 200_000, 0), ("1000", 0, 200_000)}


def test_refunds_cannot_be_recorded_twice_or_cross_tenant(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund State Gym")
    _other_gym, other_owner = make_owner(client, superuser_headers, name="Refund Other Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=200_000)
    record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=200_000, allocations=[(invoice["id"], 200_000)]),
    )
    requested = refund_request(
        client,
        owner,
        {
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 100_000,
            "method": "CASH",
            "reason": "Partial refund",
        },
    ).json()

    assert refund_transition(client, other_owner, requested["id"], "approve").status_code == 404
    assert (
        refund_transition(
            client,
            owner,
            requested["id"],
            "record",
            body={"posting_date": "2026-11-12"},
        ).status_code
        == 409
    )
    assert refund_transition(client, owner, requested["id"], "approve").status_code == 200
    first = refund_transition(
        client, owner, requested["id"], "record", body={"posting_date": "2026-11-12"}
    )
    assert first.status_code == 200, first.text
    twice = refund_transition(
        client, owner, requested["id"], "record", body={"posting_date": "2026-11-12"}
    )
    assert twice.status_code == 409, twice.text


def test_refund_requires_the_refund_permission(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund Permission Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=100_000)
    record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=100_000, allocations=[(invoice["id"], 100_000)]),
    )
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    payload = {
        "source": "INVOICE",
        "customer_user_id": customer,
        "invoice_id": invoice["id"],
        "amount_irr": 50_000,
        "method": "CASH",
        "reason": "Refund",
    }
    denied = refund_request(client, staff, payload)
    assert denied.status_code == 403, denied.text
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    assert (
        client.put(
            f"/api/v1/finance/grants/{staff_id}",
            headers=owner,
            json={"grants": [{"permission": "finance.refund.manage"}]},
        ).status_code
        == 200
    )
    assert refund_request(client, staff, payload).status_code == 200


def test_expenses_distinguish_unpaid_paid_and_repeat_safely(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Expense Gym")

    unpaid = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "اجاره",
            "counterparty": "مالک ساختمان",
            "amount_irr": 5_000_000,
            "spent_on": "2026-11-01",
            "paid": False,
        },
    )
    assert unpaid.status_code == 200, unpaid.text
    assert unpaid.json()["status"] == "UNPAID"

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    accrued = next(
        item for item in entries if item["event_type"] == "EXPENSE_RECORDED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in accrued["lines"]
    } == {("5000", 5_000_000, 0), ("2000", 0, 5_000_000)}

    paid = client.post(
        f"/api/v1/finance/expenses/{unpaid.json()['id']}/pay",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"paid_on": "2026-11-02", "method": "TRANSFER"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "PAID"
    again = client.post(
        f"/api/v1/finance/expenses/{unpaid.json()['id']}/pay",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={"paid_on": "2026-11-02", "method": "TRANSFER"},
    )
    assert again.status_code == 409, again.text
    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    payment = next(item for item in entries if item["event_type"] == "EXPENSE_PAID")
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in payment["lines"]
    } == {("2000", 5_000_000, 0), ("1000", 0, 5_000_000)}

    repeated = client.post(
        f"/api/v1/finance/expenses/{unpaid.json()['id']}/repeat",
        headers=owner,
        json={"spent_on": "2026-12-01"},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["status"] == "UNPAID"
    assert repeated.json()["amount_irr"] == 5_000_000

    duplicate = client.post(
        f"/api/v1/finance/expenses/{unpaid.json()['id']}/repeat",
        headers=owner,
        json={"spent_on": "2026-12-01"},
    )
    assert duplicate.status_code == 409, duplicate.text


def test_paid_expense_at_creation_posts_cash_immediately(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Paid Expense Gym")
    created = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "آب و برق",
            "amount_irr": 300_000,
            "spent_on": "2026-11-05",
            "paid": True,
            "method": "CASH",
        },
    )
    assert created.status_code == 200, created.text
    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(item for item in entries if item["event_type"] == "EXPENSE_RECORDED")
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("5000", 300_000, 0), ("1000", 0, 300_000)}

    missing_method = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "آب و برق",
            "amount_irr": 300_000,
            "spent_on": "2026-11-05",
            "paid": True,
        },
    )
    assert missing_method.status_code == 400, missing_method.text
    assert missing_method.json()["detail"] == "finance_expense_method_required"


def test_expenses_are_permissioned_and_tenant_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Expense Scope Gym")
    _other_gym, other_owner = make_owner(client, superuser_headers, name="Expense Other Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    payload = {
        "category": "نظافت",
        "amount_irr": 100_000,
        "spent_on": "2026-11-05",
        "paid": False,
    }
    denied = client.post(
        "/api/v1/finance/expenses",
        headers={**staff, "Idempotency-Key": uuid.uuid4().hex},
        json=payload,
    )
    assert denied.status_code == 403, denied.text

    allowed = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json=payload,
    )
    assert allowed.status_code == 200, allowed.text
    assert client.get("/api/v1/finance/expenses", headers=other_owner).json()["count"] == 0
    assert client.get(
        f"/api/v1/finance/expenses/{allowed.json()['id']}", headers=other_owner
    ).status_code == 404


def test_disabled_finance_blocks_expense_postings_but_not_refund_requests(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Disabled Expense Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=100_000)
    record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=100_000, allocations=[(invoice["id"], 100_000)]),
    )
    assert (
        client.patch(
            "/api/v1/finance/settings",
            headers={**superuser_headers, "X-Gym-ID": str(gym["id"])},
            json={"enabled": False},
        ).status_code
        == 200
    )

    expense = client.post(
        "/api/v1/finance/expenses",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "category": "اجاره",
            "amount_irr": 100_000,
            "spent_on": "2026-11-05",
            "paid": False,
        },
    )
    assert expense.status_code == 409, expense.text
    assert expense.json()["detail"] == "finance_disabled"

    request = refund_request(
        client,
        owner,
        {
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 50_000,
            "method": "CASH",
            "reason": "Disabled request",
        },
    )
    assert request.status_code == 200, request.text
    assert refund_transition(client, owner, request.json()["id"], "approve").status_code == 200
    blocked = refund_transition(
        client,
        owner,
        request.json()["id"],
        "record",
        body={"posting_date": "2026-11-12"},
    )
    assert blocked.status_code == 409, blocked.text
