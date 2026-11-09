from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.finance_models import (
    FinanceAllocation,
    FinanceAudit,
    FinanceCoachContract,
    FinancePayment,
    FinancePlatformContract,
    FinancePlatformRate,
    FinanceRefund,
    FinanceRefundAdjustment,
    FinanceSale,
    FinanceSaleTax,
    FinanceSettlement,
    FinanceSettlementItem,
    FinanceTaxDefinition,
)
from app.models import (
    Gym,
    GymMembership,
    GymMembershipRole,
    User,
)

CATEGORIES = ("MEMBERSHIP", "NUTRITION", "TRAINING")
PARTIES = ("PLATFORM", "GYM", "COACH")
MAX_BP = 10000


def finance_today() -> date:
    return datetime.now(UTC).date()


def record_finance_audit(
    session: Session,
    *,
    actor: User | None,
    gym_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(
        FinanceAudit(
            gym_id=gym_id,
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail or {},
        )
    )


def _roles(session: Session, membership_id: uuid.UUID) -> set[str]:
    rows = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == membership_id
        )
    ).all()
    return {row.role for row in rows}


def require_gym_finance_admin(
    session: Session, user: User, gym_id: uuid.UUID
) -> Gym:
    gym = session.get(Gym, gym_id)
    if gym is None or not gym.is_active:
        raise HTTPException(status_code=404, detail="gym_not_found")
    if user.is_superuser:
        return gym
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == user.id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=403, detail="not_a_gym_member")
    if gym.owner_id != user.id and "GYM_ADMIN" not in _roles(
        session, membership.id
    ):
        raise HTTPException(status_code=403, detail="gym_admin_required")
    return gym


def require_any_finance_admin(session: Session, user: User) -> None:
    if user.is_superuser:
        return
    memberships = session.exec(
        select(GymMembership).where(
            GymMembership.user_id == user.id,
            col(GymMembership.is_active).is_(True),
        )
    ).all()
    for membership in memberships:
        gym = session.get(Gym, membership.gym_id)
        if gym and (gym.owner_id == user.id or "GYM_ADMIN" in _roles(session, membership.id)):
            return
    raise HTTPException(status_code=403, detail="gym_admin_required")


def _validate_category(category: str) -> None:
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="invalid_category")


def _validate_bp(value: int, detail: str = "invalid_percentage") -> None:
    if value < 0 or value > MAX_BP:
        raise HTTPException(status_code=400, detail=detail)


def _validate_platform_rates(rates: list[dict[str, Any]]) -> None:
    if not rates:
        raise HTTPException(status_code=400, detail="contract_rates_required")
    seen: set[str] = set()
    for rate in rates:
        category = rate["category"]
        _validate_category(category)
        if category in seen:
            raise HTTPException(status_code=400, detail="duplicate_contract_category")
        seen.add(category)
        _validate_bp(int(rate["percent_bp"]))
    if seen != set(CATEGORIES):
        raise HTTPException(
            status_code=400, detail="contract_requires_all_categories"
        )


def _next_platform_version(
    session: Session, *, scope: str, gym_id: uuid.UUID | None
) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.max(FinancePlatformContract.version), 0)).where(
                FinancePlatformContract.scope == scope,
                FinancePlatformContract.gym_id == gym_id,
            )
        ).one()
    ) + 1


def _archive_active_platform_contracts(
    session: Session, *, scope: str, gym_id: uuid.UUID | None
) -> None:
    rows = session.exec(
        select(FinancePlatformContract).where(
            FinancePlatformContract.scope == scope,
            FinancePlatformContract.gym_id == gym_id,
            FinancePlatformContract.status == "ACTIVE",
        )
    ).all()
    for row in rows:
        row.status = "ARCHIVED"
        session.add(row)
    if rows:
        session.flush()


def _add_platform_contract(
    session: Session,
    *,
    actor: User,
    name: str,
    scope: str,
    gym_id: uuid.UUID | None,
    effective_from: date,
    effective_to: date | None,
    rates: list[dict[str, Any]],
) -> FinancePlatformContract:
    version = _next_platform_version(session, scope=scope, gym_id=gym_id)
    contract = FinancePlatformContract(
        name=name.strip(),
        scope=scope,
        gym_id=gym_id,
        version=version,
        status="ACTIVE",
        effective_from=effective_from,
        effective_to=effective_to,
        created_by_id=actor.id,
        activated_at=datetime.now(UTC),
    )
    session.add(contract)
    session.flush()
    for rate in rates:
        session.add(
            FinancePlatformRate(
                contract_id=contract.id,
                category=rate["category"],
                percent_bp=int(rate["percent_bp"]),
            )
        )
    session.flush()
    return contract


def _next_coach_version(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    category: str,
) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.max(FinanceCoachContract.version), 0)).where(
                FinanceCoachContract.gym_id == gym_id,
                FinanceCoachContract.coach_user_id == coach_user_id,
                FinanceCoachContract.category == category,
            )
        ).one()
    ) + 1


def _archive_active_coach_contracts(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    category: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(FinanceCoachContract).where(
        FinanceCoachContract.gym_id == gym_id,
        FinanceCoachContract.coach_user_id == coach_user_id,
        FinanceCoachContract.category == category,
        FinanceCoachContract.status == "ACTIVE",
    )
    if exclude_id is not None:
        statement = statement.where(FinanceCoachContract.id != exclude_id)
    rows = session.exec(statement).all()
    for row in rows:
        row.status = "ARCHIVED"
        session.add(row)
    if rows:
        session.flush()


def _platform_contract_public(
    session: Session, contract: FinancePlatformContract
) -> dict[str, Any]:
    rates = session.exec(
        select(FinancePlatformRate)
        .where(FinancePlatformRate.contract_id == contract.id)
        .order_by(col(FinancePlatformRate.category))
    ).all()
    return {
        "id": contract.id,
        "name": contract.name,
        "scope": contract.scope,
        "gym_id": contract.gym_id,
        "version": contract.version,
        "status": contract.status,
        "effective_from": contract.effective_from,
        "effective_to": contract.effective_to,
        "rates": [
            {"category": row.category, "percent_bp": row.percent_bp}
            for row in rates
        ],
        "activated_at": contract.activated_at,
        "created_at": contract.created_at,
    }


def list_platform_contracts(
    session: Session,
    *,
    scope: str | None = None,
    gym_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    statement = select(FinancePlatformContract).order_by(
        col(FinancePlatformContract.scope),
        col(FinancePlatformContract.gym_id),
        col(FinancePlatformContract.version).desc(),
    )
    if scope:
        statement = statement.where(FinancePlatformContract.scope == scope)
    if gym_id:
        statement = statement.where(FinancePlatformContract.gym_id == gym_id)
    rows = session.exec(statement).all()
    return [_platform_contract_public(session, row) for row in rows]


def create_platform_contract(
    session: Session,
    *,
    actor: User,
    name: str,
    scope: str,
    gym_id: uuid.UUID | None,
    effective_from: date,
    effective_to: date | None,
    rates: list[dict[str, Any]],
) -> dict[str, Any]:
    if scope not in ("DEFAULT", "GYM"):
        raise HTTPException(status_code=400, detail="invalid_contract_scope")
    if scope == "DEFAULT" and gym_id is not None:
        raise HTTPException(status_code=400, detail="default_contract_gym_forbidden")
    if scope == "GYM":
        if gym_id is None:
            raise HTTPException(status_code=400, detail="gym_contract_gym_required")
        if session.get(Gym, gym_id) is None:
            raise HTTPException(status_code=404, detail="gym_not_found")
    if not name.strip():
        raise HTTPException(status_code=400, detail="contract_name_required")
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(status_code=400, detail="invalid_effective_dates")
    if effective_from > finance_today():
        raise HTTPException(status_code=400, detail="effective_date_future")
    _validate_platform_rates(rates)

    _archive_active_platform_contracts(session, scope=scope, gym_id=gym_id)
    contract = _add_platform_contract(
        session,
        actor=actor,
        name=name,
        scope=scope,
        gym_id=gym_id,
        effective_from=effective_from,
        effective_to=effective_to,
        rates=rates,
    )
    _sync_active_coach_contracts(session, actor=actor)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="platform_contract.created",
        entity_type="platform_contract",
        entity_id=contract.id,
        detail={"scope": scope, "version": contract.version},
    )
    session.commit()
    session.refresh(contract)
    return _platform_contract_public(session, contract)


def update_platform_contract(
    session: Session,
    *,
    actor: User,
    contract_id: uuid.UUID,
    name: str,
    effective_from: date,
    effective_to: date | None,
    rates: list[dict[str, Any]],
) -> dict[str, Any]:
    original = session.get(FinancePlatformContract, contract_id)
    if original is None:
        raise HTTPException(status_code=404, detail="platform_contract_not_found")
    if not name.strip():
        raise HTTPException(status_code=400, detail="contract_name_required")
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(status_code=400, detail="invalid_effective_dates")
    if effective_from > finance_today():
        raise HTTPException(status_code=400, detail="effective_date_future")
    _validate_platform_rates(rates)

    _archive_active_platform_contracts(
        session, scope=original.scope, gym_id=original.gym_id
    )
    contract = _add_platform_contract(
        session,
        actor=actor,
        name=name,
        scope=original.scope,
        gym_id=original.gym_id,
        effective_from=effective_from,
        effective_to=effective_to,
        rates=rates,
    )
    _sync_active_coach_contracts(session, actor=actor)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=original.gym_id,
        action="platform_contract.updated",
        entity_type="platform_contract",
        entity_id=contract.id,
        detail={
            "scope": original.scope,
            "version": contract.version,
            "previous_contract_id": str(original.id),
            "previous_version": original.version,
        },
    )
    session.commit()
    session.refresh(contract)
    return _platform_contract_public(session, contract)


def activate_platform_contract(
    session: Session, *, actor: User, contract_id: uuid.UUID
) -> dict[str, Any]:
    contract = session.get(FinancePlatformContract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="platform_contract_not_found")
    if contract.status == "ACTIVE":
        return _platform_contract_public(session, contract)
    if contract.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="contract_archived")
    if contract.effective_from > finance_today():
        raise HTTPException(status_code=400, detail="effective_date_future")
    _archive_active_platform_contracts(
        session, scope=contract.scope, gym_id=contract.gym_id
    )
    contract.status = "ACTIVE"
    contract.activated_at = datetime.now(UTC)
    session.add(contract)
    session.flush()
    _sync_active_coach_contracts(session, actor=actor)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=contract.gym_id,
        action="platform_contract.activated",
        entity_type="platform_contract",
        entity_id=contract.id,
        detail={"version": contract.version},
    )
    session.commit()
    session.refresh(contract)
    return _platform_contract_public(session, contract)


def archive_platform_contract(
    session: Session, *, actor: User, contract_id: uuid.UUID
) -> dict[str, Any]:
    contract = session.get(FinancePlatformContract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="platform_contract_not_found")
    if contract.status == "ARCHIVED":
        return _platform_contract_public(session, contract)
    was_active = contract.status == "ACTIVE"
    contract.status = "ARCHIVED"
    session.add(contract)
    session.flush()
    if was_active:
        _sync_active_coach_contracts(session, actor=actor)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=contract.gym_id,
        action="platform_contract.archived",
        entity_type="platform_contract",
        entity_id=contract.id,
        detail={"version": contract.version},
    )
    session.commit()
    session.refresh(contract)
    return _platform_contract_public(session, contract)


def _sync_active_coach_contracts(session: Session, *, actor: User) -> None:
    """Keep active coach contracts aligned with the current platform policy.

    Coach percentages stay fixed; the gym share absorbs platform changes.
    A platform change that would leave the gym with a negative share is
    rejected so the caller can adjust coach contracts first.
    """
    today = finance_today()
    rows = session.exec(
        select(FinanceCoachContract).where(
            FinanceCoachContract.status == "ACTIVE",
            FinanceCoachContract.effective_from <= today,
            or_(
                col(FinanceCoachContract.effective_to).is_(None),
                col(FinanceCoachContract.effective_to) >= today,
            ),
        )
    ).all()
    for row in rows:
        try:
            policy = resolve_platform_policy(
                session,
                gym_id=row.gym_id,
                category=row.category,
                on_date=today,
            )
        except HTTPException as exc:
            if exc.detail == "platform_policy_missing":
                continue
            raise
        if (
            row.platform_bp == policy["platform_bp"]
            and row.platform_contract_id == policy["contract_id"]
            and row.platform_source == policy["source"]
        ):
            continue
        new_gym_bp = MAX_BP - policy["platform_bp"] - row.coach_bp
        if new_gym_bp < 0:
            raise HTTPException(
                status_code=409, detail="coach_contract_platform_conflict"
            )
        previous_id = row.id
        previous_version = row.version
        row.status = "ARCHIVED"
        session.add(row)
        session.flush()
        successor = FinanceCoachContract(
            gym_id=row.gym_id,
            coach_user_id=row.coach_user_id,
            category=row.category,
            version=_next_coach_version(
                session,
                gym_id=row.gym_id,
                coach_user_id=row.coach_user_id,
                category=row.category,
            ),
            status="ACTIVE",
            effective_from=today,
            effective_to=row.effective_to,
            platform_bp=policy["platform_bp"],
            gym_bp=new_gym_bp,
            coach_bp=row.coach_bp,
            platform_contract_id=policy["contract_id"],
            platform_source=policy["source"],
            created_by_id=actor.id,
            activated_at=datetime.now(UTC),
        )
        session.add(successor)
        session.flush()
        record_finance_audit(
            session,
            actor=actor,
            gym_id=row.gym_id,
            action="coach_contract.rebased",
            entity_type="coach_contract",
            entity_id=successor.id,
            detail={
                "category": row.category,
                "version": successor.version,
                "previous_contract_id": str(previous_id),
                "previous_version": previous_version,
                "platform_bp": policy["platform_bp"],
                "gym_bp": new_gym_bp,
                "coach_bp": row.coach_bp,
            },
        )


def resolve_platform_policy(
    session: Session, *, gym_id: uuid.UUID, category: str, on_date: date
) -> dict[str, Any]:
    _validate_category(category)
    base_filters = [
        FinancePlatformContract.status == "ACTIVE",
        FinancePlatformContract.effective_from <= on_date,
        or_(
            col(FinancePlatformContract.effective_to).is_(None),
            col(FinancePlatformContract.effective_to) >= on_date,
        ),
    ]
    gym_rate = session.exec(
        select(FinancePlatformRate, FinancePlatformContract)
        .join(
            FinancePlatformContract,
            col(FinancePlatformRate.contract_id)
            == col(FinancePlatformContract.id),
        )
        .where(
            *base_filters,  # type: ignore[arg-type]
            FinancePlatformContract.scope == "GYM",
            FinancePlatformContract.gym_id == gym_id,
            FinancePlatformRate.category == category,
        )
        .order_by(
            col(FinancePlatformContract.effective_from).desc(),
            col(FinancePlatformContract.version).desc(),
        )
    ).first()
    if gym_rate is not None:
        rate, contract = gym_rate
        return {
            "gym_id": gym_id,
            "category": category,
            "on_date": on_date,
            "platform_bp": rate.percent_bp,
            "source": "GYM_OVERRIDE",
            "contract_id": contract.id,
            "contract_version": contract.version,
        }
    default_rate = session.exec(
        select(FinancePlatformRate, FinancePlatformContract)
        .join(
            FinancePlatformContract,
            col(FinancePlatformRate.contract_id)
            == col(FinancePlatformContract.id),
        )
        .where(
            *base_filters,  # type: ignore[arg-type]
            FinancePlatformContract.scope == "DEFAULT",
            FinancePlatformRate.category == category,
        )
        .order_by(
            col(FinancePlatformContract.effective_from).desc(),
            col(FinancePlatformContract.version).desc(),
        )
    ).first()
    if default_rate is None:
        raise HTTPException(status_code=400, detail="platform_policy_missing")
    rate, contract = default_rate
    return {
        "gym_id": gym_id,
        "category": category,
        "on_date": on_date,
        "platform_bp": rate.percent_bp,
        "source": "PLATFORM_DEFAULT",
        "contract_id": contract.id,
        "contract_version": contract.version,
    }

# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------


def tax_public(row: FinanceTaxDefinition) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "calculation": row.calculation,
        "percent_bp": row.percent_bp,
        "fixed_amount_irr": row.fixed_amount_irr,
        "is_active": row.is_active,
        "is_default_vat": row.is_default_vat,
    }


def list_taxes(
    session: Session, *, include_inactive: bool = False
) -> list[dict[str, Any]]:
    statement = select(FinanceTaxDefinition).order_by(
        col(FinanceTaxDefinition.is_default_vat).desc(),
        col(FinanceTaxDefinition.name),
    )
    if not include_inactive:
        statement = statement.where(FinanceTaxDefinition.is_active.is_(True))  # type: ignore[attr-defined]
    return [tax_public(row) for row in session.exec(statement).all()]


def create_tax(
    session: Session,
    *,
    actor: User,
    name: str,
    calculation: str,
    percent_bp: int | None,
    fixed_amount_irr: int | None,
    is_active: bool = True,
    is_default_vat: bool = False,
) -> dict[str, Any]:
    if not name.strip():
        raise HTTPException(status_code=400, detail="tax_name_required")
    if calculation not in ("PERCENT", "FIXED"):
        raise HTTPException(status_code=400, detail="invalid_tax_calculation")
    if calculation == "PERCENT":
        if percent_bp is None or fixed_amount_irr is not None:
            raise HTTPException(status_code=400, detail="invalid_tax_value")
        _validate_bp(percent_bp, "invalid_tax_percentage")
    else:
        if fixed_amount_irr is None or fixed_amount_irr <= 0 or percent_bp is not None:
            raise HTTPException(status_code=400, detail="invalid_tax_value")
    if is_default_vat:
        for row in session.exec(
            select(FinanceTaxDefinition).where(
                FinanceTaxDefinition.is_default_vat.is_(True)  # type: ignore[attr-defined]
            )
        ).all():
            row.is_default_vat = False
            session.add(row)
    row = FinanceTaxDefinition(
        name=name.strip(),
        calculation=calculation,
        percent_bp=percent_bp,
        fixed_amount_irr=fixed_amount_irr,
        is_active=is_active,
        is_default_vat=is_default_vat,
        created_by_id=actor.id,
    )
    session.add(row)
    session.flush()
    record_finance_audit(
        session,
        actor=actor,
        gym_id=None,
        action="tax.created",
        entity_type="tax",
        entity_id=row.id,
        detail={"calculation": calculation},
    )
    session.commit()
    session.refresh(row)
    return tax_public(row)


def update_tax(
    session: Session,
    *,
    actor: User,
    tax_id: uuid.UUID,
    name: str | None = None,
    calculation: str | None = None,
    percent_bp: int | None = None,
    fixed_amount_irr: int | None = None,
    is_active: bool | None = None,
    is_default_vat: bool | None = None,
) -> dict[str, Any]:
    row = session.get(FinanceTaxDefinition, tax_id)
    if row is None:
        raise HTTPException(status_code=404, detail="tax_not_found")
    if name is not None:
        if not name.strip():
            raise HTTPException(status_code=400, detail="tax_name_required")
        row.name = name.strip()
    if calculation is not None or percent_bp is not None or fixed_amount_irr is not None:
        next_calc = calculation or row.calculation
        if next_calc not in ("PERCENT", "FIXED"):
            raise HTTPException(status_code=400, detail="invalid_tax_calculation")
        if next_calc == "PERCENT":
            next_percent = percent_bp if percent_bp is not None else row.percent_bp
            if next_percent is None:
                raise HTTPException(status_code=400, detail="invalid_tax_value")
            _validate_bp(next_percent, "invalid_tax_percentage")
            row.calculation = "PERCENT"
            row.percent_bp = next_percent
            row.fixed_amount_irr = None
        else:
            next_fixed = (
                fixed_amount_irr
                if fixed_amount_irr is not None
                else row.fixed_amount_irr
            )
            if next_fixed is None or next_fixed <= 0:
                raise HTTPException(status_code=400, detail="invalid_tax_value")
            row.calculation = "FIXED"
            row.fixed_amount_irr = next_fixed
            row.percent_bp = None
    if is_active is not None:
        row.is_active = is_active
    if is_default_vat is not None:
        if is_default_vat:
            for other in session.exec(
                select(FinanceTaxDefinition).where(
                    FinanceTaxDefinition.is_default_vat.is_(True),  # type: ignore[attr-defined]
                    col(FinanceTaxDefinition.id) != row.id,
                )
            ).all():
                other.is_default_vat = False
                session.add(other)
        row.is_default_vat = is_default_vat
    session.add(row)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=None,
        action="tax.updated",
        entity_type="tax",
        entity_id=row.id,
        detail={"active": row.is_active},
    )
    session.commit()
    session.refresh(row)
    return tax_public(row)


def _tax_amount(row: FinanceTaxDefinition, base_amount_irr: int) -> int:
    if row.calculation == "PERCENT":
        return base_amount_irr * int(row.percent_bp or 0) // MAX_BP
    return int(row.fixed_amount_irr or 0)


def _tax_lines(
    session: Session, *, tax_ids: list[uuid.UUID], base_amount_irr: int
) -> tuple[list[dict[str, Any]], int]:
    if not tax_ids:
        return [], 0
    if len(tax_ids) != len(set(tax_ids)):
        raise HTTPException(status_code=400, detail="duplicate_tax")
    rows = session.exec(
        select(FinanceTaxDefinition).where(
            col(FinanceTaxDefinition.id).in_(tax_ids)
        )
    ).all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(set(tax_ids)):
        raise HTTPException(status_code=400, detail="tax_not_found")
    lines: list[dict[str, Any]] = []
    total = 0
    for tax_id in tax_ids:
        row = by_id[tax_id]
        if not row.is_active:
            raise HTTPException(status_code=400, detail="tax_inactive")
        amount = _tax_amount(row, base_amount_irr)
        total += amount
        lines.append(
            {
                "tax_definition_id": row.id,
                "name": row.name,
                "calculation": row.calculation,
                "percent_bp": row.percent_bp,
                "fixed_amount_irr": row.fixed_amount_irr,
                "amount_irr": amount,
            }
        )
    return lines, total


# ---------------------------------------------------------------------------
# Coach contracts
# ---------------------------------------------------------------------------


def _coach_membership(
    session: Session, *, gym_id: uuid.UUID, coach_user_id: uuid.UUID
) -> GymMembership:
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == coach_user_id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if membership is None or "COACH" not in _roles(session, membership.id):
        raise HTTPException(status_code=400, detail="coach_not_in_gym")
    return membership


def coach_contract_public(
    session: Session, row: FinanceCoachContract
) -> dict[str, Any]:
    coach = session.get(User, row.coach_user_id)
    return {
        "id": row.id,
        "gym_id": row.gym_id,
        "coach_user_id": row.coach_user_id,
        "coach_name": (coach.full_name or coach.email) if coach else None,
        "category": row.category,
        "version": row.version,
        "status": row.status,
        "effective_from": row.effective_from,
        "effective_to": row.effective_to,
        "platform_bp": row.platform_bp,
        "gym_bp": row.gym_bp,
        "coach_bp": row.coach_bp,
        "platform_source": row.platform_source,
        "platform_contract_id": row.platform_contract_id,
        "activated_at": row.activated_at,
        "created_at": row.created_at,
    }


def list_coach_contracts(
    session: Session, *, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FinanceCoachContract)
        .where(FinanceCoachContract.gym_id == gym_id)
        .order_by(
            col(FinanceCoachContract.effective_from).desc(),
            col(FinanceCoachContract.version).desc(),
        )
    ).all()
    return [coach_contract_public(session, row) for row in rows]


def list_gym_coaches(
    session: Session, *, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.exec(
        select(User, GymMembership)
        .join(
            GymMembership,
            col(GymMembership.user_id) == col(User.id),
        )
        .where(
            GymMembership.gym_id == gym_id,
            col(GymMembership.is_active).is_(True),
        )
    ).all()
    result: list[dict[str, Any]] = []
    for user, membership in rows:
        if "COACH" in _roles(session, membership.id):
            result.append(
                {
                    "user_id": user.id,
                    "name": user.full_name or user.email,
                    "email": user.email,
                }
            )
    return result


def _validate_coach_contract_values(
    session: Session,
    *,
    gym_id: uuid.UUID,
    category: str,
    effective_from: date,
    effective_to: date | None,
    platform_bp: int,
    gym_bp: int,
    coach_bp: int,
) -> dict[str, Any]:
    _validate_category(category)
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(status_code=400, detail="invalid_effective_dates")
    if effective_from > finance_today():
        raise HTTPException(status_code=400, detail="effective_date_future")
    for value in (platform_bp, gym_bp, coach_bp):
        _validate_bp(value)
    if platform_bp + gym_bp + coach_bp != MAX_BP:
        raise HTTPException(status_code=400, detail="allocation_total_invalid")
    policy = resolve_platform_policy(
        session, gym_id=gym_id, category=category, on_date=effective_from
    )
    if platform_bp != policy["platform_bp"]:
        raise HTTPException(
            status_code=400, detail="platform_percentage_mismatch"
        )
    return policy


def _add_coach_contract(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    category: str,
    effective_from: date,
    effective_to: date | None,
    platform_bp: int,
    gym_bp: int,
    coach_bp: int,
    policy: dict[str, Any],
) -> FinanceCoachContract:
    _archive_active_coach_contracts(
        session,
        gym_id=gym_id,
        coach_user_id=coach_user_id,
        category=category,
    )
    row = FinanceCoachContract(
        gym_id=gym_id,
        coach_user_id=coach_user_id,
        category=category,
        version=_next_coach_version(
            session,
            gym_id=gym_id,
            coach_user_id=coach_user_id,
            category=category,
        ),
        status="ACTIVE",
        effective_from=effective_from,
        effective_to=effective_to,
        platform_bp=platform_bp,
        gym_bp=gym_bp,
        coach_bp=coach_bp,
        platform_contract_id=policy["contract_id"],
        platform_source=policy["source"],
        created_by_id=actor.id,
        activated_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def create_coach_contract(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    category: str,
    effective_from: date,
    effective_to: date | None,
    platform_bp: int,
    gym_bp: int,
    coach_bp: int,
) -> dict[str, Any]:
    _coach_membership(session, gym_id=gym_id, coach_user_id=coach_user_id)
    policy = _validate_coach_contract_values(
        session,
        gym_id=gym_id,
        category=category,
        effective_from=effective_from,
        effective_to=effective_to,
        platform_bp=platform_bp,
        gym_bp=gym_bp,
        coach_bp=coach_bp,
    )
    row = _add_coach_contract(
        session,
        actor=actor,
        gym_id=gym_id,
        coach_user_id=coach_user_id,
        category=category,
        effective_from=effective_from,
        effective_to=effective_to,
        platform_bp=platform_bp,
        gym_bp=gym_bp,
        coach_bp=coach_bp,
        policy=policy,
    )
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="coach_contract.created",
        entity_type="coach_contract",
        entity_id=row.id,
        detail={"category": category, "version": row.version},
    )
    session.commit()
    session.refresh(row)
    return coach_contract_public(session, row)


def update_coach_contract(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    contract_id: uuid.UUID,
    effective_from: date,
    effective_to: date | None,
    platform_bp: int,
    gym_bp: int,
    coach_bp: int,
) -> dict[str, Any]:
    original = session.get(FinanceCoachContract, contract_id)
    if original is None or original.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_contract_not_found")
    _coach_membership(
        session, gym_id=gym_id, coach_user_id=original.coach_user_id
    )
    policy = _validate_coach_contract_values(
        session,
        gym_id=gym_id,
        category=original.category,
        effective_from=effective_from,
        effective_to=effective_to,
        platform_bp=platform_bp,
        gym_bp=gym_bp,
        coach_bp=coach_bp,
    )
    row = _add_coach_contract(
        session,
        actor=actor,
        gym_id=gym_id,
        coach_user_id=original.coach_user_id,
        category=original.category,
        effective_from=effective_from,
        effective_to=effective_to,
        platform_bp=platform_bp,
        gym_bp=gym_bp,
        coach_bp=coach_bp,
        policy=policy,
    )
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="coach_contract.updated",
        entity_type="coach_contract",
        entity_id=row.id,
        detail={
            "category": original.category,
            "version": row.version,
            "previous_contract_id": str(original.id),
            "previous_version": original.version,
        },
    )
    session.commit()
    session.refresh(row)
    return coach_contract_public(session, row)


def activate_coach_contract(
    session: Session, *, actor: User, gym_id: uuid.UUID, contract_id: uuid.UUID
) -> dict[str, Any]:
    row = session.get(FinanceCoachContract, contract_id)
    if row is None or row.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_contract_not_found")
    if row.status == "ACTIVE":
        return coach_contract_public(session, row)
    if row.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="contract_archived")
    if row.effective_from > finance_today():
        raise HTTPException(status_code=400, detail="effective_date_future")
    policy = resolve_platform_policy(
        session, gym_id=gym_id, category=row.category, on_date=row.effective_from
    )
    if row.platform_bp != policy["platform_bp"]:
        raise HTTPException(
            status_code=400, detail="platform_percentage_mismatch"
        )
    _archive_active_coach_contracts(
        session,
        gym_id=gym_id,
        coach_user_id=row.coach_user_id,
        category=row.category,
        exclude_id=row.id,
    )
    row.status = "ACTIVE"
    row.activated_at = datetime.now(UTC)
    row.platform_contract_id = policy["contract_id"]
    row.platform_source = policy["source"]
    session.add(row)
    session.flush()
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="coach_contract.activated",
        entity_type="coach_contract",
        entity_id=row.id,
        detail={"category": row.category, "version": row.version},
    )
    session.commit()
    session.refresh(row)
    return coach_contract_public(session, row)


def archive_coach_contract(
    session: Session, *, actor: User, gym_id: uuid.UUID, contract_id: uuid.UUID
) -> dict[str, Any]:
    row = session.get(FinanceCoachContract, contract_id)
    if row is None or row.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_contract_not_found")
    if row.status == "ARCHIVED":
        return coach_contract_public(session, row)
    row.status = "ARCHIVED"
    session.add(row)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="coach_contract.archived",
        entity_type="coach_contract",
        entity_id=row.id,
        detail={"category": row.category, "version": row.version},
    )
    session.commit()
    session.refresh(row)
    return coach_contract_public(session, row)


def resolve_coach_contract(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    category: str,
    on_date: date,
) -> FinanceCoachContract | None:
    return session.exec(
        select(FinanceCoachContract)
        .where(
            FinanceCoachContract.gym_id == gym_id,
            FinanceCoachContract.coach_user_id == coach_user_id,
            FinanceCoachContract.category == category,
            FinanceCoachContract.status == "ACTIVE",
            FinanceCoachContract.effective_from <= on_date,
            or_(
                col(FinanceCoachContract.effective_to).is_(None),
                col(FinanceCoachContract.effective_to) >= on_date,
            ),
        )
        .order_by(
            col(FinanceCoachContract.effective_from).desc(),
            col(FinanceCoachContract.version).desc(),
        )
    ).first()


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


def preview_sale(
    session: Session,
    *,
    gym_id: uuid.UUID,
    category: str,
    base_amount_irr: int,
    tax_ids: list[uuid.UUID],
    coach_user_id: uuid.UUID | None,
    sold_on: date,
) -> dict[str, Any]:
    _validate_category(category)
    if base_amount_irr <= 0:
        raise HTTPException(status_code=400, detail="invalid_base_amount")
    if sold_on > finance_today():
        raise HTTPException(status_code=400, detail="sale_date_in_future")
    policy = resolve_platform_policy(
        session, gym_id=gym_id, category=category, on_date=sold_on
    )
    if coach_user_id is not None:
        _coach_membership(session, gym_id=gym_id, coach_user_id=coach_user_id)
        contract = resolve_coach_contract(
            session,
            gym_id=gym_id,
            coach_user_id=coach_user_id,
            category=category,
            on_date=sold_on,
        )
        if contract is None:
            raise HTTPException(status_code=400, detail="coach_contract_missing")
        if contract.platform_bp != policy["platform_bp"]:
            raise HTTPException(status_code=400, detail="coach_contract_outdated")
        platform_bp = contract.platform_bp
        gym_bp = contract.gym_bp
        coach_bp = contract.coach_bp
        coach_contract_id = contract.id
        coach_contract_version: int | None = contract.version
    else:
        platform_bp = policy["platform_bp"]
        gym_bp = MAX_BP - platform_bp
        coach_bp = 0
        coach_contract_id = None
        coach_contract_version = None
    tax_lines, tax_total = _tax_lines(
        session, tax_ids=tax_ids, base_amount_irr=base_amount_irr
    )
    total = base_amount_irr + tax_total
    platform_amount = total * platform_bp // MAX_BP
    coach_amount = total * coach_bp // MAX_BP
    gym_amount = total - platform_amount - coach_amount
    return {
        "gym_id": gym_id,
        "category": category,
        "base_amount_irr": base_amount_irr,
        "taxes": tax_lines,
        "tax_amount_irr": tax_total,
        "total_amount_irr": total,
        "platform_bp": platform_bp,
        "gym_bp": gym_bp,
        "coach_bp": coach_bp,
        "platform_amount_irr": platform_amount,
        "gym_amount_irr": gym_amount,
        "coach_amount_irr": coach_amount,
        "coach_user_id": coach_user_id,
        "platform_source": policy["source"],
        "platform_contract_id": policy["contract_id"],
        "platform_contract_version": policy["contract_version"],
        "coach_contract_id": coach_contract_id,
        "coach_contract_version": coach_contract_version,
    }


def create_sale(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    category: str,
    description: str,
    base_amount_irr: int,
    tax_ids: list[uuid.UUID],
    coach_user_id: uuid.UUID | None,
    sold_on: date,
) -> FinanceSale:
    if not description.strip():
        raise HTTPException(status_code=400, detail="sale_description_required")
    preview = preview_sale(
        session,
        gym_id=gym_id,
        category=category,
        base_amount_irr=base_amount_irr,
        tax_ids=tax_ids,
        coach_user_id=coach_user_id,
        sold_on=sold_on,
    )
    sale = FinanceSale(
        gym_id=gym_id,
        category=category,
        description=description.strip(),
        sold_on=sold_on,
        base_amount_irr=preview["base_amount_irr"],
        tax_amount_irr=preview["tax_amount_irr"],
        total_amount_irr=preview["total_amount_irr"],
        status="AWAITING_PAYMENT",
        platform_bp=preview["platform_bp"],
        gym_bp=preview["gym_bp"],
        coach_bp=preview["coach_bp"],
        platform_amount_irr=preview["platform_amount_irr"],
        gym_amount_irr=preview["gym_amount_irr"],
        coach_amount_irr=preview["coach_amount_irr"],
        coach_user_id=coach_user_id,
        coach_contract_id=preview["coach_contract_id"],
        platform_contract_id=preview["platform_contract_id"],
        platform_source=preview["platform_source"],
        contract_snapshot={
            "platform_bp": preview["platform_bp"],
            "gym_bp": preview["gym_bp"],
            "coach_bp": preview["coach_bp"],
            "platform_source": preview["platform_source"],
            "platform_contract_id": str(preview["platform_contract_id"]),
            "platform_contract_version": preview["platform_contract_version"],
            "coach_contract_id": str(preview["coach_contract_id"])
            if preview["coach_contract_id"]
            else None,
            "coach_contract_version": preview["coach_contract_version"],
        },
        created_by_id=actor.id,
    )
    session.add(sale)
    session.flush()
    for line in preview["taxes"]:
        session.add(
            FinanceSaleTax(
                sale_id=sale.id,
                tax_definition_id=line["tax_definition_id"],
                name=line["name"],
                calculation=line["calculation"],
                percent_bp=line["percent_bp"],
                fixed_amount_irr=line["fixed_amount_irr"],
                amount_irr=line["amount_irr"],
            )
        )
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="sale.created",
        entity_type="sale",
        entity_id=sale.id,
        detail={
            "total_amount_irr": sale.total_amount_irr,
            "category": category,
        },
    )
    session.commit()
    session.refresh(sale)
    return sale


def _sale_taxes(session: Session, sale_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FinanceSaleTax)
        .where(FinanceSaleTax.sale_id == sale_id)
        .order_by(col(FinanceSaleTax.created_at))
    ).all()
    return [
        {
            "name": row.name,
            "calculation": row.calculation,
            "percent_bp": row.percent_bp,
            "fixed_amount_irr": row.fixed_amount_irr,
            "amount_irr": row.amount_irr,
        }
        for row in rows
    ]


def _sale_refunded_irr(session: Session, sale_id: uuid.UUID) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.sum(FinanceRefund.amount_irr), 0)).where(
                FinanceRefund.sale_id == sale_id
            )
        ).one()
    )


def _latest_payment_status(session: Session, sale_id: uuid.UUID) -> str | None:
    row = session.exec(
        select(FinancePayment)
        .where(FinancePayment.sale_id == sale_id)
        .order_by(col(FinancePayment.created_at).desc())
    ).first()
    return row.status if row else None


def sale_public(session: Session, sale: FinanceSale) -> dict[str, Any]:
    coach = session.get(User, sale.coach_user_id) if sale.coach_user_id else None
    return {
        "id": sale.id,
        "gym_id": sale.gym_id,
        "category": sale.category,
        "description": sale.description,
        "sold_on": sale.sold_on,
        "base_amount_irr": sale.base_amount_irr,
        "taxes": _sale_taxes(session, sale.id),
        "tax_amount_irr": sale.tax_amount_irr,
        "total_amount_irr": sale.total_amount_irr,
        "status": sale.status,
        "platform_bp": sale.platform_bp,
        "gym_bp": sale.gym_bp,
        "coach_bp": sale.coach_bp,
        "platform_amount_irr": sale.platform_amount_irr,
        "gym_amount_irr": sale.gym_amount_irr,
        "coach_amount_irr": sale.coach_amount_irr,
        "coach_user_id": sale.coach_user_id,
        "coach_name": (coach.full_name or coach.email) if coach else None,
        "coach_contract_id": sale.coach_contract_id,
        "platform_contract_id": sale.platform_contract_id,
        "platform_source": sale.platform_source,
        "refunded_irr": _sale_refunded_irr(session, sale.id),
        "payment_status": _latest_payment_status(session, sale.id),
        "created_at": sale.created_at,
    }


def list_sales(
    session: Session,
    *,
    gym_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    statement = select(FinanceSale).where(FinanceSale.gym_id == gym_id)
    if from_date is not None:
        statement = statement.where(FinanceSale.sold_on >= from_date)
    if to_date is not None:
        statement = statement.where(FinanceSale.sold_on <= to_date)
    if category:
        statement = statement.where(FinanceSale.category == category)
    if status:
        statement = statement.where(FinanceSale.status == status)
    rows = session.exec(
        statement.order_by(col(FinanceSale.created_at).desc())
    ).all()
    return [sale_public(session, row) for row in rows]


def get_sale(
    session: Session, *, gym_id: uuid.UUID, sale_id: uuid.UUID
) -> FinanceSale:
    sale = session.get(FinanceSale, sale_id)
    if sale is None or sale.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="sale_not_found")
    return sale


# ---------------------------------------------------------------------------
# Simulated payments
# ---------------------------------------------------------------------------


def _allocation_refunded_irr(session: Session, allocation_id: uuid.UUID) -> int:
    return int(
        session.exec(
            select(
                func.coalesce(func.sum(FinanceRefundAdjustment.amount_irr), 0)
            ).where(FinanceRefundAdjustment.allocation_id == allocation_id)
        ).one()
    )


def _allocation_reserved_or_settled_irr(
    session: Session, allocation_id: uuid.UUID
) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.sum(FinanceSettlementItem.amount_irr), 0))
            .join(
                FinanceSettlement,
                col(FinanceSettlementItem.settlement_id)
                == col(FinanceSettlement.id),
            )
            .where(
                FinanceSettlementItem.allocation_id == allocation_id,
                FinanceSettlement.status != "CANCELLED",
            )
        ).one()
    )


def _allocation_completed_settled_irr(
    session: Session, allocation_id: uuid.UUID
) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.sum(FinanceSettlementItem.amount_irr), 0))
            .join(
                FinanceSettlement,
                col(FinanceSettlementItem.settlement_id)
                == col(FinanceSettlement.id),
            )
            .where(
                FinanceSettlementItem.allocation_id == allocation_id,
                FinanceSettlement.status == "COMPLETED",
            )
        ).one()
    )


def allocation_available_irr(session: Session, allocation: FinanceAllocation) -> int:
    return max(
        allocation.amount_irr
        - _allocation_refunded_irr(session, allocation.id)
        - _allocation_reserved_or_settled_irr(session, allocation.id),
        0,
    )


def _party_name(session: Session, party: str, party_user_id: uuid.UUID | None) -> str | None:
    if party == "COACH" and party_user_id:
        user = session.get(User, party_user_id)
        return (user.full_name or user.email) if user else None
    return {"PLATFORM": "پلتفرم", "GYM": "باشگاه"}.get(party)


def payment_public(session: Session, payment: FinancePayment) -> dict[str, Any]:
    allocations = session.exec(
        select(FinanceAllocation)
        .where(FinanceAllocation.payment_id == payment.id)
        .order_by(col(FinanceAllocation.party))
    ).all()
    return {
        "id": payment.id,
        "sale_id": payment.sale_id,
        "gym_id": payment.gym_id,
        "amount_irr": payment.amount_irr,
        "status": payment.status,
        "outcome": payment.outcome,
        "note": payment.note,
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
        "allocations": [
            {
                "id": row.id,
                "party": row.party,
                "party_user_id": row.party_user_id,
                "party_name": _party_name(session, row.party, row.party_user_id),
                "amount_irr": row.amount_irr,
                "refunded_irr": _allocation_refunded_irr(session, row.id),
                "settled_irr": _allocation_completed_settled_irr(
                    session, row.id
                ),
            }
            for row in allocations
        ],
    }


def simulate_payment(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    sale_id: uuid.UUID,
    outcome: str,
    idempotency_key: str,
    note: str | None = None,
) -> dict[str, Any]:
    if outcome not in ("SUCCESS", "FAILURE", "CANCELLATION"):
        raise HTTPException(status_code=400, detail="invalid_payment_outcome")
    key = idempotency_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="idempotency_key_required")
    existing = session.exec(
        select(FinancePayment).where(
            FinancePayment.gym_id == gym_id,
            FinancePayment.idempotency_key == key,
        )
    ).first()
    if existing is not None:
        if existing.sale_id != sale_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return payment_public(session, existing)
    sale = session.exec(
        select(FinanceSale)
        .where(FinanceSale.id == sale_id, FinanceSale.gym_id == gym_id)
        .with_for_update()
    ).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="sale_not_found")
    # Re-check after the row lock: a concurrent request with the same key may
    # have committed while this request was waiting.
    existing = session.exec(
        select(FinancePayment).where(
            FinancePayment.gym_id == gym_id,
            FinancePayment.idempotency_key == key,
        )
    ).first()
    if existing is not None:
        if existing.sale_id != sale_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return payment_public(session, existing)
    if sale.status in ("PAID", "PARTIALLY_REFUNDED", "REFUNDED"):
        raise HTTPException(status_code=409, detail="sale_already_paid")
    if sale.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="sale_cancelled")
    status = {
        "SUCCESS": "SUCCEEDED",
        "FAILURE": "FAILED",
        "CANCELLATION": "CANCELLED",
    }[outcome]
    payment = FinancePayment(
        gym_id=gym_id,
        sale_id=sale.id,
        amount_irr=sale.total_amount_irr,
        status=status,
        outcome=outcome,
        idempotency_key=key,
        note=note,
        paid_at=datetime.now(UTC) if outcome == "SUCCESS" else None,
        created_by_id=actor.id,
    )
    session.add(payment)
    session.flush()
    if outcome == "SUCCESS":
        sale.status = "PAID"
        session.add(sale)
        for party, amount, party_user_id in (
            ("PLATFORM", sale.platform_amount_irr, None),
            ("GYM", sale.gym_amount_irr, None),
            ("COACH", sale.coach_amount_irr, sale.coach_user_id),
        ):
            if amount <= 0:
                continue
            session.add(
                FinanceAllocation(
                    gym_id=gym_id,
                    payment_id=payment.id,
                    sale_id=sale.id,
                    party=party,
                    party_user_id=party_user_id,
                    amount_irr=amount,
                )
            )
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action=f"payment.{outcome.lower()}",
        entity_type="payment",
        entity_id=payment.id,
        detail={"sale_id": str(sale.id), "amount_irr": payment.amount_irr},
    )
    session.commit()
    session.refresh(payment)
    return payment_public(session, payment)


def list_payments(
    session: Session, *, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FinancePayment)
        .where(FinancePayment.gym_id == gym_id)
        .order_by(col(FinancePayment.created_at).desc())
    ).all()
    return [payment_public(session, row) for row in rows]


# ---------------------------------------------------------------------------
# Simulated settlements
# ---------------------------------------------------------------------------


def _eligible_allocations(
    session: Session,
    *,
    gym_id: uuid.UUID,
    party: str,
    party_user_id: uuid.UUID | None,
) -> list[tuple[FinanceAllocation, int]]:
    statement = (
        select(FinanceAllocation)
        .join(
            FinancePayment,
            col(FinanceAllocation.payment_id) == col(FinancePayment.id),
        )
        .where(
            FinanceAllocation.gym_id == gym_id,
            FinanceAllocation.party == party,
            FinancePayment.status == "SUCCEEDED",
        )
        .order_by(
            col(FinancePayment.paid_at),
            col(FinanceAllocation.created_at),
        )
    )
    if party == "COACH":
        if party_user_id is None:
            raise HTTPException(status_code=400, detail="coach_user_required")
        statement = statement.where(FinanceAllocation.party_user_id == party_user_id)
    allocations = session.exec(statement).all()
    result: list[tuple[FinanceAllocation, int]] = []
    for allocation in allocations:
        available = allocation_available_irr(session, allocation)
        if available > 0:
            result.append((allocation, available))
    return result


def settlement_public(
    session: Session, settlement: FinanceSettlement
) -> dict[str, Any]:
    items = session.exec(
        select(FinanceSettlementItem).where(
            FinanceSettlementItem.settlement_id == settlement.id
        )
    ).all()
    return {
        "id": settlement.id,
        "gym_id": settlement.gym_id,
        "party": settlement.party,
        "party_user_id": settlement.party_user_id,
        "party_name": _party_name(
            session, settlement.party, settlement.party_user_id
        ),
        "amount_irr": settlement.amount_irr,
        "status": settlement.status,
        "requested_at": settlement.requested_at,
        "completed_at": settlement.completed_at,
        "cancelled_at": settlement.cancelled_at,
        "items": [
            {
                "allocation_id": item.allocation_id,
                "party": settlement.party,
                "amount_irr": item.amount_irr,
            }
            for item in items
        ],
    }


def list_settlements(
    session: Session, *, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FinanceSettlement)
        .where(FinanceSettlement.gym_id == gym_id)
        .order_by(col(FinanceSettlement.created_at).desc())
    ).all()
    return [settlement_public(session, row) for row in rows]


def create_settlement(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    party: str,
    party_user_id: uuid.UUID | None,
    amount_irr: int,
    idempotency_key: str,
) -> dict[str, Any]:
    if party not in PARTIES:
        raise HTTPException(status_code=400, detail="invalid_settlement_party")
    if amount_irr <= 0:
        raise HTTPException(status_code=400, detail="invalid_settlement_amount")
    key = idempotency_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="idempotency_key_required")
    existing = session.exec(
        select(FinanceSettlement).where(
            FinanceSettlement.gym_id == gym_id,
            FinanceSettlement.idempotency_key == key,
        )
    ).first()
    if existing is not None:
        return settlement_public(session, existing)
    if party == "COACH":
        if party_user_id is None:
            raise HTTPException(status_code=400, detail="coach_user_required")
        _coach_membership(session, gym_id=gym_id, coach_user_id=party_user_id)
    else:
        if party_user_id is not None:
            raise HTTPException(status_code=400, detail="party_user_not_allowed")
        party_user_id = None
    eligible = _eligible_allocations(
        session, gym_id=gym_id, party=party, party_user_id=party_user_id
    )
    total_available = sum(available for _, available in eligible)
    if amount_irr > total_available:
        raise HTTPException(
            status_code=400, detail="settlement_exceeds_available"
        )
    settlement = FinanceSettlement(
        gym_id=gym_id,
        party=party,
        party_user_id=party_user_id,
        amount_irr=amount_irr,
        status="PENDING",
        idempotency_key=key,
        created_by_id=actor.id,
    )
    session.add(settlement)
    session.flush()
    remaining = amount_irr
    for allocation, available in eligible:
        if remaining <= 0:
            break
        item_amount = min(available, remaining)
        session.add(
            FinanceSettlementItem(
                settlement_id=settlement.id,
                allocation_id=allocation.id,
                amount_irr=item_amount,
            )
        )
        remaining -= item_amount
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="settlement.created",
        entity_type="settlement",
        entity_id=settlement.id,
        detail={"party": party, "amount_irr": amount_irr},
    )
    session.commit()
    session.refresh(settlement)
    return settlement_public(session, settlement)


def complete_settlement(
    session: Session, *, actor: User, gym_id: uuid.UUID, settlement_id: uuid.UUID
) -> dict[str, Any]:
    settlement = session.exec(
        select(FinanceSettlement)
        .where(
            FinanceSettlement.id == settlement_id,
            FinanceSettlement.gym_id == gym_id,
        )
        .with_for_update()
    ).first()
    if settlement is None:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if settlement.status == "COMPLETED":
        return settlement_public(session, settlement)
    if settlement.status != "PENDING":
        raise HTTPException(status_code=409, detail="settlement_not_pending")
    settlement.status = "COMPLETED"
    settlement.completed_at = datetime.now(UTC)
    session.add(settlement)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="settlement.completed",
        entity_type="settlement",
        entity_id=settlement.id,
        detail={"amount_irr": settlement.amount_irr},
    )
    session.commit()
    session.refresh(settlement)
    return settlement_public(session, settlement)


def cancel_settlement(
    session: Session, *, actor: User, gym_id: uuid.UUID, settlement_id: uuid.UUID
) -> dict[str, Any]:
    settlement = session.exec(
        select(FinanceSettlement)
        .where(
            FinanceSettlement.id == settlement_id,
            FinanceSettlement.gym_id == gym_id,
        )
        .with_for_update()
    ).first()
    if settlement is None:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if settlement.status == "CANCELLED":
        return settlement_public(session, settlement)
    if settlement.status != "PENDING":
        raise HTTPException(status_code=409, detail="settlement_not_pending")
    settlement.status = "CANCELLED"
    settlement.cancelled_at = datetime.now(UTC)
    session.add(settlement)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="settlement.cancelled",
        entity_type="settlement",
        entity_id=settlement.id,
        detail={"amount_irr": settlement.amount_irr},
    )
    session.commit()
    session.refresh(settlement)
    return settlement_public(session, settlement)


def auto_settle(
    session: Session, *, actor: User, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    targets: list[tuple[str, uuid.UUID | None]] = [("PLATFORM", None), ("GYM", None)]
    coach_rows = session.exec(
        select(FinanceAllocation.party_user_id)
        .join(
            FinancePayment,
            col(FinanceAllocation.payment_id) == col(FinancePayment.id),
        )
        .where(
            FinanceAllocation.gym_id == gym_id,
            FinanceAllocation.party == "COACH",
            FinancePayment.status == "SUCCEEDED",
            col(FinanceAllocation.party_user_id).is_not(None),
        )
        .distinct()
    ).all()
    for coach_user_id in coach_rows:
        if coach_user_id is not None:
            targets.append(("COACH", coach_user_id))
    result: list[dict[str, Any]] = []
    for party, party_user_id in targets:
        eligible = _eligible_allocations(
            session, gym_id=gym_id, party=party, party_user_id=party_user_id
        )
        total = sum(amount for _, amount in eligible)
        if total <= 0:
            continue
        created = create_settlement(
            session,
            actor=actor,
            gym_id=gym_id,
            party=party,
            party_user_id=party_user_id,
            amount_irr=total,
            idempotency_key=f"auto:{uuid.uuid4().hex}",
        )
        result.append(
            complete_settlement(
                session,
                actor=actor,
                gym_id=gym_id,
                settlement_id=created["id"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Simulated refunds
# ---------------------------------------------------------------------------


def refund_public(session: Session, refund: FinanceRefund) -> dict[str, Any]:
    adjustments = session.exec(
        select(FinanceRefundAdjustment).where(
            FinanceRefundAdjustment.refund_id == refund.id
        )
    ).all()
    return {
        "id": refund.id,
        "payment_id": refund.payment_id,
        "sale_id": refund.sale_id,
        "amount_irr": refund.amount_irr,
        "status": refund.status,
        "reason": refund.reason,
        "created_at": refund.created_at,
        "adjustments": [
            {
                "allocation_id": row.allocation_id,
                "settlement_id": row.settlement_id,
                "party": row.party,
                "amount_irr": row.amount_irr,
            }
            for row in adjustments
        ],
    }


def create_refund(
    session: Session,
    *,
    actor: User,
    gym_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount_irr: int,
    idempotency_key: str,
    reason: str,
) -> dict[str, Any]:
    if amount_irr <= 0:
        raise HTTPException(status_code=400, detail="invalid_refund_amount")
    if len(reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="refund_reason_required")
    key = idempotency_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="idempotency_key_required")
    existing = session.exec(
        select(FinanceRefund).where(
            FinanceRefund.gym_id == gym_id,
            FinanceRefund.idempotency_key == key,
        )
    ).first()
    if existing is not None:
        return refund_public(session, existing)
    payment = session.exec(
        select(FinancePayment)
        .where(
            FinancePayment.id == payment_id,
            FinancePayment.gym_id == gym_id,
        )
        .with_for_update()
    ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    if payment.status != "SUCCEEDED":
        raise HTTPException(status_code=409, detail="payment_not_refundable")
    allocations = session.exec(
        select(FinanceAllocation).where(
            FinanceAllocation.payment_id == payment.id
        )
    ).all()
    if not allocations:
        raise HTTPException(status_code=409, detail="payment_not_refundable")
    pending = session.exec(
        select(FinanceSettlementItem)
        .join(
            FinanceSettlement,
            col(FinanceSettlementItem.settlement_id) == col(FinanceSettlement.id),
        )
        .where(
            col(FinanceSettlementItem.allocation_id).in_(
                [row.id for row in allocations]
            ),
            FinanceSettlement.status == "PENDING",
        )
    ).first()
    if pending is not None:
        raise HTTPException(status_code=409, detail="settlement_pending")
    refunded = int(
        session.exec(
            select(func.coalesce(func.sum(FinanceRefund.amount_irr), 0)).where(
                FinanceRefund.payment_id == payment.id
            )
        ).one()
    )
    remaining = payment.amount_irr - refunded
    if amount_irr > remaining:
        raise HTTPException(status_code=400, detail="refund_exceeds_remaining")
    refund = FinanceRefund(
        gym_id=gym_id,
        payment_id=payment.id,
        sale_id=payment.sale_id,
        amount_irr=amount_irr,
        idempotency_key=key,
        reason=reason.strip(),
        created_by_id=actor.id,
    )
    session.add(refund)
    session.flush()
    shares = [
        amount_irr * row.amount_irr // payment.amount_irr for row in allocations
    ]
    residual = amount_irr - sum(shares)
    if shares:
        shares[-1] += residual
    for allocation, share in zip(allocations, shares, strict=True):
        if share <= 0:
            continue
        completed_item = session.exec(
            select(FinanceSettlementItem)
            .join(
                FinanceSettlement,
                col(FinanceSettlementItem.settlement_id)
                == col(FinanceSettlement.id),
            )
            .where(
                FinanceSettlementItem.allocation_id == allocation.id,
                FinanceSettlement.status == "COMPLETED",
            )
            .order_by(col(FinanceSettlement.completed_at).desc())
        ).first()
        session.add(
            FinanceRefundAdjustment(
                refund_id=refund.id,
                allocation_id=allocation.id,
                settlement_id=completed_item.settlement_id
                if completed_item
                else None,
                party=allocation.party,
                party_user_id=allocation.party_user_id,
                amount_irr=share,
            )
        )
    sale = session.get(FinanceSale, payment.sale_id)
    if sale is not None:
        total_refunded = refunded + amount_irr
        sale.status = (
            "REFUNDED" if total_refunded >= payment.amount_irr else "PARTIALLY_REFUNDED"
        )
        session.add(sale)
    record_finance_audit(
        session,
        actor=actor,
        gym_id=gym_id,
        action="refund.completed",
        entity_type="refund",
        entity_id=refund.id,
        detail={"payment_id": str(payment.id), "amount_irr": amount_irr},
    )
    session.commit()
    session.refresh(refund)
    return refund_public(session, refund)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _date_filter(column: Any, value: date) -> Any:
    return func.date(column) == value


def _report_for_gym(
    session: Session,
    *,
    gym_id: uuid.UUID,
    from_date: date,
    to_date: date,
    category: str | None = None,
) -> dict[str, Any]:
    sale_statement = select(FinanceSale).where(
        FinanceSale.gym_id == gym_id,
        FinanceSale.sold_on >= from_date,
        FinanceSale.sold_on <= to_date,
        FinanceSale.status != "CANCELLED",
    )
    if category:
        sale_statement = sale_statement.where(FinanceSale.category == category)
    sales = session.exec(sale_statement).all()
    base_sales = sum(row.base_amount_irr for row in sales)
    taxes = sum(row.tax_amount_irr for row in sales)

    payment_statement = (
        select(FinancePayment)
        .where(
            FinancePayment.gym_id == gym_id,
            FinancePayment.status == "SUCCEEDED",
            col(FinancePayment.paid_at).is_not(None),
            func.date(FinancePayment.paid_at) >= from_date,
            func.date(FinancePayment.paid_at) <= to_date,
        )
    )
    payments = session.exec(payment_statement).all()
    total_payments = sum(row.amount_irr for row in payments)
    payment_ids = [row.id for row in payments]
    allocations = (
        session.exec(
            select(FinanceAllocation).where(
                col(FinanceAllocation.payment_id).in_(payment_ids)
            )
        ).all()
        if payment_ids
        else []
    )
    platform_share = sum(row.amount_irr for row in allocations if row.party == "PLATFORM")
    gym_share = sum(row.amount_irr for row in allocations if row.party == "GYM")
    coach_share = sum(row.amount_irr for row in allocations if row.party == "COACH")
    refunds = int(
        session.exec(
            select(func.coalesce(func.sum(FinanceRefund.amount_irr), 0)).where(
                FinanceRefund.gym_id == gym_id,
                FinanceRefund.status == "COMPLETED",
                func.date(FinanceRefund.created_at) >= from_date,
                func.date(FinanceRefund.created_at) <= to_date,
            )
        ).one()
    )
    completed_settlements = int(
        session.exec(
            select(func.coalesce(func.sum(FinanceSettlement.amount_irr), 0)).where(
                FinanceSettlement.gym_id == gym_id,
                FinanceSettlement.status == "COMPLETED",
                col(FinanceSettlement.completed_at).is_not(None),
                func.date(FinanceSettlement.completed_at) >= from_date,
                func.date(FinanceSettlement.completed_at) <= to_date,
            )
        ).one()
    )

    as_of_allocations = session.exec(
        select(FinanceAllocation)
        .join(
            FinancePayment,
            col(FinanceAllocation.payment_id) == col(FinancePayment.id),
        )
        .where(
            FinanceAllocation.gym_id == gym_id,
            FinancePayment.status == "SUCCEEDED",
            col(FinancePayment.paid_at).is_not(None),
            func.date(FinancePayment.paid_at) <= to_date,
        )
    ).all()
    unsettled = {"PLATFORM": 0, "GYM": 0, "COACH": 0}
    for allocation in as_of_allocations:
        refunded_for_allocation = int(
            session.exec(
                select(
                    func.coalesce(
                        func.sum(FinanceRefundAdjustment.amount_irr), 0
                    )
                )
                .join(
                    FinanceRefund,
                    col(FinanceRefundAdjustment.refund_id) == col(FinanceRefund.id),
                )
                .where(
                    FinanceRefundAdjustment.allocation_id == allocation.id,
                    func.date(FinanceRefund.created_at) <= to_date,
                )
            ).one()
        )
        reserved = int(
            session.exec(
                select(
                    func.coalesce(func.sum(FinanceSettlementItem.amount_irr), 0)
                )
                .join(
                    FinanceSettlement,
                    col(FinanceSettlementItem.settlement_id)
                    == col(FinanceSettlement.id),
                )
                .where(
                    FinanceSettlementItem.allocation_id == allocation.id,
                    FinanceSettlement.status != "CANCELLED",
                    func.date(FinanceSettlement.requested_at) <= to_date,
                )
            ).one()
        )
        net = max(allocation.amount_irr - refunded_for_allocation - reserved, 0)
        unsettled[allocation.party] = unsettled.get(allocation.party, 0) + net
    pending_settlements = int(
        session.exec(
            select(func.coalesce(func.sum(FinanceSettlement.amount_irr), 0)).where(
                FinanceSettlement.gym_id == gym_id,
                FinanceSettlement.status == "PENDING",
                func.date(FinanceSettlement.requested_at) <= to_date,
            )
        ).one()
    )
    completed_settlements_as_of = int(
        session.exec(
            select(func.coalesce(func.sum(FinanceSettlement.amount_irr), 0)).where(
                FinanceSettlement.gym_id == gym_id,
                FinanceSettlement.status == "COMPLETED",
                col(FinanceSettlement.completed_at).is_not(None),
                func.date(FinanceSettlement.completed_at) <= to_date,
            )
        ).one()
    )
    return {
        "gym_id": gym_id,
        "activity": {
            "base_sales_irr": base_sales,
            "taxes_irr": taxes,
            "total_payments_irr": total_payments,
            "platform_share_irr": platform_share,
            "gym_share_irr": gym_share,
            "coach_share_irr": coach_share,
            "refunds_irr": refunds,
            "completed_settlements_irr": completed_settlements,
        },
        "as_of": {
            "date": to_date,
            "unsettled_platform_irr": unsettled.get("PLATFORM", 0),
            "unsettled_gym_irr": unsettled.get("GYM", 0),
            "unsettled_coach_irr": unsettled.get("COACH", 0),
            "pending_settlements_irr": pending_settlements,
            "completed_settlements_irr": completed_settlements_as_of,
        },
    }


def finance_report(
    session: Session,
    *,
    gym_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    category: str | None = None,
) -> dict[str, Any]:
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="invalid_date_range")
    if category:
        _validate_category(category)
    if gym_id is not None:
        data = _report_for_gym(
            session,
            gym_id=gym_id,
            from_date=from_date,
            to_date=to_date,
            category=category,
        )
        return {
            "gym_id": gym_id,
            "from_date": from_date,
            "to_date": to_date,
            "activity": data["activity"],
            "as_of": data["as_of"],
            "by_gym": [],
        }
    gym_ids = set(
        session.exec(select(FinanceSale.gym_id).distinct()).all()
    ) | set(session.exec(select(FinancePayment.gym_id).distinct()).all())
    by_gym: list[dict[str, Any]] = []
    totals = {
        "base_sales_irr": 0,
        "taxes_irr": 0,
        "total_payments_irr": 0,
        "platform_share_irr": 0,
        "gym_share_irr": 0,
        "coach_share_irr": 0,
        "refunds_irr": 0,
        "completed_settlements_irr": 0,
    }
    as_of_totals = {
        "unsettled_platform_irr": 0,
        "unsettled_gym_irr": 0,
        "unsettled_coach_irr": 0,
        "pending_settlements_irr": 0,
        "completed_settlements_irr": 0,
    }
    for current_gym_id in sorted(gym_ids):
        gym = session.get(Gym, current_gym_id)
        if gym is None:
            continue
        data = _report_for_gym(
            session,
            gym_id=current_gym_id,
            from_date=from_date,
            to_date=to_date,
            category=category,
        )
        for key in totals:
            totals[key] += data["activity"][key]
        for key in as_of_totals:
            as_of_totals[key] += data["as_of"][key]
        by_gym.append(
            {
                "gym_id": current_gym_id,
                "gym_name": gym.name,
                "activity": data["activity"],
                "as_of": data["as_of"],
            }
        )
    return {
        "gym_id": None,
        "from_date": from_date,
        "to_date": to_date,
        "activity": totals,
        "as_of": {"date": to_date, **as_of_totals},
        "by_gym": by_gym,
    }


def report_csv_rows(report: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["section", "metric", "value_irr"],
    ]
    for key, value in report["activity"].items():
        rows.append(["activity", key, value])
    for key, value in report["as_of"].items():
        if key == "date":
            continue
        rows.append(["as_of", key, value])
    for gym in report["by_gym"]:
        for key, value in gym["activity"].items():
            rows.append(["gym_activity", f"{gym['gym_name']}:{key}", value])
        for key, value in gym["as_of"].items():
            if key == "date":
                continue
            rows.append(["gym_as_of", f"{gym['gym_name']}:{key}", value])
    return rows


def list_audit(
    session: Session, *, gym_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = session.exec(
        select(FinanceAudit)
        .where(FinanceAudit.gym_id == gym_id)
        .order_by(col(FinanceAudit.created_at).desc())
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        actor = session.get(User, row.actor_id) if row.actor_id else None
        result.append(
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "actor_name": (actor.full_name or actor.email) if actor else None,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "detail": row.detail,
                "created_at": row.created_at,
            }
        )
    return result
