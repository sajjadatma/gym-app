from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, GymContextDep, SessionDep
from app.core.audit import audit
from app.finance_models import (
    FINANCE_VIEW,
    FinanceAccountPublic,
    FinanceAccountsPublic,
    FinanceGrantRow,
    FinanceGrantsPublic,
    FinanceGrantUpdate,
    FinanceJournalCorrectionCreate,
    FinanceJournalPublic,
    FinanceJournalsPublic,
    FinanceOpeningBalanceCreate,
    FinancePeriodPublic,
    FinancePeriodsPublic,
    FinanceSettingsPublic,
    FinanceSettingsUpdate,
)
from app.services.finance import (
    accounts_public,
    close_period,
    ensure_settings,
    get_journal,
    list_grants,
    list_journals,
    list_periods,
    lock_finance_gym,
    post_correction,
    post_opening_balance,
    record_audit,
    replace_grants,
    resolve_finance_scope,
    settings_public,
    utcnow,
)
from app.services.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/finance", tags=["finance"])

_CONSTRAINT_DETAILS = {
    "uq_finance_journal_opening": "finance_opening_balance_exists",
    "uq_finance_journal_reversal": "finance_already_corrected",
    "uq_finance_operation_key": "idempotency_key_reused",
}


def _idempotency_key(
    key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if key is None or not key.strip():
        raise HTTPException(
            status_code=400, detail="idempotency_key_required"
        )
    value = key.strip()
    if len(value) > 100:
        raise HTTPException(
            status_code=400, detail="invalid_idempotency_key"
        )
    return value


IdempotencyKey = Annotated[str, Depends(_idempotency_key)]


def _commit_conflict(session: SessionDep, exc: IntegrityError) -> HTTPException:
    session.rollback()
    message = str(exc.orig)
    for constraint, detail in _CONSTRAINT_DETAILS.items():
        if constraint in message:
            return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=409, detail="finance_conflict")


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

    # Serialize enable/disable with postings so a disable cannot be overtaken
    # by a posting that resolved the old state.
    lock_finance_gym(session, ctx.gym.id)
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
    return settings_public(resolve_finance_scope(session, ctx, current_user))


@router.get("/accounts", response_model=FinanceAccountsPublic)
def list_finance_accounts(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    rows = accounts_public(session, gym_id=ctx.gym.id)
    return FinanceAccountsPublic(
        data=[
            FinanceAccountPublic(
                id=row.id,
                code=row.code,
                name=row.name,
                type=row.type,  # type: ignore[arg-type]
            )
            for row in rows
        ],
        count=len(rows),
    )


@router.get("/journal", response_model=FinanceJournalsPublic)
def read_finance_journal(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_journals(
        session, gym_id=ctx.gym.id, offset=offset, limit=limit
    )


@router.get("/journal/{journal_id}", response_model=FinanceJournalPublic)
def read_finance_journal_entry(
    *,
    journal_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_journal(session, gym_id=ctx.gym.id, journal_id=journal_id)


@router.post("/opening-balance", response_model=FinanceJournalPublic)
def post_finance_opening_balance(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceOpeningBalanceCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return post_opening_balance(
            session,
            scope=scope,
            actor=current_user,
            body=body,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.post(
    "/journal/{journal_id}/correct", response_model=FinanceJournalPublic
)
def correct_finance_journal(
    *,
    journal_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceJournalCorrectionCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return post_correction(
            session,
            scope=scope,
            actor=current_user,
            journal_id=journal_id,
            reason=body.reason,
            posting_date=body.posting_date,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.get("/grants", response_model=FinanceGrantsPublic)
def read_finance_grants(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require_admin()
    return list_grants(session, gym_id=ctx.gym.id)


@router.put("/grants/{user_id}", response_model=FinanceGrantRow)
def update_finance_grants(
    *,
    user_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceGrantUpdate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    row = replace_grants(
        session,
        scope=scope,
        actor=current_user,
        target_user_id=user_id,
        body=body,
    )
    audit(
        "finance.grants.updated",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=user_id,
        detail=",".join(item.permission for item in body.grants),
    )
    return row


@router.get("/periods", response_model=FinancePeriodsPublic)
def read_finance_periods(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_periods(session, gym_id=ctx.gym.id)


@router.post("/periods/close", response_model=FinancePeriodPublic)
def close_finance_period(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    period = close_period(session, scope=scope, actor=current_user)
    audit(
        "finance.period.closed",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=period.id,
    )
    return period
