from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_gym,
    unique_email,
)

pytestmark = pytest.mark.usefixtures("client")


def owner_headers(client: TestClient, email: str) -> dict[str, str]:
    return auth_headers(client, email, "owner-pass-123")


def make_finance_gym(client: TestClient, superuser_headers: dict[str, str]) -> dict[str, Any]:
    owner_email = unique_email("finance-owner")
    created = create_gym(
        client,
        superuser_headers,
        name=f"Finance Sandbox {uuid.uuid4().hex[:6]}",
        owner_email=owner_email,
    )
    gym_id = str(created["gym"]["id"])
    raw_owner = owner_headers(client, owner_email)
    change_password(
        client,
        raw_owner,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    owner = auth_headers(client, owner_email, "owner-pass-456")
    owner["X-Gym-ID"] = gym_id
    coach_email = unique_email("finance-coach")
    coach_created = add_member(
        client,
        owner,
        gym_id,
        email=coach_email,
        roles=["COACH"],
        full_name="مربی مالی",
        phone="09121111111",
    )
    return {
        "gym_id": gym_id,
        "owner": owner,
        "owner_email": owner_email,
        "coach_id": str(coach_created["member"]["user_id"]),
        "coach_email": coach_email,
    }


def create_default_contract(
    client: TestClient,
    superuser_headers: dict[str, str],
    *,
    membership_bp: int = 1000,
    nutrition_bp: int = 1200,
    training_bp: int = 1000,
) -> dict[str, Any]:
    today = date.today().isoformat()
    response = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "قرارداد پیش‌فرض پلتفرم",
            "scope": "DEFAULT",
            "effective_from": today,
            "rates": [
                {"category": "MEMBERSHIP", "percent_bp": membership_bp},
                {"category": "NUTRITION", "percent_bp": nutrition_bp},
                {"category": "TRAINING", "percent_bp": training_bp},
            ],
        },
    )
    assert response.status_code == 200, response.text
    activated = client.post(
        f"/api/v1/finance/platform-contracts/{response.json()['id']}/activate",
        headers=superuser_headers,
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


def create_gym_override(
    client: TestClient,
    superuser_headers: dict[str, str],
    gym_id: str,
    *,
    membership_bp: int = 800,
    nutrition_bp: int = 1200,
    training_bp: int = 1500,
) -> dict[str, Any]:
    today = date.today().isoformat()
    response = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "قرارداد اختصاصی باشگاه",
            "scope": "GYM",
            "gym_id": gym_id,
            "effective_from": today,
            "rates": platform_rates(membership_bp, nutrition_bp, training_bp),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"
    return response.json()


def platform_rates(
    membership_bp: int = 1000,
    nutrition_bp: int = 1200,
    training_bp: int = 1500,
) -> list[dict[str, int]]:
    return [
        {"category": "MEMBERSHIP", "percent_bp": membership_bp},
        {"category": "NUTRITION", "percent_bp": nutrition_bp},
        {"category": "TRAINING", "percent_bp": training_bp},
    ]


def create_vat(
    client: TestClient, superuser_headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/finance/taxes",
        headers=superuser_headers,
        json={
            "name": "Value-added tax",
            "calculation": "PERCENT",
            "percent_bp": 1000,
            "is_default_vat": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_fixed_tax(
    client: TestClient, superuser_headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/finance/taxes",
        headers=superuser_headers,
        json={
            "name": "هزینه اداری",
            "calculation": "FIXED",
            "fixed_amount_irr": 50_000,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_coach_contract(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    coach_id: str,
    *,
    platform_bp: int = 1000,
    gym_bp: int = 4000,
    coach_bp: int = 5000,
    category: str = "TRAINING",
    effective_from: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/finance/gyms/{gym_id}/coach-contracts",
        headers=owner,
        json={
            "coach_user_id": coach_id,
            "category": category,
            "effective_from": effective_from or date.today().isoformat(),
            "platform_bp": platform_bp,
            "gym_bp": gym_bp,
            "coach_bp": coach_bp,
        },
    )
    assert response.status_code == 200, response.text
    activated = client.post(
        f"/api/v1/finance/gyms/{gym_id}/coach-contracts/{response.json()['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


def preview_sale(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    *,
    base_amount_irr: int = 1_000_000,
    tax_ids: list[str] | None = None,
    coach_id: str | None = None,
    category: str = "TRAINING",
    sold_on: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/finance/gyms/{gym_id}/sales/preview",
        headers=owner,
        json={
            "category": category,
            "base_amount_irr": base_amount_irr,
            "tax_ids": tax_ids or [],
            "coach_user_id": coach_id,
            "sold_on": sold_on or date.today().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_sale(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    *,
    base_amount_irr: int = 1_000_000,
    tax_ids: list[str] | None = None,
    coach_id: str | None = None,
    category: str = "TRAINING",
    description: str = "فروش آزمایشی",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/finance/gyms/{gym_id}/sales",
        headers=owner,
        json={
            "category": category,
            "description": description,
            "base_amount_irr": base_amount_irr,
            "tax_ids": tax_ids or [],
            "coach_user_id": coach_id,
            "sold_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def pay(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    sale_id: str,
    *,
    outcome: str = "SUCCESS",
    key: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/finance/gyms/{gym_id}/sales/{sale_id}/payments",
        headers=owner,
        json={
            "outcome": outcome,
            "idempotency_key": key or uuid.uuid4().hex,
        },
    )


def test_approved_10_40_50_with_vat_and_exact_allocation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )

    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    assert preview["base_amount_irr"] == 1_000_000
    assert preview["tax_amount_irr"] == 100_000
    assert preview["total_amount_irr"] == 1_100_000
    assert preview["platform_amount_irr"] == 110_000
    assert preview["gym_amount_irr"] == 440_000
    assert preview["coach_amount_irr"] == 550_000
    assert (
        preview["platform_amount_irr"]
        + preview["gym_amount_irr"]
        + preview["coach_amount_irr"]
        == preview["total_amount_irr"]
    )
    assert preview["platform_source"] == "PLATFORM_DEFAULT"

    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    assert sale["total_amount_irr"] == 1_100_000
    assert sale["taxes"][0]["name"] == "Value-added tax"
    payment = pay(client, env["owner"], env["gym_id"], sale["id"])
    assert payment.status_code == 200, payment.text
    body = payment.json()
    assert body["status"] == "SUCCEEDED"
    assert {row["party"]: row["amount_irr"] for row in body["allocations"]} == {
        "PLATFORM": 110_000,
        "GYM": 440_000,
        "COACH": 550_000,
    }


def test_platform_category_and_gym_override_sources(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    override = create_gym_override(
        client, superuser_headers, env["gym_id"], membership_bp=800
    )
    policy = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": date.today().isoformat(),
        },
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["platform_bp"] == 800
    assert policy.json()["source"] == "GYM_OVERRIDE"
    assert policy.json()["contract_id"] == override["id"]

    nutrition = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "NUTRITION",
            "on_date": date.today().isoformat(),
        },
    )
    assert nutrition.status_code == 200, nutrition.text
    assert nutrition.json()["platform_bp"] == 1200
    assert nutrition.json()["source"] == "GYM_OVERRIDE"
    assert nutrition.json()["contract_id"] == override["id"]

    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        base_amount_irr=1_000_000,
        category="MEMBERSHIP",
    )
    assert preview["platform_bp"] == 800
    assert preview["gym_amount_irr"] == 920_000
    assert preview["coach_amount_irr"] == 0


def test_percentage_and_fixed_taxes_are_separate_and_not_compounded(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    fixed = create_fixed_tax(client, superuser_headers)
    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        base_amount_irr=1_000_000,
        tax_ids=[vat["id"], fixed["id"]],
    )
    assert [row["name"] for row in preview["taxes"]] == [
        "Value-added tax",
        "هزینه اداری",
    ]
    assert preview["taxes"][0]["amount_irr"] == 100_000
    assert preview["taxes"][1]["amount_irr"] == 50_000
    assert preview["tax_amount_irr"] == 150_000
    assert preview["total_amount_irr"] == 1_150_000
    assert preview["platform_amount_irr"] == 115_000
    assert preview["gym_amount_irr"] == 1_035_000


def test_coach_contract_validation_and_platform_tampering(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    bad_total = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": env["coach_id"],
            "category": "TRAINING",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1000,
            "gym_bp": 4000,
            "coach_bp": 4000,
        },
    )
    assert bad_total.status_code == 400
    assert bad_total.json()["detail"] == "allocation_total_invalid"

    tampered = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": env["coach_id"],
            "category": "TRAINING",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1200,
            "gym_bp": 4000,
            "coach_bp": 4800,
        },
    )
    assert tampered.status_code == 400
    assert tampered.json()["detail"] == "platform_percentage_mismatch"

    outsider = add_member(
        client,
        {**superuser_headers, "X-Gym-ID": env["gym_id"]},
        env["gym_id"],
        email=unique_email("outsider"),
        roles=["GYM_ADMIN"],
        phone="09122222222",
    )
    outside = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": outsider["member"]["user_id"],
            "category": "TRAINING",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1000,
            "gym_bp": 4000,
            "coach_bp": 5000,
        },
    )
    assert outside.status_code == 400
    assert outside.json()["detail"] == "coach_not_in_gym"


def test_payment_failure_retry_duplicate_and_no_fictitious_coach(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    sale = create_sale(client, env["owner"], env["gym_id"])
    failed = pay(
        client, env["owner"], env["gym_id"], sale["id"], outcome="FAILURE"
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["allocations"] == []
    assert (
        client.get(
            f"/api/v1/finance/gyms/{env['gym_id']}/sales/{sale['id']}",
            headers=env["owner"],
        ).json()["status"]
        == "AWAITING_PAYMENT"
    )

    key = uuid.uuid4().hex
    first = pay(
        client, env["owner"], env["gym_id"], sale["id"], key=key
    )
    assert first.status_code == 200, first.text
    duplicate = pay(
        client, env["owner"], env["gym_id"], sale["id"], key=key
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == first.json()["id"]
    payments = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments",
        headers=env["owner"],
    ).json()
    assert len(payments) == 2
    allocations = first.json()["allocations"]
    assert {row["party"] for row in allocations} == {"PLATFORM", "GYM"}
    assert sum(row["amount_irr"] for row in allocations) == sale["total_amount_irr"]


def test_role_permissions_and_cross_gym_isolation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env_a = make_finance_gym(client, superuser_headers)
    env_b = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    sale = create_sale(client, env_a["owner"], env_a["gym_id"])

    denied = client.get(
        f"/api/v1/finance/gyms/{env_a['gym_id']}/sales",
        headers=env_b["owner"],
    )
    assert denied.status_code == 403

    coach_denied = client.get(
        "/api/v1/finance/taxes",
        headers=auth_headers(client, env_a["coach_email"], "member-pass-123"),
    )
    assert coach_denied.status_code == 403

    platform_tamper = client.post(
        "/api/v1/finance/platform-contracts",
        headers=env_a["owner"],
        json={
            "name": "tamper",
            "scope": "DEFAULT",
            "effective_from": date.today().isoformat(),
            "rates": [
                {"category": category, "percent_bp": 1000}
                for category in ("MEMBERSHIP", "NUTRITION", "TRAINING")
            ],
        },
    )
    assert platform_tamper.status_code == 403

    all_sales = client.get(
        f"/api/v1/finance/gyms/{env_a['gym_id']}/sales",
        headers=superuser_headers,
    )
    assert all_sales.status_code == 200
    assert any(row["id"] == sale["id"] for row in all_sales.json())


def test_new_contracts_replace_active_versions(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    first_default = create_default_contract(client, superuser_headers)
    second_default = create_default_contract(
        client, superuser_headers, membership_bp=1100
    )
    defaults = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "DEFAULT"},
    ).json()
    assert [row["id"] for row in defaults if row["status"] == "ACTIVE"] == [
        second_default["id"]
    ]
    assert next(
        row for row in defaults if row["id"] == first_default["id"]
    )["status"] == "ARCHIVED"

    first_coach = create_coach_contract(
        client,
        env["owner"],
        env["gym_id"],
        env["coach_id"],
        platform_bp=1000,
        gym_bp=3000,
        coach_bp=6000,
    )
    second_coach = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
        json={
            "coach_user_id": env["coach_id"],
            "category": "TRAINING",
            "effective_from": date.today().isoformat(),
            "platform_bp": 1000,
            "gym_bp": 3000,
            "coach_bp": 6000,
        },
    )
    assert second_coach.status_code == 200, second_coach.text
    assert second_coach.json()["status"] == "ACTIVE"
    assert second_coach.json()["version"] == 2
    coach_rows = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    assert [row["id"] for row in coach_rows if row["status"] == "ACTIVE"] == [
        second_coach.json()["id"]
    ]
    assert next(
        row for row in coach_rows if row["id"] == first_coach["id"]
    )["status"] == "ARCHIVED"


def test_editing_archived_platform_contract_creates_new_active_version(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    old_default = create_default_contract(client, superuser_headers)
    new_default = create_default_contract(
        client, superuser_headers, membership_bp=2000
    )
    assert new_default["id"] != old_default["id"]
    defaults = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "DEFAULT"},
    ).json()
    assert next(
        row for row in defaults if row["id"] == old_default["id"]
    )["status"] == "ARCHIVED"

    edited = client.put(
        f"/api/v1/finance/platform-contracts/{old_default['id']}",
        headers=superuser_headers,
        json={
            "name": "پیش‌فرض بایگانی‌شده ویرایش‌شده",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(3000, 1200, 1500),
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "ACTIVE"
    assert edited.json()["version"] == 3

    defaults = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "DEFAULT"},
    ).json()
    assert [row["id"] for row in defaults if row["status"] == "ACTIVE"] == [
        edited.json()["id"]
    ]
    assert next(
        row for row in defaults if row["id"] == new_default["id"]
    )["status"] == "ARCHIVED"
    policy = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": date.today().isoformat(),
        },
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["platform_bp"] == 3000
    assert policy.json()["contract_id"] == edited.json()["id"]


def test_rounding_residual_is_consistent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )
    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        base_amount_irr=1_000_001,
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    assert preview["tax_amount_irr"] == 100_000
    assert preview["total_amount_irr"] == 1_100_001
    assert preview["platform_amount_irr"] == 110_000
    assert preview["coach_amount_irr"] == 550_000
    assert preview["gym_amount_irr"] == 440_001
    assert (
        preview["platform_amount_irr"]
        + preview["gym_amount_irr"]
        + preview["coach_amount_irr"]
        == preview["total_amount_irr"]
    )


def test_partial_full_and_after_settlement_refunds(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )
    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    payment = pay(client, env["owner"], env["gym_id"], sale["id"]).json()
    settlement = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "COACH",
            "party_user_id": env["coach_id"],
            "amount_irr": 550_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()["status"] == "PENDING"
    completed = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/{settlement.json()['id']}/complete",
        headers=env["owner"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "COMPLETED"

    refund = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments/{payment['id']}/refunds",
        headers=env["owner"],
        json={
            "amount_irr": 110_000,
            "idempotency_key": uuid.uuid4().hex,
            "reason": "بازگشت آزمایشی",
        },
    )
    assert refund.status_code == 200, refund.text
    body = refund.json()
    coach_adjustment = next(
        row for row in body["adjustments"] if row["party"] == "COACH"
    )
    assert coach_adjustment["amount_irr"] == 55_000
    assert coach_adjustment["settlement_id"] == settlement.json()["id"]

    too_much = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments/{payment['id']}/refunds",
        headers=env["owner"],
        json={
            "amount_irr": 1_100_000,
            "idempotency_key": uuid.uuid4().hex,
            "reason": "بیش از مانده",
        },
    )
    assert too_much.status_code == 400
    assert too_much.json()["detail"] == "refund_exceeds_remaining"

    full = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments/{payment['id']}/refunds",
        headers=env["owner"],
        json={
            "amount_irr": 990_000,
            "idempotency_key": uuid.uuid4().hex,
            "reason": "بازگشت کامل باقی‌مانده",
        },
    )
    assert full.status_code == 200, full.text
    sale_after = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales/{sale['id']}",
        headers=env["owner"],
    )
    assert sale_after.json()["status"] == "REFUNDED"


def test_settlement_pending_is_not_completed_and_over_amount_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    sale = create_sale(client, env["owner"], env["gym_id"])
    pay(client, env["owner"], env["gym_id"], sale["id"])
    over = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "amount_irr": sale["total_amount_irr"] + 1,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert over.status_code == 400
    assert over.json()["detail"] == "settlement_exceeds_available"
    created = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
        json={
            "party": "GYM",
            "amount_irr": 400_000,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "PENDING"
    settlements = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements",
        headers=env["owner"],
    ).json()
    assert settlements[0]["status"] == "PENDING"


def test_reports_and_csv_are_consistent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )
    sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    pay(client, env["owner"], env["gym_id"], sale["id"])
    today = date.today().isoformat()
    report = client.get(
        "/api/v1/finance/reports",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "from_date": today,
            "to_date": today,
        },
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["activity"]["base_sales_irr"] == 1_000_000
    assert body["activity"]["taxes_irr"] == 100_000
    assert body["activity"]["total_payments_irr"] == 1_100_000
    assert body["activity"]["platform_share_irr"] == 110_000
    assert body["activity"]["gym_share_irr"] == 440_000
    assert body["activity"]["coach_share_irr"] == 550_000
    assert body["as_of"]["pending_settlements_irr"] == 0

    export = client.get(
        "/api/v1/finance/reports/export",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "from_date": today,
            "to_date": today,
        },
    )
    assert export.status_code == 200, export.text
    assert "activity,base_sales_irr,1000000" in export.text
    assert "activity,total_payments_irr,1100000" in export.text
    assert "as_of,completed_settlements_irr,0" in export.text


def test_concurrent_payments_do_not_duplicate_allocations(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.main import app

    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    sale = create_sale(client, env["owner"], env["gym_id"])
    key = uuid.uuid4().hex

    def submit(request_key: str) -> Any:
        with TestClient(app) as thread_client:
            return thread_client.post(
                f"/api/v1/finance/gyms/{env['gym_id']}/sales/{sale['id']}/payments",
                headers=env["owner"],
                json={"outcome": "SUCCESS", "idempotency_key": request_key},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [key, key]))
    assert sorted(result.status_code for result in results) == [200, 200]
    assert len({result.json()["id"] for result in results}) == 1
    payments = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/payments",
        headers=env["owner"],
    ).json()
    assert len(payments) == 1
    assert len(payments[0]["allocations"]) == 2

    second_sale = create_sale(client, env["owner"], env["gym_id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda request_key: submit_for_sale(
                    request_key, env, second_sale
                ),
                [uuid.uuid4().hex, uuid.uuid4().hex],
            )
        )
    assert sorted(result.status_code for result in results) == [200, 409]


def submit_for_sale(
    request_key: str, env: dict[str, Any], sale: dict[str, Any]
) -> Any:
    from app.main import app

    with TestClient(app) as thread_client:
        return thread_client.post(
            f"/api/v1/finance/gyms/{env['gym_id']}/sales/{sale['id']}/payments",
            headers=env["owner"],
            json={"outcome": "SUCCESS", "idempotency_key": request_key},
        )


def test_auto_settlement_completes_eligible_allocations(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    sale = create_sale(client, env["owner"], env["gym_id"])
    pay(client, env["owner"], env["gym_id"], sale["id"])
    auto = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/settlements/auto",
        headers=env["owner"],
    )
    assert auto.status_code == 200, auto.text
    rows = auto.json()
    assert rows
    assert all(row["status"] == "COMPLETED" for row in rows)
    report = client.get(
        "/api/v1/finance/reports",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "from_date": date.today().isoformat(),
            "to_date": date.today().isoformat(),
        },
    ).json()
    assert report["as_of"]["unsettled_platform_irr"] == 0
    assert report["as_of"]["unsettled_gym_irr"] == 0
    assert report["as_of"]["completed_settlements_irr"] == sale["total_amount_irr"]


def test_duplicate_tax_selection_is_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    response = client.post(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales/preview",
        headers=env["owner"],
        json={
            "category": "MEMBERSHIP",
            "base_amount_irr": 1_000_000,
            "tax_ids": [vat["id"], vat["id"]],
            "coach_user_id": None,
            "sold_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "duplicate_tax"


def test_platform_contracts_are_immediate_editable_and_replace_by_scope(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    first = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "پیش‌فرض اول",
            "scope": "DEFAULT",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(),
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "ACTIVE"
    assert first.json()["version"] == 1
    assert first.json()["activated_at"] is not None

    second = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "پیش‌فرض دوم",
            "scope": "DEFAULT",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(1100, 1300, 1600),
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "ACTIVE"
    assert second.json()["version"] == 2

    defaults = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "DEFAULT"},
    ).json()
    assert [row["id"] for row in defaults if row["status"] == "ACTIVE"] == [
        second.json()["id"]
    ]
    assert next(row for row in defaults if row["id"] == first.json()["id"])[
        "status"
    ] == "ARCHIVED"

    gym_contract = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "اختصاصی باشگاه",
            "scope": "GYM",
            "gym_id": env["gym_id"],
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(800, 900, 1000),
        },
    )
    assert gym_contract.status_code == 200, gym_contract.text
    assert gym_contract.json()["status"] == "ACTIVE"
    for category, expected in (
        ("MEMBERSHIP", 800),
        ("NUTRITION", 900),
        ("TRAINING", 1000),
    ):
        policy = client.get(
            "/api/v1/finance/platform-policy",
            headers=env["owner"],
            params={
                "gym_id": env["gym_id"],
                "category": category,
                "on_date": date.today().isoformat(),
            },
        )
        assert policy.status_code == 200, policy.text
        assert policy.json()["platform_bp"] == expected
        assert policy.json()["source"] == "GYM_OVERRIDE"
        assert policy.json()["contract_id"] == gym_contract.json()["id"]

    edited = client.put(
        f"/api/v1/finance/platform-contracts/{gym_contract.json()['id']}",
        headers=superuser_headers,
        json={
            "name": "اختصاصی ویرایش‌شده",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(700, 950, 1100),
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "ACTIVE"
    assert edited.json()["version"] == 2
    gym_rows = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "GYM", "gym_id": env["gym_id"]},
    ).json()
    assert [row["id"] for row in gym_rows if row["status"] == "ACTIVE"] == [
        edited.json()["id"]
    ]
    assert next(
        row for row in gym_rows if row["id"] == gym_contract.json()["id"]
    )["status"] == "ARCHIVED"
    policy = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": date.today().isoformat(),
        },
    )
    assert policy.json()["platform_bp"] == 700
    assert policy.json()["contract_id"] == edited.json()["id"]

    archived = client.post(
        f"/api/v1/finance/platform-contracts/{edited.json()['id']}/archive",
        headers=superuser_headers,
    )
    assert archived.status_code == 200, archived.text
    fallback = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": date.today().isoformat(),
        },
    )
    assert fallback.json()["platform_bp"] == 1100
    assert fallback.json()["source"] == "PLATFORM_DEFAULT"
    assert fallback.json()["contract_id"] == second.json()["id"]


def test_editing_default_contract_rebases_coach_and_preserves_snapshot(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    old_default = create_default_contract(client, superuser_headers)
    vat = create_vat(client, superuser_headers)
    old_coach = create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )
    old_sale = create_sale(
        client,
        env["owner"],
        env["gym_id"],
        tax_ids=[vat["id"]],
        coach_id=env["coach_id"],
    )
    pay(client, env["owner"], env["gym_id"], old_sale["id"])

    edited = client.put(
        f"/api/v1/finance/platform-contracts/{old_default['id']}",
        headers=superuser_headers,
        json={
            "name": "پیش‌فرض ویرایش‌شده",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(1500, 1200, 1500),
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "ACTIVE"
    assert edited.json()["version"] == 2
    assert edited.json()["id"] != old_default["id"]

    stored = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/sales/{old_sale['id']}",
        headers=env["owner"],
    )
    assert stored.status_code == 200
    assert stored.json()["platform_bp"] == 1000
    assert stored.json()["platform_amount_irr"] == 110_000
    assert stored.json()["coach_contract_id"] == old_coach["id"]

    coach_rows = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    active = [row for row in coach_rows if row["status"] == "ACTIVE"]
    assert len(active) == 1
    assert active[0]["platform_bp"] == 1500
    assert active[0]["gym_bp"] == 3500
    assert active[0]["coach_bp"] == 5000
    assert active[0]["version"] == 2
    assert next(
        row for row in coach_rows if row["id"] == old_coach["id"]
    )["status"] == "ARCHIVED"

    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        base_amount_irr=1_000_000,
        coach_id=env["coach_id"],
    )
    assert preview["platform_bp"] == 1500
    assert preview["gym_bp"] == 3500
    assert preview["coach_bp"] == 5000
    assert preview["platform_amount_irr"] == 150_000
    assert preview["gym_amount_irr"] == 350_000
    assert preview["coach_amount_irr"] == 500_000


def test_editing_gym_contract_and_coach_contract_creates_replacing_versions(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    create_default_contract(client, superuser_headers)
    create_coach_contract(
        client, env["owner"], env["gym_id"], env["coach_id"]
    )
    gym_contract = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "اختصاصی اول",
            "scope": "GYM",
            "gym_id": env["gym_id"],
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(800, 1000, 800),
        },
    )
    assert gym_contract.status_code == 200, gym_contract.text

    rebased_after_create = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    active_after_create = [
        row for row in rebased_after_create if row["status"] == "ACTIVE"
    ]
    assert len(active_after_create) == 1
    assert active_after_create[0]["platform_bp"] == 800
    assert active_after_create[0]["gym_bp"] == 4200
    assert active_after_create[0]["coach_bp"] == 5000

    edited_gym = client.put(
        f"/api/v1/finance/platform-contracts/{gym_contract.json()['id']}",
        headers=superuser_headers,
        json={
            "name": "اختصاصی دوم",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(2000, 1000, 2000),
        },
    )
    assert edited_gym.status_code == 200, edited_gym.text
    assert edited_gym.json()["version"] == 2

    rebased_after_edit = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    active_after_edit = [
        row for row in rebased_after_edit if row["status"] == "ACTIVE"
    ]
    assert len(active_after_edit) == 1
    assert active_after_edit[0]["platform_bp"] == 2000
    assert active_after_edit[0]["gym_bp"] == 3000
    assert active_after_edit[0]["coach_bp"] == 5000
    assert active_after_edit[0]["version"] == 3
    assert next(
        row
        for row in rebased_after_edit
        if row["id"] == active_after_create[0]["id"]
    )["status"] == "ARCHIVED"

    updated_coach = client.put(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts/{active_after_edit[0]['id']}",
        headers=env["owner"],
        json={
            "effective_from": date.today().isoformat(),
            "platform_bp": 2000,
            "gym_bp": 2000,
            "coach_bp": 6000,
        },
    )
    assert updated_coach.status_code == 200, updated_coach.text
    assert updated_coach.json()["status"] == "ACTIVE"
    assert updated_coach.json()["version"] == 4
    assert updated_coach.json()["coach_bp"] == 6000
    coach_rows = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    active = [row for row in coach_rows if row["status"] == "ACTIVE"]
    assert len(active) == 1
    assert active[0]["id"] == updated_coach.json()["id"]
    assert next(
        row
        for row in coach_rows
        if row["id"] == active_after_edit[0]["id"]
    )["status"] == "ARCHIVED"

    preview = preview_sale(
        client,
        env["owner"],
        env["gym_id"],
        coach_id=env["coach_id"],
    )
    assert preview["platform_bp"] == 2000
    assert preview["gym_bp"] == 2000
    assert preview["coach_bp"] == 6000
    assert preview["coach_amount_irr"] == 600_000


def test_platform_edit_rejected_when_coach_share_would_conflict(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    default = create_default_contract(client, superuser_headers)
    create_coach_contract(client, env["owner"], env["gym_id"], env["coach_id"])

    conflict = client.put(
        f"/api/v1/finance/platform-contracts/{default['id']}",
        headers=superuser_headers,
        json={
            "name": "درصد ناسازگار",
            "effective_from": date.today().isoformat(),
            "rates": platform_rates(1000, 1200, 6000),
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "coach_contract_platform_conflict"

    defaults = client.get(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        params={"scope": "DEFAULT"},
    ).json()
    active_defaults = [row for row in defaults if row["status"] == "ACTIVE"]
    assert len(active_defaults) == 1
    assert active_defaults[0]["id"] == default["id"]
    policy = client.get(
        "/api/v1/finance/platform-policy",
        headers=env["owner"],
        params={
            "gym_id": env["gym_id"],
            "category": "MEMBERSHIP",
            "on_date": date.today().isoformat(),
        },
    )
    assert policy.json()["platform_bp"] == 1000
    coach_rows = client.get(
        f"/api/v1/finance/gyms/{env['gym_id']}/coach-contracts",
        headers=env["owner"],
    ).json()
    active_coaches = [row for row in coach_rows if row["status"] == "ACTIVE"]
    assert len(active_coaches) == 1
    assert active_coaches[0]["platform_bp"] == 1000
    assert active_coaches[0]["gym_bp"] == 4000
    assert active_coaches[0]["coach_bp"] == 5000


def test_platform_contract_requires_all_categories_and_immediate_dates(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    env = make_finance_gym(client, superuser_headers)
    partial = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "ناقص",
            "scope": "GYM",
            "gym_id": env["gym_id"],
            "effective_from": date.today().isoformat(),
            "rates": [{"category": "MEMBERSHIP", "percent_bp": 800}],
        },
    )
    assert partial.status_code == 400
    assert partial.json()["detail"] == "contract_requires_all_categories"

    future = client.post(
        "/api/v1/finance/platform-contracts",
        headers=superuser_headers,
        json={
            "name": "آینده",
            "scope": "DEFAULT",
            "effective_from": (date.today() + timedelta(days=1)).isoformat(),
            "rates": platform_rates(),
        },
    )
    assert future.status_code == 400
    assert future.json()["detail"] == "effective_date_future"
