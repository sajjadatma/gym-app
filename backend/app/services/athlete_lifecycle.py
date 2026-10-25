from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.api.deps import (
    GymContext,
    get_athlete_access,
    get_current_assignment,
)
from app.models import (
    AthleteCreate,
    AthleteCreated,
    AthleteDetail,
    AthleteProfile,
    AthleteRestore,
    BodyAnalysisFile,
    CoachAssignment,
    Gym,
    GymMembership,
    GymMembershipRole,
    Message,
    User,
    WorkoutProgram,
)
from app.services.access import get_membership_roles
from app.services.membership import activate_user, ensure_membership
from app.services.profiles import coach_members, staff_detail
from app.services.storage import delete_stored_files


def validate_coach(
    session: Session, *, gym_id: uuid.UUID, coach_user_id: uuid.UUID
) -> User:
    coach = session.get(User, coach_user_id)
    if not coach or not coach.is_active:
        raise HTTPException(status_code=400, detail="invalid_coach")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == coach_user_id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=400, detail="invalid_coach")
    if "COACH" not in get_membership_roles(session, membership.id):
        raise HTTPException(status_code=400, detail="invalid_coach")
    return coach


def create_athlete_record(
    *,
    session: Session,
    current_user: User,
    ctx: GymContext,
    body: AthleteCreate,
) -> AthleteCreated:
    coach_id = body.coach_user_id
    if not ctx.is_admin:
        coach_id = current_user.id
    if not coach_id:
        coach_id = current_user.id if "COACH" in ctx.roles else None
    if not coach_id:
        raise HTTPException(status_code=400, detail="coach_required")
    coach = validate_coach(session, gym_id=ctx.gym.id, coach_user_id=coach_id)

    existing_user = session.exec(select(User).where(User.email == body.email)).first()
    if existing_user:
        existing_profile = session.exec(
            select(AthleteProfile).where(
                AthleteProfile.gym_id == ctx.gym.id,
                AthleteProfile.user_id == existing_user.id,
            )
        ).first()
        if existing_profile:
            raise HTTPException(status_code=409, detail="athlete_already_exists")

    activation = activate_user(
        session,
        email=body.email,
        full_name=body.full_name,
        gym=ctx.gym,
        method=body.activation_method,
        initial_password=body.initial_password,
    )
    membership = ensure_membership(
        session, gym_id=ctx.gym.id, user_id=activation.user.id
    )
    session.flush()
    roles = get_membership_roles(session, membership.id)
    if "ATHLETE" not in roles:
        session.add(GymMembershipRole(membership_id=membership.id, role="ATHLETE"))
    if not activation.user.full_name and body.full_name:
        activation.user.full_name = body.full_name
        session.add(activation.user)

    profile = AthleteProfile(
        gym_id=ctx.gym.id,
        user_id=activation.user.id,
        phone=body.phone,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        training_goal=body.training_goal,
        training_days_count=body.training_days_count,
        training_days=[],
    )
    session.add(profile)
    session.flush()
    assignment = CoachAssignment(
        gym_id=ctx.gym.id,
        athlete_user_id=activation.user.id,
        coach_user_id=coach.id,
        assigned_by_id=current_user.id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(profile)
    session.refresh(assignment)
    detail = staff_detail(
        session,
        profile=profile,
        user=activation.user,
        assignment=assignment,
    )
    return AthleteCreated(
        athlete=detail,
        initial_password=activation.initial_password,
        invitation_sent=activation.invitation_sent,
    )


def archive_athlete_record(
    *,
    session: Session,
    current_user: User,
    ctx: GymContext,
    athlete_user_id: uuid.UUID,
) -> Message:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    now = datetime.now(UTC)
    access.profile.is_archived = True
    access.profile.updated_at = now
    assignment = get_current_assignment(session, ctx.gym.id, athlete_user_id)
    if assignment:
        assignment.ended_at = now
        session.add(assignment)
    roles = get_membership_roles(session, access.membership.id)
    is_gym_owner = ctx.gym.owner_id == access.user.id
    if roles <= {"ATHLETE"} and not is_gym_owner:
        # Keep the owner's membership active so their admin access survives.
        access.membership.is_active = False
        session.add(access.membership)
    session.add(access.profile)
    session.commit()
    return Message(message="athlete_archived")


def restore_athlete_record(
    *,
    session: Session,
    current_user: User,
    ctx: GymContext,
    athlete_user_id: uuid.UUID,
    body: AthleteRestore | None = None,
) -> AthleteDetail:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    if not access.profile.is_archived:
        return staff_detail(
            session,
            profile=access.profile,
            user=access.user,
            assignment=get_current_assignment(
                session, ctx.gym.id, athlete_user_id
            ),
        )

    coach = None
    if body and body.coach_user_id:
        coach = validate_coach(
            session, gym_id=ctx.gym.id, coach_user_id=body.coach_user_id
        )
    else:
        previous = session.exec(
            select(CoachAssignment)
            .where(
                CoachAssignment.gym_id == ctx.gym.id,
                CoachAssignment.athlete_user_id == athlete_user_id,
            )
            .order_by(col(CoachAssignment.started_at).desc())
        ).first()
        if previous:
            candidate = session.get(User, previous.coach_user_id)
            active_coach_ids = {
                item.user_id for item in coach_members(session, ctx.gym.id)
            }
            if candidate and candidate.id in active_coach_ids:
                coach = candidate

    now = datetime.now(UTC)
    access.profile.is_archived = False
    access.profile.updated_at = now
    access.membership.is_active = True
    session.add(access.profile)
    session.add(access.membership)
    if coach and not get_current_assignment(
        session, ctx.gym.id, athlete_user_id
    ):
        session.add(
            CoachAssignment(
                gym_id=ctx.gym.id,
                athlete_user_id=athlete_user_id,
                coach_user_id=coach.id,
                assigned_by_id=current_user.id,
            )
        )
    session.commit()
    session.refresh(access.profile)
    return staff_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=get_current_assignment(session, ctx.gym.id, athlete_user_id),
    )


def delete_athlete_record(
    *,
    session: Session,
    current_user: User,
    ctx: GymContext,
    athlete_user_id: uuid.UUID,
) -> Message:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    if access.user.is_superuser:
        raise HTTPException(status_code=400, detail="athlete_delete_forbidden")

    body_files = session.exec(
        select(BodyAnalysisFile).where(
            BodyAnalysisFile.gym_id == ctx.gym.id,
            BodyAnalysisFile.athlete_user_id == athlete_user_id,
        )
    ).all()
    stored_names = [file_row.stored_name for file_row in body_files]
    for file_row in body_files:
        session.delete(file_row)

    programs = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == ctx.gym.id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
        )
    ).all()
    for program in programs:
        session.delete(program)

    assignments = session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == ctx.gym.id,
            CoachAssignment.athlete_user_id == athlete_user_id,
        )
    ).all()
    for assignment in assignments:
        session.delete(assignment)

    roles = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == access.membership.id
        )
    ).all()
    remaining_roles = [role for role in roles if role.role != "ATHLETE"]
    is_gym_owner = ctx.gym.owner_id == access.user.id
    if is_gym_owner or remaining_roles:
        # Owners and staff keep their usable membership; only ATHLETE is removed.
        for role in roles:
            if role.role == "ATHLETE":
                session.delete(role)
        if is_gym_owner and not access.membership.is_active:
            access.membership.is_active = True
            session.add(access.membership)
    else:
        session.delete(access.membership)

    session.delete(access.profile)
    session.flush()

    owns_a_gym = session.exec(
        select(Gym.id).where(Gym.owner_id == access.user.id)
    ).first()
    memberships = session.exec(
        select(GymMembership).where(
            GymMembership.user_id == access.user.id
        )
    ).all()
    if not memberships and not owns_a_gym:
        session.delete(access.user)
    session.commit()
    # Files are removed only after the durable commit; cleanup is idempotent.
    delete_stored_files(stored_names)
    return Message(message="athlete_deleted")
