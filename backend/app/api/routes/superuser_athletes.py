from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.deps import CurrentSuperuser, GymContext, SessionDep
from app.models import (
    AthleteCreate,
    AthleteCreated,
    AthleteDetail,
    AthleteProfile,
    AthleteRestore,
    CoachAssignment,
    Gym,
    Message,
    SuperuserAthleteCreate,
    SuperuserAthleteRow,
    SuperuserAthletesPublic,
    User,
)
from app.services.athlete_lifecycle import (
    archive_athlete_record,
    create_athlete_record,
    delete_athlete_record,
    restore_athlete_record,
)
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
