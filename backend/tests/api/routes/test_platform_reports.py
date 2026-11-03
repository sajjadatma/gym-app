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
