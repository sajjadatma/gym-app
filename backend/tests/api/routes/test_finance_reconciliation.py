from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_coach_agreements import make_coach
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def statement_line(
    client: TestClient,
    owner: dict[str, str],
    *,
    amount: int,
    key: str | None = None,
) -> Any:
    return client.post(
        "/api/v1/finance/reconciliation",
        headers={**owner, "Idempotency-Key": key or uuid.uuid4().hex},
        json={
            "statement_on": "2026-11-07",
            "amount_irr": amount,
            "reference": "BANK-1",
            "description": "bank deposit",
        },
    )


def test_unmatched_statement_lines_remain_visible_and_match_distinctly(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Reconciliation Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    invoice = issued_invoice(client, owner, customer, amount=100_000)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=100_000, allocations=[(invoice["id"], 100_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    receipt_id = receipt.json()["id"]

    key = uuid.uuid4().hex
    line = statement_line(client, owner, amount=100_000, key=key)
    assert line.status_code == 200, line.text
    repeated = statement_line(client, owner, amount=100_000, key=key)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == line.json()["id"]

    unmatched = statement_line(client, owner, amount=75_000)
    assert unmatched.status_code == 200
    listed = client.get(
        "/api/v1/finance/reconciliation?status=UNMATCHED", headers=owner
    )
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()["data"]} >= {
        line.json()["id"],
        unmatched.json()["id"],
    }

    matched = client.post(
        f"/api/v1/finance/reconciliation/{line.json()['id']}/match",
        headers=owner,
        json={"receipt_id": receipt_id},
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["status"] == "MATCHED"
    assert matched.json()["receipt_number"] == receipt.json()["receipt_number"]
    fetched_receipt = client.get(
        f"/api/v1/finance/receipts/{receipt_id}", headers=owner
    ).json()
    assert fetched_receipt["reconciled"] is True
    # Confirmation is not reconciliation: the receipt was already confirmed.
    assert fetched_receipt["status"] == "CONFIRMED"

    # Retry is idempotent for the same receipt.
    assert (
        client.post(
            f"/api/v1/finance/reconciliation/{line.json()['id']}/match",
            headers=owner,
            json={"receipt_id": receipt_id},
        ).status_code
        == 200
    )

    mismatch = client.post(
        f"/api/v1/finance/reconciliation/{unmatched.json()['id']}/match",
        headers=owner,
        json={"receipt_id": receipt_id},
    )
    assert mismatch.status_code == 400, mismatch.text
    assert mismatch.json()["detail"] == "reconciliation_amount_mismatch"

    second_line = statement_line(client, owner, amount=100_000)
    duplicate = client.post(
        f"/api/v1/finance/reconciliation/{second_line.json()['id']}/match",
        headers=owner,
        json={"receipt_id": receipt_id},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"] == "reconciliation_already_matched"

    coach_id, coach_headers = make_coach(client, owner, gym_id)
    forbidden = client.get(
        "/api/v1/finance/reconciliation", headers=coach_headers
    )
    assert forbidden.status_code == 403, forbidden.text
