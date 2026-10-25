from __future__ import annotations

import secrets
import uuid
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.deps import (
    CurrentSuperuser,
    CurrentUser,
    GymContextDep,
    SessionDep,
)
from app.core.audit import audit
from app.core.security import get_password_hash
from app.models import (
    AthleteProfile,
    CoachesPublic,
    CoachPublic,
    Gym,
    GymCreate,
    GymCreated,
    GymMembership,
    GymMembershipRole,
    GymPublic,
    GymRole,
    GymsPublic,
    GymUpdate,
    MemberCreate,
    MemberCreated,
    MemberPublic,
    MembersPublic,
    MemberUpdate,
    OwnershipTransfer,
    OwnershipTransferred,
    User,
)
from app.services.access import get_membership_roles
from app.services.membership import (
    activate_user,
    add_roles,
    ensure_membership,
    replace_staff_roles,
    send_invitation_for_user,
    to_gym_public,
)
from app.services.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    paginate,
)

router = APIRouter(prefix="/gyms", tags=["gyms"])


def _require_path_gym(ctx_gym: Gym, gym_id: uuid.UUID) -> None:
    if ctx_gym.id != gym_id:
        raise HTTPException(status_code=404, detail="gym_not_found")


def _member_public_from(
    *,
    membership: GymMembership,
    user: User,
    roles: set[str],
    gym: Gym,
) -> MemberPublic:
    return MemberPublic(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=cast(list[GymRole], sorted(roles)),
        phone=user.phone,
        is_active=membership.is_active,
        is_owner=gym.owner_id == user.id,
        created_at=membership.created_at,
    )


def _member_public(
    session: Session, membership: GymMembership, gym: Gym
) -> MemberPublic:
    user = session.get(User, membership.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    roles = get_membership_roles(session, membership.id)
    return _member_public_from(
        membership=membership, user=user, roles=roles, gym=gym
    )


@router.get("/", response_model=GymsPublic)
def list_gyms(session: SessionDep, current_user: CurrentUser) -> Any:
    if current_user.is_superuser:
        gyms = session.exec(select(Gym).order_by(col(Gym.name))).all()
        data = [
            to_gym_public(
                session,
                gym,
                current_user=current_user,
                membership=None,
                include_stats=True,
            )
            for gym in gyms
        ]
    else:
        memberships = session.exec(
            select(GymMembership).where(
                GymMembership.user_id == current_user.id,
                col(GymMembership.is_active).is_(True),
            )
        ).all()
        data = []
        for membership in memberships:
            gym = session.get(Gym, membership.gym_id)
            if not gym or not gym.is_active:
                continue
            roles = get_membership_roles(session, membership.id)
            if not roles and gym.owner_id != current_user.id:
                continue
            is_admin = gym.owner_id == current_user.id or "GYM_ADMIN" in roles
            data.append(
                to_gym_public(
                    session,
                    gym,
                    current_user=current_user,
                    membership=membership,
                    include_stats=is_admin,
                )
            )
        data.sort(key=lambda item: item.name)
    return GymsPublic(data=data, count=len(data))


@router.post("/", response_model=GymCreated)
def create_gym(
    *, session: SessionDep, current_superuser: CurrentSuperuser, body: GymCreate
) -> Any:
    existing = session.exec(select(User).where(User.email == body.owner_email)).first()
    initial_password: str | None = None
    invitation_sent = False
    created_user = False

    if not existing:
        created_user = True
        if body.activation_method == "password":
            initial_password = body.initial_password or secrets.token_urlsafe(9)
            existing = User(
                email=body.owner_email,
                full_name=body.owner_full_name,
                hashed_password=get_password_hash(initial_password),
                must_change_password=True,
            )
        else:
            existing = User(
                email=body.owner_email,
                full_name=body.owner_full_name,
                hashed_password=None,
            )
        session.add(existing)
        session.flush()
    elif body.owner_full_name and not existing.full_name:
        existing.full_name = body.owner_full_name
        session.add(existing)

    gym = Gym(
        name=body.name,
        description=body.description,
        address=body.address,
        phone=body.phone,
        owner_id=existing.id,
    )
    session.add(gym)
    session.flush()
    ensure_membership(session, gym_id=gym.id, user_id=existing.id)
    session.flush()

    if not existing.hashed_password:
        send_invitation_for_user(existing, gym)
        invitation_sent = True
    elif created_user and body.activation_method == "password":
        invitation_sent = False

    session.commit()
    session.refresh(gym)
    return GymCreated(
        gym=to_gym_public(
            session,
            gym,
            current_user=current_superuser,
            membership=None,
            include_stats=True,
        ),
        initial_password=initial_password,
        invitation_sent=invitation_sent,
    )


@router.get("/{gym_id}", response_model=GymPublic)
def read_gym(gym_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    gym = session.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="gym_not_found")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == current_user.id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if not current_user.is_superuser and not membership:
        raise HTTPException(status_code=404, detail="gym_not_found")
    if not gym.is_active and not current_user.is_superuser:
        raise HTTPException(status_code=404, detail="gym_not_found")
    roles = get_membership_roles(session, membership.id) if membership else set()
    if not current_user.is_superuser and gym.owner_id != current_user.id and not roles:
        raise HTTPException(status_code=404, detail="gym_not_found")
    is_admin = (
        current_user.is_superuser
        or gym.owner_id == current_user.id
        or "GYM_ADMIN" in roles
    )
    return to_gym_public(
        session,
        gym,
        current_user=current_user,
        membership=membership,
        include_stats=is_admin,
    )


@router.patch("/{gym_id}", response_model=GymPublic)
def update_gym(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: GymUpdate,
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    if body.is_active is not None and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="superuser_required")
    data = body.model_dump(exclude_unset=True)
    ctx.gym.sqlmodel_update(data)
    session.add(ctx.gym)
    session.commit()
    session.refresh(ctx.gym)
    return to_gym_public(
        session,
        ctx.gym,
        current_user=current_user,
        membership=ctx.membership,
        include_stats=True,
    )


@router.post("/{gym_id}/transfer-ownership", response_model=OwnershipTransferred)
def transfer_ownership(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: OwnershipTransfer,
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not (current_user.is_superuser or ctx.gym.owner_id == current_user.id):
        raise HTTPException(status_code=403, detail="ownership_transfer_forbidden")
    new_owner = session.exec(
        select(User).where(User.email == body.new_owner_email)
    ).first()
    initial_password: str | None = None
    invitation_sent = False
    created_user = False
    if not new_owner:
        created_user = True
        if body.activation_method == "password":
            initial_password = body.initial_password or secrets.token_urlsafe(9)
            new_owner = User(
                email=body.new_owner_email,
                full_name=body.new_owner_full_name,
                hashed_password=get_password_hash(initial_password),
                must_change_password=True,
            )
        else:
            new_owner = User(
                email=body.new_owner_email,
                full_name=body.new_owner_full_name,
                hashed_password=None,
            )
        session.add(new_owner)
        session.flush()
    if new_owner.id == ctx.gym.owner_id:
        raise HTTPException(status_code=400, detail="already_owner")
    ensure_membership(session, gym_id=ctx.gym.id, user_id=new_owner.id)
    session.flush()
    if not new_owner.hashed_password:
        send_invitation_for_user(new_owner, ctx.gym)
        invitation_sent = True
    elif created_user and body.activation_method == "password":
        invitation_sent = False
    ctx.gym.owner_id = new_owner.id
    session.add(ctx.gym)
    session.commit()
    audit(
        "gym.ownership_transferred",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=new_owner.id,
    )
    session.refresh(ctx.gym)
    return OwnershipTransferred(
        gym=to_gym_public(
            session,
            ctx.gym,
            current_user=current_user,
            membership=ctx.membership,
            include_stats=True,
        ),
        initial_password=initial_password,
        invitation_sent=invitation_sent,
    )


@router.get("/{gym_id}/members", response_model=MembersPublic)
def list_members(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    staff_only: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    statement = (
        select(GymMembership, User)
        .join(User, col(User.id) == col(GymMembership.user_id))
        .where(GymMembership.gym_id == gym_id)
    )
    if staff_only:
        statement = statement.where(
            or_(
                col(User.id) == ctx.gym.owner_id,
                col(GymMembership.id).in_(
                    select(GymMembershipRole.membership_id).where(
                        col(GymMembershipRole.role).in_(
                            ("GYM_ADMIN", "COACH")
                        )
                    )
                ),
            )
        )
    statement = statement.order_by(
        col(GymMembership.created_at), col(GymMembership.id)
    )
    rows, total = paginate(
        session, statement, offset=offset, limit=limit
    )
    role_rows = (
        session.exec(
            select(GymMembershipRole).where(
                col(GymMembershipRole.membership_id).in_(
                    [membership.id for membership, _user in rows]
                )
            )
        ).all()
        if rows
        else []
    )
    roles_by_membership: dict[uuid.UUID, set[str]] = {}
    for role_row in role_rows:
        roles_by_membership.setdefault(role_row.membership_id, set()).add(
            role_row.role
        )
    data = [
        _member_public_from(
            membership=membership,
            user=user,
            roles=roles_by_membership.get(membership.id, set()),
            gym=ctx.gym,
        )
        for membership, user in rows
    ]
    return MembersPublic(data=data, count=total)


@router.post("/{gym_id}/members", response_model=MemberCreated)
def create_member(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    body: MemberCreate,
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    phone = (body.phone or "").strip() or None
    if "COACH" in body.roles and not phone:
        raise HTTPException(status_code=400, detail="coach_phone_required")
    activation = activate_user(
        session,
        email=body.email,
        full_name=body.full_name,
        gym=ctx.gym,
        method=body.activation_method,
        initial_password=body.initial_password,
        phone=phone,
    )
    membership = ensure_membership(
        session, gym_id=ctx.gym.id, user_id=activation.user.id
    )
    session.flush()
    add_roles(session, membership=membership, roles=list(body.roles))
    session.commit()
    session.refresh(membership)
    return MemberCreated(
        member=_member_public(session, membership, ctx.gym),
        initial_password=activation.initial_password,
        invitation_sent=activation.invitation_sent,
    )


@router.patch("/{gym_id}/members/{membership_id}", response_model=MemberPublic)
def update_member(
    *,
    gym_id: uuid.UUID,
    membership_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: MemberUpdate,
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    membership = session.get(GymMembership, membership_id)
    if not membership or membership.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="membership_not_found")
    if membership.user_id == ctx.gym.owner_id and body.is_active is False:
        raise HTTPException(
            status_code=400, detail="owner_membership_cannot_be_deactivated"
        )
    if membership.user_id == current_user.id and body.is_active is False:
        raise HTTPException(status_code=400, detail="cannot_deactivate_self")
    if body.is_active is False:
        athlete_profile = session.exec(
            select(AthleteProfile).where(
                AthleteProfile.gym_id == gym_id,
                AthleteProfile.user_id == membership.user_id,
            )
        ).first()
        if athlete_profile:
            raise HTTPException(
                status_code=400,
                detail="athlete_membership_cannot_be_deactivated",
            )
    if body.roles is not None:
        if not body.roles and membership.user_id != ctx.gym.owner_id:
            raise HTTPException(status_code=400, detail="at_least_one_role_required")
        replace_staff_roles(session, membership=membership, roles=list(body.roles))
    if body.is_active is not None:
        membership.is_active = body.is_active
        session.add(membership)
    session.commit()
    audit(
        "membership.updated",
        actor_id=current_user.id,
        gym_id=gym_id,
        target_id=membership.id,
        detail=f"roles={sorted(body.roles) if body.roles is not None else 'unchanged'} active={body.is_active}",
    )
    session.refresh(membership)
    return _member_public(session, membership, ctx.gym)


@router.get("/{gym_id}/coaches", response_model=CoachesPublic)
def list_coaches(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    q: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    _require_path_gym(ctx.gym, gym_id)
    if not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    statement = (
        select(User, GymMembership)
        .join(GymMembership, col(GymMembership.user_id) == col(User.id))
        .join(
            GymMembershipRole,
            col(GymMembershipRole.membership_id) == col(GymMembership.id),
        )
        .where(
            GymMembership.gym_id == gym_id,
            col(GymMembership.is_active).is_(True),
            GymMembershipRole.role == "COACH",
            col(User.is_active).is_(True),
        )
    )
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                col(User.email).ilike(pattern),
                col(User.full_name).ilike(pattern),
            )
        )
    statement = statement.order_by(
        col(User.full_name), col(User.email), col(User.id)
    )
    rows, total = paginate(
        session, statement, offset=offset, limit=limit
    )
    data = [
        CoachPublic(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
        )
        for user, _membership in rows
    ]
    return CoachesPublic(data=data, count=total)
