from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.core.security import get_password_hash, verify_password
from app.models import (
    Gym,
    GymAccessPublic,
    GymMembership,
    GymRole,
    Message,
    UpdatePassword,
    User,
    UserMePublic,
    UserUpdateMe,
)
from app.services.access import get_membership_roles

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMePublic)
def read_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    memberships = session.exec(
        select(GymMembership)
        .where(
            GymMembership.user_id == current_user.id,
            col(GymMembership.is_active).is_(True),
        )
        .order_by(col(GymMembership.created_at))
    ).all()
    gyms: list[GymAccessPublic] = []
    for membership in memberships:
        gym = session.get(Gym, membership.gym_id)
        if not gym or not gym.is_active:
            continue
        roles = get_membership_roles(session, membership.id)
        if gym.owner_id == current_user.id:
            roles.add("GYM_ADMIN")
        gyms.append(
            GymAccessPublic(
                gym_id=gym.id,
                gym_name=gym.name,
                roles=cast(list[GymRole], sorted(roles)),
                is_owner=gym.owner_id == current_user.id,
            )
        )
    return UserMePublic(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        full_name=current_user.full_name,
        phone=current_user.phone,
        must_change_password=current_user.must_change_password,
        created_at=current_user.created_at,
        gyms=gyms,
    )


@router.patch("/me", response_model=UserMePublic)
def update_user_me(
    *,
    session: SessionDep,
    user_in: UserUpdateMe,
    current_user: CurrentUser,
) -> Any:
    if user_in.email:
        existing = session.exec(select(User).where(User.email == user_in.email)).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="email_already_exists")
    data = user_in.model_dump(exclude_unset=True)
    if "phone" in data:
        data["phone"] = (data["phone"] or "").strip() or None
    current_user.sqlmodel_update(data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return read_user_me(session=session, current_user=current_user)


@router.post("/me/password", response_model=Message)
def update_password_me(
    *,
    session: SessionDep,
    body: UpdatePassword,
    current_user: CurrentUser,
) -> Any:
    # Lock the row so the credential update and version bump are atomic.
    # populate_existing refreshes attributes loaded before the lock was taken.
    user = session.exec(
        select(User)
        .where(User.id == current_user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="password_not_set")
    verified, _ = verify_password(body.current_password, user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="incorrect_password")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="password_unchanged")
    user.hashed_password = get_password_hash(body.new_password)
    user.must_change_password = False
    user.token_version += 1
    session.add(user)
    session.commit()
    return Message(message="password_updated")
