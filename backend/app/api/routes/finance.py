from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import CurrentUser, GymContextDep, SessionDep
from app.core.audit import audit
from app.finance_models import (
    FINANCE_VIEW,
    FinanceAccountPublic,
    FinanceAccountsPublic,
    FinanceBankStatementLineCreate,
    FinanceBankStatementLinePublic,
    FinanceBankStatementLinesPublic,
    FinanceCatalogItemCreate,
    FinanceCatalogItemPublic,
    FinanceCatalogItemUpdate,
    FinanceCatalogPublic,
    FinanceCoachAgreementCreate,
    FinanceCoachAgreementPublic,
    FinanceCoachAgreementsPublic,
    FinanceCoachDiscrepanciesPublic,
    FinanceCoachDiscrepancyPublic,
    FinanceCoachDiscrepancyResolve,
    FinanceCoachEarningPublic,
    FinanceCoachEarningResolve,
    FinanceCoachEarningsPublic,
    FinanceCoachPeriodAccrual,
    FinanceCoachSettlementCancel,
    FinanceCoachSettlementCreate,
    FinanceCoachSettlementPublic,
    FinanceCoachSettlementsPublic,
    FinanceCoachVestingCreate,
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
    FinanceMembershipCancelCreate,
    FinanceMembershipCreate,
    FinanceMembershipFreezeCreate,
    FinanceMembershipPublic,
    FinanceMembershipResumeCreate,
    FinanceMembershipsPublic,
    FinanceMembershipTransferCreate,
    FinanceMyAccountPublic,
    FinanceMyRefundCreate,
    FinanceOpeningBalanceCreate,
    FinancePeriodPublic,
    FinancePeriodsPublic,
    FinanceReceiptCreate,
    FinanceReceiptPublic,
    FinanceReceiptsPublic,
    FinanceReconciliationMatchCreate,
    FinanceRefundCreate,
    FinanceRefundPreview,
    FinanceRefundPublic,
    FinanceRefundRecordCreate,
    FinanceRefundRejectCreate,
    FinanceRefundsPublic,
    FinanceRemindersPublic,
    FinanceSettingsPublic,
    FinanceSettingsUpdate,
)
from app.models import Message
from app.platform_models import (
    PlatformInvoicesPublic,
    PlatformPaymentsPublic,
    PlatformStandingPublic,
)
from app.services.finance import (
    accounts_public,
    accrue_coach_period,
    activate_coach_agreement,
    apply_customer_credit,
    approve_refund,
    cancel_coach_settlement,
    cancel_membership,
    close_period,
    confirm_coach_settlement,
    create_bank_statement_line,
    create_catalog_item,
    create_coach_agreement,
    create_coach_settlement,
    create_expense,
    create_invoice,
    create_membership,
    create_receipt,
    delete_invoice,
    ensure_settings,
    freeze_membership,
    get_coach_agreement,
    get_coach_earning,
    get_coach_settlement,
    get_expense,
    get_invoice,
    get_journal,
    get_membership,
    get_receipt,
    gym_summary,
    issue_invoice,
    list_bank_statement_lines,
    list_catalog,
    list_coach_agreements,
    list_coach_discrepancies,
    list_coach_earnings,
    list_coach_settlements,
    list_credits,
    list_expenses,
    list_grants,
    list_invoices,
    list_journals,
    list_memberships,
    list_periods,
    list_receipts,
    list_refunds,
    list_reminders,
    lock_finance_gym,
    match_bank_statement_line,
    membership_refund_preview,
    my_account,
    pay_expense,
    post_correction,
    post_opening_balance,
    record_audit,
    record_refund,
    reject_refund,
    repeat_expense,
    replace_grants,
    request_my_refund,
    request_refund,
    resolve_coach_discrepancy,
    resolve_coach_earning,
    resolve_finance_scope,
    resume_membership,
    settings_public,
    transfer_membership,
    update_catalog_item,
    update_invoice,
    utcnow,
    vest_coach_earning,
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


# ---------------------------------------------------------------------------
# Paid membership and athlete self-service (Phase 2)
# ---------------------------------------------------------------------------


@router.get("/memberships", response_model=FinanceMembershipsPublic)
def read_finance_memberships(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    athlete_user_id: uuid.UUID | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_memberships(
        session, gym_id=ctx.gym.id, athlete_user_id=athlete_user_id
    )


@router.post("/memberships", response_model=FinanceMembershipPublic)
def create_finance_membership(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMembershipCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    try:
        return create_membership(
            session, scope=scope, actor=current_user, body=body
        )
    except IntegrityError as exc:
        raise _commit_conflict(session, exc) from exc


@router.get(
    "/memberships/{membership_id}", response_model=FinanceMembershipPublic
)
def read_finance_membership(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_membership(
        session, gym_id=ctx.gym.id, membership_id=membership_id
    )


@router.get(
    "/memberships/{membership_id}/refund-preview",
    response_model=FinanceRefundPreview,
)
def read_membership_refund_preview(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    on_date: date = Query(alias="on"),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return membership_refund_preview(
        session, scope=scope, membership_id=membership_id, on_date=on_date
    )


@router.post(
    "/memberships/{membership_id}/freeze", response_model=FinanceMembershipPublic
)
def freeze_finance_membership(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMembershipFreezeCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return freeze_membership(
        session,
        scope=scope,
        actor=current_user,
        membership_id=membership_id,
        frozen_on=body.frozen_on,
    )


@router.post(
    "/memberships/{membership_id}/resume", response_model=FinanceMembershipPublic
)
def resume_finance_membership(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMembershipResumeCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return resume_membership(
        session,
        scope=scope,
        actor=current_user,
        membership_id=membership_id,
        resume_on=body.resume_on,
    )


@router.post(
    "/memberships/{membership_id}/cancel", response_model=FinanceMembershipPublic
)
def cancel_finance_membership(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMembershipCancelCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return cancel_membership(
        session,
        scope=scope,
        actor=current_user,
        membership_id=membership_id,
        cancelled_on=body.cancelled_on,
        reason=body.reason,
    )


@router.post(
    "/memberships/{membership_id}/transfer",
    response_model=FinanceMembershipPublic,
)
def transfer_finance_membership(
    *,
    membership_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMembershipTransferCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return transfer_membership(
        session,
        scope=scope,
        actor=current_user,
        membership_id=membership_id,
        athlete_user_id=body.athlete_user_id,
    )


@router.get("/my/account", response_model=FinanceMyAccountPublic)
def read_my_finance_account(
    *, session: SessionDep, ctx: GymContextDep, current_user: CurrentUser
) -> Any:
    return my_account(session, gym_id=ctx.gym.id, user=current_user)


@router.post("/my/refunds", response_model=FinanceRefundPublic)
def request_my_finance_refund(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceMyRefundCreate,
) -> Any:
    return request_my_refund(
        session, gym_id=ctx.gym.id, user=current_user, body=body
    )


@router.get("/reminders", response_model=FinanceRemindersPublic)
def read_finance_reminders(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    within_days: int = Query(default=7, ge=0, le=90),
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_reminders(session, gym_id=ctx.gym.id, within_days=within_days)


@router.get("/coach-agreements", response_model=FinanceCoachAgreementsPublic)
def read_coach_agreements(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    coach_user_id: uuid.UUID | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_coach_agreements(
        session, gym_id=ctx.gym.id, coach_user_id=coach_user_id
    )


@router.post("/coach-agreements", response_model=FinanceCoachAgreementPublic)
def create_finance_coach_agreement(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachAgreementCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return create_coach_agreement(
        session, scope=scope, actor=current_user, body=body
    )


@router.get(
    "/coach-agreements/{agreement_id}",
    response_model=FinanceCoachAgreementPublic,
)
def read_coach_agreement(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_coach_agreement(
        session, gym_id=ctx.gym.id, agreement_id=agreement_id
    )


@router.post(
    "/coach-agreements/{agreement_id}/activate",
    response_model=FinanceCoachAgreementPublic,
)
def activate_finance_coach_agreement(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return activate_coach_agreement(
        session, scope=scope, actor=current_user, agreement_id=agreement_id
    )


@router.get("/coach-earnings", response_model=FinanceCoachEarningsPublic)
def read_coach_earnings(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    coach_user_id: uuid.UUID | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_coach_earnings(
        session, gym_id=ctx.gym.id, coach_user_id=coach_user_id
    )


@router.get("/coach-earnings/{earning_id}", response_model=FinanceCoachEarningPublic)
def read_coach_earning(
    *,
    earning_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_coach_earning(
        session, gym_id=ctx.gym.id, earning_id=earning_id
    )


@router.post(
    "/coach-earnings/{earning_id}/vest",
    response_model=FinanceCoachEarningPublic,
)
def vest_finance_coach_earning(
    *,
    earning_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachVestingCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return vest_coach_earning(
        session, scope=scope, actor=current_user, earning_id=earning_id, body=body
    )


@router.get("/my/earnings", response_model=FinanceCoachEarningsPublic)
def read_my_coach_earnings(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    if not ctx.is_coach:
        raise HTTPException(status_code=403, detail="coach_access_required")
    return list_coach_earnings(
        session, gym_id=ctx.gym.id, coach_user_id=current_user.id
    )


@router.post(
    "/coach-settlements", response_model=FinanceCoachSettlementPublic
)
def create_finance_coach_settlement(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachSettlementCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return create_coach_settlement(
        session,
        scope=scope,
        actor=current_user,
        body=body,
        operation_key=idempotency_key,
    )


@router.get(
    "/coach-settlements", response_model=FinanceCoachSettlementsPublic
)
def read_coach_settlements(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    coach_user_id: uuid.UUID | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_coach_settlements(
        session, gym_id=ctx.gym.id, coach_user_id=coach_user_id
    )


@router.get(
    "/coach-settlements/{settlement_id}",
    response_model=FinanceCoachSettlementPublic,
)
def read_coach_settlement(
    *,
    settlement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return get_coach_settlement(
        session, gym_id=ctx.gym.id, settlement_id=settlement_id
    )


@router.post(
    "/coach-settlements/{settlement_id}/confirm",
    response_model=FinanceCoachSettlementPublic,
)
def confirm_finance_coach_settlement(
    *,
    settlement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return confirm_coach_settlement(
        session, scope=scope, actor=current_user, settlement_id=settlement_id
    )


@router.get("/my/settlements", response_model=FinanceCoachSettlementsPublic)
def read_my_coach_settlements(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    if not ctx.is_coach:
        raise HTTPException(status_code=403, detail="coach_access_required")
    return list_coach_settlements(
        session, gym_id=ctx.gym.id, coach_user_id=current_user.id
    )


@router.get(
    "/coach-discrepancies", response_model=FinanceCoachDiscrepanciesPublic
)
def read_coach_discrepancies(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    status: str | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_coach_discrepancies(session, gym_id=ctx.gym.id, status=status)


@router.post(
    "/coach-discrepancies/{discrepancy_id}/resolve",
    response_model=FinanceCoachDiscrepancyPublic,
)
def resolve_finance_coach_discrepancy(
    *,
    discrepancy_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachDiscrepancyResolve,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return resolve_coach_discrepancy(
        session,
        scope=scope,
        actor=current_user,
        discrepancy_id=discrepancy_id,
        body=body,
    )


@router.post(
    "/coach-earnings/{earning_id}/resolve",
    response_model=FinanceCoachEarningPublic,
)
def resolve_finance_coach_earning(
    *,
    earning_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachEarningResolve,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return resolve_coach_earning(
        session,
        scope=scope,
        actor=current_user,
        earning_id=earning_id,
        body=body,
    )


@router.post(
    "/coach-agreements/{agreement_id}/accrue-period",
    response_model=FinanceExpensePublic,
)
def accrue_finance_coach_period(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachPeriodAccrual,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return accrue_coach_period(
        session,
        scope=scope,
        actor=current_user,
        agreement_id=agreement_id,
        body=body,
        operation_key=idempotency_key,
    )


@router.get(
    "/reconciliation", response_model=FinanceBankStatementLinesPublic
)
def read_finance_reconciliation(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    status: str | None = None,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return list_bank_statement_lines(
        session, gym_id=ctx.gym.id, status=status
    )


@router.post(
    "/reconciliation", response_model=FinanceBankStatementLinePublic
)
def create_finance_reconciliation_line(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceBankStatementLineCreate,
    idempotency_key: IdempotencyKey,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return create_bank_statement_line(
        session,
        scope=scope,
        actor=current_user,
        body=body,
        operation_key=idempotency_key,
    )


@router.post(
    "/reconciliation/{line_id}/match",
    response_model=FinanceBankStatementLinePublic,
)
def match_finance_reconciliation_line(
    *,
    line_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceReconciliationMatchCreate,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return match_bank_statement_line(
        session,
        scope=scope,
        actor=current_user,
        line_id=line_id,
        body=body,
    )


@router.post(
    "/coach-settlements/{settlement_id}/cancel",
    response_model=FinanceCoachSettlementPublic,
)
def cancel_finance_coach_settlement(
    *,
    settlement_id: uuid.UUID,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    body: FinanceCoachSettlementCancel,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    return cancel_coach_settlement(
        session, scope=scope, actor=current_user, settlement_id=settlement_id, body=body
    )


@router.get("/platform/invoices", response_model=PlatformInvoicesPublic)
def read_my_gym_platform_invoices(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    from app.services import platform as platform_service

    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return platform_service.list_platform_invoices(session, gym_id=ctx.gym.id)


@router.get("/platform/dues", response_model=PlatformStandingPublic)
def read_my_gym_platform_dues(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    from app.services import platform as platform_service

    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return platform_service.platform_standing(session, gym_id=ctx.gym.id)


@router.get("/platform/payments", response_model=PlatformPaymentsPublic)
def read_my_gym_platform_payments(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    from app.services import platform as platform_service

    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return platform_service.list_platform_payments(session, gym_id=ctx.gym.id)


def _csv_response(rows: list[list[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="finance.csv"'},
    )


def _gym_report_rows(
    session: Any,
    *,
    gym_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> list[list[Any]]:
    from app.finance_models import (
        FinanceCoachEarning,
        FinanceCoachSettlement,
        FinanceExpense,
        FinanceInvoice,
        FinanceReceipt,
        FinanceRefund,
    )
    from app.platform_models import PlatformInvoiceLine

    rows: list[list[Any]] = [
        ["metric_family", "row_type", "reference", "date", "amount_irr", "status"]
    ]
    summary = gym_summary(
        session, gym_id=gym_id, from_date=from_date, to_date=to_date
    )
    for field in (
        "cash_collected_irr",
        "cash_refunded_irr",
        "cash_expenses_paid_irr",
        "cash_coach_settlements_irr",
        "net_cashflow_irr",
        "sales_irr",
        "receivable_irr",
        "overdue_irr",
        "coach_payable_irr",
        "platform_payable_irr",
        "recognized_revenue_irr",
        "recognized_expenses_irr",
        "estimated_operating_profit_irr",
    ):
        family = (
            "ACCRUAL"
            if field
            in {
                "recognized_revenue_irr",
                "recognized_expenses_irr",
                "estimated_operating_profit_irr",
            }
            else "BALANCE"
            if field
            in {
                "receivable_irr",
                "overdue_irr",
                "coach_payable_irr",
                "platform_payable_irr",
            }
            else "BILLING"
            if field == "sales_irr"
            else "CASHFLOW"
        )
        rows.append([family, "summary", field, "", getattr(summary, field), ""])

    for invoice in session.exec(
        select(FinanceInvoice).where(FinanceInvoice.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "BILLING",
                "invoice",
                str(invoice.invoice_number or ""),
                invoice.issue_date.isoformat() if invoice.issue_date else "",
                invoice.total_irr,
                invoice.status,
            ]
        )
    for receipt in session.exec(
        select(FinanceReceipt).where(FinanceReceipt.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "CASHFLOW",
                "receipt",
                str(receipt.receipt_number),
                receipt.received_on.isoformat(),
                receipt.amount_irr,
                receipt.status,
            ]
        )
    for refund in session.exec(
        select(FinanceRefund).where(FinanceRefund.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "CASHFLOW",
                "refund",
                str(refund.id),
                refund.created_at.date().isoformat(),
                refund.amount_irr,
                refund.status,
            ]
        )
    for expense in session.exec(
        select(FinanceExpense).where(FinanceExpense.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "CASHFLOW" if expense.status == "PAID" else "ACCRUAL",
                "expense",
                str(expense.id),
                expense.spent_on.isoformat(),
                expense.amount_irr,
                expense.status,
            ]
        )
    for earning in session.exec(
        select(FinanceCoachEarning).where(FinanceCoachEarning.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "ACCRUAL",
                "coach_earning",
                str(earning.id),
                earning.created_at.date().isoformat(),
                earning.coach_share_irr,
                earning.status,
            ]
        )
    for settlement in session.exec(
        select(FinanceCoachSettlement).where(
            FinanceCoachSettlement.gym_id == gym_id
        )
    ).all():
        rows.append(
            [
                "CASHFLOW" if settlement.status == "CONFIRMED" else "BALANCE",
                "coach_settlement",
                str(settlement.id),
                settlement.paid_on.isoformat(),
                settlement.amount_irr,
                settlement.status,
            ]
        )
    for line in session.exec(
        select(PlatformInvoiceLine).where(PlatformInvoiceLine.gym_id == gym_id)
    ).all():
        rows.append(
            [
                "BALANCE",
                "platform_invoice_line",
                line.source_key,
                "",
                line.amount_irr,
                "PAID" if line.paid_irr >= line.amount_irr else "OPEN",
            ]
        )
    return rows


@router.get("/reports/summary")
def read_gym_summary(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    from_date: date,
    to_date: date,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return gym_summary(
        session, gym_id=ctx.gym.id, from_date=from_date, to_date=to_date
    )


@router.get("/reports/export")
def export_gym_report(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
    from_date: date,
    to_date: date,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return _csv_response(
        _gym_report_rows(
            session, gym_id=ctx.gym.id, from_date=from_date, to_date=to_date
        )
    )


@router.get("/reports/offboarding-export")
def export_gym_offboarding(
    *,
    session: SessionDep,
    ctx: GymContextDep,
    current_user: CurrentUser,
) -> Any:
    scope = resolve_finance_scope(session, ctx, current_user)
    scope.require(FINANCE_VIEW)
    return _csv_response(
        _gym_report_rows(
            session,
            gym_id=ctx.gym.id,
            from_date=date(2000, 1, 1),
            to_date=date.today(),
        )
    )
