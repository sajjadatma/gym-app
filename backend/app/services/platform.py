from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlmodel import Session, col, select

from app.models import AthleteProfile, GymMembership, GymMembershipRole, User
from app.platform_models import (
    MAX_PLATFORM_IRR,
    PlatformAgreement,
    PlatformAudit,
    PlatformGroupMember,
    PlatformOperation,
    PlatformPlan,
    PlatformPlanCreate,
    PlatformPlanPublic,
    PlatformPlansPublic,
    PlatformPlanUsagePublic,
    PlatformPlanVersion,
    PlatformPlanVersionCreate,
    PlatformPlanVersionPublic,
)

ALLOWED_LIMITS: dict[str, type] = {
    "active_athletes": int,
    "staff_seats": int,
    "advanced_finance": bool,
    "sms": int,
    "storage_mb": int,
}


def utcnow() -> datetime:
    from app.services.finance import utcnow as finance_utcnow

    return finance_utcnow()


def _lock_platform(session: Session) -> None:
    session.connection().execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('platform', 0))")
    )


def _request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _find_operation(
    session: Session, operation_key: str, payload: dict[str, Any]
) -> PlatformPlan | None:
    operation = session.exec(
        select(PlatformOperation).where(
            PlatformOperation.operation_key == operation_key
        )
    ).first()
    if operation is None:
        return None
    if operation.request_hash != _request_hash(payload):
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    if operation.result_type != "platform_plan":
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    plan = session.get(PlatformPlan, operation.result_id)
    if plan is None:
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    return plan


def _remember_operation(
    session: Session,
    *,
    operation_key: str,
    payload: dict[str, Any],
    result_type: str,
    result_id: uuid.UUID,
) -> None:
    session.add(
        PlatformOperation(
            operation_key=operation_key,
            request_hash=_request_hash(payload),
            result_type=result_type,
            result_id=result_id,
        )
    )
    session.flush()


def _audit(
    session: Session,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    detail: dict[str, Any] | None = None,
    gym_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
) -> None:
    session.add(
        PlatformAudit(
            gym_id=gym_id,
            group_id=group_id,
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
        )
    )


def _validate_limits(limits: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in limits.items():
        expected = ALLOWED_LIMITS.get(key)
        if expected is None:
            raise HTTPException(
                status_code=422, detail="platform_limits_invalid"
            )
        if expected is bool:
            if not isinstance(value, bool):
                raise HTTPException(
                    status_code=422, detail="platform_limits_invalid"
                )
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HTTPException(
                status_code=422, detail="platform_limits_invalid"
            )
        clean[key] = value
    return clean


def _validate_version_dates(
    effective_from: date, effective_to: date | None
) -> None:
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(
            status_code=400, detail="platform_plan_invalid_dates"
        )


def _version_public(version: PlatformPlanVersion) -> PlatformPlanVersionPublic:
    return PlatformPlanVersionPublic(
        id=version.id,
        plan_id=version.plan_id,
        version_number=version.version_number,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        monthly_price_irr=version.monthly_price_irr,
        limits=version.limits,
        status=version.status,
        created_at=version.created_at,
    )


def _plan_public(
    session: Session, plan: PlatformPlan
) -> PlatformPlanPublic:
    versions = session.exec(
        select(PlatformPlanVersion)
        .where(PlatformPlanVersion.plan_id == plan.id)
        .order_by(col(PlatformPlanVersion.version_number))
    ).all()
    return PlatformPlanPublic(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        is_active=plan.is_active,
        versions=[_version_public(version) for version in versions],
        created_at=plan.created_at,
    )


def list_plans(session: Session) -> PlatformPlansPublic:
    plans = session.exec(
        select(PlatformPlan).order_by(col(PlatformPlan.code))
    ).all()
    return PlatformPlansPublic(
        data=[_plan_public(session, plan) for plan in plans]
    )


def get_plan(session: Session, plan_id: uuid.UUID) -> PlatformPlanPublic:
    plan = session.get(PlatformPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="platform_plan_not_found")
    return _plan_public(session, plan)


def create_plan(
    session: Session,
    *,
    actor: User,
    body: PlatformPlanCreate,
    operation_key: str,
) -> PlatformPlanPublic:
    _lock_platform(session)
    payload = body.model_dump(mode="json")
    existing_operation = _find_operation(session, operation_key, payload)
    if existing_operation is not None:
        return _plan_public(session, existing_operation)

    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=422, detail="platform_plan_code_required")
    existing = session.exec(
        select(PlatformPlan).where(PlatformPlan.code == code)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="platform_plan_code_exists")

    version_body = body.version
    _validate_version_dates(
        version_body.effective_from, version_body.effective_to
    )
    limits = _validate_limits(version_body.limits)
    if version_body.monthly_price_irr < 0:
        raise HTTPException(
            status_code=422, detail="platform_plan_price_invalid"
        )

    plan = PlatformPlan(
        code=code,
        name=body.name.strip(),
        created_by_id=actor.id,
    )
    session.add(plan)
    session.flush()
    version = PlatformPlanVersion(
        plan_id=plan.id,
        version_number=1,
        effective_from=version_body.effective_from,
        effective_to=version_body.effective_to,
        monthly_price_irr=version_body.monthly_price_irr,
        limits=limits,
        status="ACTIVE",
        created_by_id=actor.id,
    )
    session.add(version)
    session.flush()
    _audit(
        session,
        actor=actor,
        action="platform.plan.created",
        target_type="platform_plan",
        target_id=plan.id,
        detail={"code": plan.code, "version_id": str(version.id)},
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_plan",
        result_id=plan.id,
    )
    session.commit()
    session.refresh(plan)
    return _plan_public(session, plan)


def create_plan_version(
    session: Session,
    *,
    actor: User,
    plan_id: uuid.UUID,
    body: PlatformPlanVersionCreate,
    operation_key: str,
) -> PlatformPlanVersionPublic:
    _lock_platform(session)
    plan = session.get(PlatformPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="platform_plan_not_found")
    _validate_version_dates(body.effective_from, body.effective_to)
    if body.monthly_price_irr < 0:
        raise HTTPException(
            status_code=422, detail="platform_plan_price_invalid"
        )
    limits = _validate_limits(body.limits)

    existing_versions = session.exec(
        select(PlatformPlanVersion).where(
            PlatformPlanVersion.plan_id == plan.id
        )
    ).all()
    for version in existing_versions:
        if version.effective_from == body.effective_from:
            raise HTTPException(
                status_code=409, detail="platform_plan_period_overlap"
            )
        if version.status == "ACTIVE":
            # The current open-ended version is closed when the replacement
            # is activated; a draft replacement may coexist until then.
            continue
        version_end = version.effective_to
        new_end = body.effective_to
        if version_end is not None and version_end < body.effective_from:
            continue
        if new_end is not None and version.effective_from > new_end:
            continue
        raise HTTPException(
            status_code=409, detail="platform_plan_period_overlap"
        )
    next_number = (
        max((version.version_number for version in existing_versions), default=0)
        + 1
    )
    version = PlatformPlanVersion(
        plan_id=plan.id,
        version_number=next_number,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        monthly_price_irr=body.monthly_price_irr,
        limits=limits,
        status="DRAFT",
        created_by_id=actor.id,
    )
    session.add(version)
    session.flush()
    _audit(
        session,
        actor=actor,
        action="platform.plan.version_created",
        target_type="platform_plan",
        target_id=plan.id,
        detail={"version_id": str(version.id)},
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload={"plan_id": str(plan_id), **body.model_dump(mode="json")},
        result_type="platform_plan",
        result_id=plan.id,
    )
    session.commit()
    session.refresh(version)
    return _version_public(version)


def _set_version_status(
    session: Session,
    *,
    actor: User,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    status: str,
    action: str,
    operation_key: str,
) -> PlatformPlanVersionPublic:
    _lock_platform(session)
    plan = session.get(PlatformPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="platform_plan_not_found")
    version = session.get(PlatformPlanVersion, version_id)
    if version is None or version.plan_id != plan.id:
        raise HTTPException(
            status_code=404, detail="platform_plan_version_not_found"
        )
    if status == "ACTIVE":
        active_versions = session.exec(
            select(PlatformPlanVersion).where(
                PlatformPlanVersion.plan_id == plan.id,
                PlatformPlanVersion.status == "ACTIVE",
                PlatformPlanVersion.id != version.id,
            )
        ).all()
        for active in active_versions:
            if active.effective_from >= version.effective_from:
                raise HTTPException(
                    status_code=409,
                    detail="platform_plan_period_overlap",
                )
            if (
                active.effective_to is None
                or active.effective_to >= version.effective_from
            ):
                active.effective_to = version.effective_from - timedelta(days=1)
            active.status = "RETIRED"
            session.add(active)
    version.status = status
    session.add(version)
    _audit(
        session,
        actor=actor,
        action=action,
        target_type="platform_plan",
        target_id=plan.id,
        detail={"version_id": str(version.id), "status": status},
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload={"plan_id": str(plan_id), "version_id": str(version_id)},
        result_type="platform_plan",
        result_id=plan.id,
    )
    session.commit()
    session.refresh(version)
    return _version_public(version)


def activate_plan_version(
    session: Session,
    *,
    actor: User,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    operation_key: str,
) -> PlatformPlanVersionPublic:
    return _set_version_status(
        session,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        status="ACTIVE",
        action="platform.plan.version_activated",
        operation_key=operation_key,
    )


def retire_plan_version(
    session: Session,
    *,
    actor: User,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    operation_key: str,
) -> PlatformPlanVersionPublic:
    return _set_version_status(
        session,
        actor=actor,
        plan_id=plan_id,
        version_id=version_id,
        status="RETIRED",
        action="platform.plan.version_retired",
        operation_key=operation_key,
    )


def plan_usage(
    session: Session, *, plan_version_id: uuid.UUID
) -> PlatformPlanUsagePublic:
    version = session.get(PlatformPlanVersion, plan_version_id)
    if version is None:
        raise HTTPException(
            status_code=404, detail="platform_plan_version_not_found"
        )
    gym_ids: set[uuid.UUID] = set()
    agreements = session.exec(
        select(PlatformAgreement).where(
            PlatformAgreement.plan_version_id == plan_version_id,
            PlatformAgreement.status == "EFFECTIVE",
        )
    ).all()
    for agreement in agreements:
        if agreement.gym_id is not None:
            gym_ids.add(agreement.gym_id)
        elif agreement.group_id is not None:
            members = session.exec(
                select(PlatformGroupMember).where(
                    PlatformGroupMember.group_id == agreement.group_id
                )
            ).all()
            gym_ids.update(member.gym_id for member in members)
    if not gym_ids:
        active_athletes = 0
        staff_seats = 0
    else:
        active_athletes = session.exec(
            select(func.count())
            .select_from(AthleteProfile)
            .where(
                col(AthleteProfile.gym_id).in_(gym_ids),
                col(AthleteProfile.is_archived).is_(False),
            )
        ).one()
        staff_seats = session.exec(
            select(func.count(func.distinct(GymMembership.id)))
            .select_from(GymMembership)
            .join(
                GymMembershipRole,
                col(GymMembershipRole.membership_id) == col(GymMembership.id),
            )
            .where(
                col(GymMembership.gym_id).in_(gym_ids),
                col(GymMembership.is_active).is_(True),
                col(GymMembershipRole.role).in_(
                    ("GYM_ADMIN", "COACH", "FINANCE_STAFF")
                ),
            )
        ).one()
    limits = version.limits
    exceeded = False
    for key, used in (
        ("active_athletes", active_athletes),
        ("staff_seats", staff_seats),
    ):
        if key in limits and isinstance(limits[key], int):
            if used > limits[key]:
                exceeded = True
    return PlatformPlanUsagePublic(
        plan_version_id=plan_version_id,
        limits=limits,
        active_athletes=int(active_athletes),
        staff_seats=int(staff_seats),
        limit_status="EXCEEDED" if exceeded else "OK",
    )


def _find_result(
    session: Session,
    *,
    operation_key: str,
    payload: dict[str, Any],
    result_type: str,
) -> uuid.UUID | None:
    operation = session.exec(
        select(PlatformOperation).where(
            PlatformOperation.operation_key == operation_key
        )
    ).first()
    if operation is None:
        return None
    if (
        operation.request_hash != _request_hash(payload)
        or operation.result_type != result_type
    ):
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    return operation.result_id


def _validate_terms(
    mode: str, terms: list[Any]
) -> None:
    if mode in ("FREE", "SUBSCRIPTION") and terms:
        raise HTTPException(
            status_code=400, detail="platform_terms_not_allowed"
        )
    if mode == "COMMISSION" and not terms:
        raise HTTPException(
            status_code=400, detail="platform_terms_required"
        )
    seen: set[tuple[str, str]] = set()
    for term in terms:
        key = (term.kind, term.acquisition_source)
        if key in seen:
            raise HTTPException(status_code=422, detail="platform_term_duplicate")
        seen.add(key)
        if term.kind not in (
            "ANY",
            "MEMBERSHIP",
            "PROGRAM",
            "SESSION",
            "PACK",
            "PRODUCT",
            "SERVICE",
            "CUSTOM",
        ):
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.acquisition_source not in ("ANY", "GYM", "ASCORA"):
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.basis not in ("PERCENT", "FIXED", "PERCENT_PLUS_FIXED"):
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if not 0 <= term.percent_bp <= 10000:
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.fixed_irr < 0 or term.max_fee_irr < 0:
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.fixed_irr > MAX_PLATFORM_IRR or term.max_fee_irr > MAX_PLATFORM_IRR:
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.basis == "PERCENT" and term.fixed_irr:
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.basis == "FIXED" and term.percent_bp:
            raise HTTPException(status_code=422, detail="platform_term_invalid")
        if term.basis == "PERCENT_PLUS_FIXED" and not (
            term.percent_bp or term.fixed_irr
        ):
            raise HTTPException(status_code=422, detail="platform_term_invalid")


def _terms_public(
    session: Session, agreement_id: uuid.UUID
) -> list[Any]:
    from app.platform_models import PlatformCommissionTerm, PlatformCommissionTermPublic

    terms = session.exec(
        select(PlatformCommissionTerm)
        .where(PlatformCommissionTerm.agreement_id == agreement_id)
        .order_by(col(PlatformCommissionTerm.created_at), col(PlatformCommissionTerm.id))
    ).all()
    return [
        PlatformCommissionTermPublic(
            id=term.id,
            kind=term.kind,
            acquisition_source=term.acquisition_source,
            basis=term.basis,
            percent_bp=term.percent_bp,
            fixed_irr=term.fixed_irr,
            max_fee_irr=term.max_fee_irr,
        )
        for term in terms
    ]


def _agreement_public(
    session: Session, agreement: PlatformAgreement
) -> Any:
    from app.platform_models import PlatformAgreementPublic

    return PlatformAgreementPublic(
        id=agreement.id,
        gym_id=agreement.gym_id,
        group_id=agreement.group_id,
        version=agreement.version,
        supersedes_id=agreement.supersedes_id,
        mode=agreement.mode,
        status=agreement.status,
        effective_from=agreement.effective_from,
        effective_to=agreement.effective_to,
        plan_version_id=agreement.plan_version_id,
        subscription_amount_irr=agreement.subscription_amount_irr,
        billing_interval=agreement.billing_interval,
        volume_discount_bp=agreement.volume_discount_bp,
        grace_days=agreement.grace_days,
        restrict_after_days=agreement.restrict_after_days,
        terms=_terms_public(session, agreement.id),
        created_at=agreement.created_at,
        activated_at=agreement.activated_at,
    )


def _group_public(session: Session, group: Any) -> Any:
    from app.platform_models import (
        PlatformGroupMember,
        PlatformGroupMemberPublic,
        PlatformGroupPublic,
    )

    members = session.exec(
        select(PlatformGroupMember).where(
            PlatformGroupMember.group_id == group.id
        )
    ).all()
    return PlatformGroupPublic(
        id=group.id,
        name=group.name,
        members=[
            PlatformGroupMemberPublic(
                gym_id=member.gym_id, allocation_bp=member.allocation_bp
            )
            for member in members
        ],
        created_at=group.created_at,
    )


def create_group(
    session: Session,
    *,
    actor: User,
    body: Any,
    operation_key: str,
) -> Any:
    from app.models import Gym
    from app.platform_models import PlatformGroup, PlatformGroupMember

    _lock_platform(session)
    payload = body.model_dump(mode="json")
    existing_id = _find_result(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_group",
    )
    if existing_id is not None:
        group = session.get(PlatformGroup, existing_id)
        if group is None:
            raise HTTPException(
                status_code=409, detail="idempotency_key_reused"
            )
        return _group_public(session, group)
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=422, detail="platform_group_name_required"
        )
    if session.exec(
        select(PlatformGroup).where(PlatformGroup.name == name)
    ).first() is not None:
        raise HTTPException(
            status_code=409, detail="platform_group_name_exists"
        )
    members = list(body.members)
    if not members:
        raise HTTPException(
            status_code=400, detail="platform_group_members_required"
        )
    if sum(member.allocation_bp for member in members) != 10000:
        raise HTTPException(
            status_code=400, detail="platform_group_allocation_invalid"
        )
    for member in members:
        if member.allocation_bp < 0 or member.allocation_bp > 10000:
            raise HTTPException(
                status_code=400, detail="platform_group_allocation_invalid"
            )
        if session.get(Gym, member.gym_id) is None:
            raise HTTPException(status_code=404, detail="gym_not_found")
    group = PlatformGroup(name=name, created_by_id=actor.id)
    session.add(group)
    session.flush()
    for member in members:
        session.add(
            PlatformGroupMember(
                group_id=group.id,
                gym_id=member.gym_id,
                allocation_bp=member.allocation_bp,
            )
        )
    session.flush()
    _audit(
        session,
        actor=actor,
        action="platform.group.created",
        target_type="platform_group",
        target_id=group.id,
        detail={"name": group.name},
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_group",
        result_id=group.id,
    )
    session.commit()
    session.refresh(group)
    return _group_public(session, group)


def list_groups(session: Session) -> Any:
    from app.platform_models import PlatformGroup, PlatformGroupsPublic

    groups = session.exec(
        select(PlatformGroup).order_by(col(PlatformGroup.name))
    ).all()
    return PlatformGroupsPublic(
        data=[_group_public(session, group) for group in groups]
    )


def add_group_member(
    session: Session,
    *,
    actor: User,
    group_id: uuid.UUID,
    gym_id: uuid.UUID,
    allocation_bp: int,
) -> Any:
    from app.models import Gym
    from app.platform_models import PlatformGroup, PlatformGroupMember

    _lock_platform(session)
    group = session.get(PlatformGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="platform_group_not_found")
    if session.get(Gym, gym_id) is None:
        raise HTTPException(status_code=404, detail="gym_not_found")
    if allocation_bp < 0 or allocation_bp > 10000:
        raise HTTPException(
            status_code=400, detail="platform_group_allocation_invalid"
        )
    effective = session.exec(
        select(PlatformAgreement).where(
            PlatformAgreement.group_id == group_id,
            PlatformAgreement.status == "EFFECTIVE",
        )
    ).first()
    if effective is not None:
        raise HTTPException(
            status_code=409, detail="platform_group_effective"
        )
    existing = session.exec(
        select(PlatformGroupMember).where(
            PlatformGroupMember.group_id == group_id,
            PlatformGroupMember.gym_id == gym_id,
        )
    ).first()
    others_total = session.exec(
        select(func.coalesce(func.sum(PlatformGroupMember.allocation_bp), 0)).where(
            PlatformGroupMember.group_id == group_id,
            PlatformGroupMember.gym_id != gym_id,
        )
    ).one()
    if int(others_total) + allocation_bp != 10000:
        raise HTTPException(
            status_code=400, detail="platform_group_allocation_invalid"
        )
    if existing is not None:
        previous = existing.allocation_bp
        existing.allocation_bp = allocation_bp
        session.add(existing)
    else:
        previous = None
        session.add(
            PlatformGroupMember(
                group_id=group_id,
                gym_id=gym_id,
                allocation_bp=allocation_bp,
            )
        )
    session.flush()
    _audit(
        session,
        actor=actor,
        action="platform.group.member_updated",
        target_type="platform_group",
        target_id=group_id,
        detail={
            "gym_id": str(gym_id),
            "allocation_bp": allocation_bp,
            "previous_allocation_bp": previous,
        },
    )
    session.commit()
    return _group_public(session, group)


def create_agreement(
    session: Session,
    *,
    actor: User,
    body: Any,
    operation_key: str,
) -> Any:
    from app.platform_models import (
        PlatformAgreement,
        PlatformCommissionTerm,
        PlatformGroup,
        PlatformGroupMember,
    )

    _lock_platform(session)
    payload = body.model_dump(mode="json")
    existing_id = _find_result(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
    )
    if existing_id is not None:
        agreement = session.get(PlatformAgreement, existing_id)
        if agreement is None:
            raise HTTPException(
                status_code=409, detail="idempotency_key_reused"
            )
        return _agreement_public(session, agreement)
    if (body.gym_id is None) == (body.group_id is None):
        raise HTTPException(
            status_code=400, detail="platform_agreement_scope_invalid"
        )
    if body.effective_to is not None and body.effective_to < body.effective_from:
        raise HTTPException(
            status_code=400, detail="platform_agreement_dates_invalid"
        )
    if body.grace_days < 0 or body.restrict_after_days < body.grace_days:
        raise HTTPException(
            status_code=400, detail="platform_agreement_policy_invalid"
        )
    if not 0 <= body.volume_discount_bp <= 10000:
        raise HTTPException(
            status_code=400, detail="platform_volume_discount_invalid"
        )
    if body.gym_id is not None:
        from app.models import Gym

        if session.get(Gym, body.gym_id) is None:
            raise HTTPException(status_code=404, detail="gym_not_found")
    _validate_terms(body.mode, body.terms)
    plan_price = 0
    if body.plan_version_id is not None:
        plan_version = session.get(PlatformPlanVersion, body.plan_version_id)
        if plan_version is None:
            raise HTTPException(
                status_code=404, detail="platform_plan_version_not_found"
            )
        if plan_version.status != "ACTIVE":
            raise HTTPException(
                status_code=400, detail="platform_plan_version_inactive"
            )
        if plan_version.effective_from > body.effective_from:
            raise HTTPException(
                status_code=400,
                detail="platform_plan_version_outside_effective",
            )
        if plan_version.effective_to is not None and (
            body.effective_to is None
            or body.effective_to > plan_version.effective_to
        ):
            raise HTTPException(
                status_code=400,
                detail="platform_plan_version_outside_effective",
            )
        plan_price = plan_version.monthly_price_irr
    subscription_amount = (
        body.subscription_amount_irr
        if body.subscription_amount_irr is not None
        else plan_price
    )
    if body.mode in ("FREE", "COMMISSION"):
        if subscription_amount:
            raise HTTPException(
                status_code=400, detail="platform_subscription_not_allowed"
            )
        subscription_amount = 0
    if subscription_amount is None or subscription_amount < 0:
        raise HTTPException(
            status_code=400, detail="platform_subscription_invalid"
        )
    if subscription_amount > MAX_PLATFORM_IRR:
        raise HTTPException(
            status_code=400, detail="platform_subscription_invalid"
        )
    if body.group_id is not None:
        group = session.get(PlatformGroup, body.group_id)
        if group is None:
            raise HTTPException(
                status_code=404, detail="platform_group_not_found"
            )
        members = session.exec(
            select(PlatformGroupMember).where(
                PlatformGroupMember.group_id == body.group_id
            )
        ).all()
        if not members or sum(member.allocation_bp for member in members) != 10000:
            raise HTTPException(
                status_code=400, detail="platform_group_allocation_invalid"
            )
    prior = session.exec(
        select(PlatformAgreement)
        .where(
            PlatformAgreement.gym_id == body.gym_id,
            PlatformAgreement.group_id == body.group_id,
        )
        .order_by(col(PlatformAgreement.version).desc())
    ).first()
    if prior is not None and prior.effective_from == body.effective_from:
        raise HTTPException(
            status_code=409, detail="platform_agreement_period_overlap"
        )
    agreement = PlatformAgreement(
        gym_id=body.gym_id,
        group_id=body.group_id,
        version=(prior.version + 1) if prior else 1,
        supersedes_id=prior.id if prior else None,
        mode=body.mode,
        status="DRAFT",
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        plan_version_id=body.plan_version_id,
        subscription_amount_irr=subscription_amount or 0,
        volume_discount_bp=body.volume_discount_bp,
        grace_days=body.grace_days,
        restrict_after_days=body.restrict_after_days,
        created_by_id=actor.id,
    )
    session.add(agreement)
    session.flush()
    for term in body.terms:
        session.add(
            PlatformCommissionTerm(
                agreement_id=agreement.id,
                kind=term.kind,
                acquisition_source=term.acquisition_source,
                basis=term.basis,
                percent_bp=term.percent_bp,
                fixed_irr=term.fixed_irr,
                max_fee_irr=term.max_fee_irr,
            )
        )
    session.flush()
    _audit(
        session,
        actor=actor,
        action="platform.agreement.created",
        target_type="platform_agreement",
        target_id=agreement.id,
        gym_id=agreement.gym_id,
        group_id=agreement.group_id,
        detail={
            "mode": agreement.mode,
            "plan_version_id": str(agreement.plan_version_id)
            if agreement.plan_version_id
            else None,
            "subscription_amount_irr": agreement.subscription_amount_irr,
            "effective_from": agreement.effective_from.isoformat(),
            "effective_to": agreement.effective_to.isoformat()
            if agreement.effective_to
            else None,
            "volume_discount_bp": agreement.volume_discount_bp,
            "terms": [
                {
                    "kind": term.kind,
                    "acquisition_source": term.acquisition_source,
                    "basis": term.basis,
                    "percent_bp": term.percent_bp,
                    "fixed_irr": term.fixed_irr,
                    "max_fee_irr": term.max_fee_irr,
                }
                for term in body.terms
            ],
        },
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
        result_id=agreement.id,
    )
    session.commit()
    session.refresh(agreement)
    return _agreement_public(session, agreement)


def list_agreements(session: Session) -> Any:
    from app.platform_models import PlatformAgreement, PlatformAgreementsPublic

    agreements = session.exec(
        select(PlatformAgreement).order_by(
            col(PlatformAgreement.created_at),
            col(PlatformAgreement.version),
        )
    ).all()
    return PlatformAgreementsPublic(
        data=[_agreement_public(session, row) for row in agreements]
    )


def activate_agreement(
    session: Session,
    *,
    actor: User,
    agreement_id: uuid.UUID,
    operation_key: str,
) -> Any:
    from app.platform_models import PlatformAgreement

    _lock_platform(session)
    payload = {"action": "activate", "agreement_id": str(agreement_id)}
    existing_id = _find_result(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
    )
    if existing_id is not None:
        agreement = session.get(PlatformAgreement, existing_id)
        if agreement is None:
            raise HTTPException(
                status_code=409, detail="idempotency_key_reused"
            )
        return _agreement_public(session, agreement)
    agreement = session.get(PlatformAgreement, agreement_id)
    if agreement is None:
        raise HTTPException(
            status_code=404, detail="platform_agreement_not_found"
        )
    if agreement.status == "EFFECTIVE":
        return _agreement_public(session, agreement)
    if agreement.status == "REPLACED":
        raise HTTPException(
            status_code=409, detail="platform_agreement_replaced"
        )
    prior = session.exec(
        select(PlatformAgreement).where(
            PlatformAgreement.gym_id == agreement.gym_id,
            PlatformAgreement.group_id == agreement.group_id,
            PlatformAgreement.status == "EFFECTIVE",
            PlatformAgreement.id != agreement.id,
        )
    ).all()
    for row in prior:
        if row.effective_from >= agreement.effective_from:
            raise HTTPException(
                status_code=409, detail="platform_agreement_period_overlap"
            )
        if agreement.supersedes_id is None:
            agreement.supersedes_id = row.id
        # A future-dated replacement must not truncate or replace the
        # agreement that is in force today. Selection is effective-dated.
        if agreement.effective_from <= date.today():
            if (
                row.effective_to is None
                or row.effective_to >= agreement.effective_from
            ):
                row.effective_to = agreement.effective_from - timedelta(days=1)
            row.status = "REPLACED"
            session.add(row)
    agreement.status = "EFFECTIVE"
    agreement.activated_at = utcnow()
    session.add(agreement)
    _audit(
        session,
        actor=actor,
        action="platform.agreement.activated",
        target_type="platform_agreement",
        target_id=agreement.id,
        gym_id=agreement.gym_id,
        group_id=agreement.group_id,
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
        result_id=agreement.id,
    )
    session.commit()
    session.refresh(agreement)
    return _agreement_public(session, agreement)


def disable_agreement(
    session: Session,
    *,
    actor: User,
    agreement_id: uuid.UUID,
    operation_key: str,
) -> Any:
    from app.platform_models import PlatformAgreement

    _lock_platform(session)
    agreement = session.get(PlatformAgreement, agreement_id)
    if agreement is None:
        raise HTTPException(
            status_code=404, detail="platform_agreement_not_found"
        )
    payload = {"action": "disable", "agreement_id": str(agreement_id)}
    existing_id = _find_result(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
    )
    if existing_id is not None:
        existing = session.get(PlatformAgreement, existing_id)
        if existing is None:
            raise HTTPException(
                status_code=409, detail="idempotency_key_reused"
            )
        return _agreement_public(session, existing)
    if agreement.status == "DISABLED":
        return _agreement_public(session, agreement)
    if agreement.status == "REPLACED":
        raise HTTPException(
            status_code=409, detail="platform_agreement_replaced"
        )
    agreement.status = "DISABLED"
    session.add(agreement)
    _audit(
        session,
        actor=actor,
        action="platform.agreement.disabled",
        target_type="platform_agreement",
        target_id=agreement.id,
        gym_id=agreement.gym_id,
        group_id=agreement.group_id,
    )
    _remember_operation(
        session,
        operation_key=operation_key,
        payload=payload,
        result_type="platform_agreement",
        result_id=agreement.id,
    )
    session.commit()
    session.refresh(agreement)
    return _agreement_public(session, agreement)


def agreement_snapshot(session: Session, agreement: PlatformAgreement) -> dict[str, Any]:
    from app.platform_models import PlatformCommissionTerm

    group_allocations = []
    if agreement.group_id is not None:
        members = session.exec(
            select(PlatformGroupMember).where(
                PlatformGroupMember.group_id == agreement.group_id
            )
        ).all()
        group_allocations = [
            {"gym_id": str(member.gym_id), "allocation_bp": member.allocation_bp}
            for member in members
        ]
    return {
        "agreement_id": str(agreement.id),
        "version": agreement.version,
        "mode": agreement.mode,
        "plan_version_id": (
            str(agreement.plan_version_id)
            if agreement.plan_version_id is not None
            else None
        ),
        "subscription_amount_irr": agreement.subscription_amount_irr,
        "volume_discount_bp": agreement.volume_discount_bp,
        "grace_days": agreement.grace_days,
        "restrict_after_days": agreement.restrict_after_days,
        "group_allocations": group_allocations,
        "terms": [
            {
                "kind": term.kind,
                "acquisition_source": term.acquisition_source,
                "basis": term.basis,
                "percent_bp": term.percent_bp,
                "fixed_irr": term.fixed_irr,
                "max_fee_irr": term.max_fee_irr,
            }
            for term in session.exec(
                select(PlatformCommissionTerm)
                .where(PlatformCommissionTerm.agreement_id == agreement.id)
                .order_by(
                    col(PlatformCommissionTerm.created_at),
                    col(PlatformCommissionTerm.id),
                )
            ).all()
        ],
    }


def find_effective_agreement(
    session: Session, *, gym_id: uuid.UUID, on_date: date
) -> PlatformAgreement | None:
    from app.platform_models import PlatformGroupMember

    direct = session.exec(
        select(PlatformAgreement)
        .where(
            PlatformAgreement.gym_id == gym_id,
            PlatformAgreement.status == "EFFECTIVE",
            PlatformAgreement.effective_from <= on_date,
            or_(
                col(PlatformAgreement.effective_to).is_(None),
                col(PlatformAgreement.effective_to) >= on_date,
            ),
        )
        .order_by(col(PlatformAgreement.version).desc())
    ).first()
    if direct is not None:
        return direct
    return session.exec(
        select(PlatformAgreement)
        .join(
            PlatformGroupMember,
            col(PlatformGroupMember.group_id) == col(PlatformAgreement.group_id),
        )
        .where(
            PlatformGroupMember.gym_id == gym_id,
            PlatformAgreement.status == "EFFECTIVE",
            PlatformAgreement.effective_from <= on_date,
            or_(
                col(PlatformAgreement.effective_to).is_(None),
                col(PlatformAgreement.effective_to) >= on_date,
            ),
        )
        .order_by(col(PlatformAgreement.version).desc())
    ).first()


def match_commission_term(
    session: Session,
    *,
    agreement: PlatformAgreement,
    line_kind: str,
    acquisition_source: str,
) -> Any:
    from app.platform_models import PlatformCommissionTerm

    terms = session.exec(
        select(PlatformCommissionTerm).where(
            PlatformCommissionTerm.agreement_id == agreement.id
        )
    ).all()
    candidates: list[tuple[int, Any]] = []
    for term in terms:
        if term.kind not in (line_kind, "ANY"):
            continue
        if term.acquisition_source not in (acquisition_source, "ANY"):
            continue
        score = (2 if term.kind == line_kind else 0) + (
            1 if term.acquisition_source == acquisition_source else 0
        )
        candidates.append((score, term))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1].created_at,
            str(item[1].id),
        )
    )
    return candidates[0][1]


def platform_fee_for_line(term: Any, payable_irr: int) -> int:
    if payable_irr <= 0:
        return 0
    fee = 0
    if term.basis in ("PERCENT", "PERCENT_PLUS_FIXED"):
        fee += payable_irr * term.percent_bp // 10_000
    if term.basis in ("FIXED", "PERCENT_PLUS_FIXED"):
        fee += term.fixed_irr
    if term.max_fee_irr > 0:
        fee = min(fee, term.max_fee_irr)
    return min(fee, payable_irr)


def platform_fee_for_portion(
    snapshot: dict[str, Any], portion_irr: int, line_payable_irr: int
) -> int:
    term = snapshot.get("term") or {}
    if portion_irr <= 0 or line_payable_irr <= 0:
        return 0
    fee = 0
    if term.get("basis") in ("PERCENT", "PERCENT_PLUS_FIXED"):
        fee += portion_irr * int(term.get("percent_bp", 0)) // 10_000
    if term.get("basis") in ("FIXED", "PERCENT_PLUS_FIXED"):
        fee += int(term.get("fixed_irr", 0)) * portion_irr // line_payable_irr
    cap = int(term.get("max_fee_irr", 0) or 0)
    if cap > 0:
        fee = min(fee, cap)
    return min(fee, portion_irr)


def _next_platform_entry(session: Session) -> int:
    from app.platform_models import PlatformSequence

    sequence = session.exec(
        select(PlatformSequence).where(
            PlatformSequence.doc_type == "PLATFORM_JOURNAL"
        )
    ).first()
    if sequence is None:
        sequence = PlatformSequence(doc_type="PLATFORM_JOURNAL", last_value=0)
        session.add(sequence)
        session.flush()
    sequence.last_value += 1
    session.add(sequence)
    session.flush()
    return sequence.last_value


def post_platform_journal(
    session: Session,
    *,
    actor: User,
    posting_date: date,
    event_type: str,
    description: str,
    lines: list[tuple[str, int, int, str | None]],
    source_type: str,
    source_id: uuid.UUID | None,
) -> Any:
    from app.platform_models import PlatformJournal, PlatformJournalLine

    _lock_platform(session)
    total_debit = sum(line[1] for line in lines)
    total_credit = sum(line[2] for line in lines)
    if total_debit != total_credit or total_debit <= 0 or len(lines) < 2:
        raise HTTPException(
            status_code=500, detail="platform_journal_unbalanced"
        )
    journal = PlatformJournal(
        entry_number=_next_platform_entry(session),
        posting_date=posting_date,
        event_type=event_type,
        description=description,
        source_type=source_type,
        source_id=source_id,
        created_by_id=actor.id,
    )
    session.add(journal)
    session.flush()
    for account_code, debit, credit, memo in lines:
        session.add(
            PlatformJournalLine(
                journal_id=journal.id,
                account_code=account_code,
                debit_irr=debit,
                credit_irr=credit,
                memo=memo,
            )
        )
    session.flush()
    return journal


def list_receivables(
    session: Session, *, gym_id: uuid.UUID | None = None
) -> Any:
    from app.platform_models import (
        PlatformReceivable,
        PlatformReceivablesPublic,
    )

    statement = select(PlatformReceivable).order_by(
        col(PlatformReceivable.created_at),
        col(PlatformReceivable.id),
    )
    if gym_id is not None:
        statement = statement.where(PlatformReceivable.gym_id == gym_id)
    rows = session.exec(statement).all()
    return PlatformReceivablesPublic(
        data=[
            _platform_receivable_public(row)
            for row in rows
        ]
    )


def _platform_receivable_public(row: Any) -> Any:
    from app.platform_models import PlatformReceivablePublic

    return PlatformReceivablePublic(
        id=row.id,
        gym_id=row.gym_id,
        agreement_id=row.agreement_id,
        source_type=row.source_type,
        source_id=row.source_id,
        source_key=row.source_key,
        amount_irr=row.amount_irr,
        paid_irr=row.paid_irr,
        due_on=row.due_on,
        status=row.status,
        snapshot=row.snapshot,
        created_at=row.created_at,
    )


def create_platform_ascora_receivable(
    session: Session,
    *,
    gym_id: uuid.UUID,
    actor: User,
    invoice: Any,
    amount_irr: int,
    received_on: date,
    receipt_id: uuid.UUID | None,
    credit_movement_id: uuid.UUID | None,
    source_prefix: str,
) -> int:
    from app.finance_models import (
        FinanceCoachEarning,
        FinanceInvoiceLine,
    )
    from app.platform_models import (
        PLATFORM_COMMISSION_ACCOUNT,
        PLATFORM_CUSTOM_ACCOUNT,
        PLATFORM_RECEIVABLE_ACCOUNT,
        PlatformReceivable,
    )
    from app.services.finance import _split_proportional

    _lock_platform(session)
    lines = session.exec(
        select(FinanceInvoiceLine)
        .where(FinanceInvoiceLine.invoice_id == invoice.id)
        .order_by(col(FinanceInvoiceLine.line_number))
    ).all()
    portions = _split_proportional(amount_irr, [line.payable_irr for line in lines])
    earnings = session.exec(
        select(FinanceCoachEarning).where(
            FinanceCoachEarning.invoice_id == invoice.id,
            FinanceCoachEarning.receipt_id == receipt_id,
            FinanceCoachEarning.credit_movement_id == credit_movement_id,
        )
    ).all()
    earning_by_line: dict[uuid.UUID, list[Any]] = {}
    for earning in earnings:
        earning_by_line.setdefault(earning.invoice_line_id, []).append(earning)

    total = 0
    for line, portion in zip(lines, portions, strict=True):
        if portion <= 0:
            continue
        snapshot = line.platform_snapshot or {}
        source = snapshot.get("source")
        if source == "COACH_ASCORA_TERM":
            if session.exec(
                select(PlatformReceivable).where(
                    PlatformReceivable.source_id == line.id,
                    PlatformReceivable.source_type == "COMMISSION",
                )
            ).first() is not None:
                _audit(
                    session,
                    actor=actor,
                    action="platform.ascora_source.conflict_ignored",
                    target_type="finance_invoice_line",
                    target_id=line.id,
                    gym_id=gym_id,
                    detail={"source": "COACH_ASCORA_TERM"},
                )
                continue
            prefix = f"ascora:{invoice.id}:{line.id}:"
            prior = session.exec(
                select(func.coalesce(func.sum(PlatformReceivable.amount_irr), 0)).where(
                    PlatformReceivable.source_type == "COACH_ASCORA_SHARE",
                    col(PlatformReceivable.source_key).like(f"{prefix}%"),
                )
            ).one()
            remaining = max(line.platform_ascora_term_share_irr - int(prior), 0)
            for earning in earning_by_line.get(line.id, []):
                if earning.platform_share_irr <= 0 or remaining <= 0:
                    continue
                amount = min(earning.platform_share_irr, remaining)
                source_key = f"{prefix}{earning.id}"
                if session.exec(
                    select(PlatformReceivable).where(
                        PlatformReceivable.source_key == source_key
                    )
                ).first() is not None:
                    continue
                receivable = PlatformReceivable(
                    gym_id=gym_id,
                    agreement_id=None,
                    source_type="COACH_ASCORA_SHARE",
                    source_id=earning.id,
                    source_key=source_key,
                    amount_irr=amount,
                    due_on=received_on + timedelta(days=30),
                    status="OPEN",
                    snapshot=snapshot,
                )
                session.add(receivable)
                session.flush()
                post_platform_journal(
                    session,
                    actor=actor,
                    posting_date=received_on,
                    event_type="PLATFORM_FEE",
                    description="ASCORA coach-term share",
                    lines=[
                        (
                            PLATFORM_RECEIVABLE_ACCOUNT,
                            amount,
                            0,
                            "ASCORA receivable",
                        ),
                        (
                            PLATFORM_COMMISSION_ACCOUNT,
                            0,
                            amount,
                            "ASCORA revenue",
                        ),
                    ],
                    source_type=(
                        "finance_receipt" if receipt_id else "finance_credit"
                    ),
                    source_id=receipt_id or credit_movement_id,
                )
                _audit(
                    session,
                    actor=actor,
                    action="platform.ascora.recognized",
                    target_type="platform_receivable",
                    target_id=receivable.id,
                    gym_id=gym_id,
                    detail={
                        "source": "COACH_ASCORA_TERM",
                        "amount_irr": amount,
                        "source_key": source_key,
                    },
                )
                total += amount
                remaining -= amount
            continue
        if line.platform_allocation_status != "SNAPSHOTTED":
            continue
        if any(
            earning.platform_share_irr > 0
            for earning in earning_by_line.get(line.id, [])
        ):
            _audit(
                session,
                actor=actor,
                action="platform.ascora_source.conflict_ignored",
                target_type="finance_invoice_line",
                target_id=line.id,
                gym_id=gym_id,
                detail={"source": "PLATFORM_COMMISSION"},
            )
        fee = platform_fee_for_portion(
            snapshot, portion, line.payable_irr
        )
        if fee <= 0:
            continue
        prior = session.exec(
            select(func.coalesce(func.sum(PlatformReceivable.amount_irr), 0)).where(
                PlatformReceivable.source_id == line.id,
                PlatformReceivable.source_type == "COMMISSION",
            )
        ).one()
        cap = int((snapshot.get("term") or {}).get("max_fee_irr", 0) or 0)
        if cap > 0:
            fee = min(fee, max(cap - int(prior), 0))
        if fee <= 0:
            continue
        source_key = f"{source_prefix}:{line.id}"
        if session.exec(
            select(PlatformReceivable).where(
                PlatformReceivable.source_key == source_key
            )
        ).first() is not None:
            continue
        receivable = PlatformReceivable(
            gym_id=gym_id,
            agreement_id=line.platform_agreement_id,
            source_type="COMMISSION",
            source_id=line.id,
            source_key=source_key,
            amount_irr=fee,
            due_on=received_on + timedelta(days=30),
            status="OPEN",
            snapshot=snapshot,
        )
        session.add(receivable)
        session.flush()
        revenue_account = (
            PLATFORM_CUSTOM_ACCOUNT
            if snapshot.get("mode") == "CUSTOM"
            else PLATFORM_COMMISSION_ACCOUNT
        )
        post_platform_journal(
            session,
            actor=actor,
            posting_date=received_on,
            event_type="PLATFORM_FEE",
            description="Platform commission",
            lines=[
                (PLATFORM_RECEIVABLE_ACCOUNT, fee, 0, "Platform receivable"),
                (revenue_account, 0, fee, "Platform commission revenue"),
            ],
            source_type=(
                "finance_receipt" if receipt_id else "finance_credit"
            ),
            source_id=receipt_id or credit_movement_id,
        )
        _audit(
            session,
            actor=actor,
            action="platform.ascora.recognized",
            target_type="platform_receivable",
            target_id=receivable.id,
            gym_id=gym_id,
            detail={
                "source": "PLATFORM_COMMISSION",
                "amount_irr": fee,
                "source_key": source_key,
            },
        )
        total += fee
    return total
