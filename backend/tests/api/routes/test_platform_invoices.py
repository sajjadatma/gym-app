from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import FinanceJournal
from app.platform_models import (
    PlatformInvoice,
    PlatformInvoiceCancellation,
    PlatformInvoiceLineReversal,
    PlatformJournal,
)
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


def activate(client: TestClient, headers: dict[str, str], agreement_id: str) -> None:
    response = client.post(
        f"/api/v1/platform/agreements/{agreement_id}/activate",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text


def subscription_agreement(
    client: TestClient,
    headers: dict[str, str],
    gym_id: str,
    *,
    amount: int = 500_000,
    mode: str = "SUBSCRIPTION",
    terms: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    created = create_platform_agreement(
        client,
        headers,
        gym_id=gym_id,
        mode=mode,
        subscription_amount_irr=amount,
        terms=terms or [],
        effective_from="2026-11-01",
    )
    assert created.status_code == 200, created.text
    activate(client, headers, created.json()["id"])
    return created.json()


def accrue(
    client: TestClient,
    headers: dict[str, str],
    agreement_id: str,
    period: str = "2026-11",
    *,
    key: str | None = None,
):
    return client.post(
        f"/api/v1/platform/agreements/{agreement_id}/accrue-period",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json={"period": period},
    )


def issue_platform_invoice(
    client: TestClient,
    headers: dict[str, str],
    *,
    gym_id: str | None = None,
    group_id: str | None = None,
):
    payload: dict[str, object] = {
        "period_start": "2026-11-01",
        "period_end": "2026-12-31",
        "due_on": "2027-01-15",
    }
    if gym_id is not None:
        payload["gym_id"] = gym_id
    if group_id is not None:
        payload["group_id"] = group_id
    return client.post(
        "/api/v1/platform/invoices",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json=payload,
    )


def test_subscription_accrual_is_month_bounded_idempotent_and_not_fabricated(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Subscription Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    key = uuid.uuid4().hex
    first = accrue(client, superuser_headers, agreement["id"], key=key)
    assert first.status_code == 200, first.text
    assert first.json()["amount_irr"] == 500_000
    replay = accrue(client, superuser_headers, agreement["id"], key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]
    outside = accrue(
        client, superuser_headers, agreement["id"], period="2026-10"
    )
    assert outside.status_code == 400, outside.text
    assert outside.json()["detail"] == "platform_period_outside_agreement"

    commission_gym, _ = make_owner(
        client, superuser_headers, name="No Subscription Accrual"
    )
    commission = create_platform_agreement(
        client,
        superuser_headers,
        gym_id=str(commission_gym["id"]),
        mode="COMMISSION",
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert commission.status_code == 200, commission.text
    activate(client, superuser_headers, commission.json()["id"])
    no_subscription = accrue(
        client, superuser_headers, commission.json()["id"]
    )
    assert no_subscription.status_code == 400, no_subscription.text
    assert (
        no_subscription.json()["detail"] == "platform_subscription_not_configured"
    )
    assert (
        client.get("/api/v1/platform/plans", headers=superuser_headers).json()[
            "data"
        ]
        == []
    )


def test_group_invoice_keeps_branch_lines_and_volume_discount(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    created_owners = [
        make_owner(client, superuser_headers, name=f"Invoice Group {index}")
        for index in range(3)
    ]
    gyms = [pair[0] for pair in created_owners]
    owners = [pair[1] for pair in created_owners]
    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Invoice Group",
            "members": [
                {"gym_id": str(gyms[0]["id"]), "allocation_bp": 3334},
                {"gym_id": str(gyms[1]["id"]), "allocation_bp": 3333},
                {"gym_id": str(gyms[2]["id"]), "allocation_bp": 3333},
            ],
        },
    )
    assert group.status_code == 200, group.text
    group_id = group.json()["id"]
    group_agreement = create_platform_agreement(
        client,
        superuser_headers,
        group_id=group_id,
        mode="HYBRID",
        subscription_amount_irr=100_000,
        volume_discount_bp=500,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert group_agreement.status_code == 200, group_agreement.text
    activate(client, superuser_headers, group_agreement.json()["id"])

    for gym, owner in zip(gyms, owners, strict=True):
        gym_id = str(gym["id"])
        customer = make_customer(client, owner, gym_id)
        commission = create_platform_agreement(
            client,
            superuser_headers,
            gym_id=gym_id,
            mode="COMMISSION",
            terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
        )
        assert commission.status_code == 200, commission.text
        activate(client, superuser_headers, commission.json()["id"])
        invoice = issued_invoice(client, owner, customer, amount=1_000_000)
        receipt = record_receipt(
            client,
            owner,
            receipt_payload(
                customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
            ),
        )
        assert receipt.status_code == 200, receipt.text

    gym_journals_before = len(
        db_session.exec(select(FinanceJournal)).all()
    )
    issued = issue_platform_invoice(
        client, superuser_headers, group_id=group_id
    )
    assert issued.status_code == 200, issued.text
    body = issued.json()
    assert body["group_id"] == group_id
    assert body["gym_id"] is None
    assert body["discount_irr"] > 0
    assert len(body["lines"]) == 3
    assert {row["gym_id"] for row in body["lines"]} == {
        str(gym["id"]) for gym in gyms
    }
    assert sum(row["amount_irr"] for row in body["lines"]) == body["total_irr"]
    assert len(db_session.exec(select(FinanceJournal)).all()) == gym_journals_before
    cancelled = client.post(
        f"/api/v1/platform/invoices/{body['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "group invoice error"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"


def test_platform_payment_is_partial_safe_idempotent_and_only_platform_cash(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Payment Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(client, superuser_headers, gym_id, amount=500_000)
    accrued = accrue(client, superuser_headers, agreement["id"])
    assert accrued.status_code == 200, accrued.text
    invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert invoice.status_code == 200, invoice.text
    invoice_id = invoice.json()["id"]
    gym_journals_before = len(db_session.exec(select(FinanceJournal)).all())
    key = uuid.uuid4().hex
    payment = client.post(
        f"/api/v1/platform/invoices/{invoice_id}/payments",
        headers={**superuser_headers, "Idempotency-Key": key},
        json={
            "amount_irr": 200_000,
            "method": "TRANSFER",
            "reference": "BANK-1",
            "received_on": "2026-12-01",
        },
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["amount_irr"] == 200_000
    replay = client.post(
        f"/api/v1/platform/invoices/{invoice_id}/payments",
        headers={**superuser_headers, "Idempotency-Key": key},
        json={
            "amount_irr": 200_000,
            "method": "TRANSFER",
            "reference": "BANK-1",
            "received_on": "2026-12-01",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == payment.json()["id"]
    over = client.post(
        f"/api/v1/platform/invoices/{invoice_id}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 500_000,
            "method": "CASH",
            "received_on": "2026-12-01",
        },
    )
    assert over.status_code == 400, over.text
    assert len(db_session.exec(select(FinanceJournal)).all()) == gym_journals_before
    platform_journal = db_session.exec(select(PlatformJournal)).all()
    assert any(row.event_type == "PLATFORM_PAYMENT" for row in platform_journal)


def test_unpaid_platform_invoice_cancellation_is_append_only_and_reversible(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Cancel Invoice Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(client, superuser_headers, gym_id, amount=500_000)
    accrued = accrue(client, superuser_headers, agreement["id"])
    assert accrued.status_code == 200, accrued.text
    invoice_response = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert invoice_response.status_code == 200, invoice_response.text
    invoice = invoice_response.json()
    original_lines = {
        row["id"]: row["amount_irr"] for row in invoice["lines"]
    }
    key = uuid.uuid4().hex
    cancelled = client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": key},
        json={"reason": "issued in error"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    replay = client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": key},
        json={"reason": "issued in error"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "CANCELLED"
    for row in cancelled.json()["lines"]:
        assert row["amount_irr"] == original_lines[row["id"]]
    stored = db_session.get(PlatformInvoice, uuid.UUID(invoice["id"]))
    assert stored is not None and stored.total_irr == invoice["total_irr"]
    cancellation = db_session.exec(select(PlatformInvoiceCancellation)).one()
    reversals = db_session.exec(
        select(PlatformInvoiceLineReversal).where(
            PlatformInvoiceLineReversal.cancellation_id == cancellation.id
        )
    ).all()
    assert sum(row.amount_irr for row in reversals) == invoice["total_irr"]

    paid_invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert paid_invoice.status_code == 200, paid_invoice.text
    # No receivable remains for a second invoice once the first is cancelled
    # because the subscription receivable is still open; the platform invoice
    # is empty, so pay the first reusable subscription through a new accrual.
    assert paid_invoice.json()["status"] == "ISSUED"
    paid = client.post(
        f"/api/v1/platform/invoices/{paid_invoice.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": paid_invoice.json()["total_irr"],
            "method": "CASH",
            "received_on": "2026-12-01",
        },
    )
    assert paid.status_code == 200, paid.text
    cannot = client.post(
        f"/api/v1/platform/invoices/{paid_invoice.json()['id']}/cancel",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "too late"},
    )
    assert cannot.status_code == 409, cannot.text
    assert cannot.json()["detail"] == "platform_invoice_paid"


def test_partially_paid_receivable_is_not_reinvoiced_or_overcollected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="No Rebill Gym")
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    accrued = accrue(client, superuser_headers, agreement["id"])
    assert accrued.status_code == 200, accrued.text
    first = issue_platform_invoice(client, superuser_headers, gym_id=gym_id)
    assert first.status_code == 200, first.text
    payment = client.post(
        f"/api/v1/platform/invoices/{first.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 200_000,
            "method": "CASH",
            "received_on": "2026-12-01",
        },
    )
    assert payment.status_code == 200, payment.text
    second = issue_platform_invoice(client, superuser_headers, gym_id=gym_id)
    assert second.status_code == 400, second.text
    assert second.json()["detail"] == "platform_invoice_empty"
    remaining = client.post(
        f"/api/v1/platform/invoices/{first.json()['id']}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 300_000,
            "method": "CASH",
            "received_on": "2026-12-02",
        },
    )
    assert remaining.status_code == 200, remaining.text
    assert remaining.json()["invoice_id"] == first.json()["id"]
