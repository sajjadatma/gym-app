from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.finance_models import FinanceAudit, FinanceGrant
from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.api.routes.test_finance_journal import opening_payload, post_opening

pytestmark = pytest.mark.usefixtures("client")


def grant(
    client: TestClient,
    headers: dict[str, str],
    user_id: str,
    grants: list[dict[str, object]],
) -> object:
    return client.put(
        f"/api/v1/finance/grants/{user_id}",
        headers=headers,
        json={"grants": grants},
    )


def test_admin_grants_opening_permission_with_an_amount_limit(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Limit Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    me = client.get("/api/v1/users/me", headers=staff).json()
    staff_id = me["id"]

    listed = client.get("/api/v1/finance/grants", headers=owner)
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] == 0

    updated = grant(
        client,
        owner,
        staff_id,
        [{"permission": "finance.opening.manage", "amount_limit_irr": 1_000_000}],
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["user_id"] == staff_id
    assert body["grants"] == [
        {"permission": "finance.opening.manage", "amount_limit_irr": 1_000_000}
    ]

    settings = client.get("/api/v1/finance/settings", headers=staff).json()
    assert settings["permissions"] == [
        "finance.view",
        "finance.opening.manage",
    ]

    within_limit = post_opening(
        client, staff, opening_payload(debit=1_000_000)
    )
    assert within_limit.status_code == 200, within_limit.text

    # A second gym with the same limit proves the excess is refused.
    gym_b, owner_b = make_owner(client, superuser_headers, name="Grant Limit Gym B")
    staff_b = add_staff(client, owner_b, str(gym_b["id"]), roles=["FINANCE_STAFF"])
    staff_b_id = client.get("/api/v1/users/me", headers=staff_b).json()["id"]
    assert (
        grant(
            client,
            owner_b,
            staff_b_id,
            [
                {
                    "permission": "finance.opening.manage",
                    "amount_limit_irr": 1_000_000,
                }
            ],
        ).status_code
        == 200
    )
    over_limit = post_opening(
        client, staff_b, opening_payload(debit=1_000_001)
    )
    assert over_limit.status_code == 403, over_limit.text
    assert over_limit.json()["detail"] == "finance_amount_limit_exceeded"

    # A rejected over-limit attempt must not leave a journal behind.
    assert (
        client.get("/api/v1/finance/journal", headers=staff_b).json()["count"]
        == 0
    )

    latest = client.get("/api/v1/finance/grants", headers=owner)
    assert latest.json()["count"] == 1
    assert latest.json()["data"][0]["grants"] == [
        {"permission": "finance.opening.manage", "amount_limit_irr": 1_000_000}
    ]


def test_grants_require_an_active_finance_staff_target(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Target Gym")
    coach = add_staff(client, owner, str(gym["id"]), roles=["COACH"])
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]

    not_finance_staff = grant(
        client,
        owner,
        coach_id,
        [{"permission": "finance.opening.manage"}],
    )
    assert not_finance_staff.status_code == 400, not_finance_staff.text
    assert not_finance_staff.json()["detail"] == "finance_staff_required"

    unknown = grant(
        client,
        owner,
        str(uuid.uuid4()),
        [{"permission": "finance.opening.manage"}],
    )
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["detail"] == "user_not_found"

    # An inactive finance membership cannot hold an actionable grant.
    finance_staff = add_staff(
        client, owner, str(gym["id"]), roles=["FINANCE_STAFF"]
    )
    finance_id = client.get("/api/v1/users/me", headers=finance_staff).json()["id"]
    membership_id = next(
        row["membership_id"]
        for row in client.get(
            f"/api/v1/gyms/{gym['id']}/members?staff_only=true",
            headers=owner,
        ).json()["data"]
        if row["user_id"] == finance_id
    )
    deactivated = client.patch(
        f"/api/v1/gyms/{gym['id']}/members/{membership_id}",
        headers=owner,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text

    inactive = grant(
        client, owner, finance_id, [{"permission": "finance.opening.manage"}]
    )
    assert inactive.status_code == 400, inactive.text
    assert inactive.json()["detail"] == "finance_staff_required"

    blocked = post_opening(client, finance_staff)
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"] == "not_a_gym_member"


def test_only_gym_finance_admins_can_manage_grants(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Permission Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]

    self_grant = grant(
        client, staff, staff_id, [{"permission": "finance.opening.manage"}]
    )
    assert self_grant.status_code == 403, self_grant.text
    assert self_grant.json()["detail"] == "finance_manage_required"

    staff_list = client.get("/api/v1/finance/grants", headers=staff)
    assert staff_list.status_code == 403, staff_list.text

    coach = add_staff(client, owner, str(gym["id"]), roles=["COACH"])
    coach_attempt = grant(
        client, coach, staff_id, [{"permission": "finance.opening.manage"}]
    )
    assert coach_attempt.status_code == 403, coach_attempt.text
    assert coach_attempt.json()["detail"] == "finance_access_denied"

    superuser_grant = grant(
        client,
        {**superuser_headers, "X-Gym-ID": str(gym["id"])},
        staff_id,
        [{"permission": "finance.opening.manage"}],
    )
    assert superuser_grant.status_code == 200, superuser_grant.text


def test_replacing_grants_revokes_removed_permissions(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Revoke Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]

    granted = grant(
        client,
        owner,
        staff_id,
        [{"permission": "finance.period.manage"}],
    )
    assert granted.status_code == 200, granted.text

    post_opening(client, owner)
    closed = client.post("/api/v1/finance/periods/close", headers=staff)
    assert closed.status_code == 200, closed.text

    revoked = grant(client, owner, staff_id, [])
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["grants"] == []

    denied = client.post("/api/v1/finance/periods/close", headers=staff)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "finance_access_denied"

    assert client.get("/api/v1/finance/settings", headers=staff).json()[
        "permissions"
    ] == ["finance.view"]


def test_grant_payload_is_validated(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Validation Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]

    unknown_permission = grant(
        client, owner, staff_id, [{"permission": "finance.everything"}]
    )
    assert unknown_permission.status_code == 422, unknown_permission.text

    implicit_view = grant(
        client, owner, staff_id, [{"permission": "finance.view"}]
    )
    assert implicit_view.status_code == 422, implicit_view.text

    negative_limit = grant(
        client,
        owner,
        staff_id,
        [{"permission": "finance.opening.manage", "amount_limit_irr": -1}],
    )
    assert negative_limit.status_code == 422, negative_limit.text

    duplicate = grant(
        client,
        owner,
        staff_id,
        [
            {"permission": "finance.opening.manage"},
            {"permission": "finance.opening.manage"},
        ],
    )
    assert duplicate.status_code == 422, duplicate.text


def test_grants_are_tenant_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Grant Scope A")
    gym_b, owner_b = make_owner(client, superuser_headers, name="Grant Scope B")
    staff_a = add_staff(client, owner_a, str(gym_a["id"]), roles=["FINANCE_STAFF"])
    staff_a_id = client.get("/api/v1/users/me", headers=staff_a).json()["id"]

    cross = grant(
        client,
        {**owner_b, "X-Gym-ID": str(gym_a["id"])},
        staff_a_id,
        [{"permission": "finance.opening.manage"}],
    )
    assert cross.status_code in {403, 404}, cross.text

    # The grant list only shows grants for the selected gym.
    assert client.get("/api/v1/finance/grants", headers=owner_a).json()["count"] == 0


def test_grant_changes_leave_an_audit_trail(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Grant Audit Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]

    grant(
        client,
        owner,
        staff_id,
        [{"permission": "finance.opening.manage", "amount_limit_irr": 500_000}],
    )
    grant(client, owner, staff_id, [])

    rows = db_session.exec(
        select(FinanceAudit)
        .where(FinanceAudit.gym_id == uuid.UUID(str(gym["id"])))
        .order_by(FinanceAudit.created_at)
    ).all()
    actions = [row.action for row in rows]
    assert actions.count("finance.grants.updated") == 2

    granted_row = next(row for row in rows if row.action == "finance.grants.updated")
    assert granted_row.target_id == uuid.UUID(staff_id)
    assert granted_row.detail["granted"] == [
        {"permission": "finance.opening.manage", "amount_limit_irr": 500_000}
    ]

    revoked_row = [row for row in rows if row.action == "finance.grants.updated"][-1]
    assert revoked_row.detail["revoked"] == ["finance.opening.manage"]

    active = db_session.exec(
        select(FinanceGrant).where(
            FinanceGrant.gym_id == uuid.UUID(str(gym["id"])),
            col(FinanceGrant.revoked_at).is_(None),
        )
    ).all()
    assert active == []


def _membership_id(
    client: TestClient, owner: dict[str, str], gym_id: str, user_id: str
) -> str:
    return next(
        row["membership_id"]
        for row in client.get(
            f"/api/v1/gyms/{gym_id}/members?staff_only=true", headers=owner
        ).json()["data"]
        if row["user_id"] == user_id
    )


def test_removing_the_finance_role_revokes_active_grants(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Role Removal Gym")
    gym_id = str(gym["id"])
    staff = add_staff(client, owner, gym_id, roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    assert (
        grant(
            client,
            owner,
            staff_id,
            [{"permission": "finance.opening.manage"}],
        ).status_code
        == 200
    )

    updated = client.patch(
        f"/api/v1/gyms/{gym_id}/members/{_membership_id(client, owner, gym_id, staff_id)}",
        headers=owner,
        json={"roles": ["COACH"]},
    )
    assert updated.status_code == 200, updated.text

    assert client.get("/api/v1/finance/grants", headers=owner).json()["count"] == 0
    denied = client.get("/api/v1/finance/settings", headers=staff)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "finance_access_denied"

    rows = db_session.exec(
        select(FinanceAudit)
        .where(FinanceAudit.gym_id == uuid.UUID(gym_id))
        .order_by(FinanceAudit.created_at)
    ).all()
    revoked = [row for row in rows if row.action == "finance.grants.revoked"]
    assert len(revoked) == 1
    assert revoked[0].target_id == uuid.UUID(staff_id)
    assert revoked[0].detail["permissions"] == ["finance.opening.manage"]

    # Re-adding the role later must not silently restore the old grant.
    readded = client.patch(
        f"/api/v1/gyms/{gym_id}/members/{_membership_id(client, owner, gym_id, staff_id)}",
        headers=owner,
        json={"roles": ["FINANCE_STAFF"]},
    )
    assert readded.status_code == 200, readded.text
    settings = client.get("/api/v1/finance/settings", headers=staff)
    assert settings.status_code == 200, settings.text
    assert settings.json()["permissions"] == ["finance.view"]
    assert client.get("/api/v1/finance/grants", headers=owner).json()["count"] == 0


def test_deactivating_a_finance_membership_revokes_active_grants(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Deactivate Grants Gym")
    gym_id = str(gym["id"])
    staff = add_staff(client, owner, gym_id, roles=["FINANCE_STAFF"])
    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    assert (
        grant(
            client,
            owner,
            staff_id,
            [{"permission": "finance.period.manage"}],
        ).status_code
        == 200
    )

    deactivated = client.patch(
        f"/api/v1/gyms/{gym_id}/members/{_membership_id(client, owner, gym_id, staff_id)}",
        headers=owner,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text

    assert client.get("/api/v1/finance/grants", headers=owner).json()["count"] == 0
    blocked = client.get("/api/v1/finance/settings", headers=staff)
    assert blocked.status_code == 403, blocked.text
