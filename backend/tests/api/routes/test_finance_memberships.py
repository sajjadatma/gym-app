from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    issued_invoice,
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def create_membership(
    client: TestClient,
    headers: dict[str, str],
    athlete_id: str,
    *,
    invoice_id: str | None = None,
    start: str = "2026-11-01",
    end: str = "2026-11-30",
    access_required: int = 0,
) -> Any:
    return client.post(
        "/api/v1/finance/memberships",
        headers=headers,
        json={
            "athlete_user_id": athlete_id,
            "invoice_id": invoice_id,
            "start_date": start,
            "end_date": end,
            "access_required_irr": access_required,
        },
    )


def test_paid_membership_access_follows_the_configured_downpayment(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Gym")
    athlete = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, athlete, amount=1_000_000)

    created = create_membership(
        client,
        owner,
        athlete,
        invoice_id=invoice["id"],
        access_required=400_000,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "ACTIVE"
    assert body["access_granted"] is False
    assert body["paid_irr"] == 0

    record_receipt(
        client,
        owner,
        receipt_payload(athlete, amount=400_000, allocations=[(invoice["id"], 400_000)]),
    )
    refreshed = client.get(
        f"/api/v1/finance/memberships/{body['id']}", headers=owner
    ).json()
    assert refreshed["paid_irr"] == 400_000
    assert refreshed["access_granted"] is True


def test_only_one_active_membership_per_athlete(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Overlap Gym")
    athlete = make_customer(client, owner, str(gym["id"]))
    first = create_membership(client, owner, athlete)
    assert first.status_code == 200, first.text

    overlap = create_membership(client, owner, athlete, start="2026-11-15")
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["detail"] == "membership_already_active"

    # A later period is allowed and closes the previous one as expired.
    later = create_membership(
        client, owner, athlete, start="2026-12-01", end="2026-12-31"
    )
    assert later.status_code == 200, later.text
    stale = client.get(
        f"/api/v1/finance/memberships/{first.json()['id']}", headers=owner
    ).json()
    assert stale["status"] == "EXPIRED"


def test_freeze_resume_cancel_and_transfer(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Lifecycle Gym")
    athlete = make_customer(client, owner, str(gym["id"]))
    other = make_customer(client, owner, str(gym["id"]), prefix="other")
    membership = create_membership(client, owner, athlete).json()

    frozen = client.post(
        f"/api/v1/finance/memberships/{membership['id']}/freeze",
        headers=owner,
        json={"frozen_on": "2026-11-10"},
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["status"] == "FROZEN"

    resumed = client.post(
        f"/api/v1/finance/memberships/{membership['id']}/resume",
        headers=owner,
        json={"resume_on": "2026-11-15"},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "ACTIVE"
    assert resumed.json()["end_date"] == "2026-12-05"
    assert resumed.json()["frozen_days"] == 5

    transferred = client.post(
        f"/api/v1/finance/memberships/{membership['id']}/transfer",
        headers=owner,
        json={"athlete_user_id": other},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["athlete_user_id"] == other

    cancelled = client.post(
        f"/api/v1/finance/memberships/{membership['id']}/cancel",
        headers=owner,
        json={"cancelled_on": "2026-11-20", "reason": "Moved away"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    # A cancelled membership frees the athlete for a new period.
    assert create_membership(client, owner, other, start="2027-01-01", end="2027-01-31").status_code == 200


def test_refund_preview_is_time_proportional_and_needs_no_attendance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Preview Gym")
    athlete = make_customer(client, owner, str(gym["id"]))
    invoice = issued_invoice(client, owner, athlete, amount=1_000_000)
    record_receipt(
        client,
        owner,
        receipt_payload(athlete, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]),
    )
    membership = create_membership(
        client,
        owner,
        athlete,
        invoice_id=invoice["id"],
        start="2026-11-01",
        end="2026-11-10",
    ).json()

    preview = client.get(
        f"/api/v1/finance/memberships/{membership['id']}/refund-preview",
        headers=owner,
        params={"on": "2026-11-09"},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_days"] == 10
    assert body["unused_days"] == 2
    assert body["refundable_paid_irr"] == 1_000_000
    assert body["proposed_refund_irr"] == 200_000

    no_invoice = create_membership(client, owner, athlete, start="2027-02-01", end="2027-02-10").json()
    missing = client.get(
        f"/api/v1/finance/memberships/{no_invoice['id']}/refund-preview",
        headers=owner,
        params={"on": "2027-02-05"},
    )
    assert missing.status_code == 400, missing.text


def test_athlete_sees_only_their_own_finances_and_can_request_a_refund(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Self Gym")
    gym_id = str(gym["id"])
    athlete_email = f"self-{uuid.uuid4().hex[:8]}@example.com"
    from tests.utils.helpers import create_athlete, gym_headers, unique_email

    coach_email = unique_email("self-coach")
    add_staff(client, owner, gym_id, roles=["COACH"], email=coach_email)
    coach = gym_headers(
        client, email=coach_email, password="staff-pass-456", gym_id=gym_id
    )
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    athlete = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_id,
        password="athlete-pass-123",
    )["athlete"]["profile"]
    from tests.utils.helpers import auth_headers, change_password

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
    other = make_customer(client, owner, gym_id, prefix="other")
    own_invoice = issued_invoice(client, owner, athlete["user_id"], amount=300_000)
    other_invoice = issued_invoice(client, owner, other, amount=300_000)
    record_receipt(
        client,
        owner,
        receipt_payload(
            athlete["user_id"], amount=300_000, allocations=[(own_invoice["id"], 300_000)]
        ),
    )

    account = client.get("/api/v1/finance/my/account", headers=athlete_headers)
    assert account.status_code == 200, account.text
    body = account.json()
    assert [row["id"] for row in body["invoices"]] == [own_invoice["id"]]
    assert len(body["receipts"]) == 1
    assert other_invoice["id"] not in [row["id"] for row in body["invoices"]]

    other_invoice_request = client.post(
        "/api/v1/finance/my/refunds",
        headers=athlete_headers,
        json={
            "invoice_id": other_invoice["id"],
            "amount_irr": 100_000,
            "method": "CASH",
            "reason": "Wrong invoice",
        },
    )
    assert other_invoice_request.status_code == 404, other_invoice_request.text

    too_much = client.post(
        "/api/v1/finance/my/refunds",
        headers=athlete_headers,
        json={
            "invoice_id": own_invoice["id"],
            "amount_irr": 400_000,
            "method": "CASH",
            "reason": "Too much",
        },
    )
    assert too_much.status_code == 400, too_much.text

    request = client.post(
        "/api/v1/finance/my/refunds",
        headers=athlete_headers,
        json={
            "invoice_id": own_invoice["id"],
            "amount_irr": 100_000,
            "method": "CASH",
            "reason": "Session cancelled",
        },
    )
    assert request.status_code == 200, request.text
    assert request.json()["status"] == "REQUESTED"


def test_membership_management_requires_the_permission(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Membership Permission Gym")
    athlete = make_customer(client, owner, str(gym["id"]))
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    denied = create_membership(client, staff, athlete)
    assert denied.status_code == 403, denied.text

    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    assert (
        client.put(
            f"/api/v1/finance/grants/{staff_id}",
            headers=owner,
            json={"grants": [{"permission": "finance.membership.manage"}]},
        ).status_code
        == 200
    )
    allowed = create_membership(client, staff, athlete)
    assert allowed.status_code == 200, allowed.text
