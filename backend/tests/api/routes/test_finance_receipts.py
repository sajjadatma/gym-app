from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_invoices import (
    create_draft,
    invoice_payload,
    issue,
    make_customer,
)

pytestmark = pytest.mark.usefixtures("client")


def receipt_payload(
    customer_id: str,
    *,
    amount: int,
    allocations: list[tuple[str, int]] | None = None,
    method: str = "CASH",
) -> dict[str, Any]:
    return {
        "customer_user_id": customer_id,
        "method": method,
        "amount_irr": amount,
        "reference": "REF-1",
        "received_on": "2026-11-05",
        "allocations": [
            {"invoice_id": invoice_id, "amount_irr": value}
            for invoice_id, value in (allocations or [])
        ],
    }


def record_receipt(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    key: str | None = None,
) -> Any:
    return client.post(
        "/api/v1/finance/receipts",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json=payload,
    )


def issued_invoice(
    client: TestClient,
    owner: dict[str, str],
    customer: str,
    *,
    amount: int = 1_000_000,
) -> dict[str, Any]:
    draft = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            lines=[
                {
                    "kind": "PROGRAM",
                    "description": "Program",
                    "quantity": 1,
                    "unit_price_irr": amount,
                }
            ],
        ),
    )
    assert draft.status_code == 200, draft.text
    issued = issue(client, owner, draft.json()["id"])
    assert issued.status_code == 200, issued.text
    return issued.json()


def test_partial_receipt_reduces_the_invoice_balance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Receipt Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer)

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 400_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()
    assert body["receipt_number"] == 1
    assert body["amount_irr"] == 400_000
    assert body["allocated_irr"] == 400_000
    assert body["excess_irr"] == 0
    assert body["status"] == "CONFIRMED"
    assert body["verification_source"] == "STAFF_ATTESTATION"
    assert body["reconciled"] is False

    refreshed = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()
    assert refreshed["paid_irr"] == 400_000
    assert refreshed["balance_irr"] == 600_000

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(
        item for item in entries if item["event_type"] == "RECEIPT_CONFIRMED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("1000", 400_000, 0), ("1100", 0, 400_000)}


def test_one_receipt_covers_two_invoices_of_the_same_customer(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Split Receipt Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    first = issued_invoice(client, owner, customer, amount=300_000)
    second = issued_invoice(client, owner, customer, amount=500_000)

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=600_000,
            allocations=[(first["id"], 300_000), (second["id"], 300_000)],
        ),
    )
    assert receipt.status_code == 200, receipt.text
    assert len(receipt.json()["allocations"]) == 2

    first_state = client.get(
        f"/api/v1/finance/invoices/{first['id']}", headers=owner
    ).json()
    second_state = client.get(
        f"/api/v1/finance/invoices/{second['id']}", headers=owner
    ).json()
    assert first_state["balance_irr"] == 0
    assert second_state["balance_irr"] == 200_000


def test_over_allocation_and_over_payment_of_an_invoice_are_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Overpay Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)

    over_receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=400_000, allocations=[(invoice["id"], 500_000)]
        ),
    )
    assert over_receipt.status_code == 400, over_receipt.text
    assert over_receipt.json()["detail"] == "receipt_over_allocated"

    over_invoice = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=600_000, allocations=[(invoice["id"], 600_000)]
        ),
    )
    assert over_invoice.status_code == 400, over_invoice.text
    assert over_invoice.json()["detail"] == "receipt_allocation_exceeds_invoice"

    assert client.get("/api/v1/finance/receipts", headers=owner).json()["count"] == 0


def test_excess_payment_becomes_a_same_gym_customer_advance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Advance Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)

    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_200_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["excess_irr"] == 200_000

    credits = client.get("/api/v1/finance/credits", headers=owner)
    assert credits.status_code == 200, credits.text
    assert credits.json()["count"] == 1
    assert credits.json()["data"][0]["customer_user_id"] == customer
    assert credits.json()["data"][0]["balance_irr"] == 200_000

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(
        item for item in entries if item["event_type"] == "RECEIPT_CONFIRMED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {
        ("1000", 1_200_000, 0),
        ("1100", 0, 1_000_000),
        ("2000", 0, 200_000),
    }


def test_advance_can_pay_a_later_invoice_and_cannot_exceed_it(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Apply Advance Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    first = issued_invoice(client, owner, customer, amount=500_000)
    record_receipt(
        client,
        owner,
        receipt_payload(customer, amount=700_000, allocations=[(first["id"], 500_000)]),
    )
    later = issued_invoice(client, owner, customer, amount=300_000)

    too_much = client.post(
        "/api/v1/finance/credits/apply",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "invoice_id": later["id"],
            "amount_irr": 300_000,
            "received_on": "2026-11-06",
        },
    )
    assert too_much.status_code == 400, too_much.text
    assert too_much.json()["detail"] == "insufficient_customer_credit"

    applied = client.post(
        "/api/v1/finance/credits/apply",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "customer_user_id": customer,
            "invoice_id": later["id"],
            "amount_irr": 200_000,
            "received_on": "2026-11-06",
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["paid_irr"] == 200_000
    assert applied.json()["balance_irr"] == 100_000

    credits = client.get("/api/v1/finance/credits", headers=owner).json()
    assert credits["count"] == 0

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    entry = next(
        item for item in entries if item["event_type"] == "ADVANCE_APPLIED"
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("2000", 200_000, 0), ("1100", 0, 200_000)}


def test_a_receipt_cannot_pay_another_customers_invoice(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Mismatch Gym")
    first_customer = make_customer(client, owner, str(gym["id"]), prefix="first")
    second_customer = make_customer(client, owner, str(gym["id"]), prefix="second")
    invoice = issued_invoice(client, owner, second_customer, amount=200_000)

    response = record_receipt(
        client,
        owner,
        receipt_payload(
            first_customer, amount=200_000, allocations=[(invoice["id"], 200_000)]
        ),
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "receipt_customer_mismatch"


def test_receipts_are_idempotent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Idempotent Receipt Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)
    payload = receipt_payload(
        customer, amount=500_000, allocations=[(invoice["id"], 500_000)]
    )

    missing = client.post(
        "/api/v1/finance/receipts", headers=owner, json=payload
    )
    assert missing.status_code == 422, missing.text

    key = uuid.uuid4().hex
    first = record_receipt(client, owner, payload, key=key)
    assert first.status_code == 200, first.text
    replay = record_receipt(client, owner, payload, key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]

    changed = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=100_000, allocations=[(invoice["id"], 100_000)]
        ),
        key=key,
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"] == "idempotency_key_reused"
    assert client.get("/api/v1/finance/receipts", headers=owner).json()["count"] == 1


def test_concurrent_receipts_cannot_overpay_the_same_invoice(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Concurrent Receipt Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return record_receipt(
            client,
            owner,
            receipt_payload(
                customer, amount=500_000, allocations=[(invoice["id"], 500_000)]
            ),
            key=f"receipt-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert sorted(response.status_code for response in responses) == [200, 400], [
        response.text for response in responses
    ]
    refreshed = client.get(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=owner
    ).json()
    assert refreshed["paid_irr"] == 500_000
    assert refreshed["balance_irr"] == 0


def test_receipts_respect_payment_permission_and_tenancy(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Receipt Permission Gym")
    _other_gym, other_owner = make_owner(
        client, superuser_headers, name="Receipt Other Gym"
    )
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=100_000)
    payload = receipt_payload(
        customer, amount=100_000, allocations=[(invoice["id"], 100_000)]
    )

    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    denied = record_receipt(client, staff, payload)
    assert denied.status_code == 403, denied.text

    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    assert (
        client.put(
            f"/api/v1/finance/grants/{staff_id}",
            headers=owner,
            json={"grants": [{"permission": "finance.payment.record"}]},
        ).status_code
        == 200
    )
    allowed = record_receipt(client, staff, payload)
    assert allowed.status_code == 200, allowed.text

    assert client.get("/api/v1/finance/receipts", headers=other_owner).json()["count"] == 0
    assert client.get(
        f"/api/v1/finance/receipts/{allowed.json()['id']}", headers=other_owner
    ).status_code == 404


def test_invoice_with_a_confirmed_receipt_cannot_be_voided(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Void Paid Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=200_000)
    assert (
        record_receipt(
            client,
            owner,
            receipt_payload(
                customer, amount=100_000, allocations=[(invoice["id"], 100_000)]
            ),
        ).status_code
        == 200
    )

    from tests.api.routes.test_finance_invoices import void

    blocked = void(client, owner, invoice["id"])
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == "invoice_has_payments"
