from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import make_owner


def create_agreement(
    client: TestClient,
    headers: dict[str, str],
    *,
    gym_id: str | None = None,
    group_id: str | None = None,
    mode: str,
    subscription_amount_irr: int | None = None,
    plan_version_id: str | None = None,
    terms: list[dict[str, object]] | None = None,
    effective_from: str = "2026-11-01",
    volume_discount_bp: int = 0,
):
    payload: dict[str, object] = {
        "mode": mode,
        "effective_from": effective_from,
        "volume_discount_bp": volume_discount_bp,
        "terms": terms or [],
    }
    if gym_id is not None:
        payload["gym_id"] = gym_id
    if group_id is not None:
        payload["group_id"] = group_id
    if subscription_amount_irr is not None:
        payload["subscription_amount_irr"] = subscription_amount_irr
    if plan_version_id is not None:
        payload["plan_version_id"] = plan_version_id
    return client.post(
        "/api/v1/platform/agreements",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json=payload,
    )


def test_commission_only_agreement_works_with_zero_subscription_plans(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Commission Gym")
    # no plans exist
    created = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="COMMISSION",
        subscription_amount_irr=0,
        terms=[
            {
                "kind": "MEMBERSHIP",
                "acquisition_source": "GYM",
                "basis": "PERCENT",
                "percent_bp": 1000,
            },
            {
                "kind": "ANY",
                "acquisition_source": "ASCORA",
                "basis": "PERCENT",
                "percent_bp": 500,
            },
        ],
    )
    assert created.status_code == 200, created.text
    assert created.json()["mode"] == "COMMISSION"
    assert created.json()["plan_version_id"] is None
    assert created.json()["status"] == "DRAFT"
    activated = client.post(
        f"/api/v1/platform/agreements/{created.json()['id']}/activate",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "EFFECTIVE"
    assert (
        client.get("/api/v1/platform/plans", headers=superuser_headers).json()[
            "data"
        ]
        == []
    )


def test_subscription_only_hybrid_and_custom_work_without_plan_records(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym1, _ = make_owner(client, superuser_headers, name="No Plan Subscription")
    gym2, _ = make_owner(client, superuser_headers, name="No Plan Hybrid")
    gym3, _ = make_owner(client, superuser_headers, name="No Plan Custom")

    subscription = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym1["id"]),
        mode="SUBSCRIPTION",
        subscription_amount_irr=500_000,
        terms=[],
    )
    assert subscription.status_code == 200, subscription.text
    assert subscription.json()["plan_version_id"] is None
    assert subscription.json()["subscription_amount_irr"] == 500_000

    hybrid = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym2["id"]),
        mode="HYBRID",
        subscription_amount_irr=200_000,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert hybrid.status_code == 200, hybrid.text
    assert hybrid.json()["plan_version_id"] is None

    custom = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym3["id"]),
        mode="CUSTOM",
        subscription_amount_irr=0,
        terms=[{"kind": "ANY", "basis": "FIXED", "fixed_irr": 10_000}],
    )
    assert custom.status_code == 200, custom.text
    assert (
        client.get("/api/v1/platform/plans", headers=superuser_headers).json()[
            "data"
        ]
        == []
    )


def test_group_agreement_keeps_per_branch_members_and_volume_discount(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gyms = [
        make_owner(client, superuser_headers, name=f"Group Gym {index}")[0]
        for index in range(3)
    ]
    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Group Contract",
            "members": [
                {"gym_id": str(gyms[0]["id"]), "allocation_bp": 3334},
                {"gym_id": str(gyms[1]["id"]), "allocation_bp": 3333},
                {"gym_id": str(gyms[2]["id"]), "allocation_bp": 3333},
            ],
        },
    )
    assert group.status_code == 200, group.text
    assert len(group.json()["members"]) == 3

    agreement = create_agreement(
        client,
        superuser_headers,
        group_id=group.json()["id"],
        mode="HYBRID",
        subscription_amount_irr=100_000,
        volume_discount_bp=500,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert agreement.status_code == 200, agreement.text
    assert agreement.json()["group_id"] == group.json()["id"]
    assert agreement.json()["volume_discount_bp"] == 500
    assert agreement.json()["subscription_amount_irr"] == 100_000
    assert agreement.json()["plan_version_id"] is None


def test_agreement_rejects_bad_modes_terms_overlap_and_non_superuser(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Bad Agreement")
    denied = create_agreement(
        client, owner, gym_id=str(gym["id"]), mode="COMMISSION"
    )
    assert denied.status_code == 403

    both_scopes = client.post(
        "/api/v1/platform/agreements",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": str(gym["id"]),
            "group_id": str(uuid.uuid4()),
            "mode": "FREE",
            "effective_from": "2026-11-01",
            "terms": [],
        },
    )
    assert both_scopes.status_code == 400, both_scopes.text

    bad_percent = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="COMMISSION",
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 10001}],
    )
    assert bad_percent.status_code == 422, bad_percent.text

    first = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="FREE",
    )
    assert first.status_code == 200, first.text
    duplicate = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="FREE",
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"] == "platform_agreement_period_overlap"


def test_group_allocation_must_equal_10000_and_is_locked_while_effective(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gyms = [
        make_owner(client, superuser_headers, name=f"Locked Group {index}")[0]
        for index in range(3)
    ]
    group = client.post(
        "/api/v1/platform/groups",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "name": "Locked Group",
            "members": [
                {"gym_id": str(gyms[0]["id"]), "allocation_bp": 3334},
                {"gym_id": str(gyms[1]["id"]), "allocation_bp": 3333},
                {"gym_id": str(gyms[2]["id"]), "allocation_bp": 3333},
            ],
        },
    )
    assert group.status_code == 200, group.text
    group_id = group.json()["id"]

    invalid = client.post(
        f"/api/v1/platform/groups/{group_id}/members",
        headers=superuser_headers,
        json={"gym_id": str(gyms[0]["id"]), "allocation_bp": 0},
    )
    assert invalid.status_code == 400, invalid.text

    agreement = create_agreement(
        client,
        superuser_headers,
        group_id=group_id,
        mode="COMMISSION",
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert agreement.status_code == 200, agreement.text
    activated = client.post(
        f"/api/v1/platform/agreements/{agreement.json()['id']}/activate",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert activated.status_code == 200, activated.text

    locked = client.post(
        f"/api/v1/platform/groups/{group_id}/members",
        headers=superuser_headers,
        json={"gym_id": str(gyms[0]["id"]), "allocation_bp": 10000},
    )
    assert locked.status_code == 409, locked.text
    assert locked.json()["detail"] == "platform_group_effective"


def test_activate_disable_idempotency_and_future_replacement_preserve_current(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Lifecycle Gym")
    first = create_agreement(
        client, superuser_headers, gym_id=str(gym["id"]), mode="FREE"
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]
    activate_key = uuid.uuid4().hex
    activated = client.post(
        f"/api/v1/platform/agreements/{first_id}/activate",
        headers={**superuser_headers, "Idempotency-Key": activate_key},
    )
    assert activated.status_code == 200, activated.text
    replay = client.post(
        f"/api/v1/platform/agreements/{first_id}/activate",
        headers={**superuser_headers, "Idempotency-Key": activate_key},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "EFFECTIVE"

    future = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="SUBSCRIPTION",
        subscription_amount_irr=100_000,
        effective_from="2027-01-01",
    )
    assert future.status_code == 200, future.text
    future_activated = client.post(
        f"/api/v1/platform/agreements/{future.json()['id']}/activate",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert future_activated.status_code == 200, future_activated.text

    listed = client.get("/api/v1/platform/agreements", headers=superuser_headers)
    rows = {row["id"]: row for row in listed.json()["data"]}
    assert rows[first_id]["status"] == "EFFECTIVE"
    assert rows[first_id]["effective_to"] is None
    assert rows[future.json()["id"]]["status"] == "EFFECTIVE"

    disable_key = uuid.uuid4().hex
    disabled = client.post(
        f"/api/v1/platform/agreements/{future.json()['id']}/disable",
        headers={**superuser_headers, "Idempotency-Key": disable_key},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "DISABLED"
    disabled_replay = client.post(
        f"/api/v1/platform/agreements/{future.json()['id']}/disable",
        headers={**superuser_headers, "Idempotency-Key": disable_key},
    )
    assert disabled_replay.status_code == 200, disabled_replay.text
    assert disabled_replay.json()["status"] == "DISABLED"

    # The key used for activation cannot silently perform a disable.
    collision = client.post(
        f"/api/v1/platform/agreements/{future.json()['id']}/disable",
        headers={**superuser_headers, "Idempotency-Key": activate_key},
    )
    assert collision.status_code == 409, collision.text


def test_custom_negative_duplicate_terms_and_unknown_gym_are_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, _ = make_owner(client, superuser_headers, name="Validation Gym")
    negative = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="CUSTOM",
        subscription_amount_irr=-1,
        terms=[{"kind": "ANY", "basis": "FIXED", "fixed_irr": 1000}],
    )
    assert negative.status_code == 400, negative.text

    duplicates = create_agreement(
        client,
        superuser_headers,
        gym_id=str(gym["id"]),
        mode="COMMISSION",
        terms=[
            {"kind": "ANY", "basis": "PERCENT", "percent_bp": 500},
            {"kind": "ANY", "basis": "PERCENT", "percent_bp": 700},
        ],
    )
    assert duplicates.status_code == 422, duplicates.text

    unknown = create_agreement(
        client,
        superuser_headers,
        gym_id=str(uuid.uuid4()),
        mode="FREE",
    )
    assert unknown.status_code == 404, unknown.text
