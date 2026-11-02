from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, GymContextDep, SessionDep
from app.core.audit import audit
from app.finance_models import FinanceSettingsPublic, FinanceSettingsUpdate
from app.services.finance import (
    ensure_settings,
    record_audit,
    resolve_finance_scope,
    settings_public,
    utcnow,
)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/settings", response_model=FinanceSettingsPublic)
def read_finance_settings(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return settings_public(scope)


@router.patch("/settings", response_model=FinanceSettingsPublic)
def update_finance_settings(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceSettingsUpdate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    if "enabled" in data and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="superuser_required")
    if "display_unit" in data and not scope.is_admin:
        raise HTTPException(status_code=403, detail="finance_manage_required")
    if not data:
        return settings_public(scope)

    settings = ensure_settings(session, ctx.gym.id, current_user)
    changes: dict[str, Any] = {}
    if "enabled" in data:
        changes["enabled"] = {"from": settings.enabled, "to": bool(data["enabled"])}
        settings.enabled = bool(data["enabled"])
    if "display_unit" in data:
        changes["display_unit"] = {
            "from": settings.display_unit,
            "to": data["display_unit"],
        }
        settings.display_unit = str(data["display_unit"])
    settings.updated_by_id = current_user.id
    settings.updated_at = utcnow()
    session.add(settings)
    record_audit(
        session,
        gym_id=ctx.gym.id,
        actor_id=current_user.id,
        action="finance.settings.updated",
        target_type="finance_settings",
        target_id=settings.id,
        detail={"changes": changes},
    )
    session.commit()
    session.refresh(settings)
    audit(
        "finance.settings.updated",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=settings.id,
        detail=",".join(sorted(changes)),
    )
    return settings_public(
        resolve_finance_scope(session, ctx, current_user)
    )
