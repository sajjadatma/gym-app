from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.finance_models import FinanceCoachSettlement, FinanceJournal
from app.platform_models import (
    PlatformInvoice,
    PlatformInvoiceCancellation,
    PlatformInvoiceLine,
    PlatformJournal,
    PlatformPayment,
)
from tests.api.routes.test_finance_coach_agreements import make_coach
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)
from tests.api.routes.test_finance_refunds_expenses import (
    refund_request,
    refund_transition,
)
from tests.api.routes.test_platform_agreements import (
    create_agreement as create_platform_agreement,
)
from tests.api.routes.test_platform_fees import commission_agreement
from tests.api.routes.test_platform_invoices import (
    accrue,
    activate,
    issue_platform_invoice,
    subscription_agreement,
)

pytestmark = pytest.mark.usefixtures("client")


def _count(session: Session, model: Any, *where: Any) -> int:
    statement = select(func.count()).select_from(model)
    if where:
        statement = statement.where(*where)
    return int(session.exec(statement).one())


def test_concurrent_duplicate_receipt_posts_one_journal(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Concurrent Receipt Key Gym"
    )
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)
    barrier = threading.Barrier(2, timeout=20)
    key = uuid.uuid4().hex

    def attempt(_index: int) -> Any:
        barrier.wait()
        return record_receipt(
            client,
            owner,
            receipt_payload(
                customer,
                amount=500_000,
                allocations=[(invoice["id"], 500_000)],
            ),
            key=key,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert [response.status_code for response in responses] == [200, 200], [
        response.text for response in responses
    ]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert (
        _count(
            db_session,
            FinanceJournal,
            FinanceJournal.gym_id == uuid.UUID(str(gym["id"])),
            FinanceJournal.event_type == "RECEIPT_CONFIRMED",
            FinanceJournal.source_id == uuid.UUID(responses[0].json()["id"]),
        )
        == 1
    )


def test_concurrent_platform_payments_cannot_overpay(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Concurrent Platform Payment Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert invoice.status_code == 200, invoice.text
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return client.post(
            f"/api/v1/platform/invoices/{invoice.json()['id']}/payments",
            headers={**superuser_headers, "Idempotency-Key": f"pay-{index}"},
            json={
                "amount_irr": 400_000,
                "method": "TRANSFER",
                "reference": f"CONCURRENT-{index}",
                "received_on": "2026-12-01",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert sorted(response.status_code for response in responses) == [200, 400], [
        response.text for response in responses
    ]
    assert (
        _count(
            db_session,
            PlatformPayment,
            PlatformPayment.invoice_id == uuid.UUID(invoice.json()["id"]),
        )
        == 1
    )
    assert (
        _count(
            db_session,
            PlatformJournal,
            PlatformJournal.event_type == "PLATFORM_PAYMENT",
        )
        == 1
    )
    refreshed = client.get(
        f"/api/v1/platform/invoices/{invoice.json()['id']}",
        headers=superuser_headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["paid_irr"] == 400_000
    assert refreshed.json()["balance_irr"] == 100_000


def test_concurrent_platform_cancellation_creates_one_cancellation(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Concurrent Cancellation Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
    invoice = issue_platform_invoice(
        client, superuser_headers, gym_id=gym_id
    )
    assert invoice.status_code == 200, invoice.text
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return client.post(
            f"/api/v1/platform/invoices/{invoice.json()['id']}/cancel",
            headers={
                **superuser_headers,
                "Idempotency-Key": f"cancel-{index}",
            },
            json={"reason": "concurrent cancellation"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert [response.status_code for response in responses] == [200, 200], [
        response.text for response in responses
    ]
    assert (
        _count(
            db_session,
            PlatformInvoiceCancellation,
            PlatformInvoiceCancellation.invoice_id
            == uuid.UUID(invoice.json()["id"]),
        )
        == 1
    )
    refreshed = client.get(
        f"/api/v1/platform/invoices/{invoice.json()['id']}",
        headers=superuser_headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["status"] == "CANCELLED"


def test_concurrent_group_invoice_issue_does_not_duplicate_lines(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gyms = []
    for index in range(2):
        gym, owner = make_owner(
            client, superuser_headers, name=f"Concurrent Group Gym {index}"
        )
        gyms.append(gym)
        gym_id = str(gym["id"])
        customer = make_customer(client, owner, gym_id)
        commission_agreement(client, superuser_headers, gym_id, percent_bp=1000)
        invoice = issued_invoice(client, owner, customer, amount=1_000_000)
        receipt = record_receipt(
            client,
            owner,
            receipt_payload(
                customer,
                amount=1_000_000,
                allocations=[(invoice["id"], 1_000_000)],
            ),
        )
        assert receipt.status_code == 200, receipt.text

    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Concurrent Group",
            "members": [
                {"gym_id": str(gyms[0]["id"]), "allocation_bp": 5000},
                {"gym_id": str(gyms[1]["id"]), "allocation_bp": 5000},
            ],
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
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return client.post(
            "/api/v1/platform/invoices",
            headers={
                **superuser_headers,
                "Idempotency-Key": f"group-issue-{index}",
            },
            json={
                "group_id": group.json()["id"],
                "period_start": "2026-11-01",
                "period_end": "2026-12-31",
                "due_on": "2027-01-15",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert sorted(response.status_code for response in responses) == [200, 400], [
        response.text for response in responses
    ]
    assert (
        _count(
            db_session,
            PlatformInvoice,
            PlatformInvoice.group_id == uuid.UUID(group.json()["id"]),
        )
        == 1
    )
    assert (
        _count(
            db_session,
            PlatformInvoiceLine,
            PlatformInvoiceLine.gym_id.in_(
                [uuid.UUID(str(gym["id"])) for gym in gyms]
            ),
        )
        == 2
    )


def test_concurrent_refund_record_posts_one_journal(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Concurrent Refund Gym"
    )
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    requested = refund_request(
        client,
        owner,
        {
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 100_000,
            "reason": "concurrent refund",
        },
    )
    assert requested.status_code == 200, requested.text
    approved = refund_transition(
        client, owner, requested.json()["id"], "approve"
    )
    assert approved.status_code == 200, approved.text
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return refund_transition(
            client,
            owner,
            requested.json()["id"],
            "record",
            body={"posting_date": "2026-11-07"},
            key=f"record-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409], [
        response.text for response in responses
    ]
    assert (
        _count(
            db_session,
            FinanceJournal,
            FinanceJournal.gym_id == uuid.UUID(str(gym["id"])),
            FinanceJournal.event_type == "REFUND_RECORDED",
            FinanceJournal.source_id == uuid.UUID(requested.json()["id"]),
        )
        == 1
    )


def test_concurrent_coach_settlements_cannot_double_pay(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(
        client, superuser_headers, name="Concurrent Settlement Gym"
    )
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _coach_headers = make_coach(client, owner, gym_id)
    active_agreement(client, owner, coach_id, vesting_mode="MANUAL")
    invoice = coached_invoice(
        client, owner, customer, coach_id, amount=1_000_000
    )
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200, receipt.text
    earning = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    ).json()["data"][0]
    vested = client.post(
        f"/api/v1/finance/coach-earnings/{earning['id']}/vest",
        headers=owner,
        json={"reason": "concurrent settlement"},
    )
    assert vested.status_code == 200, vested.text
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return client.post(
            "/api/v1/finance/coach-settlements",
            headers={**owner, "Idempotency-Key": f"settle-{index}"},
            json={
                "coach_user_id": coach_id,
                "amount_irr": 300_000,
                "method": "CASH",
                "reference": f"CONCURRENT-{index}",
                "paid_on": "2026-11-06",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert sorted(response.status_code for response in responses) == [200, 400], [
        response.text for response in responses
    ]
    assert (
        _count(
            db_session,
            FinanceJournal,
            FinanceJournal.gym_id == uuid.UUID(gym_id),
            FinanceJournal.event_type == "COACH_SETTLEMENT",
        )
        == 1
    )
    settlements = db_session.exec(
        select(FinanceCoachSettlement).where(
            FinanceCoachSettlement.gym_id == uuid.UUID(gym_id)
        )
    ).all()
    assert len(settlements) == 1
    assert settlements[0].amount_irr == 300_000


def test_concurrent_subscription_accrual_is_idempotent(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner = make_owner(
        client, superuser_headers, name="Concurrent Accrual Gym"
    )
    gym_id = str(gym["id"])
    agreement = subscription_agreement(
        client, superuser_headers, gym_id, amount=500_000
    )
    barrier = threading.Barrier(2, timeout=20)
    key = uuid.uuid4().hex

    def attempt(_index: int) -> Any:
        barrier.wait()
        return accrue(client, superuser_headers, agreement["id"], key=key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    assert [response.status_code for response in responses] == [200, 200], [
        response.text for response in responses
    ]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert (
        _count(
            db_session,
            PlatformJournal,
            PlatformJournal.event_type == "PLATFORM_FEE",
            PlatformJournal.source_id == uuid.UUID(agreement["id"]),
        )
        == 1
    )
