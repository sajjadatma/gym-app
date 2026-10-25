from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.deps import CurrentSuperuser, SessionDep
from app.models import (
    AthleteProfile,
    Gym,
    GymMembership,
    GymMembershipRole,
    GymRole,
    Message,
    SuperuserCoachCreate,
    SuperuserCoachCreated,
    SuperuserCoachesPublic,
    SuperuserCoachRow,
    User,
)
from app.services.access import get_membership_roles
from app.services.membership import (
    activate_user,
    add_roles,
    end_active_coach_assignments,
    ensure_membership,
)

router = APIRouter(prefix="/superuser/coaches", tags=["superuser-coaches"])


def _coach_row(
    user: User,
    membership: GymMembership,
    gym: Gym,
    roles: set[str],
    can_archive: bool,
) -> SuperuserCoachRow:
    return SuperuserCoachRow(
        membership_id=membership.id,
        gym_id=gym.id,
        gym_name=gym.name,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        roles=cast(list[GymRole], sorted(roles)),
        is_active=membership.is_active,
        can_archive=can_archive,
        created_at=membership.created_at,
    )


def _load_coach(
    session: Session, membership_id: uuid.UUID
) -> tuple[GymMembership, Gym, User, set[str]]:
    membership = session.get(GymMembership, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="coach_not_found")
    roles = get_membership_roles(session, membership.id)
    if "COACH" not in roles:
        raise HTTPException(status_code=404, detail="coach_not_found")
    gym = session.get(Gym, membership.gym_id)
    user = session.get(User, membership.user_id)
    if not gym or not user:
        raise HTTPException(status_code=404, detail="coach_not_found")
    return membership, gym, user, roles


def _profile_in_gym(
    session: Session, gym_id: uuid.UUID, user_id: uuid.UUID
) -> AthleteProfile | None:
    return session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_id,
            AthleteProfile.user_id == user_id,
        )
    ).first()


@router.get("", response_model=SuperuserCoachesPublic)
def list_coaches(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    q: str = "",
    gym_id: uuid.UUID | None = None,
    include_archived: bool = Query(default=False),
) -> Any:
    statement = (
        select(User, GymMembership, Gym)
        .join(
            GymMembership,
            col(GymMembership.user_id) == col(User.id),
        )
        .join(Gym, col(Gym.id) == col(GymMembership.gym_id))
        .join(
            GymMembershipRole,
            col(GymMembershipRole.membership_id) == col(GymMembership.id),
        )
        .where(GymMembershipRole.role == "COACH")
    )
    if gym_id is not None:
        statement = statement.where(GymMembership.gym_id == gym_id)
    if not include_archived:
        statement = statement.where(col(GymMembership.is_active).is_(True))
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                col(User.email).ilike(pattern),
                col(User.full_name).ilike(pattern),
                col(User.phone).ilike(pattern),
            )
        )
    statement = statement.order_by(
        col(Gym.name), col(User.full_name), col(User.email)
    )
    result = session.exec(statement).all()
    gym_ids = {gym.id for _user, _membership, gym in result}
    profile_pairs = (
        set(
            session.exec(
                select(AthleteProfile.gym_id, AthleteProfile.user_id).where(
                    col(AthleteProfile.gym_id).in_(gym_ids)
                )
            ).all()
        )
        if gym_ids
        else set()
    )
    rows = []
    for user, membership, gym in result:
        roles = get_membership_roles(session, membership.id)
        rows.append(
            _coach_row(
                user,
                membership,
                gym,
                roles,
                roles == {"COACH"}
                and gym.owner_id != user.id
                and user.id != current_user.id
                and (gym.id, user.id) not in profile_pairs,
            )
        )
    return SuperuserCoachesPublic(data=rows, count=len(rows))


@router.post("", response_model=SuperuserCoachCreated)
def create_coach(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: SuperuserCoachCreate,
) -> Any:
    phone = body.phone.strip() or None
    if not phone:
        raise HTTPException(status_code=400, detail="coach_phone_required")
    gym = session.get(Gym, body.gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="gym_not_found")

    existing = session.exec(
        select(User).where(User.email == body.email)
    ).first()
    if existing:
        membership = session.exec(
            select(GymMembership).where(
                GymMembership.gym_id == gym.id,
                GymMembership.user_id == existing.id,
            )
        ).first()
        if membership and "COACH" in get_membership_roles(
            session, membership.id
        ):
            raise HTTPException(status_code=409, detail="coach_already_exists")

    activation = activate_user(
        session,
        email=body.email,
        full_name=body.full_name,
        gym=gym,
        method=body.activation_method,
        initial_password=body.initial_password,
        phone=phone,
    )
    membership = ensure_membership(
        session, gym_id=gym.id, user_id=activation.user.id
    )
    session.flush()
    add_roles(session, membership=membership, roles=["COACH"])
    session.commit()
    session.refresh(membership)
    session.refresh(activation.user)
    roles = get_membership_roles(session, membership.id)
    return SuperuserCoachCreated(
        coach=_coach_row(
            activation.user,
            membership,
            gym,
            roles,
            roles == {"COACH"}
            and gym.owner_id != activation.user.id
            and activation.user.id != current_user.id
            and _profile_in_gym(session, gym.id, activation.user.id) is None,
        ),
        initial_password=activation.initial_password,
        invitation_sent=activation.invitation_sent,
    )


@router.post("/{membership_id}/archive", response_model=Message)
def archive_coach(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
) -> Any:
    membership, gym, user, roles = _load_coach(session, membership_id)
    if not membership.is_active:
        raise HTTPException(status_code=400, detail="coach_already_archived")
    if (
        roles != {"COACH"}
        or gym.owner_id == user.id
        or user.id == current_user.id
        or _profile_in_gym(session, gym.id, user.id)
    ):
        raise HTTPException(
            status_code=409, detail="coach_archive_not_allowed"
        )
    end_active_coach_assignments(
        session, gym_id=gym.id, coach_user_id=user.id
    )
    membership.is_active = False
    session.add(membership)
    session.commit()
    return Message(message="coach_archived")


@router.post("/{membership_id}/restore", response_model=Message)
def restore_coach(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
) -> Any:
    membership, gym, user, roles = _load_coach(session, membership_id)
    if membership.is_active:
        raise HTTPException(status_code=400, detail="coach_not_archived")
    if (
        roles != {"COACH"}
        or gym.owner_id == user.id
        or user.id == current_user.id
        or _profile_in_gym(session, gym.id, user.id)
    ):
        raise HTTPException(
            status_code=409, detail="coach_archive_not_allowed"
        )
    membership.is_active = True
    session.add(membership)
    session.commit()
    return Message(message="coach_restored")


@router.delete("/{membership_id}", response_model=Message)
def delete_coach(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentSuperuser,
) -> Any:
    membership, gym, user, roles = _load_coach(session, membership_id)
    end_active_coach_assignments(
        session, gym_id=gym.id, coach_user_id=user.id
    )
    role_rows = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == membership.id,
            GymMembershipRole.role == "COACH",
        )
    ).all()
    for row in role_rows:
        session.delete(row)
    remaining = roles - {"COACH"}
    if (
        not remaining
        and gym.owner_id != user.id
        and not _profile_in_gym(session, gym.id, user.id)
    ):
        session.delete(membership)
    session.commit()
    return Message(message="coach_removed")
