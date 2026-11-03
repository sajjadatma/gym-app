from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import make_owner


def create_plan(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str = "STARTER",
    price: int = 500_000,
    effective_from: str = "2026-11-01",
    limits: dict[str, object] | None = None,
):
    return client.post(
        "/api/v1/platform/plans",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "code": code,
            "name": code.title(),
            "version": {
                "effective_from": effective_from,
                "monthly_price_irr": price,
                "limits": limits
                or {
                    "active_athletes": 50,
                    "staff_seats": 5,
                    "advanced_finance": True,
                    "sms": 0,
                    "storage_mb": 500,
                },
            },
        },
    )


def test_superuser_can_create_zero_price_plan_and_no_active_plan_is_valid(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    empty = client.get("/api/v1/platform/plans", headers=superuser_headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"] == []

    gym, owner = make_owner(client, superuser_headers, name="Plan Gym")
    denied = client.get("/api/v1/platform/plans", headers=owner)
    assert denied.status_code == 403

    created = create_plan(
        client,
        superuser_headers,
        code="free",
        price=0,
        limits={
            "active_athletes": 20,
            "staff_seats": 2,
            "advanced_finance": False,
            "sms": 0,
            "storage_mb": 100,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["code"] == "FREE"
    assert body["versions"][0]["status"] == "ACTIVE"
    assert body["versions"][0]["monthly_price_irr"] == 0
    usage = client.get(
        f"/api/v1/platform/plans/{body['id']}/versions/"
        f"{body['versions'][0]['id']}/usage",
        headers=superuser_headers,
    )
    assert usage.status_code == 200, usage.text
    assert usage.json()["limit_status"] in {"OK", "EXCEEDED"}
    assert usage.json()["limits"]["active_athletes"] == 20


def test_plan_versions_are_effective_dated_and_retirable_without_history_loss(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    created = create_plan(client, superuser_headers, effective_from="2026-01-01")
    assert created.status_code == 200, created.text
    plan = created.json()
    plan_id = plan["id"]

    replacement = client.post(
        f"/api/v1/platform/plans/{plan_id}/versions",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "effective_from": "2026-06-01",
            "monthly_price_irr": 900_000,
            "limits": {
                "active_athletes": 100,
                "staff_seats": 10,
                "advanced_finance": True,
                "sms": 100,
                "storage_mb": 2000,
            },
        },
    )
    assert replacement.status_code == 200, replacement.text
    new_version = replacement.json()
    assert new_version["status"] == "DRAFT"

    activated = client.post(
        f"/api/v1/platform/plans/{plan_id}/versions/{new_version['id']}/activate",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert activated.status_code == 200, activated.text
    listed = client.get(
        f"/api/v1/platform/plans/{plan_id}", headers=superuser_headers
    )
    assert listed.status_code == 200, listed.text
    versions = {row["id"]: row for row in listed.json()["versions"]}
    assert versions[new_version["id"]]["status"] == "ACTIVE"
    assert versions[plan["versions"][0]["id"]]["status"] == "RETIRED"

    overlap = client.post(
        f"/api/v1/platform/plans/{plan_id}/versions",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "effective_from": "2026-06-01",
            "monthly_price_irr": 1,
            "limits": {"active_athletes": 1},
        },
    )
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["detail"] == "platform_plan_period_overlap"

    retired = client.post(
        f"/api/v1/platform/plans/{plan_id}/versions/{new_version['id']}/retire",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["status"] == "RETIRED"
    final = client.get(
        f"/api/v1/platform/plans/{plan_id}", headers=superuser_headers
    ).json()
    assert all(row["status"] == "RETIRED" for row in final["versions"])
