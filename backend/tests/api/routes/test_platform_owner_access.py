from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.services.platform import platform_today
from tests.api.routes.test_finance_foundation import make_owner
from tests.api.routes.test_platform_invoices import (
    accrue,
    subscription_agreement,
)
from tests.api.routes.test_platform_reports import platform_invoice


def test_gym_owner_has_read_only_access_to_own_platform_billing(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Owner Platform A")
    gym_b, owner_b = make_owner(client, superuser_headers, name="Owner Platform B")
    invoices: dict[str, str] = {}
    for gym, _owner in ((gym_a, owner_a), (gym_b, owner_b)):
        gym_id = str(gym["id"])
        agreement = subscription_agreement(
            client, superuser_headers, gym_id, amount=500_000
        )
        assert accrue(client, superuser_headers, agreement["id"]).status_code == 200
        issued = platform_invoice(
            client, superuser_headers, gym_id=gym_id, due_on=platform_today()
        )
        assert issued.status_code == 200, issued.text
        invoices[gym_id] = issued.json()["id"]

    own = client.get("/api/v1/finance/platform/invoices", headers=owner_a)
    assert own.status_code == 200, own.text
    assert {row["id"] for row in own.json()["data"]} == {invoices[str(gym_a["id"])]}

    dues = client.get("/api/v1/finance/platform/dues", headers=owner_a)
    assert dues.status_code == 200, dues.text
    assert dues.json()["gym_id"] == str(gym_a["id"])

    payment = client.post(
        f"/api/v1/platform/invoices/{invoices[str(gym_a['id'])]}/payments",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "amount_irr": 200_000,
            "method": "TRANSFER",
            "reference": "OWNER-1",
            "received_on": platform_today().isoformat(),
        },
    )
    assert payment.status_code == 200, payment.text
    payments = client.get("/api/v1/finance/platform/payments", headers=owner_a)
    assert payments.status_code == 200, payments.text
    assert {row["id"] for row in payments.json()["data"]} == {payment.json()["id"]}

    other = client.get("/api/v1/finance/platform/invoices", headers=owner_b)
    assert other.status_code == 200, other.text
    assert invoices[str(gym_a["id"])] not in {
        row["id"] for row in other.json()["data"]
    }

    denied = client.post(
        "/api/v1/platform/agreements",
        headers={**owner_a, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": str(gym_a["id"]),
            "mode": "FREE",
            "effective_from": "2026-12-01",
            "terms": [],
        },
    )
    assert denied.status_code == 403, denied.text

    all_invoices = client.get(
        "/api/v1/platform/invoices", headers=superuser_headers
    )
    assert all_invoices.status_code == 200, all_invoices.text
    assert {invoices[str(gym_a["id"])], invoices[str(gym_b["id"])]} == {
        row["id"] for row in all_invoices.json()["data"]
    }

    disabled = client.patch(
        "/api/v1/finance/settings",
        headers={**superuser_headers, "X-Gym-ID": str(gym_a["id"])},
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    for path in (
        "/api/v1/finance/platform/invoices",
        "/api/v1/finance/platform/dues",
        "/api/v1/finance/platform/payments",
    ):
        still_readable = client.get(path, headers=owner_a)
        assert still_readable.status_code == 200, still_readable.text
