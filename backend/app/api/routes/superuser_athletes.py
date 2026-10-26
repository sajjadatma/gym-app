from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.deps import (
    CurrentSuperuser,
    GymContext,
    SessionDep,
    get_current_assignment,
)
from app.core.audit import audit
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
    Message,
    SuperuserAthleteCreate,
    SuperuserAthleteRow,
    SuperuserAthletesPublic,
    SuperuserAthleteTransfer,
    SuperuserAthleteUpdate,
    User,
    WorkoutProgram,
)
from app.services.access import get_membership_roles
from app.services.athlete_lifecycle import (
    archive_athlete_record,
    create_athlete_record,
    delete_athlete_record,
    restore_athlete_record,
    validate_coach,
)
from app.services.membership import add_roles, ensure_membership
from app.services.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    paginate,
)

router = APIRouter(prefix="/superuser/athletes", tags=["superuser-athletes"])


def _ctx(gym: Gym, current_user: User) -> GymContext:
    return GymContext(
        gym=gym,
        membership=None,
        roles=set(),
        is_owner=gym.owner_id == current_user.id,
        is_superuser=True,
    )


def _load_gym(session: Session, gym_id: uuid.UUID) -> Gym:
    gym = session.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="gym_not_found")
    return gym


@router.get("", response_model=SuperuserAthletesPublic)
def list_athletes(
    *,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    q: str = "",
    gym_id: uuid.UUID | None = None,
    include_archived: bool = Query(default=False),
    is_archived: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    statement = (
        select(AthleteProfile, User, Gym)
        .join(User, col(User.id) == col(AthleteProfile.user_id))
        .join(Gym, col(Gym.id) == col(AthleteProfile.gym_id))
    )
    if gym_id is not None:
        statement = statement.where(AthleteProfile.gym_id == gym_id)
    if is_archived is not None:
        statement = statement.where(
            col(AthleteProfile.is_archived).is_(is_archived)
        )
    elif not include_archived:
        statement = statement.where(
            col(AthleteProfile.is_archived).is_(False)
        )
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                col(User.email).ilike(pattern),
                col(User.full_name).ilike(pattern),
                col(AthleteProfile.phone).ilike(pattern),
            )
        )
    statement = statement.order_by(
        col(Gym.name),
        col(User.full_name),
        col(User.email),
        col(User.id),
    )
    rows, total = paginate(
        session, statement, offset=offset, limit=limit
    )

    gym_ids = {gym.id for _profile, _user, gym in rows}
    athlete_ids = {user.id for _profile, user, _gym in rows}
    assignments = (
        session.exec(
            select(CoachAssignment).where(
                col(CoachAssignment.ended_at).is_(None),
                col(CoachAssignment.gym_id).in_(gym_ids),
                col(CoachAssignment.athlete_user_id).in_(athlete_ids),
            )
        ).all()
        if gym_ids
        else []
    )
    assignment_map = {
        (assignment.gym_id, assignment.athlete_user_id): assignment
        for assignment in assignments
    }
    coach_ids = {assignment.coach_user_id for assignment in assignments}
    coaches = (
        session.exec(select(User).where(col(User.id).in_(coach_ids))).all()
        if coach_ids
        else []
    )
    coach_names = {
        coach.id: coach.full_name or coach.email for coach in coaches
    }

    data = []
    for profile, user, gym in rows:
        assignment = assignment_map.get((gym.id, user.id))
        data.append(
            SuperuserAthleteRow(
                user_id=user.id,
                gym_id=gym.id,
                gym_name=gym.name,
                email=user.email,
                full_name=user.full_name,
                phone=profile.phone,
                is_archived=profile.is_archived,
                coach_user_id=(
                    assignment.coach_user_id if assignment else None
                ),
                coach_name=(
                    coach_names.get(assignment.coach_user_id)
                    if assignment
                    else None
                ),
                created_at=profile.created_at,
            )
        )
    return SuperuserAthletesPublic(data=data, count=total)


@router.post("", response_model=AthleteCreated)
def create_athlete(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: SuperuserAthleteCreate,
) -> Any:
    gym = _load_gym(session, body.gym_id)
    if not body.coach_user_id:
        raise HTTPException(status_code=400, detail="coach_required")
    payload = AthleteCreate(**body.model_dump(exclude={"gym_id"}))
    return create_athlete_record(
        session=session,
        current_user=current_user,
        ctx=_ctx(gym, current_user),
        body=payload,
    )


@router.patch(
    "/{gym_id}/{athlete_user_id}", response_model=SuperuserAthleteRow
)
def update_athlete(
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: SuperuserAthleteUpdate,
) -> Any:
    gym = _load_gym(session, gym_id)
    profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym.id,
            AthleteProfile.user_id == athlete_user_id,
        )
    ).first()
    user = session.get(User, athlete_user_id)
    if not profile or not user:
        raise HTTPException(status_code=404, detail="athlete_not_found")
    if profile.is_archived:
        raise HTTPException(status_code=409, detail="athlete_archived")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="empty_update")

    assignment = get_current_assignment(session, gym.id, athlete_user_id)
    requested_coach_id = data.get("coach_user_id")
    if "coach_user_id" in data:
        if requested_coach_id is None:
            raise HTTPException(status_code=400, detail="coach_required")
        coach = validate_coach(
            session, gym_id=gym.id, coach_user_id=requested_coach_id
        )
        if assignment is None or assignment.coach_user_id != coach.id:
            if assignment:
                assignment.ended_at = datetime.now(UTC)
                session.add(assignment)
                session.flush()
            assignment = CoachAssignment(
                gym_id=gym.id,
                athlete_user_id=athlete_user_id,
                coach_user_id=coach.id,
                assigned_by_id=current_user.id,
            )
            session.add(assignment)

    if "full_name" in data:
        full_name = data["full_name"]
        user.full_name = full_name.strip() or None if full_name else None
        session.add(user)
    if "phone" in data:
        profile.phone = (data["phone"] or "").strip() or None
    profile.updated_at = datetime.now(UTC)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.refresh(user)
    assignment = get_current_assignment(session, gym.id, athlete_user_id)
    assigned_coach = (
        session.get(User, assignment.coach_user_id) if assignment else None
    )
    audit(
        "athlete.updated",
        actor_id=current_user.id,
        gym_id=gym.id,
        target_id=athlete_user_id,
    )
    return SuperuserAthleteRow(
        user_id=user.id,
        gym_id=gym.id,
        gym_name=gym.name,
        email=user.email,
        full_name=user.full_name,
        phone=profile.phone,
        is_archived=profile.is_archived,
        coach_user_id=assignment.coach_user_id if assignment else None,
        coach_name=(assigned_coach.full_name or assigned_coach.email)
        if assigned_coach
        else None,
        created_at=profile.created_at,
    )


@router.post(
    "/{gym_id}/{athlete_user_id}/transfer",
    response_model=SuperuserAthleteRow,
)
def transfer_athlete(
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: SuperuserAthleteTransfer,
) -> Any:
    source = _load_gym(session, gym_id)
    profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == source.id,
            AthleteProfile.user_id == athlete_user_id,
        )
    ).first()
    user = session.get(User, athlete_user_id)
    if not profile or not user:
        raise HTTPException(status_code=404, detail="athlete_not_found")
    if profile.is_archived:
        raise HTTPException(status_code=409, detail="athlete_archived")
    if source.owner_id == athlete_user_id:
        raise HTTPException(
            status_code=409, detail="athlete_transfer_not_allowed"
        )
    if body.gym_id == source.id:
        raise HTTPException(status_code=400, detail="gym_unchanged")
    destination = _load_gym(session, body.gym_id)
    destination_membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == destination.id,
            GymMembership.user_id == athlete_user_id,
        )
    ).first()
    destination_profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == destination.id,
            AthleteProfile.user_id == athlete_user_id,
        )
    ).first()
    destination_program = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == destination.id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
        )
    ).first()
    if destination_membership or destination_profile or destination_program:
        raise HTTPException(status_code=409, detail="athlete_already_member")
    coach = validate_coach(
        session, gym_id=destination.id, coach_user_id=body.coach_user_id
    )
    source_membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == source.id,
            GymMembership.user_id == athlete_user_id,
        )
    ).first()
    if source_membership:
        source_roles = get_membership_roles(session, source_membership.id)
        if source_roles - {"ATHLETE"}:
            raise HTTPException(
                status_code=409, detail="athlete_has_other_roles"
            )

    now = datetime.now(UTC)
    programs = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == source.id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
        )
    ).all()
    body_files = session.exec(
        select(BodyAnalysisFile).where(
            BodyAnalysisFile.gym_id == source.id,
            BodyAnalysisFile.athlete_user_id == athlete_user_id,
        )
    ).all()
    for program in programs:
        program.gym_id = destination.id
        session.add(program)
    for body_file in body_files:
        body_file.gym_id = destination.id
        session.add(body_file)
    profile.gym_id = destination.id
    profile.updated_at = now
    session.add(profile)
    current_assignment = get_current_assignment(
        session, source.id, athlete_user_id
    )
    if current_assignment:
        current_assignment.ended_at = now
        session.add(current_assignment)
    if source_membership:
        session.delete(source_membership)
    membership = ensure_membership(
        session, gym_id=destination.id, user_id=athlete_user_id
    )
    session.flush()
    add_roles(session, membership=membership, roles=["ATHLETE"])
    assignment = CoachAssignment(
        gym_id=destination.id,
        athlete_user_id=athlete_user_id,
        coach_user_id=coach.id,
        assigned_by_id=current_user.id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(profile)
    audit(
        "athlete.transferred",
        actor_id=current_user.id,
        gym_id=destination.id,
        target_id=athlete_user_id,
        detail=str(source.id),
    )
    return SuperuserAthleteRow(
        user_id=user.id,
        gym_id=destination.id,
        gym_name=destination.name,
        email=user.email,
        full_name=user.full_name,
        phone=profile.phone,
        is_archived=profile.is_archived,
        coach_user_id=coach.id,
        coach_name=coach.full_name or coach.email,
        created_at=profile.created_at,
    )


@router.post("/{gym_id}/{athlete_user_id}/archive", response_model=Message)
def archive_athlete(
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
) -> Any:
    gym = _load_gym(session, gym_id)
    return archive_athlete_record(
        session=session,
        current_user=current_user,
        ctx=_ctx(gym, current_user),
        athlete_user_id=athlete_user_id,
    )


@router.post("/{gym_id}/{athlete_user_id}/restore", response_model=AthleteDetail)
def restore_athlete(
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: AthleteRestore | None = None,
) -> Any:
    gym = _load_gym(session, gym_id)
    return restore_athlete_record(
        session=session,
        current_user=current_user,
        ctx=_ctx(gym, current_user),
        athlete_user_id=athlete_user_id,
        body=body,
    )


@router.delete("/{gym_id}/{athlete_user_id}", response_model=Message)
def delete_athlete(
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
) -> Any:
    gym = _load_gym(session, gym_id)
    return delete_athlete_record(
        session=session,
        current_user=current_user,
        ctx=_ctx(gym, current_user),
        athlete_user_id=athlete_user_id,
    )
