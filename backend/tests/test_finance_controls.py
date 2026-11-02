from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.deps import GymContext
from app.finance_models import (
    FinanceOpeningBalanceCreate,
    FinanceOpeningBalanceLine,
)
from app.models import Gym, GymMembership, User
from app.services.access import get_membership_roles
from app.services.finance import post_opening_balance, resolve_finance_scope
from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.utils.helpers import gym_headers, unique_email


def _admin_scope(
    session: Session, gym_id: uuid.UUID
) -> tuple[object, User]:
    gym = session.get(Gym, gym_id)
    assert gym is not None
    user = session.get(User, gym.owner_id)
    assert user is not None
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym.id,
            GymMembership.user_id == user.id,
        )
    ).first()
    ctx = GymContext(
        gym=gym,
        membership=membership,
        roles=get_membership_roles(session, membership.id) if membership else set(),
        is_owner=True,
        is_superuser=False,
    )
    return resolve_finance_scope(session, ctx, user), user


def _staff_scope(
    session: Session, gym_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[object, User]:
    gym = session.get(Gym, gym_id)
    assert gym is not None
    user = session.get(User, user_id)
    assert user is not None
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym.id,
            GymMembership.user_id == user.id,
        )
    ).first()
    assert membership is not None
    ctx = GymContext(
        gym=gym,
        membership=membership,
        roles=get_membership_roles(session, membership.id),
        is_owner=False,
        is_superuser=False,
    )
    return resolve_finance_scope(session, ctx, user), user


def _body(amount: int = 500_000) -> FinanceOpeningBalanceCreate:
    return FinanceOpeningBalanceCreate(
        posting_date=date(2026, 11, 2),
        description="Opening",
        lines=[
            FinanceOpeningBalanceLine(account_code="1000", debit_irr=amount),
            FinanceOpeningBalanceLine(account_code="3000", credit_irr=amount),
        ],
    )


def test_disabling_finance_between_resolution_and_posting_blocks_the_posting(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, _owner_headers = make_owner(
        client, superuser_headers, name="Control Disable Gym"
    )
    gym_id = uuid.UUID(str(gym["id"]))
    scope, actor = _admin_scope(db_session, gym_id)
    assert scope.enabled is True  # type: ignore[attr-defined]

    disabled = client.patch(
        "/api/v1/finance/settings",
        headers={**superuser_headers, "X-Gym-ID": str(gym_id)},
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    db_session.expire_all()

    with pytest.raises(HTTPException) as failure:
        post_opening_balance(
            db_session,
            scope=scope,  # type: ignore[arg-type]
            actor=actor,
            body=_body(),
            operation_key=uuid.uuid4().hex,
        )
    assert failure.value.status_code == 409
    assert failure.value.detail == "finance_disabled"


def test_lowering_a_grant_limit_between_resolution_and_posting_blocks_the_posting(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Control Limit Gym")
    gym_id = str(gym["id"])
    staff_email = unique_email("finance-staff")
    add_staff(
        client, owner, gym_id, roles=["FINANCE_STAFF"], email=staff_email
    )
    staff = gym_headers(
        client, email=staff_email, password="staff-pass-456", gym_id=gym_id
    )
    staff_user_id = client.get("/api/v1/users/me", headers=staff).json()["id"]

    granted = client.put(
        f"/api/v1/finance/grants/{staff_user_id}",
        headers=owner,
        json={
            "grants": [
                {
                    "permission": "finance.opening.manage",
                    "amount_limit_irr": 1_000_000,
                }
            ]
        },
    )
    assert granted.status_code == 200, granted.text

    scope, actor = _staff_scope(
        db_session, uuid.UUID(gym_id), uuid.UUID(staff_user_id)
    )
    assert scope.amount_limit("finance.opening.manage") == 1_000_000  # type: ignore[attr-defined]

    lowered = client.put(
        f"/api/v1/finance/grants/{staff_user_id}",
        headers=owner,
        json={
            "grants": [
                {"permission": "finance.opening.manage", "amount_limit_irr": 100}
            ]
        },
    )
    assert lowered.status_code == 200, lowered.text
    db_session.expire_all()

    with pytest.raises(HTTPException) as failure:
        post_opening_balance(
            db_session,
            scope=scope,  # type: ignore[arg-type]
            actor=actor,
            body=_body(500_000),
            operation_key=uuid.uuid4().hex,
        )
    assert failure.value.status_code == 403
    assert failure.value.detail == "finance_amount_limit_exceeded"


def test_an_athlete_with_finance_history_is_not_hard_deleted(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    from app.finance_models import FinanceAudit
    from tests.utils.helpers import create_athlete

    gym, owner = make_owner(client, superuser_headers, name="Retention Gym")
    gym_id = str(gym["id"])
    coach_email = unique_email("retention-coach")
    add_staff(client, owner, gym_id, roles=["COACH"], email=coach_email)
    coach = gym_headers(
        client, email=coach_email, password="staff-pass-456", gym_id=gym_id
    )
    coach_user_id = client.get("/api/v1/users/me", headers=coach).json()["id"]

    with_history = create_athlete(
        client,
        coach,
        email=unique_email("finance-history-athlete"),
        coach_user_id=coach_user_id,
    )["athlete"]["profile"]
    db_session.add(
        FinanceAudit(
            gym_id=uuid.UUID(gym_id),
            actor_id=uuid.UUID(with_history["user_id"]),
            action="finance.opening_balance.posted",
            target_type="finance_journal",
        )
    )
    db_session.commit()

    blocked = client.delete(
        f"/api/v1/athletes/{with_history['user_id']}", headers=owner
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == "user_has_finance_history"

    # The refusal is atomic: the athlete is still fully present.
    still_there = client.get(
        f"/api/v1/athletes/{with_history['user_id']}", headers=owner
    )
    assert still_there.status_code == 200, still_there.text

    without_history = create_athlete(
        client,
        coach,
        email=unique_email("plain-athlete"),
        coach_user_id=coach_user_id,
    )["athlete"]["profile"]
    deleted = client.delete(
        f"/api/v1/athletes/{without_history['user_id']}", headers=owner
    )
    assert deleted.status_code == 200, deleted.text
