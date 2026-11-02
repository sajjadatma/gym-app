from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import GymContext
from app.finance_models import (
    FINANCE_OPENING_MANAGE,
    FINANCE_PERIOD_MANAGE,
    FINANCE_VIEW,
    FinanceAudit,
    FinancePermissionName,
    FinanceSettings,
    FinanceSettingsPublic,
)
from app.models import User

ADMIN_PERMISSIONS: tuple[str, ...] = (
    FINANCE_VIEW,
    FINANCE_OPENING_MANAGE,
    FINANCE_PERIOD_MANAGE,
)

DEFAULT_DISPLAY_UNIT = "RIAL"
DEFAULT_TIMEZONE = "Asia/Tehran"


def utcnow() -> datetime:
    return datetime.now(UTC)


def get_finance_settings(
    session: Session, gym_id: uuid.UUID
) -> FinanceSettings | None:
    return session.exec(
        select(FinanceSettings).where(FinanceSettings.gym_id == gym_id)
    ).first()


def finance_enabled(session: Session, gym_id: uuid.UUID) -> bool:
    """Absence of a settings row means finance is enabled by default."""
    settings = get_finance_settings(session, gym_id)
    return settings.enabled if settings else True


def resolve_finance_scope(
    session: Session, ctx: GymContext, current_user: User
) -> FinanceScope:
    settings = get_finance_settings(session, ctx.gym.id)
    if current_user.is_superuser or ctx.is_admin:
        return FinanceScope(
            gym_id=ctx.gym.id,
            settings=settings,
            is_admin=True,
            is_superuser=current_user.is_superuser,
            grants={},
        )
    if "FINANCE_STAFF" in ctx.roles:
        # Action grants arrive with the grant slice; a finance staff member
        # sees read-only finance until an explicit grant exists.
        return FinanceScope(
            gym_id=ctx.gym.id,
            settings=settings,
            is_admin=False,
            is_superuser=False,
            grants={},
        )
    raise HTTPException(status_code=403, detail="finance_access_denied")


@dataclass(frozen=True)
class FinanceScope:
    gym_id: uuid.UUID
    settings: FinanceSettings | None
    is_admin: bool
    is_superuser: bool
    grants: dict[str, int | None]

    @property
    def enabled(self) -> bool:
        return self.settings.enabled if self.settings else True

    @property
    def display_unit(self) -> str:
        return self.settings.display_unit if self.settings else DEFAULT_DISPLAY_UNIT

    @property
    def timezone(self) -> str:
        return self.settings.timezone if self.settings else DEFAULT_TIMEZONE

    @property
    def permissions(self) -> list[str]:
        if self.is_admin:
            return list(ADMIN_PERMISSIONS)
        return [FINANCE_VIEW, *sorted(self.grants)]

    def can(self, permission: FinancePermissionName) -> bool:
        if self.is_admin:
            return True
        return permission == FINANCE_VIEW or permission in self.grants

    def require(self, permission: FinancePermissionName) -> None:
        if not self.can(permission):
            raise HTTPException(status_code=403, detail="finance_access_denied")

    def require_admin(self) -> None:
        if not self.is_admin:
            raise HTTPException(status_code=403, detail="finance_manage_required")

    def require_enabled(self) -> None:
        if not self.enabled:
            raise HTTPException(status_code=409, detail="finance_disabled")

    def amount_limit(self, permission: FinancePermissionName) -> int | None:
        if self.is_admin:
            return None
        return self.grants.get(permission)


def settings_public(scope: FinanceScope) -> FinanceSettingsPublic:
    return FinanceSettingsPublic(
        enabled=scope.enabled,
        display_unit=scope.display_unit,  # type: ignore[arg-type]
        timezone=scope.timezone,
        can_manage=scope.is_admin,
        can_toggle=scope.is_superuser,
        permissions=scope.permissions,
    )


def ensure_settings(
    session: Session, gym_id: uuid.UUID, actor: User | None = None
) -> FinanceSettings:
    settings = get_finance_settings(session, gym_id)
    if settings is not None:
        return settings
    try:
        with session.begin_nested():
            settings = FinanceSettings(
                gym_id=gym_id,
                enabled=True,
                display_unit=DEFAULT_DISPLAY_UNIT,
                timezone=DEFAULT_TIMEZONE,
                updated_by_id=actor.id if actor else None,
            )
            session.add(settings)
    except IntegrityError:
        # A concurrent first write created the row; the committed row is now
        # visible under READ COMMITTED.
        existing = get_finance_settings(session, gym_id)
        if existing is None:
            raise
        return existing
    return settings


def record_audit(
    session: Session,
    *,
    gym_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    reason: str | None = None,
    detail: dict[str, Any] | None = None,
) -> FinanceAudit:
    entry = FinanceAudit(
        gym_id=gym_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        detail=detail or {},
    )
    session.add(entry)
    return entry

