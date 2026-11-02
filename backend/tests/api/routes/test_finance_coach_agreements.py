from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.utils.helpers import gym_headers, unique_email

pytestmark = pytest.mark.usefixtures("client")


def make_coach(
    client: TestClient, owner: dict[str, str], gym_id: str, prefix: str = "coach"
) -> tuple[str, dict[str, str]]:
    email = unique_email(f"{prefix}-agreement")
    add_staff(client, owner, gym_id, roles=["COACH"], email=email)
    headers = gym_headers(
        client, email=email, password="staff-pass-456", gym_id=gym_id
    )
    user_id = client.get("/api/v1/users/me", headers=headers).json()["id"]
    return user_id, headers


def agreement_payload(coach_user_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "coach_user_id": coach_user_id,
        "effective_from": "2026-11-01",
        "effective_to": None,
        "mode": "DIRECT",
        "vesting_mode": "ON_DATE",
        "vesting_days": 7,
        "notes": "standard contract",
        "terms": [
            {
                "recipient": "COACH",
                "basis": "PERCENT",
                "percent_bp": 3000,
                "label": "coach share",
            },
            {
                "recipient": "GYM",
                "basis": "PERCENT",
                "percent_bp": 7000,
                "label": "gym share",
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_versioned_coach_agreement_is_created_activated_and_gym_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Agreement Gym")
    other_gym, other_owner = make_owner(
        client, superuser_headers, name="Agreement Other Gym"
    )
    gym_id = str(gym["id"])
    coach_id, coach_headers = make_coach(client, owner, gym_id)
    other_coach_id, _ = make_coach(
        client, other_owner, str(other_gym["id"]), prefix="other"
    )

    created = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(coach_id),
    )
    assert created.status_code == 200, created.text
    agreement = created.json()
    assert agreement["status"] == "DRAFT"
    assert agreement["version"] == 1
    assert agreement["coach_user_id"] == coach_id
    assert [term["sequence"] for term in agreement["terms"]] == [1, 2]
    assert agreement["terms"][0]["recipient"] == "COACH"

    activated = client.post(
        f"/api/v1/finance/coach-agreements/{agreement['id']}/activate",
        headers=owner,
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "ACTIVE"
    assert activated.json()["activated_at"] is not None

    second = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            effective_from="2026-12-01",
            terms=[
                {
                    "recipient": "COACH",
                    "basis": "FIXED",
                    "fixed_irr": 250_000,
                },
                {
                    "recipient": "GYM",
                    "basis": "PERCENT",
                    "percent_bp": 10000,
                },
            ],
        ),
    )
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2
    assert second.json()["terms"][0]["basis"] == "FIXED"

    listed = client.get("/api/v1/finance/coach-agreements", headers=owner)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()["data"]} == {
        agreement["id"],
        second.json()["id"],
    }
    coach_view = client.get(
        f"/api/v1/finance/coach-agreements?coach_user_id={coach_id}",
        headers=owner,
    )
    assert coach_view.status_code == 200
    assert coach_view.json()["count"] == 2

    other_list = client.get(
        "/api/v1/finance/coach-agreements", headers=other_owner
    )
    assert other_list.status_code == 200
    assert other_list.json()["count"] == 0

    forbidden = client.post(
        "/api/v1/finance/coach-agreements",
        headers=coach_headers,
        json=agreement_payload(coach_id),
    )
    assert forbidden.status_code == 403, forbidden.text

    # A coach from another gym cannot be attached to this gym's contract.
    cross_gym = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(other_coach_id),
    )
    assert cross_gym.status_code == 400, cross_gym.text
    assert cross_gym.json()["detail"] == "invalid_coach_agreement_coach"


def test_coach_agreement_requires_a_coach_term(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Agreement Term Gym")
    coach_id, _ = make_coach(client, owner, str(gym["id"]))
    payload = agreement_payload(
        coach_id,
        terms=[
            {"recipient": "GYM", "basis": "PERCENT", "percent_bp": 10000}
        ],
    )
    rejected = client.post(
        "/api/v1/finance/coach-agreements", headers=owner, json=payload
    )
    assert rejected.status_code == 400, rejected.text
    assert rejected.json()["detail"] == "coach_term_required"

    invalid_percent = client.post(
        "/api/v1/finance/coach-agreements",
        headers=owner,
        json=agreement_payload(
            coach_id,
            terms=[
                {
                    "recipient": "COACH",
                    "basis": "PERCENT",
                    "percent_bp": 10_001,
                }
            ],
        ),
    )
    assert invalid_percent.status_code == 422, invalid_percent.text
