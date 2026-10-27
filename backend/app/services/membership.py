from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.core.security import get_password_hash
from app.models import (
    ActivationMethod,
    AthleteProfile,
    CoachAssignment,
    Gym,
    GymMembership,
    GymMembershipRole,
    GymPublic,
    GymRole,
    GymStaffCounts,
    User,
    WorkoutProgram,
    WorkoutProgramVersion,
)
from app.utils import generate_invitation_email, generate_invitation_token, send_email

from .access import get_membership_roles


@dataclass
class ActivationResult:
    user: User
    initial_password: str | None = None
    invitation_sent: bool = False
    created: bool = False


def normalize_roles(roles: list[str]) -> list[str]:
    return sorted(set(roles))


def end_active_coach_assignments(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID,
    now: datetime | None = None,
) -> int:
    """Close current assignments for this coach in this gym only."""
    ended_at = now or datetime.now(UTC)
    rows = session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_id,
            CoachAssignment.coach_user_id == coach_user_id,
            col(CoachAssignment.ended_at).is_(None),
        )
    ).all()
    for row in rows:
        row.ended_at = ended_at
        session.add(row)
    return len(rows)


def ensure_membership(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> GymMembership:
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == user_id,
        )
    ).first()
    if membership:
        if not membership.is_active:
            membership.is_active = True
            session.add(membership)
        return membership
    membership = GymMembership(gym_id=gym_id, user_id=user_id)
    session.add(membership)
    return membership


def add_roles(session: Session, *, membership: GymMembership, roles: list[str]) -> None:
    existing = get_membership_roles(session, membership.id)
    for role in normalize_roles(roles):
        if role not in existing:
            session.add(GymMembershipRole(membership_id=membership.id, role=role))


def replace_staff_roles(
    session: Session, *, membership: GymMembership, roles: list[str]
) -> None:
    rows = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == membership.id
        )
    ).all()
    for row in rows:
        if row.role != "ATHLETE":
            session.delete(row)
    add_roles(session, membership=membership, roles=roles)


def send_invitation_for_user(user: User, gym: Gym) -> None:
    token = generate_invitation_token(user.email)
    email_data = generate_invitation_email(
        email_to=user.email,
        full_name=user.full_name,
        gym_name=gym.name,
        token=token,
    )
    try:
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as exc:  # pragma: no cover - configured Mailpit is tested manually
        raise HTTPException(status_code=502, detail="email_delivery_failed") from exc


def activate_user(
    session: Session,
    *,
    email: str,
    full_name: str | None,
    gym: Gym,
    method: ActivationMethod,
    initial_password: str | None,
    phone: str | None = None,
) -> ActivationResult:
    user = session.exec(select(User).where(User.email == email)).first()
    created = False
    generated_password = initial_password
    invitation_sent = False

    if not user:
        created = True
        if method == "password":
            generated_password = initial_password or secrets.token_urlsafe(9)
            user = User(
                email=email,
                full_name=full_name,
                phone=phone or None,
                hashed_password=get_password_hash(generated_password),
                must_change_password=True,
            )
            session.add(user)
        else:
            user = User(
                email=email,
                full_name=full_name,
                phone=phone or None,
                hashed_password=None,
                must_change_password=False,
            )
            session.add(user)
            session.flush()
            send_invitation_for_user(user, gym)
            invitation_sent = True
        return ActivationResult(
            user=user,
            initial_password=generated_password if method == "password" else None,
            invitation_sent=invitation_sent,
            created=created,
        )

    if full_name and not user.full_name:
        user.full_name = full_name
        session.add(user)
    if phone and not user.phone:
        user.phone = phone
        session.add(user)

    if not user.hashed_password:
        if method == "password":
            generated_password = initial_password or secrets.token_urlsafe(9)
            user.hashed_password = get_password_hash(generated_password)
            user.must_change_password = True
            session.add(user)
        else:
            send_invitation_for_user(user, gym)
            invitation_sent = True
    return ActivationResult(
        user=user,
        initial_password=generated_password
        if method == "password" and user.must_change_password
        else None,
        invitation_sent=invitation_sent,
        created=created,
    )


def gym_stats(session: Session, gym: Gym) -> GymStaffCounts:
    coach_count = session.exec(
        select(func.count(func.distinct(col(GymMembership.user_id))))
        .select_from(GymMembership)
        .join(
            GymMembershipRole,
            col(GymMembershipRole.membership_id) == col(GymMembership.id),
        )
        .where(
            GymMembership.gym_id == gym.id,
            col(GymMembership.is_active).is_(True),
            GymMembershipRole.role == "COACH",
        )
    ).one()
    admin_count = session.exec(
        select(func.count(func.distinct(col(GymMembership.user_id))))
        .select_from(GymMembership)
        .join(
            GymMembershipRole,
            col(GymMembershipRole.membership_id) == col(GymMembership.id),
        )
        .where(
            GymMembership.gym_id == gym.id,
            col(GymMembership.is_active).is_(True),
            GymMembershipRole.role == "GYM_ADMIN",
        )
    ).one()
    athlete_count = session.exec(
        select(func.count(col(AthleteProfile.id))).where(
            AthleteProfile.gym_id == gym.id,
            col(AthleteProfile.is_archived).is_(False),
        )
    ).one()
    active_count = session.exec(
        select(func.count(col(WorkoutProgramVersion.id)))
        .select_from(WorkoutProgramVersion)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            WorkoutProgram.gym_id == gym.id,
            WorkoutProgramVersion.status == "ACTIVE",
        )
    ).one()
    draft_count = session.exec(
        select(func.count(col(WorkoutProgramVersion.id)))
        .select_from(WorkoutProgramVersion)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            WorkoutProgram.gym_id == gym.id,
            WorkoutProgramVersion.status == "DRAFT",
        )
    ).one()
    archived_count = session.exec(
        select(func.count(col(WorkoutProgramVersion.id)))
        .select_from(WorkoutProgramVersion)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            WorkoutProgram.gym_id == gym.id,
            WorkoutProgramVersion.status == "ARCHIVED",
        )
    ).one()
    return GymStaffCounts(
        coaches=coach_count,
        admins=admin_count,
        athletes=athlete_count,
        active_programs=active_count,
        draft_programs=draft_count,
        archived_programs=archived_count,
    )


def to_gym_public(
    session: Session,
    gym: Gym,
    *,
    current_user: User,
    membership: GymMembership | None,
    roles: list[str] | set[str] | None = None,
    include_stats: bool = False,
) -> GymPublic:
    owner = session.get(User, gym.owner_id)
    effective_roles = (
        get_membership_roles(session, membership.id) if membership else set()
    )
    if roles is not None:
        effective_roles = set(roles)
    if gym.owner_id == current_user.id:
        effective_roles.add("GYM_ADMIN")
    if current_user.is_superuser:
        effective_roles = effective_roles | {"GYM_ADMIN"}
    return GymPublic(
        id=gym.id,
        name=gym.name,
        description=gym.description,
        address=gym.address,
        phone=gym.phone,
        brand_primary_color=gym.brand_primary_color,
        brand_accent_color=gym.brand_accent_color,
        logo_url=(
            f"/api/v1/gyms/{gym.id}/branding/logo"
            f"?v={int(gym.logo_updated_at.timestamp())}"
            if gym.logo_key and gym.logo_updated_at
            else None
        ),
        owner_id=gym.owner_id,
        owner_name=owner.full_name if owner else None,
        is_active=gym.is_active,
        created_at=gym.created_at,
        is_owner=gym.owner_id == current_user.id,
        my_roles=cast(list[GymRole], sorted(effective_roles)),
        stats=gym_stats(session, gym) if include_stats else None,
    )
