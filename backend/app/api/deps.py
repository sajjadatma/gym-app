from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import (
    AthleteProfile,
    CoachAssignment,
    Gym,
    GymMembership,
    TokenPayload,
    User,
)
from app.services.access import get_membership_roles

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(request: Request, session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        if not token_data.sub:
            raise ValidationError.from_exception_data("token", [])
        user_id = uuid.UUID(token_data.sub)
    except InvalidTokenError, ValidationError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_credentials",
        )
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="inactive_user")
    if user.must_change_password and request.url.path not in {
        f"{settings.API_V1_STR}/users/me",
        f"{settings.API_V1_STR}/users/me/password",
    }:
        raise HTTPException(status_code=403, detail="password_change_required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="insufficient_privileges")
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]


@dataclass
class GymContext:
    gym: Gym
    membership: GymMembership | None
    roles: set[str]
    is_owner: bool
    is_superuser: bool

    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.is_owner or "GYM_ADMIN" in self.roles

    @property
    def is_coach(self) -> bool:
        return "COACH" in self.roles

    @property
    def is_athlete(self) -> bool:
        return "ATHLETE" in self.roles

    @property
    def is_staff(self) -> bool:
        return self.is_admin or self.is_coach


def get_gym_context(
    session: SessionDep,
    current_user: CurrentUser,
    x_gym_id: Annotated[uuid.UUID | None, Header(alias="X-Gym-ID")] = None,
) -> GymContext:
    if not x_gym_id:
        raise HTTPException(status_code=400, detail="gym_context_required")
    gym = session.get(Gym, x_gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="gym_not_found")
    if not gym.is_active and not current_user.is_superuser:
        raise HTTPException(status_code=404, detail="gym_not_found")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym.id,
            GymMembership.user_id == current_user.id,
        )
    ).first()
    if current_user.is_superuser:
        roles = get_membership_roles(session, membership.id) if membership else set()
        return GymContext(
            gym=gym,
            membership=membership,
            roles=roles,
            is_owner=gym.owner_id == current_user.id,
            is_superuser=True,
        )
    if not membership or not membership.is_active:
        raise HTTPException(status_code=403, detail="not_a_gym_member")
    roles = get_membership_roles(session, membership.id)
    if gym.owner_id != current_user.id and not roles:
        raise HTTPException(status_code=403, detail="not_a_gym_member")
    return GymContext(
        gym=gym,
        membership=membership,
        roles=roles,
        is_owner=gym.owner_id == current_user.id,
        is_superuser=False,
    )


GymContextDep = Annotated[GymContext, Depends(get_gym_context)]


def require_gym_admin(ctx: GymContextDep) -> GymContext:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    return ctx


GymAdminDep = Annotated[GymContext, Depends(require_gym_admin)]


def require_gym_staff(ctx: GymContextDep) -> GymContext:
    if not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    return ctx


GymStaffDep = Annotated[GymContext, Depends(require_gym_staff)]


@dataclass
class AthleteAccess:
    user: User
    profile: AthleteProfile
    membership: GymMembership
    assignment: CoachAssignment | None
    is_self: bool
    is_admin: bool
    is_current_coach: bool

    @property
    def can_edit_staff_fields(self) -> bool:
        return self.is_admin or self.is_current_coach


def get_current_assignment(
    session: Session, gym_id: uuid.UUID, athlete_user_id: uuid.UUID
) -> CoachAssignment | None:
    return session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_id,
            CoachAssignment.athlete_user_id == athlete_user_id,
            col(CoachAssignment.ended_at).is_(None),
        )
    ).first()


def get_athlete_access(
    session: Session,
    ctx: GymContext,
    current_user: User,
    athlete_user_id: uuid.UUID,
    *,
    allow_archived: bool = False,
) -> AthleteAccess:
    user = session.get(User, athlete_user_id)
    profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == ctx.gym.id,
            AthleteProfile.user_id == athlete_user_id,
        )
    ).first()
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == ctx.gym.id,
            GymMembership.user_id == athlete_user_id,
        )
    ).first()
    if not user or not profile or not membership:
        raise HTTPException(status_code=404, detail="athlete_not_found")

    is_self = current_user.id == athlete_user_id
    assignment = get_current_assignment(session, ctx.gym.id, athlete_user_id)

    if is_self:
        if not membership.is_active or profile.is_archived:
            raise HTTPException(status_code=404, detail="athlete_not_found")
        return AthleteAccess(
            user=user,
            profile=profile,
            membership=membership,
            assignment=assignment,
            is_self=True,
            is_admin=False,
            is_current_coach=False,
        )

    if ctx.is_admin:
        if profile.is_archived and not allow_archived:
            raise HTTPException(status_code=404, detail="athlete_not_found")
        return AthleteAccess(
            user=user,
            profile=profile,
            membership=membership,
            assignment=assignment,
            is_self=False,
            is_admin=True,
            is_current_coach=False,
        )

    if (
        ctx.is_coach
        and assignment
        and assignment.coach_user_id == current_user.id
        and membership.is_active
        and not profile.is_archived
    ):
        return AthleteAccess(
            user=user,
            profile=profile,
            membership=membership,
            assignment=assignment,
            is_self=False,
            is_admin=False,
            is_current_coach=True,
        )

    raise HTTPException(status_code=404, detail="athlete_not_found")
