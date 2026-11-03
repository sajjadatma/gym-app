from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlmodel import Session, col, select

from app.models import AthleteProfile, GymMembership, GymMembershipRole, User
from app.platform_models import (
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
) -> None:
    session.add(
        PlatformAudit(
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
