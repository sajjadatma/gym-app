from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app.activity_models import (
    WorkoutSession,
    WorkoutSessionCreate,
    WorkoutSessionPublic,
)
from app.api.deps import CurrentUser, GymContextDep, SessionDep, get_athlete_access
from app.core.audit import audit
from app.finance_models import (
    FinanceAllocation,
    FinancePayment,
    FinanceProgramRequest,
    FinanceSale,
    FinanceSettlement,
)
from app.models import (
    AthleteProfile,
    CoachAssignment,
    Gym,
    GymMembership,
    User,
    WorkoutDay,
    WorkoutExercise,
    WorkoutProgram,
    WorkoutProgramVersion,
    WorkoutSet,
)
from app.services import finance
from app.services.programs import load_version_context

router = APIRouter(tags=["activity"])


def _session_public(row: WorkoutSession) -> WorkoutSessionPublic:
    return WorkoutSessionPublic.model_validate(row)


@router.get(
    "/athletes/{athlete_user_id}/workout-sessions",
    response_model=list[WorkoutSessionPublic],
)
def list_workout_sessions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    athlete_user_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
) -> Any:
    get_athlete_access(session, ctx, current_user, athlete_user_id, allow_archived=True)
    rows = session.exec(
        select(WorkoutSession)
        .where(
            WorkoutSession.gym_id == ctx.gym.id,
            WorkoutSession.athlete_user_id == athlete_user_id,
        )
        .order_by(
            col(WorkoutSession.performed_on).desc(),
            col(WorkoutSession.created_at).desc(),
        )
        .limit(limit)
    ).all()
    return [_session_public(row) for row in rows]


@router.post(
    "/athletes/{athlete_user_id}/workout-sessions", response_model=WorkoutSessionPublic
)
def create_workout_session(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    athlete_user_id: uuid.UUID,
    body: WorkoutSessionCreate,
) -> Any:
    access = get_athlete_access(session, ctx, current_user, athlete_user_id)
    if not access.is_self or not ctx.is_athlete:
        raise HTTPException(status_code=403, detail="athlete_self_required")
    if access.profile.is_archived:
        raise HTTPException(status_code=409, detail="athlete_archived")
    if body.performed_on > finance.finance_today():
        raise HTTPException(status_code=400, detail="workout_future_date")
    # Reuse the gym transaction mutex to serialize retries and program changes.
    finance._lock_finance_gym(session, ctx.gym.id)
    existing = session.exec(
        select(WorkoutSession).where(
            WorkoutSession.gym_id == ctx.gym.id,
            WorkoutSession.athlete_user_id == athlete_user_id,
            WorkoutSession.idempotency_key == body.idempotency_key,
        )
    ).first()
    if existing is not None:
        old_sets = [
            {key: row.get(key) for key in ("set_id", "completed", "reps", "weight_kg")}
            for row in existing.sets
        ]
        new_sets = [item.model_dump(mode="json") for item in body.sets]
        if (
            any(
                getattr(existing, key) != getattr(body, key)
                for key in (
                    "version_id",
                    "day_id",
                    "performed_on",
                    "completed",
                    "effort",
                    "note",
                )
            )
            or old_sets != new_sets
        ):
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _session_public(existing)
    version, program, _access = load_version_context(
        session, ctx=ctx, current_user=current_user, version_id=body.version_id
    )
    if program.athlete_user_id != athlete_user_id or version.status == "DRAFT":
        raise HTTPException(status_code=404, detail="program_not_found")
    day = session.get(WorkoutDay, body.day_id)
    if day is None or day.version_id != version.id:
        raise HTTPException(status_code=400, detail="workout_day_mismatch")
    selected = session.exec(
        select(WorkoutSet, WorkoutExercise)
        .join(
            WorkoutExercise,
            col(WorkoutSet.workout_exercise_id) == col(WorkoutExercise.id),
        )
        .where(WorkoutExercise.day_id == day.id)
    ).all()
    lookup = {row.id: (row, exercise) for row, exercise in selected}
    if len({item.set_id for item in body.sets}) != len(body.sets):
        raise HTTPException(status_code=400, detail="workout_duplicate_set")
    actuals: list[dict[str, Any]] = []
    for item in body.sets:
        if item.set_id not in lookup:
            raise HTTPException(status_code=400, detail="workout_set_mismatch")
        target, exercise = lookup[item.set_id]
        actuals.append(
            {
                **item.model_dump(mode="json"),
                "exercise_id": str(exercise.exercise_id),
                "exercise_name": exercise.exercise_name,
                "set_number": target.set_number,
                "target_reps_min": target.reps_min,
                "target_reps_max": target.reps_max,
                "target_weight_kg": target.weight_kg,
            }
        )
    row = WorkoutSession(
        gym_id=ctx.gym.id,
        athlete_user_id=athlete_user_id,
        version_id=version.id,
        day_id=day.id,
        program_title=version.title,
        day_title=day.title,
        performed_on=body.performed_on,
        completed=body.completed,
        effort=body.effort,
        note=body.note,
        sets=actuals,
        idempotency_key=body.idempotency_key,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="workout_retry_conflict")
    session.refresh(row)
    audit(
        "workout_session.created",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=row.id,
    )
    return _session_public(row)


@router.get("/gyms/{gym_id}/coach/statement")
def coach_statement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
) -> dict[str, Any]:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    # No caller-supplied coach ID: this endpoint can only expose one's own share.
    allocations = session.exec(
        select(FinanceAllocation)
        .where(
            FinanceAllocation.gym_id == gym_id,
            FinanceAllocation.party == "COACH",
            FinanceAllocation.party_user_id == current_user.id,
        )
        .order_by(col(FinanceAllocation.created_at).desc())
    ).all()
    entries: list[dict[str, Any]] = []
    gross = refunded = settled = reserved = available = adjustment = 0
    for allocation in allocations:
        refund = finance._allocation_refunded_irr(session, allocation.id)
        paid = finance._allocation_completed_settled_irr(session, allocation.id)
        pending = finance._allocation_reserved_irr(session, allocation.id) - paid
        payment = session.get(FinancePayment, allocation.payment_id)
        sale = session.get(FinanceSale, payment.sale_id) if payment else None
        gross += allocation.amount_irr
        refunded += refund
        settled += paid
        reserved += pending
        available += finance.allocation_available_irr(session, allocation)
        adjustment += max(paid + refund - allocation.amount_irr, 0)
        entries.append(
            {
                "id": allocation.id,
                "description": sale.description if sale else "",
                "category": sale.category if sale else None,
                "earned_irr": allocation.amount_irr,
                "refunded_irr": refund,
                "settled_irr": paid,
                "pending_irr": pending,
                "available_irr": finance.allocation_available_irr(session, allocation),
                "created_at": payment.paid_at if payment else allocation.created_at,
            }
        )
    payouts = session.exec(
        select(FinanceSettlement)
        .where(
            FinanceSettlement.gym_id == gym_id,
            FinanceSettlement.party == "COACH",
            FinanceSettlement.party_user_id == current_user.id,
        )
        .order_by(col(FinanceSettlement.requested_at).desc())
    ).all()
    return {
        "gym_id": gym_id,
        "earned_irr": gross,
        "refunded_irr": refunded,
        "settled_irr": settled,
        "pending_irr": reserved,
        "available_irr": available,
        "post_settlement_adjustments_irr": adjustment,
        "entries": entries,
        "settlements": [
            {
                "id": row.id,
                "amount_irr": row.amount_irr,
                "status": row.status,
                "requested_at": row.requested_at,
                "completed_at": row.completed_at,
            }
            for row in payouts
        ],
        "simulated": True,
    }


def _own_sale(
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    sale_id: uuid.UUID,
) -> FinanceSale:
    if ctx.gym.id != gym_id or not ctx.is_athlete:
        raise HTTPException(status_code=403, detail="athlete_access_required")
    sale = session.exec(
        select(FinanceSale).where(
            FinanceSale.id == sale_id,
            FinanceSale.gym_id == gym_id,
            FinanceSale.athlete_user_id == current_user.id,
        )
    ).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="sale_not_found")
    return sale


@router.get("/gyms/{gym_id}/athlete/purchases/{sale_id}/document")
def purchase_document(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    sale_id: uuid.UUID,
) -> dict[str, Any]:
    sale = _own_sale(session, current_user, ctx, gym_id, sale_id)
    public = finance.sale_public(session, sale)
    payments = session.exec(
        select(FinancePayment)
        .where(FinancePayment.sale_id == sale.id, FinancePayment.status == "SUCCEEDED")
        .order_by(col(FinancePayment.created_at))
    ).all()
    gym = session.get(Gym, gym_id)
    return {
        "reference": f"ASC-{sale.id.hex.upper()}",
        "sale_id": sale.id,
        "gym_name": gym.name if gym else "",
        "gym_address": gym.address if gym else None,
        "gym_phone": gym.phone if gym else None,
        "athlete_name": current_user.full_name or current_user.email,
        "description": sale.description,
        "issued_at": sale.created_at,
        "base_amount_irr": sale.base_amount_irr,
        "taxes": public["taxes"],
        "tax_amount_irr": sale.tax_amount_irr,
        "total_amount_irr": sale.total_amount_irr,
        "status": sale.status,
        "refunded_irr": public["refunded_irr"],
        "payments": [
            {
                "reference": f"PAY-{row.id.hex.upper()}",
                "amount_irr": row.amount_irr,
                "paid_at": row.paid_at,
                "status": row.status,
            }
            for row in payments
        ],
        "simulated": True,
    }


@router.get("/gyms/{gym_id}/tasks")
def gym_tasks(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
) -> dict[str, Any]:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    requests = select(FinanceProgramRequest).where(
        FinanceProgramRequest.gym_id == gym_id,
        col(FinanceProgramRequest.status).in_(["REQUESTED", "IN_PROGRESS"]),
    )
    profiles = (
        select(AthleteProfile)
        .join(User, col(User.id) == col(AthleteProfile.user_id))
        .join(
            GymMembership,
            (col(GymMembership.user_id) == col(AthleteProfile.user_id))
            & (col(GymMembership.gym_id) == gym_id),
        )
        .where(
            AthleteProfile.gym_id == gym_id,
            col(AthleteProfile.is_archived).is_(False),
            col(User.is_active).is_(True),
            col(GymMembership.is_active).is_(True),
        )
    )
    if not ctx.is_admin:
        requests = requests.where(
            FinanceProgramRequest.coach_user_id == current_user.id
        )
        assigned = select(CoachAssignment.athlete_user_id).where(
            CoachAssignment.gym_id == gym_id,
            CoachAssignment.coach_user_id == current_user.id,
            col(CoachAssignment.ended_at).is_(None),
        )
        profiles = profiles.where(col(AthleteProfile.user_id).in_(assigned))
    active = (
        select(WorkoutProgram.athlete_user_id)
        .join(
            WorkoutProgramVersion,
            col(WorkoutProgramVersion.program_id) == col(WorkoutProgram.id),
        )
        .where(
            WorkoutProgram.gym_id == gym_id, WorkoutProgramVersion.status == "ACTIVE"
        )
    )
    profiles = profiles.where(col(AthleteProfile.user_id).not_in(active))
    missing_count = session.exec(
        select(func.count()).select_from(profiles.subquery())
    ).one()
    requested_count = session.exec(
        select(func.count()).select_from(
            requests.where(FinanceProgramRequest.status == "REQUESTED").subquery()
        )
    ).one()
    progress_count = session.exec(
        select(func.count()).select_from(
            requests.where(FinanceProgramRequest.status == "IN_PROGRESS").subquery()
        )
    ).one()
    rows = session.exec(
        requests.order_by(col(FinanceProgramRequest.created_at)).limit(8)
    ).all()
    missing = session.exec(
        profiles.order_by(col(AthleteProfile.created_at)).limit(8)
    ).all()
    return {
        "requested_count": requested_count,
        "in_progress_count": progress_count,
        "without_program_count": missing_count,
        "requests": [finance.program_request_public(session, row) for row in rows],
        "without_program": [
            {
                "id": row.user_id,
                "name": (user.full_name or user.email)
                if (user := session.get(User, row.user_id))
                else "",
            }
            for row in missing
        ],
    }
