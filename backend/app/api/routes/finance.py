from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, GymContextDep, SessionDep
from app.core.audit import audit
from app.finance_models import (
    FINANCE_VIEW,
    FinanceAccountPublic,
    FinanceAccountsPublic,
    FinanceCatalogItemCreate,
    FinanceCatalogItemPublic,
    FinanceCatalogItemUpdate,
    FinanceCatalogPublic,
    FinanceCreditApplyCreate,
    FinanceCreditsPublic,
    FinanceExpenseCreate,
    FinanceExpensePayCreate,
    FinanceExpensePublic,
    FinanceExpenseRepeatCreate,
    FinanceExpensesPublic,
    FinanceGrantRow,
    FinanceGrantsPublic,
    FinanceGrantUpdate,
    FinanceInvoiceCreate,
    FinanceInvoiceIssueCreate,
    FinanceInvoicePublic,
    FinanceInvoicesPublic,
    FinanceInvoiceUpdate,
    FinanceInvoiceVoidCreate,
    FinanceJournalCorrectionCreate,
    FinanceJournalPublic,
    FinanceJournalsPublic,
    FinanceOpeningBalanceCreate,
    FinancePeriodPublic,
    FinancePeriodsPublic,
    FinanceReceiptCreate,
    FinanceReceiptPublic,
    FinanceReceiptsPublic,
    FinanceRefundCreate,
    FinanceRefundPublic,
    FinanceRefundRecordCreate,
    FinanceRefundRejectCreate,
    FinanceRefundsPublic,
    FinanceSettingsPublic,
    FinanceSettingsUpdate,
)
from app.models import Message
from app.services.finance import (
    accounts_public,
    apply_customer_credit,
    approve_refund,
    close_period,
    create_catalog_item,
    create_expense,
    create_invoice,
    create_receipt,
    delete_invoice,
    ensure_settings,
    get_expense,
    get_invoice,
    get_journal,
    get_receipt,
    issue_invoice,
    list_catalog,
    list_credits,
    list_expenses,
    list_grants,
    list_invoices,
    list_journals,
    list_periods,
    list_receipts,
    list_refunds,
    lock_finance_gym,
    pay_expense,
    post_correction,
    post_opening_balance,
    record_audit,
    record_refund,
    reject_refund,
    repeat_expense,
    replace_grants,
    request_refund,
    resolve_finance_scope,
    settings_public,
    update_catalog_item,
    update_invoice,
    utcnow,
    void_invoice,
)
from app.services.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/finance", tags=["finance"])

_CONSTRAINT_DETAILS = {
    "uq_finance_journal_opening": "finance_opening_balance_exists",
    "uq_finance_journal_reversal": "finance_already_corrected",
    "uq_finance_operation_key": "idempotency_key_reused",
}


# Declared required so the generated client and OpenAPI match runtime: a
# missing or empty key is rejected by request validation before any work.
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=100),
]


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


# ---------------------------------------------------------------------------
# Catalog and invoices (Phase 2)
# ---------------------------------------------------------------------------


@router.get("/catalog", response_model=FinanceCatalogPublic)
def read_finance_catalog(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    active_only: bool = False,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_catalog(
        session, gym_id=ctx.gym.id, active_only=active_only
    )


@router.post("/catalog", response_model=FinanceCatalogItemPublic)
def create_finance_catalog_item(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCatalogItemCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return create_catalog_item(
        session, scope=scope, actor=current_user, body=body
    )


@router.patch("/catalog/{item_id}", response_model=FinanceCatalogItemPublic)
def update_finance_catalog_item(
    *,
    item_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCatalogItemUpdate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return update_catalog_item(
        session,
        scope=scope,
        actor=current_user,
        item_id=item_id,
        body=body,
    )


@router.get("/invoices", response_model=FinanceInvoicesPublic)
def read_finance_invoices(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    status: str | None = Query(default=None, max_length=20),
    customer_user_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_invoices(
        session,
        gym_id=ctx.gym.id,
        status=status,
        customer_user_id=customer_user_id,
        offset=offset,
        limit=limit,
    )


@router.post("/invoices", response_model=FinanceInvoicePublic)
def create_finance_invoice(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceInvoiceCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return create_invoice(session, scope=scope, actor=current_user, body=body)


@router.get("/invoices/{invoice_id}", response_model=FinanceInvoicePublic)
def read_finance_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_invoice(session, gym_id=ctx.gym.id, invoice_id=invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=FinanceInvoicePublic)
def update_finance_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceInvoiceUpdate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return update_invoice(
        session,
        scope=scope,
        actor=current_user,
        invoice_id=invoice_id,
        body=body,
    )


@router.delete("/invoices/{invoice_id}", response_model=Message)
def delete_finance_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    delete_invoice(
        session, scope=scope, actor=current_user, invoice_id=invoice_id
    )
    return Message(message="invoice_deleted")


@router.post("/invoices/{invoice_id}/issue", response_model=FinanceInvoicePublic)
def issue_finance_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceInvoiceIssueCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return issue_invoice(
            session,
            scope=scope,
            actor=current_user,
            invoice_id=invoice_id,
            posting_date=body.posting_date,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.post("/invoices/{invoice_id}/void", response_model=FinanceInvoicePublic)
def void_finance_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceInvoiceVoidCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return void_invoice(
            session,
            scope=scope,
            actor=current_user,
            invoice_id=invoice_id,
            reason=body.reason,
            posting_date=body.posting_date,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


# ---------------------------------------------------------------------------
# Manual receipts and customer advances (Phase 2)
# ---------------------------------------------------------------------------


@router.get("/receipts", response_model=FinanceReceiptsPublic)
def read_finance_receipts(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    customer_user_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_receipts(
        session,
        gym_id=ctx.gym.id,
        customer_user_id=customer_user_id,
        offset=offset,
        limit=limit,
    )


@router.post("/receipts", response_model=FinanceReceiptPublic)
def record_finance_receipt(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceReceiptCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return create_receipt(
            session,
            scope=scope,
            actor=current_user,
            body=body,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.get("/receipts/{receipt_id}", response_model=FinanceReceiptPublic)
def read_finance_receipt(
    *,
    receipt_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_receipt(session, gym_id=ctx.gym.id, receipt_id=receipt_id)


@router.get("/credits", response_model=FinanceCreditsPublic)
def read_finance_credits(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_credits(session, gym_id=ctx.gym.id)


@router.post("/credits/apply", response_model=FinanceInvoicePublic)
def apply_finance_credit(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCreditApplyCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return apply_customer_credit(
            session,
            scope=scope,
            actor=current_user,
            body=body,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


# ---------------------------------------------------------------------------
# Refunds and operating expenses (Phase 2)
# ---------------------------------------------------------------------------


@router.get("/refunds", response_model=FinanceRefundsPublic)
def read_finance_refunds(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_refunds(session, gym_id=ctx.gym.id)


@router.post("/refunds", response_model=FinanceRefundPublic)
def request_finance_refund(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceRefundCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return request_refund(
            session,
            scope=scope,
            actor=current_user,
            body=body,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.post("/refunds/{refund_id}/approve", response_model=FinanceRefundPublic)
def approve_finance_refund(
    *,
    refund_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return approve_refund(
        session, scope=scope, actor=current_user, refund_id=refund_id
    )


@router.post("/refunds/{refund_id}/reject", response_model=FinanceRefundPublic)
def reject_finance_refund(
    *,
    refund_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceRefundRejectCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return reject_refund(
        session,
        scope=scope,
        actor=current_user,
        refund_id=refund_id,
        reason=body.reason,
    )


@router.post("/refunds/{refund_id}/record", response_model=FinanceRefundPublic)
def record_finance_refund(
    *,
    refund_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceRefundRecordCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return record_refund(
            session,
            scope=scope,
            actor=current_user,
            refund_id=refund_id,
            posting_date=body.posting_date,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.get("/expenses", response_model=FinanceExpensesPublic)
def read_finance_expenses(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    status: str | None = Query(default=None, max_length=20),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_expenses(
        session,
        gym_id=ctx.gym.id,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.post("/expenses", response_model=FinanceExpensePublic)
def create_finance_expense(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceExpenseCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return create_expense(
            session,
            scope=scope,
            actor=current_user,
            body=body,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.get("/expenses/{expense_id}", response_model=FinanceExpensePublic)
def read_finance_expense(
    *,
    expense_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_expense(session, gym_id=ctx.gym.id, expense_id=expense_id)


@router.post("/expenses/{expense_id}/pay", response_model=FinanceExpensePublic)
def pay_finance_expense(
    *,
    expense_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceExpensePayCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return pay_expense(
            session,
            scope=scope,
            actor=current_user,
            expense_id=expense_id,
            paid_on=body.paid_on,
            method=body.method,
            operation_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.post("/expenses/{expense_id}/repeat", response_model=FinanceExpensePublic)
def repeat_finance_expense(
    *,
    expense_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceExpenseRepeatCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return repeat_expense(
        session,
        scope=scope,
        actor=current_user,
        expense_id=expense_id,
        spent_on=body.spent_on,
    )
