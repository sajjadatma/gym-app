from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_invoices import (
    create_draft,
    invoice_payload,
    issue,
    make_customer,
)
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)
from tests.utils.helpers import (
    auth_headers,
    change_password,
    create_athlete,
    gym_headers,
    unique_email,
)

pytestmark = pytest.mark.usefixtures("client")


def test_sale_snapshots_acquisition_source_and_discount_funding(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Snapshot Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    payload = {
        **invoice_payload(customer),
        "acquisition_source": "ASCORA",
        "discount_funding": "MIXED",
    }
    draft = create_draft(client, owner, payload)
    assert draft.status_code == 200, draft.text
    assert draft.json()["acquisition_source"] == "ASCORA"
    assert draft.json()["discount_funding"] == "MIXED"

    # Drafts may change the snapshot before issue.
    updated = client.patch(
        f"/api/v1/finance/invoices/{draft.json()['id']}",
        headers=owner,
        json={**payload, "discount_funding": "COACH"},
    )
    assert updated.status_code == 200
    assert updated.json()["discount_funding"] == "COACH"

    issued = issue(client, owner, draft.json()["id"])
    assert issued.status_code == 200, issued.text
    frozen = issued.json()
    assert frozen["acquisition_source"] == "ASCORA"
    assert frozen["discount_funding"] == "COACH"

    # Issued sales cannot be retroactively changed.
    attempted = client.patch(
        f"/api/v1/finance/invoices/{frozen['id']}",
        headers=owner,
        json={**payload, "discount_funding": "GYM"},
    )
    assert attempted.status_code == 409, attempted.text


def test_refund_defaults_to_the_original_payment_method(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Refund Method Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, customer, amount=500_000)
    record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=500_000,
            allocations=[(invoice["id"], 500_000)],
            method="TRANSFER",
        ),
    )

    defaulted = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 100_000,
            "reason": "Default method",
        },
    )
    assert defaulted.status_code == 200, defaulted.text
    assert defaulted.json()["method"] == "TRANSFER"
    assert defaulted.json()["original_method"] == "TRANSFER"

    missing_reason = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 50_000,
            "method": "CASH",
            "reason": "Alternative method",
        },
    )
    assert missing_reason.status_code == 400, missing_reason.text
    assert missing_reason.json()["detail"] == "refund_method_reason_required"

    allowed = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "INVOICE",
            "customer_user_id": customer,
            "invoice_id": invoice["id"],
            "amount_irr": 50_000,
            "method": "CASH",
            "method_override_reason": "Customer asked for cash",
            "reason": "Alternative method",
        },
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["method"] == "CASH"
    assert allowed.json()["original_method"] == "TRANSFER"
    assert allowed.json()["method_override_reason"] == "Customer asked for cash"

    # An advance refund defaults to the method that funded the advance.
    advance_invoice = issued_invoice(client, owner, customer, amount=100_000)
    record_receipt(
        client,
        owner,
        receipt_payload(
            customer,
            amount=200_000,
            allocations=[(advance_invoice["id"], 100_000)],
            method="POS",
        ),
    )
    advance_refund = client.post(
        "/api/v1/finance/refunds",
        headers={**owner, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "source": "ADVANCE",
            "customer_user_id": customer,
            "amount_irr": 100_000,
            "reason": "Return deposit",
        },
    )
    assert advance_refund.status_code == 200, advance_refund.text
    assert advance_refund.json()["method"] == "POS"
    assert advance_refund.json()["original_method"] == "POS"


def test_reminders_report_due_installments_and_renewals(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Reminder Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    today = date.today()
    past_due = (today - timedelta(days=2)).isoformat()
    later_due = (today + timedelta(days=20)).isoformat()
    draft = create_draft(
        client,
        owner,
        {
            **invoice_payload(customer),
            "installments": [
                {"due_date": past_due, "amount_irr": 600_000},
                {"due_date": later_due, "amount_irr": 400_000},
            ],
        },
    )
    issued = issue(client, owner, draft.json()["id"]).json()

    # Freeze the clock through the API's own date source by asking for a wide
    # horizon: both installments are in scope, the next one is reported first.
    wide = client.get(
        "/api/v1/finance/reminders", headers=owner, params={"within_days": 90}
    )
    assert wide.status_code == 200, wide.text
    body = wide.json()
    assert len(body["installments"]) == 1
    row = body["installments"][0]
    assert row["invoice_id"] == issued["id"]
    assert row["due_date"] == past_due
    assert row["amount_irr"] == 600_000
    assert row["overdue"] is True
    assert row["days_until"] == -2

    narrow = client.get(
        "/api/v1/finance/reminders", headers=owner, params={"within_days": 0}
    ).json()
    assert narrow["within_days"] == 0

    # A paid invoice stops reminding.
    record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(issued["id"], 1_000_000)]
        ),
    )
    assert (
        client.get(
            "/api/v1/finance/reminders", headers=owner, params={"within_days": 90}
        ).json()["installments"]
        == []
    )

    membership = client.post(
        "/api/v1/finance/memberships",
        headers=owner,
        json={
            "athlete_user_id": customer,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=10)).isoformat(),
            "access_required_irr": 0,
        },
    )
    assert membership.status_code == 200, membership.text
    reminders = client.get(
        "/api/v1/finance/reminders", headers=owner, params={"within_days": 90}
    ).json()
    assert [row["membership_id"] for row in reminders["renewals"]] == [
        membership.json()["id"]
    ]


def test_athlete_account_includes_own_reminders_only(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Athlete Reminder Gym")
    gym_id = str(gym["id"])
    coach_email = unique_email("reminder-coach")
    add_staff(client, owner, gym_id, roles=["COACH"], email=coach_email)
    coach = gym_headers(
        client, email=coach_email, password="staff-pass-456", gym_id=gym_id
    )
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    athlete_email = unique_email("reminder-athlete")
    athlete = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_id,
        password="athlete-pass-123",
    )["athlete"]["profile"]
    raw = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client, email=athlete_email, password="athlete-pass-456", gym_id=gym_id
    )
    other = make_customer(client, owner, gym_id, prefix="reminder-other")
    due = (date.today() + timedelta(days=2)).isoformat()
    own = issue(
        client,
        owner,
        create_draft(
            client,
            owner,
            {
                **invoice_payload(athlete["user_id"]),
                "due_date": due,
            },
        ).json()["id"],
    ).json()
    issue(
        client,
        owner,
        create_draft(
            client,
            owner,
            {**invoice_payload(other), "due_date": due},
        ).json()["id"],
    )

    account = client.get("/api/v1/finance/my/account", headers=athlete_headers)
    assert account.status_code == 200, account.text
    body = account.json()
    assert body["reminders"]["within_days"] == 7
    assert [row["invoice_id"] for row in body["reminders"]["installments"]] == [
        own["id"]
    ]
