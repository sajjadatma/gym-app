from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.api.routes.test_finance_coach_agreements import (
    agreement_payload,
    make_coach,
)
from tests.api.routes.test_finance_coach_allocations import (
    active_agreement,
    coach_earning,
    coached_invoice,
)
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_finance_invoices import make_customer
from tests.api.routes.test_finance_receipts import (
    receipt_payload,
    record_receipt,
)

pytestmark = pytest.mark.usefixtures("client")


def paid_invoice(
    client: TestClient,
    owner: dict[str, str],
    customer: str,
    coach_id: str,
    *,
    received_on: str = "2026-11-05",
) -> dict[str, str]:
    invoice = coached_invoice(client, owner, customer, coach_id, amount=1_000_000)
    payload = receipt_payload(
        customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
    )
    payload["received_on"] = received_on
    receipt = record_receipt(client, owner, payload)
    assert receipt.status_code == 200, receipt.text
    return invoice


def test_fixed_and_waterfall_terms_cap_at_the_collected_base(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Waterfall Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    created = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            mode="WATERFALL",
            terms=[
                {
                    "recipient": "COACH",
                    "basis": "FIXED",
                    "fixed_irr": 250_000,
                },
                {
                    "recipient": "GYM",
                    "basis": "PERCENT",
                    "percent_bp": 5000,
                },
            ],
        ),
    )
    assert created.status_code == 200, created.text
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{created.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text

    invoice = paid_invoice(client, owner, customer, coach_id)
    first = coach_earning(db_session, invoice["id"])
    assert first.base_irr == 1_000_000
    assert first.coach_share_irr == 250_000
    assert first.gym_share_irr == 750_000
    assert first.status == "CALCULATED"


def test_on_date_vesting_is_derived_and_manual_vesting_is_audited(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Vesting Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, coach_headers = make_coach(client, owner, gym_id)
    active_agreement(
        client,
        owner,
        coach_id,
        vesting_mode="ON_DATE",
        vesting_days=7,
        terms=[
            {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
        ],
    )
    old = paid_invoice(
        client, owner, customer, coach_id, received_on="2026-01-01"
    )
    old_earning = coach_earning(db_session, old["id"])
    listed = client.get(
        f"/api/v1/finance/coach-earnings?coach_user_id={coach_id}",
        headers=owner,
    )
    assert listed.status_code == 200, listed.text
    old_public = next(
        row for row in listed.json()["data"] if row["id"] == str(old_earning.id)
    )
    assert old_public["status"] == "VESTED"
    assert old_public["vested_irr"] == old_public["coach_share_irr"]
    assert old_public["eligible_irr"] == old_public["coach_share_irr"]

    # A future ON_DATE earning is calculated but not eligible until its date.
    future = paid_invoice(client, owner, customer, coach_id)
    future_earning = coach_earning(db_session, future["id"])
    premature = client.post(
        f"/api/v1/finance/coach-earnings/{future_earning.id}/vest",
        headers=owner,
        json={"reason": "premature"},
    )
    assert premature.status_code == 409, premature.text
    assert premature.json()["detail"] == "coach_earning_not_manual_vesting"
    future_public = client.get(
        f"/api/v1/finance/coach-earnings/{future_earning.id}", headers=owner
    )
    assert future_public.status_code == 200, future_public.text
    assert future_public.json()["status"] == "CALCULATED"
    assert future_public.json()["eligible_irr"] == 0

    manual = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            effective_from="2026-01-01",
            vesting_mode="MANUAL",
            terms=[
                {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
                {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
            ],
        ),
    )
    assert manual.status_code == 200, manual.text
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{manual.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text
    manual_invoice = paid_invoice(client, owner, customer, coach_id)
    manual_earning = coach_earning(db_session, manual_invoice["id"])
    assert manual_earning.status == "CALCULATED"
    vested = client.post(
        f"/api/v1/finance/coach-earnings/{manual_earning.id}/vest",
        headers=owner,
        json={"reason": "delivery attested by gym manager"},
    )
    assert vested.status_code == 200, vested.text
    assert vested.json()["status"] == "VESTED"
    assert vested.json()["vested_at"] is not None

    coach_list = client.get("/api/v1/finance/my/earnings", headers=coach_headers)
    assert coach_list.status_code == 200, coach_list.text
    assert coach_list.json()["count"] == 3
    assert {row["coach_user_id"] for row in coach_list.json()["data"]} == {
        coach_id
    }


def test_unresolved_earning_can_be_attached_to_an_agreement_manually(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Resolve Gym")
    gym_id = str(gym["id"])
    customer = make_customer(client, owner, gym_id)
    coach_id, _ = make_coach(client, owner, gym_id)
    invoice = coached_invoice(client, owner, customer, coach_id)
    receipt = record_receipt(
        client,
        owner,
        receipt_payload(
            customer, amount=1_000_000, allocations=[(invoice["id"], 1_000_000)]
        ),
    )
    assert receipt.status_code == 200
    earning = coach_earning(db_session, invoice["id"])
    assert earning.status == "UNRESOLVED"

    agreement = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            terms=[
                {"recipient": "COACH", "basis": "PERCENT", "percent_bp": 3000},
                {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 7000},
            ],
        ),
    )
    assert agreement.status_code == 200
    activated = client.post(
        f"/api/v1/finance/coach-agreements/{agreement.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200
    resolved = client.post(
        f"/api/v1/finance/coach-earnings/{earning.id}/resolve",
        headers=owner,
        json={
            "agreement_id": agreement.json()["id"],
            "reason": "missing contract attached after review",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "CALCULATED"
    assert resolved.json()["coach_share_irr"] == 300_000
    assert resolved.json()["agreement_id"] == agreement.json()["id"]
    listed = client.get("/api/v1/finance/journal?limit=50", headers=owner)
    assert listed.status_code == 200, listed.text
    assert any(
        entry["event_type"] == "COACH_ALLOCATION"
        for entry in listed.json()["data"]
    )
