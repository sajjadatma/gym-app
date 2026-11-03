from __future__ import annotations

import calendar
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.deps import GymContext
from app.core.audit import audit
from app.finance_models import (
    FINANCE_CATALOG_MANAGE,
    FINANCE_COACH_AGREEMENT_MANAGE,
    FINANCE_EXPENSE_MANAGE,
    FINANCE_INVOICE_MANAGE,
    FINANCE_MEMBERSHIP_MANAGE,
    FINANCE_OPENING_MANAGE,
    FINANCE_PAYMENT_RECORD,
    FINANCE_PERIOD_MANAGE,
    FINANCE_REFUND_MANAGE,
    FINANCE_SETTLEMENT_MANAGE,
    FINANCE_VIEW,
    FinanceAccount,
    FinanceAudit,
    FinanceBankStatementLine,
    FinanceBankStatementLineCreate,
    FinanceBankStatementLinePublic,
    FinanceBankStatementLinesPublic,
    FinanceCatalogItem,
    FinanceCatalogItemCreate,
    FinanceCatalogItemPublic,
    FinanceCatalogItemUpdate,
    FinanceCatalogPublic,
    FinanceCoachAgreement,
    FinanceCoachAgreementCreate,
    FinanceCoachAgreementPublic,
    FinanceCoachAgreementsPublic,
    FinanceCoachAgreementTerm,
    FinanceCoachAgreementTermPublic,
    FinanceCoachDiscrepanciesPublic,
    FinanceCoachDiscrepancy,
    FinanceCoachDiscrepancyPublic,
    FinanceCoachDiscrepancyResolve,
    FinanceCoachEarning,
    FinanceCoachEarningAdjustment,
    FinanceCoachEarningPublic,
    FinanceCoachEarningResolve,
    FinanceCoachEarningsPublic,
    FinanceCoachPeriodAccrual,
    FinanceCoachSettlement,
    FinanceCoachSettlementCancel,
    FinanceCoachSettlementCreate,
    FinanceCoachSettlementItem,
    FinanceCoachSettlementItemPublic,
    FinanceCoachSettlementPublic,
    FinanceCoachSettlementsPublic,
    FinanceCoachVestingCreate,
    FinanceCreditApplyCreate,
    FinanceCreditMovement,
    FinanceCreditPublic,
    FinanceCreditsPublic,
    FinanceCustomerCredit,
    FinanceExpense,
    FinanceExpenseCreate,
    FinanceExpensePublic,
    FinanceExpensesPublic,
    FinanceGrant,
    FinanceGrantItem,
    FinanceGrantRow,
    FinanceGrantsPublic,
    FinanceGrantUpdate,
    FinanceInstallment,
    FinanceInstallmentPublic,
    FinanceInstallmentReminder,
    FinanceInvoice,
    FinanceInvoiceCreate,
    FinanceInvoiceLine,
    FinanceInvoiceLinePublic,
    FinanceInvoicePublic,
    FinanceInvoicesPublic,
    FinanceInvoiceUpdate,
    FinanceJournal,
    FinanceJournalLine,
    FinanceJournalLinePublic,
    FinanceJournalPublic,
    FinanceJournalsPublic,
    FinanceMembership,
    FinanceMembershipCreate,
    FinanceMembershipPublic,
    FinanceMembershipsPublic,
    FinanceMyAccountPublic,
    FinanceMyRefundCreate,
    FinanceOpeningBalanceCreate,
    FinanceOperation,
    FinancePeriod,
    FinancePeriodPublic,
    FinancePeriodsPublic,
    FinancePermissionName,
    FinanceReceipt,
    FinanceReceiptAllocation,
    FinanceReceiptAllocationPublic,
    FinanceReceiptCreate,
    FinanceReceiptPublic,
    FinanceReceiptsPublic,
    FinanceReconciliationMatchCreate,
    FinanceRefund,
    FinanceRefundCreate,
    FinanceRefundPreview,
    FinanceRefundPublic,
    FinanceRefundsPublic,
    FinanceRemindersPublic,
    FinanceRenewalReminder,
    FinanceSequence,
    FinanceSettings,
    FinanceSettingsPublic,
    GrantableFinancePermission,
)
from app.models import (
    AthleteProfile,
    Gym,
    GymMembership,
    GymMembershipRole,
    User,
)

ADMIN_PERMISSIONS: tuple[FinancePermissionName, ...] = (
    FINANCE_VIEW,
    FINANCE_OPENING_MANAGE,
    FINANCE_EXPENSE_MANAGE,
    FINANCE_MEMBERSHIP_MANAGE,
    FINANCE_PAYMENT_RECORD,
    FINANCE_PERIOD_MANAGE,
    FINANCE_REFUND_MANAGE,
    FINANCE_CATALOG_MANAGE,
    FINANCE_COACH_AGREEMENT_MANAGE,
    FINANCE_INVOICE_MANAGE,
    FINANCE_SETTLEMENT_MANAGE,
)

DEFAULT_DISPLAY_UNIT = "RIAL"
DEFAULT_TIMEZONE = "Asia/Tehran"
JOURNAL_DOC_TYPE = "JOURNAL"

# Minimal chart of accounts used by the opening-balance workflow. Phase 2
# posts invoices, receipts and expenses through the same accounts.
DEFAULT_ACCOUNTS: tuple[tuple[str, str, str], ...] = (
    ("1000", "نقد و بانک", "ASSET"),
    ("1100", "مطالبات", "ASSET"),
    ("2000", "بدهی‌ها", "LIABILITY"),
    ("2100", "بدهی به مربیان", "LIABILITY"),
    ("2200", "تسویه‌های در انتظار", "LIABILITY"),
    ("3000", "سرمایه افتتاحیه", "EQUITY"),
    ("4000", "درآمد", "INCOME"),
    ("4100", "برگشت از فروش", "INCOME"),
    ("5000", "هزینه‌ها", "EXPENSE"),
    ("5100", "حق‌الزحمه مربیان", "EXPENSE"),
)


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Settings and access
# ---------------------------------------------------------------------------


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


def _grants_for(
    session: Session, gym_id: uuid.UUID, user_id: uuid.UUID
) -> dict[FinancePermissionName, int | None]:
    rows = session.exec(
        select(FinanceGrant).where(
            FinanceGrant.gym_id == gym_id,
            FinanceGrant.user_id == user_id,
            col(FinanceGrant.revoked_at).is_(None),
        )
    ).all()
    return {
        cast(FinancePermissionName, row.permission): row.amount_limit_irr
        for row in rows
    }


def resolve_finance_scope(
    session: Session, ctx: GymContext, current_user: User
) -> FinanceScope:
    settings = get_finance_settings(session, ctx.gym.id)
    if current_user.is_superuser or ctx.is_admin:
        return FinanceScope(
            gym_id=ctx.gym.id,
            user_id=current_user.id,
            settings=settings,
            is_admin=True,
            is_superuser=current_user.is_superuser,
            grants={},
        )
    if "FINANCE_STAFF" in ctx.roles:
        return FinanceScope(
            gym_id=ctx.gym.id,
            user_id=current_user.id,
            settings=settings,
            is_admin=False,
            is_superuser=False,
            grants=_grants_for(session, ctx.gym.id, current_user.id),
        )
    raise HTTPException(status_code=403, detail="finance_access_denied")


@dataclass(frozen=True)
class FinanceScope:
    gym_id: uuid.UUID
    user_id: uuid.UUID
    settings: FinanceSettings | None
    is_admin: bool
    is_superuser: bool
    grants: dict[FinancePermissionName, int | None]

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
            return [str(permission) for permission in ADMIN_PERMISSIONS]
        return [str(FINANCE_VIEW), *sorted(self.grants)]

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


def reload_finance_scope(session: Session, scope: FinanceScope) -> FinanceScope:
    """Re-read finance controls after taking the per-gym write lock.

    Settings and grants are changed outside that lock, so a posting must not
    trust a scope resolved before it acquired the lock.
    """
    grants = (
        {}
        if scope.is_admin
        else _grants_for(session, scope.gym_id, scope.user_id)
    )
    return replace(
        scope,
        settings=get_finance_settings(session, scope.gym_id),
        grants=grants,
    )


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


# ---------------------------------------------------------------------------
# Chart of accounts, periods and numbering
# ---------------------------------------------------------------------------


def ensure_accounts(
    session: Session, gym_id: uuid.UUID
) -> dict[str, FinanceAccount]:
    rows = session.exec(
        select(FinanceAccount).where(FinanceAccount.gym_id == gym_id)
    ).all()
    by_code = {row.code: row for row in rows}
    missing = [
        (code, name, kind)
        for code, name, kind in DEFAULT_ACCOUNTS
        if code not in by_code
    ]
    if missing:
        now = utcnow()
        session.execute(
            pg_insert(FinanceAccount.__table__)  # type: ignore[attr-defined]
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "gym_id": gym_id,
                        "code": code,
                        "name": name,
                        "type": kind,
                        "created_at": now,
                    }
                    for code, name, kind in missing
                ]
            )
            .on_conflict_do_nothing()
        )
        session.flush()
        rows = session.exec(
            select(FinanceAccount).where(FinanceAccount.gym_id == gym_id)
        ).all()
        by_code = {row.code: row for row in rows}
    return by_code


def lock_finance_gym(session: Session, gym_id: uuid.UUID) -> None:
    """Serialize finance writes for one gym for the current transaction."""
    session.connection().execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"finance:{gym_id}"},
    )


def get_open_period(session: Session, gym_id: uuid.UUID) -> FinancePeriod | None:
    return session.exec(
        select(FinancePeriod).where(
            FinancePeriod.gym_id == gym_id,
            col(FinancePeriod.closed_at).is_(None),
        )
    ).first()


def ensure_open_period(session: Session, gym_id: uuid.UUID) -> FinancePeriod:
    period = get_open_period(session, gym_id)
    if period is not None:
        return period
    period = FinancePeriod(gym_id=gym_id, opened_at=utcnow())
    session.add(period)
    session.flush()
    return period


def allocate_document_number(
    session: Session, gym_id: uuid.UUID, doc_type: str
) -> int:
    """Allocate the next per-gym document number.

    Callers must hold ``lock_finance_gym`` so two concurrent writers cannot
    read the same last value.
    """
    sequence = session.exec(
        select(FinanceSequence).where(
            FinanceSequence.gym_id == gym_id,
            FinanceSequence.doc_type == doc_type,
        )
    ).first()
    if sequence is None:
        sequence = FinanceSequence(
            gym_id=gym_id, doc_type=doc_type, last_value=0
        )
        session.add(sequence)
        session.flush()
    sequence.last_value += 1
    session.add(sequence)
    session.flush()
    return sequence.last_value


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


def post_journal(
    session: Session,
    *,
    gym_id: uuid.UUID,
    posting_date: date,
    event_type: str,
    description: str | None,
    lines: list[tuple[uuid.UUID, int, int, str | None]],
    created_by_id: uuid.UUID | None,
    reversal_of_id: uuid.UUID | None = None,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
) -> FinanceJournal:
    lock_finance_gym(session, gym_id)
    total_debit = sum(line[1] for line in lines)
    total_credit = sum(line[2] for line in lines)
    if total_debit != total_credit or total_debit <= 0:
        raise HTTPException(status_code=400, detail="finance_unbalanced_journal")
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="finance_unbalanced_journal")
    account_ids = {line[0] for line in lines}
    owned = set(
        session.exec(
            select(FinanceAccount.id).where(
                FinanceAccount.gym_id == gym_id,
                col(FinanceAccount.id).in_(account_ids),
            )
        ).all()
    )
    if owned != account_ids:
        raise HTTPException(status_code=400, detail="invalid_finance_account")

    period = ensure_open_period(session, gym_id)
    journal = FinanceJournal(
        gym_id=gym_id,
        period_id=period.id,
        entry_number=allocate_document_number(
            session, gym_id, JOURNAL_DOC_TYPE
        ),
        posting_date=posting_date,
        event_type=event_type,
        description=description,
        reversal_of_id=reversal_of_id,
        source_type=source_type,
        source_id=source_id,
        created_by_id=created_by_id,
    )
    session.add(journal)
    session.flush()
    for account_id, debit, credit, memo in lines:
        session.add(
            FinanceJournalLine(
                journal_id=journal.id,
                account_id=account_id,
                debit_irr=debit,
                credit_irr=credit,
                memo=memo,
            )
        )
    session.flush()
    return journal


def _request_hash(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def find_operation(
    session: Session, *, gym_id: uuid.UUID, operation_key: str, payload: dict[str, Any]
) -> FinanceOperation | None:
    operation = session.exec(
        select(FinanceOperation).where(
            FinanceOperation.gym_id == gym_id,
            FinanceOperation.operation_key == operation_key,
        )
    ).first()
    if operation is None:
        return None
    if operation.request_hash != _request_hash(payload):
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    return operation


def remember_operation(
    session: Session,
    *,
    gym_id: uuid.UUID,
    operation_key: str,
    payload: dict[str, Any],
    result_type: str,
    result_id: uuid.UUID,
) -> None:
    session.add(
        FinanceOperation(
            gym_id=gym_id,
            operation_key=operation_key,
            request_hash=_request_hash(payload),
            result_type=result_type,
            result_id=result_id,
        )
    )


def _replay(
    session: Session, *, gym_id: uuid.UUID, operation_key: str, payload: dict[str, Any]
) -> FinanceJournal | None:
    operation = find_operation(
        session, gym_id=gym_id, operation_key=operation_key, payload=payload
    )
    if operation is None:
        return None
    journal = session.get(FinanceJournal, operation.result_id)
    if journal is None or journal.gym_id != gym_id:
        raise HTTPException(status_code=409, detail="idempotency_key_reused")
    return journal


def _remember(
    session: Session,
    *,
    gym_id: uuid.UUID,
    operation_key: str,
    payload: dict[str, Any],
    journal: FinanceJournal,
) -> None:
    remember_operation(
        session,
        gym_id=gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_journal",
        result_id=journal.id,
    )


def active_opening_balance(
    session: Session, gym_id: uuid.UUID
) -> FinanceJournal | None:
    """The latest opening journal that has not been reversed."""
    openings = session.exec(
        select(FinanceJournal)
        .where(
            FinanceJournal.gym_id == gym_id,
            FinanceJournal.event_type == "OPENING_BALANCE",
        )
        .order_by(col(FinanceJournal.entry_number).desc())
    ).all()
    for opening in openings:
        reversal = session.exec(
            select(FinanceJournal.id).where(
                FinanceJournal.reversal_of_id == opening.id
            )
        ).first()
        if reversal is None:
            return opening
    return None


def post_opening_balance(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceOpeningBalanceCreate,
    operation_key: str,
) -> FinanceJournalPublic:
    scope.require(FINANCE_OPENING_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_OPENING_MANAGE)
    payload = body.model_dump(mode="json")
    replay = _replay(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if replay is not None:
        return journal_public(session, replay)

    existing = active_opening_balance(session, scope.gym_id)
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="finance_opening_balance_exists"
        )

    accounts = ensure_accounts(session, scope.gym_id)
    lines: list[tuple[uuid.UUID, int, int, str | None]] = []
    total_debit = 0
    for item in body.lines:
        account = accounts.get(item.account_code)
        if account is None:
            raise HTTPException(status_code=400, detail="invalid_finance_account")
        total_debit += item.debit_irr
        lines.append((account.id, item.debit_irr, item.credit_irr, item.memo))

    limit = scope.amount_limit(FINANCE_OPENING_MANAGE)
    if limit is not None and total_debit > limit:
        raise HTTPException(
            status_code=403, detail="finance_amount_limit_exceeded"
        )

    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=body.posting_date,
        event_type="OPENING_BALANCE",
        description=body.description,
        lines=lines,
        created_by_id=actor.id,
    )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.opening_balance.posted",
        target_type="finance_journal",
        target_id=journal.id,
        detail={
            "entry_number": journal.entry_number,
            "total_debit_irr": total_debit,
            "posting_date": body.posting_date.isoformat(),
        },
    )
    audit(
        "finance.opening_balance.posted",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=journal.id,
        detail=f"entry={journal.entry_number}",
    )
    _remember(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        journal=journal,
    )
    session.commit()
    session.refresh(journal)
    return journal_public(session, journal)


def post_correction(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    journal_id: uuid.UUID,
    reason: str,
    posting_date: date,
    operation_key: str,
) -> FinanceJournalPublic:
    if not actor.is_superuser:
        raise HTTPException(status_code=403, detail="superuser_required")
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    payload = {
        "journal_id": str(journal_id),
        "reason": reason,
        "posting_date": posting_date.isoformat(),
    }
    replay = _replay(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if replay is not None:
        return journal_public(session, replay)

    journal = session.get(FinanceJournal, journal_id)
    if journal is None or journal.gym_id != scope.gym_id:
        raise HTTPException(
            status_code=404, detail="finance_journal_not_found"
        )
    if journal.event_type != "OPENING_BALANCE" or journal.reversal_of_id:
        raise HTTPException(
            status_code=400, detail="finance_journal_not_correctable"
        )
    already = session.exec(
        select(FinanceJournal).where(FinanceJournal.reversal_of_id == journal.id)
    ).first()
    if already is not None:
        raise HTTPException(
            status_code=409, detail="finance_already_corrected"
        )

    original_lines = session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == journal.id
        )
    ).all()
    lines = [
        (line.account_id, line.credit_irr, line.debit_irr, line.memo)
        for line in original_lines
    ]
    reversal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=posting_date,
        event_type="CORRECTION",
        description=reason,
        lines=lines,
        created_by_id=actor.id,
        reversal_of_id=journal.id,
    )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.journal.corrected",
        target_type="finance_journal",
        target_id=reversal.id,
        reason=reason,
        detail={
            "entry_number": reversal.entry_number,
            "reversal_of_id": str(journal.id),
            "reversed_entry_number": journal.entry_number,
        },
    )
    audit(
        "finance.journal.corrected",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=reversal.id,
        detail=str(journal.id),
    )
    _remember(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        journal=reversal,
    )
    session.commit()
    session.refresh(reversal)
    return journal_public(session, reversal)


def close_period(
    session: Session, *, scope: FinanceScope, actor: User
) -> FinancePeriodPublic:
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_PERIOD_MANAGE)
    period = get_open_period(session, scope.gym_id)
    if period is None:
        raise HTTPException(status_code=409, detail="finance_no_open_period")
    period.closed_at = utcnow()
    period.closed_by_id = actor.id
    session.add(period)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.period.closed",
        target_type="finance_period",
        target_id=period.id,
        detail={"opened_at": period.opened_at.isoformat()},
    )
    session.commit()
    session.refresh(period)
    return period_public(period)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def journal_public(
    session: Session, journal: FinanceJournal
) -> FinanceJournalPublic:
    rows = session.exec(
        select(FinanceJournalLine, FinanceAccount)
        .join(
            FinanceAccount,
            col(FinanceAccount.id) == col(FinanceJournalLine.account_id),
        )
        .where(FinanceJournalLine.journal_id == journal.id)
        .order_by(col(FinanceAccount.code))
    ).all()
    creator = session.get(User, journal.created_by_id) if journal.created_by_id else None
    return FinanceJournalPublic(
        id=journal.id,
        entry_number=journal.entry_number,
        posting_date=journal.posting_date,
        event_type=journal.event_type,  # type: ignore[arg-type]
        description=journal.description,
        reversal_of_id=journal.reversal_of_id,
        source_type=journal.source_type,
        source_id=journal.source_id,
        period_id=journal.period_id,
        created_by_id=journal.created_by_id,
        created_by_name=(creator.full_name or creator.email) if creator else None,
        created_at=journal.created_at,
        lines=[
            FinanceJournalLinePublic(
                id=line.id,
                account_code=account.code,
                account_name=account.name,
                debit_irr=line.debit_irr,
                credit_irr=line.credit_irr,
                memo=line.memo,
            )
            for line, account in rows
        ],
    )


def list_journals(
    session: Session, *, gym_id: uuid.UUID, offset: int, limit: int
) -> FinanceJournalsPublic:
    total = session.exec(
        select(func.count(col(FinanceJournal.id))).where(
            FinanceJournal.gym_id == gym_id
        )
    ).one()
    journals = session.exec(
        select(FinanceJournal)
        .where(FinanceJournal.gym_id == gym_id)
        .order_by(col(FinanceJournal.entry_number).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return FinanceJournalsPublic(
        data=[journal_public(session, journal) for journal in journals],
        count=int(total),
    )


def get_journal(
    session: Session, *, gym_id: uuid.UUID, journal_id: uuid.UUID
) -> FinanceJournalPublic:
    journal = session.get(FinanceJournal, journal_id)
    if journal is None or journal.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="finance_journal_not_found")
    return journal_public(session, journal)


def accounts_public(
    session: Session, *, gym_id: uuid.UUID
) -> list[FinanceAccount]:
    return list(
        session.exec(
            select(FinanceAccount)
            .where(FinanceAccount.gym_id == gym_id)
            .order_by(col(FinanceAccount.code))
        ).all()
    )


def period_public(period: FinancePeriod) -> FinancePeriodPublic:
    return FinancePeriodPublic(
        id=period.id,
        opened_at=period.opened_at,
        closed_at=period.closed_at,
        status="CLOSED" if period.closed_at else "OPEN",
    )


def list_periods(session: Session, *, gym_id: uuid.UUID) -> FinancePeriodsPublic:
    periods = session.exec(
        select(FinancePeriod)
        .where(FinancePeriod.gym_id == gym_id)
        .order_by(col(FinancePeriod.opened_at).desc())
    ).all()
    return FinancePeriodsPublic(
        data=[period_public(period) for period in periods],
        count=len(periods),
    )


# ---------------------------------------------------------------------------
# Finance staff action grants
# ---------------------------------------------------------------------------


def active_finance_staff(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    from app.models import GymMembership, GymMembershipRole

    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == user_id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if membership is None:
        return False
    role = session.exec(
        select(GymMembershipRole).where(
            GymMembershipRole.membership_id == membership.id,
            GymMembershipRole.role == "FINANCE_STAFF",
        )
    ).first()
    return role is not None


def _active_grant_rows(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> list[FinanceGrant]:
    statement = select(FinanceGrant).where(
        FinanceGrant.gym_id == gym_id,
        col(FinanceGrant.revoked_at).is_(None),
    )
    if user_id is not None:
        statement = statement.where(FinanceGrant.user_id == user_id)
    return list(
        session.exec(statement.order_by(col(FinanceGrant.created_at))).all()
    )


def _grant_items(rows: list[FinanceGrant]) -> list[FinanceGrantItem]:
    return [
        FinanceGrantItem(
            permission=cast(GrantableFinancePermission, row.permission),
            amount_limit_irr=row.amount_limit_irr,
        )
        for row in rows
    ]


def _grant_row(
    session: Session, *, rows: list[FinanceGrant], user_id: uuid.UUID
) -> FinanceGrantRow:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return FinanceGrantRow(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        grants=_grant_items(rows),
    )


def list_grants(session: Session, *, gym_id: uuid.UUID) -> FinanceGrantsPublic:
    rows = _active_grant_rows(session, gym_id=gym_id)
    grouped: dict[uuid.UUID, list[FinanceGrant]] = {}
    for row in rows:
        grouped.setdefault(row.user_id, []).append(row)
    data = [
        _grant_row(session, rows=items, user_id=user_id)
        for user_id, items in grouped.items()
    ]
    return FinanceGrantsPublic(data=data, count=len(data))


def replace_grants(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    target_user_id: uuid.UUID,
    body: FinanceGrantUpdate,
) -> FinanceGrantRow:
    scope.require_admin()
    target = session.get(User, target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    lock_finance_gym(session, scope.gym_id)
    if not active_finance_staff(
        session, gym_id=scope.gym_id, user_id=target_user_id
    ):
        raise HTTPException(status_code=400, detail="finance_staff_required")
    current = {
        row.permission: row
        for row in _active_grant_rows(
            session, gym_id=scope.gym_id, user_id=target_user_id
        )
    }
    desired = {item.permission: item.amount_limit_irr for item in body.grants}
    now = utcnow()
    revoked: list[str] = []
    for permission, row in current.items():
        if permission not in desired or row.amount_limit_irr != desired[permission]:
            row.revoked_at = now
            session.add(row)
            revoked.append(permission)
    session.flush()

    granted: list[dict[str, Any]] = []
    for permission, limit in desired.items():
        existing = current.get(permission)
        if existing is not None and existing.amount_limit_irr == limit:
            continue
        session.add(
            FinanceGrant(
                gym_id=scope.gym_id,
                user_id=target_user_id,
                permission=permission,
                amount_limit_irr=limit,
                granted_by_id=actor.id,
            )
        )
        granted.append({"permission": permission, "amount_limit_irr": limit})
    session.flush()

    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.grants.updated",
        target_type="user",
        target_id=target_user_id,
        detail={"granted": granted, "revoked": revoked},
    )
    session.commit()
    rows = _active_grant_rows(
        session, gym_id=scope.gym_id, user_id=target_user_id
    )
    return _grant_row(session, rows=rows, user_id=target_user_id)


def revoke_grants_for_user(
    session: Session,
    *,
    gym_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    reason: str,
) -> list[str]:
    """Revoke every active grant when finance access is taken away."""
    lock_finance_gym(session, gym_id)
    rows = _active_grant_rows(session, gym_id=gym_id, user_id=user_id)
    if not rows:
        return []
    now = utcnow()
    permissions = sorted(row.permission for row in rows)
    for row in rows:
        row.revoked_at = now
        session.add(row)
    session.flush()
    record_audit(
        session,
        gym_id=gym_id,
        actor_id=actor_id,
        action="finance.grants.revoked",
        target_type="user",
        target_id=user_id,
        reason=reason,
        detail={"permissions": permissions},
    )
    return permissions


# ---------------------------------------------------------------------------
# Catalog and invoices (Phase 2)
# ---------------------------------------------------------------------------

INVOICE_DOC_TYPE = "INVOICE"


def _catalog_public(item: FinanceCatalogItem) -> FinanceCatalogItemPublic:
    return FinanceCatalogItemPublic(
        id=item.id,
        name=item.name,
        kind=item.kind,  # type: ignore[arg-type]
        default_price_irr=item.default_price_irr,
        is_active=item.is_active,
    )


def list_catalog(
    session: Session, *, gym_id: uuid.UUID, active_only: bool
) -> FinanceCatalogPublic:
    statement = select(FinanceCatalogItem).where(
        FinanceCatalogItem.gym_id == gym_id
    )
    if active_only:
        statement = statement.where(col(FinanceCatalogItem.is_active).is_(True))
    items = session.exec(statement.order_by(col(FinanceCatalogItem.name))).all()
    return FinanceCatalogPublic(
        data=[_catalog_public(item) for item in items], count=len(items)
    )


def create_catalog_item(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceCatalogItemCreate,
) -> FinanceCatalogItemPublic:
    scope.require(FINANCE_CATALOG_MANAGE)
    existing = session.exec(
        select(FinanceCatalogItem).where(
            FinanceCatalogItem.gym_id == scope.gym_id,
            FinanceCatalogItem.name == body.name,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="catalog_item_exists")
    item = FinanceCatalogItem(
        gym_id=scope.gym_id,
        name=body.name,
        kind=body.kind,
        default_price_irr=body.default_price_irr,
        created_by_id=actor.id,
    )
    session.add(item)
    session.flush()
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.catalog.created",
        target_type="finance_catalog_item",
        target_id=item.id,
        detail={"name": item.name, "kind": item.kind},
    )
    session.commit()
    session.refresh(item)
    return _catalog_public(item)


def update_catalog_item(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    item_id: uuid.UUID,
    body: FinanceCatalogItemUpdate,
) -> FinanceCatalogItemPublic:
    scope.require(FINANCE_CATALOG_MANAGE)
    item = session.get(FinanceCatalogItem, item_id)
    if item is None or item.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="catalog_item_not_found")
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in data:
        duplicate = session.exec(
            select(FinanceCatalogItem).where(
                FinanceCatalogItem.gym_id == scope.gym_id,
                FinanceCatalogItem.name == data["name"],
                col(FinanceCatalogItem.id) != item.id,
            )
        ).first()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="catalog_item_exists")
    changes = {
        key: {"from": getattr(item, key), "to": value}
        for key, value in data.items()
    }
    item.sqlmodel_update(data)
    session.add(item)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.catalog.updated",
        target_type="finance_catalog_item",
        target_id=item.id,
        detail={"changes": changes},
    )
    session.commit()
    session.refresh(item)
    return _catalog_public(item)


def _invoice_customer(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = session.get(User, user_id)
    gym = session.get(Gym, gym_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid_invoice_customer")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == user_id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if membership is None and (gym is None or gym.owner_id != user_id):
        raise HTTPException(status_code=400, detail="invalid_invoice_customer")
    return user


def _invoice_lines(
    body: FinanceInvoiceCreate,
) -> tuple[list[dict[str, Any]], int, int]:
    nets: list[int] = []
    for item in body.lines:
        gross = item.quantity * item.unit_price_irr
        if item.line_discount_irr > gross:
            raise HTTPException(
                status_code=400, detail="finance_invalid_line_discount"
            )
        nets.append(gross - item.line_discount_irr)
    subtotal = sum(nets)
    if body.discount_irr > subtotal:
        raise HTTPException(
            status_code=400, detail="finance_discount_exceeds_total"
        )
    explicit = [item.bundle_discount_irr for item in body.lines]
    if any(value is not None for value in explicit):
        if any(value is None for value in explicit):
            raise HTTPException(
                status_code=400,
                detail="finance_discount_allocation_mismatch",
            )
        shares = [int(value) for value in explicit if value is not None]
        if any(
            share > net for share, net in zip(shares, nets, strict=True)
        ) or sum(shares) != body.discount_irr:
            raise HTTPException(
                status_code=400,
                detail="finance_discount_allocation_mismatch",
            )
    else:
        shares = (
            [body.discount_irr * net // subtotal for net in nets]
            if subtotal
            else [0] * len(nets)
        )
        remainder = body.discount_irr - sum(shares)
        # Deterministic residual: fill the largest lines first, then line
        # order, so every share stays inside its own line and the total is
        # exact.
        for index in sorted(range(len(nets)), key=lambda i: (-nets[i], i)):
            if remainder == 0:
                break
            take = min(nets[index] - shares[index], remainder)
            shares[index] += take
            remainder -= take
        if remainder != 0:
            raise HTTPException(
                status_code=400, detail="finance_discount_exceeds_total"
            )
    rows = [
        {
            "line_number": index + 1,
            "net_irr": net,
            "discount_share_irr": share,
            "payable_irr": net - share,
        }
        for index, (net, share) in enumerate(zip(nets, shares, strict=True))
    ]
    return rows, subtotal, subtotal - body.discount_irr


def _replace_invoice_body(
    session: Session, *, invoice: FinanceInvoice, body: FinanceInvoiceCreate
) -> None:
    for line in session.exec(
        select(FinanceInvoiceLine).where(
            FinanceInvoiceLine.invoice_id == invoice.id
        )
    ).all():
        session.delete(line)
    for installment in session.exec(
        select(FinanceInstallment).where(
            FinanceInstallment.invoice_id == invoice.id
        )
    ).all():
        session.delete(installment)
    session.flush()

    customer = _invoice_customer(
        session, gym_id=invoice.gym_id, user_id=body.customer_user_id
    )
    rows, subtotal, total = _invoice_lines(body)
    if body.installments is not None:
        if sum(item.amount_irr for item in body.installments) != total:
            raise HTTPException(
                status_code=400, detail="finance_installments_mismatch"
            )
    for item, calculated in zip(body.lines, rows, strict=True):
        if item.coach_user_id is not None and not _is_gym_coach(
            session, gym_id=invoice.gym_id, user_id=item.coach_user_id
        ):
            raise HTTPException(
                status_code=400, detail="invalid_invoice_coach"
            )
        if item.catalog_item_id is not None:
            catalog_item = session.get(
                FinanceCatalogItem, item.catalog_item_id
            )
            if catalog_item is None or catalog_item.gym_id != invoice.gym_id:
                raise HTTPException(
                    status_code=400, detail="invalid_catalog_item"
                )
        session.add(
            FinanceInvoiceLine(
                invoice_id=invoice.id,
                line_number=calculated["line_number"],
                catalog_item_id=item.catalog_item_id,
                kind=item.kind,
                description=item.description,
                quantity=item.quantity,
                unit_price_irr=item.unit_price_irr,
                line_discount_irr=item.line_discount_irr,
                coach_user_id=item.coach_user_id,
                net_irr=calculated["net_irr"],
                discount_share_irr=calculated["discount_share_irr"],
                payable_irr=calculated["payable_irr"],
            )
        )
    if body.installments is not None:
        for sequence, schedule in enumerate(body.installments, start=1):
            session.add(
                FinanceInstallment(
                    invoice_id=invoice.id,
                    sequence=sequence,
                    due_date=schedule.due_date,
                    amount_irr=schedule.amount_irr,
                )
            )
    invoice.customer_user_id = customer.id
    invoice.customer_name = customer.full_name or customer.email
    invoice.acquisition_source = body.acquisition_source
    invoice.discount_funding = body.discount_funding
    invoice.description = body.description
    invoice.due_date = body.due_date
    invoice.subtotal_irr = subtotal
    invoice.discount_irr = body.discount_irr
    invoice.total_irr = total
    session.add(invoice)
    session.flush()


def _get_invoice(
    session: Session, *, gym_id: uuid.UUID, invoice_id: uuid.UUID
) -> FinanceInvoice:
    invoice = session.get(FinanceInvoice, invoice_id)
    if invoice is None or invoice.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    return invoice


def invoice_public(
    session: Session, invoice: FinanceInvoice
) -> FinanceInvoicePublic:
    lines = session.exec(
        select(FinanceInvoiceLine)
        .where(FinanceInvoiceLine.invoice_id == invoice.id)
        .order_by(col(FinanceInvoiceLine.line_number))
    ).all()
    installments = session.exec(
        select(FinanceInstallment)
        .where(FinanceInstallment.invoice_id == invoice.id)
        .order_by(col(FinanceInstallment.sequence))
    ).all()
    paid = 0 if invoice.status == "VOID" else _invoice_paid_irr(session, invoice.id)
    balance = 0 if invoice.status == "VOID" else invoice.total_irr - paid
    today = utcnow().date()
    overdue = (
        invoice.status == "ISSUED"
        and balance > 0
        and invoice.due_date is not None
        and invoice.due_date < today
    )
    return FinanceInvoicePublic(
        id=invoice.id,
        status=invoice.status,  # type: ignore[arg-type]
        acquisition_source=invoice.acquisition_source,  # type: ignore[arg-type]
        discount_funding=invoice.discount_funding,  # type: ignore[arg-type]
        invoice_number=invoice.invoice_number,
        customer_user_id=invoice.customer_user_id,
        customer_name=invoice.customer_name,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        description=invoice.description,
        subtotal_irr=invoice.subtotal_irr,
        discount_irr=invoice.discount_irr,
        total_irr=invoice.total_irr,
        paid_irr=paid,
        balance_irr=balance,
        overdue=overdue,
        void_reason=invoice.void_reason,
        created_at=invoice.created_at,
        issued_at=invoice.issued_at,
        lines=[
            FinanceInvoiceLinePublic(
                id=line.id,
                line_number=line.line_number,
                catalog_item_id=line.catalog_item_id,
                kind=line.kind,  # type: ignore[arg-type]
                description=line.description,
                quantity=line.quantity,
                unit_price_irr=line.unit_price_irr,
                line_discount_irr=line.line_discount_irr,
                net_irr=line.net_irr,
                discount_share_irr=line.discount_share_irr,
                payable_irr=line.payable_irr,
                coach_user_id=line.coach_user_id,
                coach_agreement_id=line.coach_agreement_id,
                coach_agreement_version=line.coach_agreement_version,
                coach_allocation_status=line.coach_allocation_status,
                platform_allocation_status=line.platform_allocation_status,
                platform_fee_irr=line.platform_fee_irr,
                platform_ascora_term_share_irr=line.platform_ascora_term_share_irr,
            )
            for line in lines
        ],
        installments=[
            FinanceInstallmentPublic(
                id=installment.id,
                sequence=installment.sequence,
                due_date=installment.due_date,
                amount_irr=installment.amount_irr,
            )
            for installment in installments
        ],
    )


def list_invoices(
    session: Session,
    *,
    gym_id: uuid.UUID,
    status: str | None,
    customer_user_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> FinanceInvoicesPublic:
    filters = [FinanceInvoice.gym_id == gym_id]
    if status:
        filters.append(FinanceInvoice.status == status)
    if customer_user_id:
        filters.append(FinanceInvoice.customer_user_id == customer_user_id)
    total = session.exec(
        select(func.count(col(FinanceInvoice.id))).where(*filters)
    ).one()
    invoices = session.exec(
        select(FinanceInvoice)
        .where(*filters)
        .order_by(col(FinanceInvoice.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return FinanceInvoicesPublic(
        data=[invoice_public(session, invoice) for invoice in invoices],
        count=int(total),
    )


def get_invoice(
    session: Session, *, gym_id: uuid.UUID, invoice_id: uuid.UUID
) -> FinanceInvoicePublic:
    return invoice_public(
        session, _get_invoice(session, gym_id=gym_id, invoice_id=invoice_id)
    )


def create_invoice(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceInvoiceCreate,
) -> FinanceInvoicePublic:
    scope.require(FINANCE_INVOICE_MANAGE)
    invoice = FinanceInvoice(
        gym_id=scope.gym_id,
        customer_user_id=body.customer_user_id,
        status="DRAFT",
        created_by_id=actor.id,
        subtotal_irr=0,
        discount_irr=0,
        total_irr=0,
    )
    session.add(invoice)
    session.flush()
    _replace_invoice_body(session, invoice=invoice, body=body)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.invoice.drafted",
        target_type="finance_invoice",
        target_id=invoice.id,
        detail={"total_irr": invoice.total_irr},
    )
    session.commit()
    session.refresh(invoice)
    return invoice_public(session, invoice)


def update_invoice(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    invoice_id: uuid.UUID,
    body: FinanceInvoiceUpdate,
) -> FinanceInvoicePublic:
    scope.require(FINANCE_INVOICE_MANAGE)
    invoice = _get_invoice(session, gym_id=scope.gym_id, invoice_id=invoice_id)
    if invoice.status != "DRAFT":
        raise HTTPException(status_code=409, detail="invoice_not_draft")
    _replace_invoice_body(session, invoice=invoice, body=body)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.invoice.updated",
        target_type="finance_invoice",
        target_id=invoice.id,
        detail={"total_irr": invoice.total_irr},
    )
    session.commit()
    session.refresh(invoice)
    return invoice_public(session, invoice)


def delete_invoice(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    invoice_id: uuid.UUID,
) -> None:
    scope.require(FINANCE_INVOICE_MANAGE)
    invoice = _get_invoice(session, gym_id=scope.gym_id, invoice_id=invoice_id)
    if invoice.status != "DRAFT":
        raise HTTPException(status_code=409, detail="invoice_not_draft")
    session.delete(invoice)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.invoice.discarded",
        target_type="finance_invoice",
        target_id=invoice_id,
    )
    session.commit()




# ---------------------------------------------------------------------------
# Deterministic revenue allocation (Phase 3)
# ---------------------------------------------------------------------------


def _split_proportional(total: int, weights: list[int]) -> list[int]:
    """Split an integer total by weights, exact to the rial."""
    if total <= 0 or not weights:
        return [0] * len(weights)
    weight_total = sum(weights)
    if weight_total <= 0:
        return [0] * len(weights)
    shares = [total * weight // weight_total for weight in weights]
    remainder = total - sum(shares)
    for index in sorted(range(len(weights)), key=lambda i: (-weights[i], i)):
        if remainder == 0:
            break
        take = min(max(weights[index] - shares[index], 0), remainder)
        shares[index] += take
        remainder -= take
    if remainder:
        shares[0] += remainder
    return shares


def _allocate_coach_shares(
    snapshot: dict[str, Any],
    *,
    base_irr: int,
    discount_irr: int,
    discount_funding: str,
) -> tuple[int, int, int]:
    """Return coach, platform and gym shares summing to collected net."""
    totals = {"COACH": 0, "ASCORA": 0, "GYM": 0}
    remaining = base_irr
    mode = snapshot.get("mode", "DIRECT")
    for term in snapshot.get("terms", []):
        if remaining <= 0:
            break
        recipient = term.get("recipient")
        if recipient not in totals:
            continue
        if term.get("basis") == "PERCENT":
            denominator = base_irr if mode == "DIRECT" else remaining
            amount = denominator * int(term.get("percent_bp", 0)) // 10_000
        else:
            amount = int(term.get("fixed_irr", 0))
        amount = max(0, min(amount, remaining))
        totals[recipient] += amount
        remaining -= amount
    totals["GYM"] += remaining

    discount = min(discount_irr, base_irr)
    if discount > 0:
        if discount_funding == "MIXED":
            shares = _split_proportional(
                discount,
                [totals["COACH"], totals["ASCORA"], totals["GYM"]],
            )
            totals["COACH"] -= shares[0]
            totals["ASCORA"] -= shares[1]
            totals["GYM"] -= shares[2]
        else:
            funder = discount_funding if discount_funding in totals else "GYM"
            taken = min(discount, totals[funder])
            totals[funder] -= taken
            remainder = discount - taken
            for recipient in ("GYM", "COACH", "ASCORA"):
                if remainder == 0:
                    break
                take = min(remainder, totals[recipient])
                totals[recipient] -= take
                remainder -= take

    # Keep the invariant exact even for a malformed historical snapshot.
    delta = (base_irr - discount) - sum(totals.values())
    totals["GYM"] += delta
    if totals["GYM"] < 0:
        totals["GYM"] = 0
    return totals["COACH"], totals["ASCORA"], totals["GYM"]


def _create_coach_earnings(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    invoice: FinanceInvoice,
    amount_irr: int,
    received_on: date,
    receipt_id: uuid.UUID | None,
    credit_movement_id: uuid.UUID | None,
    source_prefix: str,
) -> int:
    lines = session.exec(
        select(FinanceInvoiceLine)
        .where(FinanceInvoiceLine.invoice_id == invoice.id)
        .order_by(col(FinanceInvoiceLine.line_number))
    ).all()
    payables = [line.payable_irr for line in lines]
    portions = _split_proportional(amount_irr, payables)
    created: list[FinanceCoachEarning] = []
    for line, portion in zip(lines, portions, strict=True):
        if portion <= 0 or line.coach_user_id is None:
            continue
        snapshot = (
            line.agreement_snapshot
            if line.coach_allocation_status == "SNAPSHOTTED"
            else None
        )
        resolved = None
        if snapshot is None:
            resolved = session.exec(
                select(FinanceCoachEarning)
                .where(
                    FinanceCoachEarning.invoice_line_id == line.id,
                    col(FinanceCoachEarning.agreement_id).is_not(None),
                )
                .order_by(col(FinanceCoachEarning.created_at).desc())
            ).first()
        if snapshot is None and resolved is not None:
            agreement_row = session.get(FinanceCoachAgreement, resolved.agreement_id)
            if agreement_row is not None:
                snapshot = _agreement_snapshot(session, agreement_row)
        discount_portion = (
            line.discount_share_irr * portion // line.payable_irr
            if line.payable_irr > 0
            else 0
        )
        base_portion = portion + discount_portion
        if snapshot is None:
            coach = platform = gym = 0
            status = "UNRESOLVED"
            reason = "coach_agreement_missing"
            vesting_mode = "MANUAL"
            vesting_date = None
        else:
            coach, platform, gym = _allocate_coach_shares(
                snapshot,
                base_irr=base_portion,
                discount_irr=discount_portion,
                discount_funding=invoice.discount_funding,
            )
            scheduled_coach, _, _ = _allocate_coach_shares(
                snapshot,
                base_irr=line.net_irr,
                discount_irr=line.discount_share_irr,
                discount_funding=invoice.discount_funding,
            )
            prior_coach = session.exec(
                select(
                    func.coalesce(
                        func.sum(FinanceCoachEarning.coach_share_irr), 0
                    )
                ).where(
                    FinanceCoachEarning.gym_id == scope.gym_id,
                    FinanceCoachEarning.invoice_line_id == line.id,
                )
            ).one()
            remaining_coach = max(scheduled_coach - int(prior_coach), 0)
            if coach > remaining_coach:
                gym += coach - remaining_coach
                coach = remaining_coach
            status = "CALCULATED"
            reason = None
            vesting_mode = snapshot.get("vesting_mode", "MANUAL")
            vesting_date = (
                received_on + timedelta(days=int(snapshot.get("vesting_days", 0)))
                if vesting_mode == "ON_DATE"
                else None
            )
        earning = FinanceCoachEarning(
            gym_id=scope.gym_id,
            coach_user_id=line.coach_user_id,
            invoice_id=invoice.id,
            invoice_line_id=line.id,
            receipt_id=receipt_id,
            credit_movement_id=credit_movement_id,
            source_key=f"{source_prefix}:{line.id}",
            agreement_id=line.coach_agreement_id,
            agreement_version=line.coach_agreement_version,
            discount_funding=invoice.discount_funding,
            base_irr=base_portion,
            discount_irr=discount_portion,
            coach_share_irr=coach,
            platform_share_irr=platform,
            gym_share_irr=gym,
            status=status,
            unresolved_reason=reason,
            vesting_mode=vesting_mode,
            vesting_date=vesting_date,
        )
        session.add(earning)
        created.append(earning)
    if not created:
        return 0
    session.flush()
    coach_total = sum(row.coach_share_irr for row in created)
    if coach_total > 0:
        accounts = ensure_accounts(session, scope.gym_id)
        journal = post_journal(
            session,
            gym_id=scope.gym_id,
            posting_date=received_on,
            event_type="COACH_ALLOCATION",
            description="Coach revenue allocation",
            lines=[
                (accounts["5100"].id, coach_total, 0, "Coach share"),
                (accounts["2100"].id, 0, coach_total, "Coach payable"),
            ],
            created_by_id=actor.id,
            source_type="finance_coach_earning",
            source_id=created[0].id,
        )
        for row in created:
            if row.coach_share_irr > 0:
                row.journal_id = journal.id
                session.add(row)
    return coach_total


def _agreement_snapshot(
    session: Session, agreement: FinanceCoachAgreement
) -> dict[str, Any]:
    terms = session.exec(
        select(FinanceCoachAgreementTerm)
        .where(FinanceCoachAgreementTerm.agreement_id == agreement.id)
        .order_by(col(FinanceCoachAgreementTerm.sequence))
    ).all()
    return {
        "agreement_id": str(agreement.id),
        "version": agreement.version,
        "mode": agreement.mode,
        "vesting_mode": agreement.vesting_mode,
        "vesting_days": agreement.vesting_days,
        "effective_from": agreement.effective_from.isoformat(),
        "effective_to": (
            agreement.effective_to.isoformat()
            if agreement.effective_to
            else None
        ),
        "terms": [
            {
                "sequence": term.sequence,
                "recipient": term.recipient,
                "basis": term.basis,
                "percent_bp": term.percent_bp,
                "fixed_irr": term.fixed_irr,
                "label": term.label,
            }
            for term in terms
        ],
    }


def _snapshot_invoice_coaches(
    session: Session, *, invoice: FinanceInvoice, issue_date: date
) -> None:
    lines = session.exec(
        select(FinanceInvoiceLine).where(
            FinanceInvoiceLine.invoice_id == invoice.id
        )
    ).all()
    for line in lines:
        if line.coach_user_id is None:
            line.coach_allocation_status = "NOT_APPLICABLE"
            line.coach_agreement_id = None
            line.coach_agreement_version = None
            line.agreement_snapshot = None
            session.add(line)
            continue
        agreement = session.exec(
            select(FinanceCoachAgreement)
            .where(
                FinanceCoachAgreement.gym_id == invoice.gym_id,
                FinanceCoachAgreement.coach_user_id == line.coach_user_id,
                FinanceCoachAgreement.status == "ACTIVE",
                FinanceCoachAgreement.effective_from <= issue_date,
                or_(
                    col(FinanceCoachAgreement.effective_to).is_(None),
                    col(FinanceCoachAgreement.effective_to) >= issue_date,
                ),
            )
            .order_by(col(FinanceCoachAgreement.version).desc())
        ).first()
        if (
            agreement is None
            or (
                agreement.effective_to is not None
                and agreement.effective_to < issue_date
            )
        ):
            line.coach_allocation_status = "UNRESOLVED"
            line.coach_agreement_id = None
            line.coach_agreement_version = None
            line.agreement_snapshot = None
            session.add(line)
            continue
        line.coach_allocation_status = "SNAPSHOTTED"
        line.coach_agreement_id = agreement.id
        line.coach_agreement_version = agreement.version
        line.agreement_snapshot = _agreement_snapshot(session, agreement)
        session.add(line)



def _snapshot_invoice_platform(
    session: Session,
    *,
    invoice: FinanceInvoice,
    issue_date: date,
    actor: User,
) -> None:
    from app.platform_models import PlatformAudit
    from app.services import platform as platform_service

    lines = session.exec(
        select(FinanceInvoiceLine).where(
            FinanceInvoiceLine.invoice_id == invoice.id
        )
    ).all()
    agreement = platform_service.find_effective_agreement(
        session, gym_id=invoice.gym_id, on_date=issue_date
    )

    def audit_line(line: FinanceInvoiceLine) -> None:
        session.add(
            PlatformAudit(
                gym_id=invoice.gym_id,
                actor_id=actor.id,
                action="platform.ascora_source.snapshotted",
                target_type="finance_invoice",
                target_id=invoice.id,
                detail={
                    "invoice_line_id": str(line.id),
                    "source": line.platform_allocation_status,
                    "platform_fee_irr": line.platform_fee_irr,
                    "ascora_term_share_irr": line.platform_ascora_term_share_irr,
                },
            )
        )

    for line in lines:
        line.platform_agreement_id = None
        line.platform_agreement_version = None
        line.platform_allocation_status = "NOT_APPLICABLE"
        line.platform_snapshot = None
        line.platform_fee_irr = 0
        line.platform_ascora_term_share_irr = 0
        ascora_share = 0
        if line.coach_user_id is not None and line.agreement_snapshot:
            _, ascora_share, _ = _allocate_coach_shares(
                line.agreement_snapshot,
                base_irr=line.payable_irr + line.discount_share_irr,
                discount_irr=line.discount_share_irr,
                discount_funding=invoice.discount_funding,
            )
        if ascora_share > 0:
            line.platform_allocation_status = "COACH_ASCORA_TERM"
            line.platform_ascora_term_share_irr = ascora_share
            line.platform_fee_irr = ascora_share
            line.platform_snapshot = {
                "source": "COACH_ASCORA_TERM",
                "coach_agreement_id": (
                    str(line.coach_agreement_id)
                    if line.coach_agreement_id is not None
                    else None
                ),
                "coach_agreement_version": line.coach_agreement_version,
                "scheduled_ascora_share_irr": ascora_share,
            }
            session.add(line)
            audit_line(line)
            continue
        if agreement is None or agreement.mode in ("FREE", "SUBSCRIPTION"):
            session.add(line)
            audit_line(line)
            continue
        term = platform_service.match_commission_term(
            session,
            agreement=agreement,
            line_kind=line.kind,
            acquisition_source=invoice.acquisition_source,
        )
        if term is None:
            line.platform_allocation_status = "NO_TERM"
            session.add(line)
            audit_line(line)
            continue
        line.platform_allocation_status = "SNAPSHOTTED"
        line.platform_agreement_id = agreement.id
        line.platform_agreement_version = agreement.version
        line.platform_fee_irr = platform_service.platform_fee_for_line(
            term, line.payable_irr
        )
        line.platform_snapshot = {
            "source": "PLATFORM_COMMISSION",
            "agreement_id": str(agreement.id),
            "version": agreement.version,
            "mode": agreement.mode,
            "volume_discount_bp": agreement.volume_discount_bp,
            "group_allocations": (
                platform_service.agreement_snapshot(session, agreement).get(
                    "group_allocations", []
                )
            ),
            "term": {
                "kind": term.kind,
                "acquisition_source": term.acquisition_source,
                "basis": term.basis,
                "percent_bp": term.percent_bp,
                "fixed_irr": term.fixed_irr,
                "max_fee_irr": term.max_fee_irr,
            },
        }
        session.add(line)
        audit_line(line)


def issue_invoice(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    invoice_id: uuid.UUID,
    posting_date: date,
    operation_key: str,
) -> FinanceInvoicePublic:
    scope.require(FINANCE_INVOICE_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_INVOICE_MANAGE)
    payload = {"invoice_id": str(invoice_id), "posting_date": posting_date.isoformat()}
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        invoice = session.get(FinanceInvoice, operation.result_id)
        if invoice is None or invoice.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return invoice_public(session, invoice)

    invoice = _get_invoice(session, gym_id=scope.gym_id, invoice_id=invoice_id)
    if invoice.status != "DRAFT":
        raise HTTPException(status_code=409, detail="invoice_not_draft")
    if invoice.total_irr <= 0:
        raise HTTPException(
            status_code=400, detail="finance_invoice_total_required"
        )

    _snapshot_invoice_coaches(session, invoice=invoice, issue_date=posting_date)
    _snapshot_invoice_platform(session, invoice=invoice, issue_date=posting_date, actor=actor)
    accounts = ensure_accounts(session, scope.gym_id)
    number = allocate_document_number(
        session, scope.gym_id, INVOICE_DOC_TYPE
    )
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=posting_date,
        event_type="INVOICE_ISSUED",
        description=f"Invoice {number}",
        lines=[
            (accounts["1100"].id, invoice.total_irr, 0, f"Invoice {number}"),
            (accounts["4000"].id, 0, invoice.total_irr, f"Invoice {number}"),
        ],
        created_by_id=actor.id,
        source_type="finance_invoice",
        source_id=invoice.id,
    )
    invoice.invoice_number = number
    invoice.status = "ISSUED"
    invoice.issue_date = posting_date
    invoice.issued_at = utcnow()
    invoice.journal_id = journal.id
    session.add(invoice)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.invoice.issued",
        target_type="finance_invoice",
        target_id=invoice.id,
        detail={
            "invoice_number": number,
            "total_irr": invoice.total_irr,
            "journal_id": str(journal.id),
        },
    )
    audit(
        "finance.invoice.issued",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=invoice.id,
        detail=f"number={number}",
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_invoice",
        result_id=invoice.id,
    )
    session.commit()
    session.refresh(invoice)
    return invoice_public(session, invoice)


def void_invoice(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    invoice_id: uuid.UUID,
    reason: str,
    posting_date: date,
    operation_key: str,
) -> FinanceInvoicePublic:
    scope.require(FINANCE_INVOICE_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_INVOICE_MANAGE)
    payload = {
        "invoice_id": str(invoice_id),
        "reason": reason,
        "posting_date": posting_date.isoformat(),
    }
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        invoice = session.get(FinanceInvoice, operation.result_id)
        if invoice is None or invoice.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return invoice_public(session, invoice)

    invoice = _get_invoice(session, gym_id=scope.gym_id, invoice_id=invoice_id)
    if invoice.status != "ISSUED":
        raise HTTPException(status_code=409, detail="invoice_not_issued")
    if _invoice_paid_irr(session, invoice.id) > 0:
        raise HTTPException(status_code=409, detail="invoice_has_payments")
    if invoice.journal_id is None:
        raise HTTPException(
            status_code=400, detail="finance_invoice_not_posted"
        )
    journal = session.get(FinanceJournal, invoice.journal_id)
    if journal is None:
        raise HTTPException(
            status_code=400, detail="finance_invoice_not_posted"
        )
    original_lines = session.exec(
        select(FinanceJournalLine).where(
            FinanceJournalLine.journal_id == journal.id
        )
    ).all()
    reversal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=posting_date,
        event_type="INVOICE_VOID",
        description=f"Void invoice {invoice.invoice_number}: {reason}",
        lines=[
            (line.account_id, line.credit_irr, line.debit_irr, line.memo)
            for line in original_lines
        ],
        created_by_id=actor.id,
        reversal_of_id=journal.id,
        source_type="finance_invoice",
        source_id=invoice.id,
    )
    invoice.status = "VOID"
    invoice.void_reason = reason
    invoice.voided_at = utcnow()
    session.add(invoice)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.invoice.voided",
        target_type="finance_invoice",
        target_id=invoice.id,
        reason=reason,
        detail={
            "invoice_number": invoice.invoice_number,
            "reversal_journal_id": str(reversal.id),
        },
    )
    audit(
        "finance.invoice.voided",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=invoice.id,
        detail=f"number={invoice.invoice_number}",
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_invoice",
        result_id=invoice.id,
    )
    session.commit()
    session.refresh(invoice)
    return invoice_public(session, invoice)


# ---------------------------------------------------------------------------
# Manual receipts, allocations and advances (Phase 2)
# ---------------------------------------------------------------------------

RECEIPT_DOC_TYPE = "RECEIPT"


def _invoice_paid_irr(session: Session, invoice_id: uuid.UUID) -> int:
    allocated = session.exec(
        select(
            func.coalesce(func.sum(FinanceReceiptAllocation.amount_irr), 0)
        ).where(FinanceReceiptAllocation.invoice_id == invoice_id)
    ).one()
    applied = session.exec(
        select(func.coalesce(func.sum(FinanceCreditMovement.amount_irr), 0)).where(
            FinanceCreditMovement.invoice_id == invoice_id,
            FinanceCreditMovement.kind == "APPLIED",
        )
    ).one()
    return int(allocated) + int(applied)


def _customer_credit(
    session: Session, *, gym_id: uuid.UUID, customer_user_id: uuid.UUID
) -> FinanceCustomerCredit | None:
    return session.exec(
        select(FinanceCustomerCredit).where(
            FinanceCustomerCredit.gym_id == gym_id,
            FinanceCustomerCredit.customer_user_id == customer_user_id,
        )
    ).first()


def _credit_public(
    session: Session, credit: FinanceCustomerCredit
) -> FinanceCreditPublic:
    user = session.get(User, credit.customer_user_id)
    return FinanceCreditPublic(
        customer_user_id=credit.customer_user_id,
        customer_name=(user.full_name or user.email) if user else None,
        balance_irr=credit.balance_irr,
    )


def receipt_public(
    session: Session, receipt: FinanceReceipt
) -> FinanceReceiptPublic:
    rows = session.exec(
        select(FinanceReceiptAllocation, FinanceInvoice.invoice_number)
        .join(
            FinanceInvoice,
            col(FinanceInvoice.id) == col(FinanceReceiptAllocation.invoice_id),
        )
        .where(FinanceReceiptAllocation.receipt_id == receipt.id)
        .order_by(col(FinanceInvoice.invoice_number))
    ).all()
    allocated = sum(line.amount_irr for line, _number in rows)
    return FinanceReceiptPublic(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        customer_user_id=receipt.customer_user_id,
        customer_name=receipt.customer_name,
        method=receipt.method,  # type: ignore[arg-type]
        amount_irr=receipt.amount_irr,
        allocated_irr=allocated,
        excess_irr=receipt.amount_irr - allocated,
        reference=receipt.reference,
        received_on=receipt.received_on,
        status=receipt.status,  # type: ignore[arg-type]
        verification_source=receipt.verification_source,
        reconciled=receipt.reconciled_at is not None,
        created_at=receipt.created_at,
        allocations=[
            FinanceReceiptAllocationPublic(
                invoice_id=line.invoice_id,
                invoice_number=number,
                amount_irr=line.amount_irr,
            )
            for line, number in rows
        ],
    )


def list_receipts(
    session: Session,
    *,
    gym_id: uuid.UUID,
    customer_user_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> FinanceReceiptsPublic:
    filters = [FinanceReceipt.gym_id == gym_id]
    if customer_user_id:
        filters.append(FinanceReceipt.customer_user_id == customer_user_id)
    total = session.exec(
        select(func.count(col(FinanceReceipt.id))).where(*filters)
    ).one()
    receipts = session.exec(
        select(FinanceReceipt)
        .where(*filters)
        .order_by(col(FinanceReceipt.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return FinanceReceiptsPublic(
        data=[receipt_public(session, receipt) for receipt in receipts],
        count=int(total),
    )


def get_receipt(
    session: Session, *, gym_id: uuid.UUID, receipt_id: uuid.UUID
) -> FinanceReceiptPublic:
    receipt = session.get(FinanceReceipt, receipt_id)
    if receipt is None or receipt.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="receipt_not_found")
    return receipt_public(session, receipt)


def list_credits(
    session: Session, *, gym_id: uuid.UUID
) -> FinanceCreditsPublic:
    credits = session.exec(
        select(FinanceCustomerCredit)
        .where(
            FinanceCustomerCredit.gym_id == gym_id,
            col(FinanceCustomerCredit.balance_irr) > 0,
        )
        .order_by(col(FinanceCustomerCredit.updated_at).desc())
    ).all()
    return FinanceCreditsPublic(
        data=[_credit_public(session, credit) for credit in credits],
        count=len(credits),
    )


def create_receipt(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceReceiptCreate,
    operation_key: str,
) -> FinanceReceiptPublic:
    scope.require(FINANCE_PAYMENT_RECORD)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_PAYMENT_RECORD)
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        receipt = session.get(FinanceReceipt, operation.result_id)
        if receipt is None or receipt.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return receipt_public(session, receipt)

    customer = _invoice_customer(
        session, gym_id=scope.gym_id, user_id=body.customer_user_id
    )
    seen: set[uuid.UUID] = set()
    invoices: list[FinanceInvoice] = []
    allocated = 0
    for allocation in body.allocations:
        if allocation.invoice_id in seen:
            raise HTTPException(
                status_code=400, detail="duplicate_invoice_allocation"
            )
        seen.add(allocation.invoice_id)
        invoice = _get_invoice(
            session, gym_id=scope.gym_id, invoice_id=allocation.invoice_id
        )
        if invoice.customer_user_id != customer.id:
            raise HTTPException(
                status_code=400, detail="receipt_customer_mismatch"
            )
        if invoice.status != "ISSUED":
            raise HTTPException(
                status_code=400, detail="invoice_not_issued"
            )
        remaining = invoice.total_irr - _invoice_paid_irr(session, invoice.id)
        if allocation.amount_irr > remaining:
            raise HTTPException(
                status_code=400,
                detail="receipt_allocation_exceeds_invoice",
            )
        allocated += allocation.amount_irr
        invoices.append(invoice)
    if allocated > body.amount_irr:
        raise HTTPException(status_code=400, detail="receipt_over_allocated")
    excess = body.amount_irr - allocated

    accounts = ensure_accounts(session, scope.gym_id)
    number = allocate_document_number(session, scope.gym_id, RECEIPT_DOC_TYPE)
    receipt = FinanceReceipt(
        gym_id=scope.gym_id,
        customer_user_id=customer.id,
        customer_name=customer.full_name or customer.email,
        receipt_number=number,
        method=body.method,
        amount_irr=body.amount_irr,
        reference=body.reference,
        received_on=body.received_on,
        status="CONFIRMED",
        verification_source="STAFF_ATTESTATION",
        created_by_id=actor.id,
    )
    session.add(receipt)
    session.flush()

    journal_lines: list[tuple[uuid.UUID, int, int, str | None]] = [
        (accounts["1000"].id, body.amount_irr, 0, f"Receipt {number}")
    ]
    if allocated:
        journal_lines.append(
            (accounts["1100"].id, 0, allocated, f"Receipt {number}")
        )
    if excess:
        journal_lines.append(
            (accounts["2000"].id, 0, excess, f"Customer advance {number}")
        )
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=body.received_on,
        event_type="RECEIPT_CONFIRMED",
        description=f"Receipt {number}",
        lines=journal_lines,
        created_by_id=actor.id,
        source_type="finance_receipt",
        source_id=receipt.id,
    )
    receipt.journal_id = journal.id
    session.add(receipt)

    for allocation, invoice in zip(body.allocations, invoices, strict=True):
        session.add(
            FinanceReceiptAllocation(
                receipt_id=receipt.id,
                invoice_id=invoice.id,
                amount_irr=allocation.amount_irr,
            )
        )
        _create_coach_earnings(
            session,
            scope=scope,
            actor=actor,
            invoice=invoice,
            amount_irr=allocation.amount_irr,
            received_on=body.received_on,
            receipt_id=receipt.id,
            credit_movement_id=None,
            source_prefix=f"receipt:{receipt.id}",
        )
        from app.services import platform as platform_service

        platform_service.create_platform_ascora_receivable(
            session,
            gym_id=scope.gym_id,
            actor=actor,
            invoice=invoice,
            amount_irr=allocation.amount_irr,
            received_on=body.received_on,
            receipt_id=receipt.id,
            credit_movement_id=None,
            source_prefix=f"receipt:{receipt.id}",
        )

    if excess:
        credit = _customer_credit(
            session, gym_id=scope.gym_id, customer_user_id=customer.id
        )
        if credit is None:
            credit = FinanceCustomerCredit(
                gym_id=scope.gym_id,
                customer_user_id=customer.id,
                balance_irr=0,
            )
            session.add(credit)
            session.flush()
        credit.balance_irr += excess
        credit.updated_at = utcnow()
        session.add(credit)
        session.add(
            FinanceCreditMovement(
                credit_id=credit.id,
                kind="RECEIPT_EXCESS",
                amount_irr=excess,
                receipt_id=receipt.id,
                created_by_id=actor.id,
            )
        )

    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.receipt.confirmed",
        target_type="finance_receipt",
        target_id=receipt.id,
        detail={
            "receipt_number": number,
            "amount_irr": body.amount_irr,
            "allocated_irr": allocated,
            "excess_irr": excess,
            "method": body.method,
        },
    )
    audit(
        "finance.receipt.confirmed",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=receipt.id,
        detail=f"number={number}",
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_receipt",
        result_id=receipt.id,
    )
    session.commit()
    session.refresh(receipt)
    return receipt_public(session, receipt)


def apply_customer_credit(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceCreditApplyCreate,
    operation_key: str,
) -> FinanceInvoicePublic:
    scope.require(FINANCE_PAYMENT_RECORD)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_PAYMENT_RECORD)
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        invoice = session.get(FinanceInvoice, operation.result_id)
        if invoice is None or invoice.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return invoice_public(session, invoice)

    customer = _invoice_customer(
        session, gym_id=scope.gym_id, user_id=body.customer_user_id
    )
    invoice = _get_invoice(
        session, gym_id=scope.gym_id, invoice_id=body.invoice_id
    )
    if invoice.customer_user_id != customer.id:
        raise HTTPException(status_code=400, detail="receipt_customer_mismatch")
    if invoice.status != "ISSUED":
        raise HTTPException(status_code=400, detail="invoice_not_issued")
    credit = _customer_credit(
        session, gym_id=scope.gym_id, customer_user_id=customer.id
    )
    if credit is None or credit.balance_irr < body.amount_irr:
        raise HTTPException(
            status_code=400, detail="insufficient_customer_credit"
        )
    remaining = invoice.total_irr - _invoice_paid_irr(session, invoice.id)
    if body.amount_irr > remaining:
        raise HTTPException(
            status_code=400, detail="credit_exceeds_invoice_balance"
        )

    accounts = ensure_accounts(session, scope.gym_id)
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=body.received_on,
        event_type="ADVANCE_APPLIED",
        description=f"Advance applied to invoice {invoice.invoice_number}",
        lines=[
            (accounts["2000"].id, body.amount_irr, 0, "Customer advance"),
            (accounts["1100"].id, 0, body.amount_irr, "Invoice settlement"),
        ],
        created_by_id=actor.id,
        source_type="finance_invoice",
        source_id=invoice.id,
    )
    credit.balance_irr -= body.amount_irr
    credit.updated_at = utcnow()
    session.add(credit)
    movement = FinanceCreditMovement(
        credit_id=credit.id,
        kind="APPLIED",
        amount_irr=body.amount_irr,
        invoice_id=invoice.id,
        created_by_id=actor.id,
    )
    session.add(movement)
    session.flush()
    _create_coach_earnings(
        session,
        scope=scope,
        actor=actor,
        invoice=invoice,
        amount_irr=body.amount_irr,
        received_on=body.received_on,
        receipt_id=None,
        credit_movement_id=movement.id,
        source_prefix=f"advance:{movement.id}",
    )
    from app.services import platform as platform_service

    platform_service.create_platform_ascora_receivable(
        session,
        gym_id=scope.gym_id,
        actor=actor,
        invoice=invoice,
        amount_irr=body.amount_irr,
        received_on=body.received_on,
        receipt_id=None,
        credit_movement_id=movement.id,
        source_prefix=f"advance:{movement.id}",
    )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.credit.applied",
        target_type="finance_invoice",
        target_id=invoice.id,
        detail={
            "amount_irr": body.amount_irr,
            "journal_id": str(journal.id),
        },
    )
    audit(
        "finance.credit.applied",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=invoice.id,
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_invoice",
        result_id=invoice.id,
    )
    session.commit()
    session.refresh(invoice)
    return invoice_public(session, invoice)


# ---------------------------------------------------------------------------
# Refunds and operating expenses (Phase 2)
# ---------------------------------------------------------------------------


def _refund_public(refund: FinanceRefund) -> FinanceRefundPublic:
    return FinanceRefundPublic(
        id=refund.id,
        source=refund.source,  # type: ignore[arg-type]
        status=refund.status,  # type: ignore[arg-type]
        customer_user_id=refund.customer_user_id,
        invoice_id=refund.invoice_id,
        amount_irr=refund.amount_irr,
        method=refund.method,  # type: ignore[arg-type]
        original_method=refund.original_method,
        method_override_reason=refund.method_override_reason,
        reason=refund.reason,
        created_at=refund.created_at,
        recorded_at=refund.recorded_at,
    )


def _get_refund(
    session: Session, *, gym_id: uuid.UUID, refund_id: uuid.UUID
) -> FinanceRefund:
    refund = session.get(FinanceRefund, refund_id)
    if refund is None or refund.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="refund_not_found")
    return refund


def _invoice_refundable_irr(
    session: Session, invoice_id: uuid.UUID, *, exclude_refund_id: uuid.UUID | None = None
) -> int:
    allocated = _invoice_paid_irr(session, invoice_id)
    filters: list[Any] = [
        FinanceRefund.invoice_id == invoice_id,
        FinanceRefund.source == "INVOICE",
        FinanceRefund.status != "REJECTED",
    ]
    if exclude_refund_id is not None:
        filters.append(col(FinanceRefund.id) != exclude_refund_id)
    reserved = session.exec(
        select(func.coalesce(func.sum(FinanceRefund.amount_irr), 0)).where(*filters)
    ).one()
    return allocated - int(reserved)


def _advance_reserved_irr(
    session: Session,
    *,
    credit_id: uuid.UUID,
    exclude_refund_id: uuid.UUID | None = None,
) -> int:
    filters: list[Any] = [
        FinanceRefund.credit_id == credit_id,
        FinanceRefund.source == "ADVANCE",
        FinanceRefund.status != "REJECTED",
    ]
    if exclude_refund_id is not None:
        filters.append(col(FinanceRefund.id) != exclude_refund_id)
    return int(
        session.exec(
            select(func.coalesce(func.sum(FinanceRefund.amount_irr), 0)).where(*filters)
        ).one()
    )


def list_refunds(
    session: Session, *, gym_id: uuid.UUID
) -> FinanceRefundsPublic:
    refunds = session.exec(
        select(FinanceRefund)
        .where(FinanceRefund.gym_id == gym_id)
        .order_by(col(FinanceRefund.created_at).desc())
    ).all()
    return FinanceRefundsPublic(
        data=[_refund_public(refund) for refund in refunds],
        count=len(refunds),
    )


def request_refund(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceRefundCreate,
    operation_key: str,
) -> FinanceRefundPublic:
    scope.require(FINANCE_REFUND_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        refund = session.get(FinanceRefund, operation.result_id)
        if refund is None or refund.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _refund_public(refund)

    customer = _invoice_customer(
        session, gym_id=scope.gym_id, user_id=body.customer_user_id
    )
    credit: FinanceCustomerCredit | None = None
    if body.source == "INVOICE":
        if body.invoice_id is None:
            raise HTTPException(status_code=400, detail="invoice_required")
        invoice = _get_invoice(
            session, gym_id=scope.gym_id, invoice_id=body.invoice_id
        )
        if invoice.customer_user_id != customer.id:
            raise HTTPException(
                status_code=400, detail="receipt_customer_mismatch"
            )
        refundable = _invoice_refundable_irr(session, invoice.id)
        if body.amount_irr > refundable:
            raise HTTPException(
                status_code=400, detail="refund_exceeds_refundable"
            )
    else:
        if body.invoice_id is not None:
            raise HTTPException(status_code=400, detail="invoice_not_allowed")
        credit = _customer_credit(
            session, gym_id=scope.gym_id, customer_user_id=customer.id
        )
        if credit is None:
            raise HTTPException(
                status_code=400, detail="insufficient_customer_credit"
            )
        available = credit.balance_irr - _advance_reserved_irr(
            session, credit_id=credit.id
        )
        if body.amount_irr > available:
            raise HTTPException(
                status_code=400, detail="refund_exceeds_advance"
            )

    original_method = _refund_original_method(
        session,
        invoice_id=body.invoice_id if body.source == "INVOICE" else None,
        credit_id=credit.id if credit else None,
    )
    method, override_reason = _resolve_refund_method(
        requested_method=body.method,
        original_method=original_method,
        override_reason=body.method_override_reason,
    )
    refund = FinanceRefund(
        gym_id=scope.gym_id,
        customer_user_id=customer.id,
        source=body.source,
        invoice_id=body.invoice_id,
        credit_id=credit.id if credit else None,
        amount_irr=body.amount_irr,
        method=method,
        original_method=original_method,
        method_override_reason=override_reason,
        reason=body.reason,
        status="REQUESTED",
        requested_by_id=actor.id,
    )
    session.add(refund)
    session.flush()
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.refund.requested",
        target_type="finance_refund",
        target_id=refund.id,
        reason=body.reason,
        detail={
            "amount_irr": body.amount_irr,
            "source": body.source,
            "method": method,
            "original_method": original_method,
            "method_override_reason": override_reason,
        },
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_refund",
        result_id=refund.id,
    )
    session.commit()
    session.refresh(refund)
    return _refund_public(refund)


def approve_refund(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    refund_id: uuid.UUID,
) -> FinanceRefundPublic:
    scope.require(FINANCE_REFUND_MANAGE)
    refund = _get_refund(session, gym_id=scope.gym_id, refund_id=refund_id)
    if refund.status != "REQUESTED":
        raise HTTPException(status_code=409, detail="refund_not_requested")
    refund.status = "APPROVED"
    refund.approved_by_id = actor.id
    refund.approved_at = utcnow()
    session.add(refund)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.refund.approved",
        target_type="finance_refund",
        target_id=refund.id,
    )
    session.commit()
    session.refresh(refund)
    return _refund_public(refund)


def reject_refund(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    refund_id: uuid.UUID,
    reason: str,
) -> FinanceRefundPublic:
    scope.require(FINANCE_REFUND_MANAGE)
    refund = _get_refund(session, gym_id=scope.gym_id, refund_id=refund_id)
    if refund.status != "REQUESTED":
        raise HTTPException(status_code=409, detail="refund_not_requested")
    refund.status = "REJECTED"
    session.add(refund)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.refund.rejected",
        target_type="finance_refund",
        target_id=refund.id,
        reason=reason,
    )
    session.commit()
    session.refresh(refund)
    return _refund_public(refund)


def record_refund(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    refund_id: uuid.UUID,
    posting_date: date,
    operation_key: str,
) -> FinanceRefundPublic:
    scope.require(FINANCE_REFUND_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_REFUND_MANAGE)
    payload = {"refund_id": str(refund_id), "posting_date": posting_date.isoformat()}
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        refund = session.get(FinanceRefund, operation.result_id)
        if refund is None or refund.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _refund_public(refund)

    refund = _get_refund(session, gym_id=scope.gym_id, refund_id=refund_id)
    if refund.status != "APPROVED":
        raise HTTPException(status_code=409, detail="refund_not_approved")

    accounts = ensure_accounts(session, scope.gym_id)
    if refund.source == "INVOICE":
        if refund.invoice_id is None:
            raise HTTPException(
                status_code=400, detail="finance_refund_not_postable"
            )
        available = _invoice_refundable_irr(
            session, refund.invoice_id, exclude_refund_id=refund.id
        )
        if refund.amount_irr > available:
            raise HTTPException(
                status_code=400, detail="refund_exceeds_refundable"
            )
        lines: list[tuple[uuid.UUID, int, int, str | None]] = [
            (accounts["4100"].id, refund.amount_irr, 0, refund.reason),
            (accounts["1000"].id, 0, refund.amount_irr, refund.reason),
        ]
    else:
        credit = session.get(FinanceCustomerCredit, refund.credit_id)
        if credit is None:
            raise HTTPException(
                status_code=400, detail="finance_refund_not_postable"
            )
        if refund.amount_irr > credit.balance_irr:
            raise HTTPException(
                status_code=400, detail="refund_exceeds_advance"
            )
        credit.balance_irr -= refund.amount_irr
        credit.updated_at = utcnow()
        session.add(credit)
        session.add(
            FinanceCreditMovement(
                credit_id=credit.id,
                kind="REFUNDED",
                amount_irr=refund.amount_irr,
                created_by_id=actor.id,
            )
        )
        lines = [
            (accounts["2000"].id, refund.amount_irr, 0, refund.reason),
            (accounts["1000"].id, 0, refund.amount_irr, refund.reason),
        ]

    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=posting_date,
        event_type="REFUND_RECORDED",
        description=f"Refund: {refund.reason}",
        lines=lines,
        created_by_id=actor.id,
        source_type="finance_refund",
        source_id=refund.id,
    )
    refund.status = "RECORDED"
    refund.journal_id = journal.id
    refund.recorded_at = utcnow()
    session.add(refund)
    _apply_coach_refund(
        session,
        scope=scope,
        actor=actor,
        refund=refund,
        posting_date=posting_date,
    )
    from app.services import platform as platform_service

    platform_service.apply_platform_refund(
        session,
        gym_id=scope.gym_id,
        actor=actor,
        refund=refund,
        posting_date=posting_date,
    )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.refund.recorded",
        target_type="finance_refund",
        target_id=refund.id,
        reason=refund.reason,
        detail={
            "amount_irr": refund.amount_irr,
            "source": refund.source,
            "journal_id": str(journal.id),
        },
    )
    audit(
        "finance.refund.recorded",
        actor_id=actor.id,
        gym_id=scope.gym_id,
        target_id=refund.id,
        detail=f"amount={refund.amount_irr}",
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_refund",
        result_id=refund.id,
    )
    session.commit()
    session.refresh(refund)
    return _refund_public(refund)


def _expense_public(expense: FinanceExpense) -> FinanceExpensePublic:
    return FinanceExpensePublic(
        id=expense.id,
        category=expense.category,
        counterparty=expense.counterparty,
        description=expense.description,
        amount_irr=expense.amount_irr,
        spent_on=expense.spent_on,
        status=expense.status,  # type: ignore[arg-type]
        method=expense.method,  # type: ignore[arg-type]
        paid_at=expense.paid_at,
        recurrence_key=expense.recurrence_key,
        created_at=expense.created_at,
    )


def _get_expense(
    session: Session, *, gym_id: uuid.UUID, expense_id: uuid.UUID
) -> FinanceExpense:
    expense = session.get(FinanceExpense, expense_id)
    if expense is None or expense.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="expense_not_found")
    return expense


def list_expenses(
    session: Session,
    *,
    gym_id: uuid.UUID,
    status: str | None,
    offset: int,
    limit: int,
) -> FinanceExpensesPublic:
    filters = [FinanceExpense.gym_id == gym_id]
    if status:
        filters.append(FinanceExpense.status == status)
    total = session.exec(
        select(func.count(col(FinanceExpense.id))).where(*filters)
    ).one()
    expenses = session.exec(
        select(FinanceExpense)
        .where(*filters)
        .order_by(col(FinanceExpense.spent_on).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return FinanceExpensesPublic(
        data=[_expense_public(expense) for expense in expenses],
        count=int(total),
    )


def get_expense(
    session: Session, *, gym_id: uuid.UUID, expense_id: uuid.UUID
) -> FinanceExpensePublic:
    return _expense_public(
        _get_expense(session, gym_id=gym_id, expense_id=expense_id)
    )


def _post_expense_accrual(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    expense: FinanceExpense,
) -> None:
    accounts = ensure_accounts(session, scope.gym_id)
    lines: list[tuple[uuid.UUID, int, int, str | None]]
    if expense.status == "PAID":
        lines = [
            (accounts["5000"].id, expense.amount_irr, 0, expense.category),
            (accounts["1000"].id, 0, expense.amount_irr, expense.category),
        ]
    else:
        lines = [
            (accounts["5000"].id, expense.amount_irr, 0, expense.category),
            (accounts["2000"].id, 0, expense.amount_irr, expense.category),
        ]
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=expense.spent_on,
        event_type="EXPENSE_RECORDED",
        description=expense.description or expense.category,
        lines=lines,
        created_by_id=actor.id,
        source_type="finance_expense",
        source_id=expense.id,
    )
    expense.journal_id = journal.id
    session.add(expense)


def create_expense(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceExpenseCreate,
    operation_key: str,
) -> FinanceExpensePublic:
    scope.require(FINANCE_EXPENSE_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_EXPENSE_MANAGE)
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        expense = session.get(FinanceExpense, operation.result_id)
        if expense is None or expense.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _expense_public(expense)
    if body.paid and body.method is None:
        raise HTTPException(
            status_code=400, detail="finance_expense_method_required"
        )
    period_key = body.spent_on.strftime("%Y-%m") if body.recurrence_key else None
    if body.recurrence_key is not None:
        duplicate = session.exec(
            select(FinanceExpense).where(
                FinanceExpense.gym_id == scope.gym_id,
                FinanceExpense.recurrence_key == body.recurrence_key,
                FinanceExpense.period_key == period_key,
            )
        ).first()
        if duplicate is not None:
            raise HTTPException(
                status_code=409, detail="expense_recurrence_exists"
            )
    expense = FinanceExpense(
        gym_id=scope.gym_id,
        category=body.category,
        counterparty=body.counterparty,
        description=body.description,
        amount_irr=body.amount_irr,
        spent_on=body.spent_on,
        status="PAID" if body.paid else "UNPAID",
        method=body.method,
        paid_at=utcnow() if body.paid else None,
        recurrence_key=body.recurrence_key,
        period_key=period_key,
        created_by_id=actor.id,
    )
    session.add(expense)
    session.flush()
    _post_expense_accrual(
        session, scope=scope, actor=actor, expense=expense
    )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.expense.recorded",
        target_type="finance_expense",
        target_id=expense.id,
        detail={
            "amount_irr": expense.amount_irr,
            "status": expense.status,
            "category": expense.category,
        },
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_expense",
        result_id=expense.id,
    )
    session.commit()
    session.refresh(expense)
    return _expense_public(expense)


def pay_expense(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    expense_id: uuid.UUID,
    paid_on: date,
    method: str,
    operation_key: str,
) -> FinanceExpensePublic:
    scope.require(FINANCE_EXPENSE_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_EXPENSE_MANAGE)
    payload = {
        "expense_id": str(expense_id),
        "paid_on": paid_on.isoformat(),
        "method": method,
    }
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        expense = session.get(FinanceExpense, operation.result_id)
        if expense is None or expense.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _expense_public(expense)

    expense = _get_expense(session, gym_id=scope.gym_id, expense_id=expense_id)
    if expense.status != "UNPAID":
        raise HTTPException(status_code=409, detail="expense_not_unpaid")
    accounts = ensure_accounts(session, scope.gym_id)
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=paid_on,
        event_type="EXPENSE_PAID",
        description=expense.description or expense.category,
        lines=[
            (accounts["2000"].id, expense.amount_irr, 0, expense.category),
            (accounts["1000"].id, 0, expense.amount_irr, expense.category),
        ],
        created_by_id=actor.id,
        source_type="finance_expense",
        source_id=expense.id,
    )
    expense.status = "PAID"
    expense.method = method
    expense.paid_at = utcnow()
    expense.journal_id = journal.id
    session.add(expense)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.expense.paid",
        target_type="finance_expense",
        target_id=expense.id,
        detail={"amount_irr": expense.amount_irr, "journal_id": str(journal.id)},
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_expense",
        result_id=expense.id,
    )
    session.commit()
    session.refresh(expense)
    return _expense_public(expense)


def repeat_expense(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    expense_id: uuid.UUID,
    spent_on: date,
) -> FinanceExpensePublic:
    scope.require(FINANCE_EXPENSE_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_EXPENSE_MANAGE)
    source = _get_expense(session, gym_id=scope.gym_id, expense_id=expense_id)
    recurrence_key = source.recurrence_key or source.id
    period_key = spent_on.strftime("%Y-%m")
    duplicate = session.exec(
        select(FinanceExpense).where(
            FinanceExpense.gym_id == scope.gym_id,
            FinanceExpense.recurrence_key == recurrence_key,
            FinanceExpense.period_key == period_key,
        )
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="expense_recurrence_exists")
    expense = FinanceExpense(
        gym_id=scope.gym_id,
        category=source.category,
        counterparty=source.counterparty,
        description=source.description,
        amount_irr=source.amount_irr,
        spent_on=spent_on,
        status="UNPAID",
        recurrence_key=recurrence_key,
        period_key=period_key,
        created_by_id=actor.id,
    )
    session.add(expense)
    session.flush()
    _post_expense_accrual(session, scope=scope, actor=actor, expense=expense)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.expense.repeated",
        target_type="finance_expense",
        target_id=expense.id,
        detail={"source_expense_id": str(source.id), "period_key": period_key},
    )
    session.commit()
    session.refresh(expense)
    return _expense_public(expense)


# ---------------------------------------------------------------------------
# Paid gym membership and athlete self-service (Phase 2)
# ---------------------------------------------------------------------------


def _athlete_profile(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> AthleteProfile:
    profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym_id,
            AthleteProfile.user_id == user_id,
        )
    ).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="athlete_not_found")
    return profile


def _get_membership(
    session: Session, *, gym_id: uuid.UUID, membership_id: uuid.UUID
) -> FinanceMembership:
    membership = session.get(FinanceMembership, membership_id)
    if membership is None or membership.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="membership_not_found")
    return membership


def _membership_paid_irr(
    session: Session, membership: FinanceMembership
) -> int:
    if membership.invoice_id is None:
        return 0
    return _invoice_paid_irr(session, membership.invoice_id)


def _derived_membership_status(membership: FinanceMembership) -> str:
    if (
        membership.status in ("ACTIVE", "FROZEN")
        and membership.end_date < utcnow().date()
    ):
        return "EXPIRED"
    return membership.status


def membership_public(
    session: Session, membership: FinanceMembership
) -> FinanceMembershipPublic:
    paid = _membership_paid_irr(session, membership)
    return FinanceMembershipPublic(
        id=membership.id,
        athlete_user_id=membership.athlete_user_id,
        invoice_id=membership.invoice_id,
        start_date=membership.start_date,
        end_date=membership.end_date,
        status=_derived_membership_status(membership),  # type: ignore[arg-type]
        access_required_irr=membership.access_required_irr,
        paid_irr=paid,
        access_granted=paid >= membership.access_required_irr,
        frozen_at=membership.frozen_at,
        frozen_days=membership.frozen_days,
        cancelled_at=membership.cancelled_at,
        updated_at=membership.updated_at,
    )


def _expire_stale_memberships(
    session: Session,
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    on_date: date,
) -> None:
    rows = session.exec(
        select(FinanceMembership).where(
            FinanceMembership.gym_id == gym_id,
            FinanceMembership.athlete_user_id == athlete_user_id,
            col(FinanceMembership.status).in_(("ACTIVE", "FROZEN")),
            FinanceMembership.end_date < on_date,
        )
    ).all()
    for row in rows:
        row.status = "EXPIRED"
        row.updated_at = utcnow()
        session.add(row)


def list_memberships(
    session: Session, *, gym_id: uuid.UUID, athlete_user_id: uuid.UUID | None
) -> FinanceMembershipsPublic:
    statement = select(FinanceMembership).where(
        FinanceMembership.gym_id == gym_id
    )
    if athlete_user_id is not None:
        statement = statement.where(
            FinanceMembership.athlete_user_id == athlete_user_id
        )
    rows = session.exec(
        statement.order_by(col(FinanceMembership.start_date).desc())
    ).all()
    return FinanceMembershipsPublic(
        data=[membership_public(session, row) for row in rows],
        count=len(rows),
    )


def get_membership(
    session: Session, *, gym_id: uuid.UUID, membership_id: uuid.UUID
) -> FinanceMembershipPublic:
    return membership_public(
        session, _get_membership(session, gym_id=gym_id, membership_id=membership_id)
    )


def create_membership(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceMembershipCreate,
) -> FinanceMembershipPublic:
    scope.require(FINANCE_MEMBERSHIP_MANAGE)
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="invalid_membership_dates")
    _athlete_profile(
        session, gym_id=scope.gym_id, user_id=body.athlete_user_id
    )
    if body.invoice_id is not None:
        invoice = _get_invoice(
            session, gym_id=scope.gym_id, invoice_id=body.invoice_id
        )
        if invoice.customer_user_id != body.athlete_user_id:
            raise HTTPException(
                status_code=400, detail="membership_invoice_mismatch"
            )
    elif body.access_required_irr > 0:
        raise HTTPException(
            status_code=400, detail="membership_invoice_required"
        )

    lock_finance_gym(session, scope.gym_id)
    _expire_stale_memberships(
        session,
        gym_id=scope.gym_id,
        athlete_user_id=body.athlete_user_id,
        on_date=body.start_date,
    )
    session.flush()
    existing = session.exec(
        select(FinanceMembership).where(
            FinanceMembership.gym_id == scope.gym_id,
            FinanceMembership.athlete_user_id == body.athlete_user_id,
            col(FinanceMembership.status).in_(("ACTIVE", "FROZEN")),
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="membership_already_active"
        )
    membership = FinanceMembership(
        gym_id=scope.gym_id,
        athlete_user_id=body.athlete_user_id,
        invoice_id=body.invoice_id,
        start_date=body.start_date,
        end_date=body.end_date,
        status="ACTIVE",
        access_required_irr=body.access_required_irr,
        created_by_id=actor.id,
    )
    session.add(membership)
    session.flush()
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.membership.created",
        target_type="finance_membership",
        target_id=membership.id,
        detail={
            "athlete_user_id": str(body.athlete_user_id),
            "start_date": body.start_date.isoformat(),
            "end_date": body.end_date.isoformat(),
        },
    )
    session.commit()
    session.refresh(membership)
    return membership_public(session, membership)


def freeze_membership(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    membership_id: uuid.UUID,
    frozen_on: date,
) -> FinanceMembershipPublic:
    scope.require(FINANCE_MEMBERSHIP_MANAGE)
    membership = _get_membership(
        session, gym_id=scope.gym_id, membership_id=membership_id
    )
    if membership.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="membership_not_active")
    if frozen_on > membership.end_date:
        raise HTTPException(status_code=400, detail="invalid_membership_dates")
    membership.status = "FROZEN"
    membership.frozen_at = frozen_on
    membership.updated_at = utcnow()
    session.add(membership)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.membership.frozen",
        target_type="finance_membership",
        target_id=membership.id,
        detail={"frozen_on": frozen_on.isoformat()},
    )
    session.commit()
    session.refresh(membership)
    return membership_public(session, membership)


def resume_membership(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    membership_id: uuid.UUID,
    resume_on: date,
) -> FinanceMembershipPublic:
    scope.require(FINANCE_MEMBERSHIP_MANAGE)
    membership = _get_membership(
        session, gym_id=scope.gym_id, membership_id=membership_id
    )
    if membership.status != "FROZEN" or membership.frozen_at is None:
        raise HTTPException(status_code=409, detail="membership_not_frozen")
    if resume_on < membership.frozen_at:
        raise HTTPException(status_code=400, detail="invalid_membership_dates")
    paused_days = (resume_on - membership.frozen_at).days
    membership.end_date = membership.end_date + timedelta(days=paused_days)
    membership.frozen_days += paused_days
    membership.frozen_at = None
    membership.status = "ACTIVE"
    membership.updated_at = utcnow()
    session.add(membership)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.membership.resumed",
        target_type="finance_membership",
        target_id=membership.id,
        detail={"resume_on": resume_on.isoformat(), "paused_days": paused_days},
    )
    session.commit()
    session.refresh(membership)
    return membership_public(session, membership)


def cancel_membership(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    membership_id: uuid.UUID,
    cancelled_on: date,
    reason: str | None,
) -> FinanceMembershipPublic:
    scope.require(FINANCE_MEMBERSHIP_MANAGE)
    membership = _get_membership(
        session, gym_id=scope.gym_id, membership_id=membership_id
    )
    if membership.status not in {"ACTIVE", "FROZEN"}:
        raise HTTPException(status_code=409, detail="membership_not_active")
    membership.status = "CANCELLED"
    membership.cancelled_at = cancelled_on
    membership.frozen_at = None
    membership.updated_at = utcnow()
    session.add(membership)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.membership.cancelled",
        target_type="finance_membership",
        target_id=membership.id,
        reason=reason,
        detail={"cancelled_on": cancelled_on.isoformat()},
    )
    session.commit()
    session.refresh(membership)
    return membership_public(session, membership)


def transfer_membership(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    membership_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
) -> FinanceMembershipPublic:
    scope.require(FINANCE_MEMBERSHIP_MANAGE)
    membership = _get_membership(
        session, gym_id=scope.gym_id, membership_id=membership_id
    )
    if membership.status not in {"ACTIVE", "FROZEN"}:
        raise HTTPException(status_code=409, detail="membership_not_active")
    _athlete_profile(
        session, gym_id=scope.gym_id, user_id=athlete_user_id
    )
    if athlete_user_id == membership.athlete_user_id:
        raise HTTPException(status_code=400, detail="membership_same_athlete")
    lock_finance_gym(session, scope.gym_id)
    conflict = session.exec(
        select(FinanceMembership).where(
            FinanceMembership.gym_id == scope.gym_id,
            FinanceMembership.athlete_user_id == athlete_user_id,
            col(FinanceMembership.status).in_(("ACTIVE", "FROZEN")),
        )
    ).first()
    if conflict is not None:
        raise HTTPException(
            status_code=409, detail="membership_already_active"
        )
    previous_athlete_id = membership.athlete_user_id
    membership.athlete_user_id = athlete_user_id
    membership.updated_at = utcnow()
    session.add(membership)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.membership.transferred",
        target_type="finance_membership",
        target_id=membership.id,
        detail={
            "from_athlete_user_id": str(previous_athlete_id),
            "to_athlete_user_id": str(athlete_user_id),
        },
    )
    session.commit()
    session.refresh(membership)
    return membership_public(session, membership)


def membership_refund_preview(
    session: Session,
    *,
    scope: FinanceScope,
    membership_id: uuid.UUID,
    on_date: date,
) -> FinanceRefundPreview:
    membership = _get_membership(
        session, gym_id=scope.gym_id, membership_id=membership_id
    )
    if membership.invoice_id is None:
        raise HTTPException(
            status_code=400, detail="membership_invoice_required"
        )
    refundable = _invoice_refundable_irr(session, membership.invoice_id)
    total_days = (membership.end_date - membership.start_date).days + 1
    unused_days = max(0, min(total_days, (membership.end_date - on_date).days + 1))
    proposed = refundable * unused_days // total_days if total_days else 0
    return FinanceRefundPreview(
        refundable_paid_irr=refundable,
        unused_days=unused_days,
        total_days=total_days,
        proposed_refund_irr=proposed,
    )


def my_account(
    session: Session, *, gym_id: uuid.UUID, user: User
) -> FinanceMyAccountPublic:
    _athlete_profile(session, gym_id=gym_id, user_id=user.id)
    invoices = session.exec(
        select(FinanceInvoice)
        .where(
            FinanceInvoice.gym_id == gym_id,
            FinanceInvoice.customer_user_id == user.id,
            col(FinanceInvoice.status).in_(("ISSUED", "VOID")),
        )
        .order_by(col(FinanceInvoice.created_at).desc())
    ).all()
    receipts = session.exec(
        select(FinanceReceipt)
        .where(
            FinanceReceipt.gym_id == gym_id,
            FinanceReceipt.customer_user_id == user.id,
        )
        .order_by(col(FinanceReceipt.created_at).desc())
    ).all()
    memberships = session.exec(
        select(FinanceMembership)
        .where(
            FinanceMembership.gym_id == gym_id,
            FinanceMembership.athlete_user_id == user.id,
        )
        .order_by(col(FinanceMembership.start_date).desc())
    ).all()
    credit = _customer_credit(
        session, gym_id=gym_id, customer_user_id=user.id
    )
    refunds = session.exec(
        select(FinanceRefund)
        .where(
            FinanceRefund.gym_id == gym_id,
            FinanceRefund.customer_user_id == user.id,
        )
        .order_by(col(FinanceRefund.created_at).desc())
    ).all()
    return FinanceMyAccountPublic(
        invoices=[invoice_public(session, invoice) for invoice in invoices],
        receipts=[receipt_public(session, receipt) for receipt in receipts],
        memberships=[membership_public(session, row) for row in memberships],
        refunds=[_refund_public(refund) for refund in refunds],
        advance_balance_irr=credit.balance_irr if credit else 0,
        reminders=list_reminders(
            session,
            gym_id=gym_id,
            within_days=7,
            customer_user_id=user.id,
        ),
    )


def request_my_refund(
    session: Session,
    *,
    gym_id: uuid.UUID,
    user: User,
    body: FinanceMyRefundCreate,
) -> FinanceRefundPublic:
    _athlete_profile(session, gym_id=gym_id, user_id=user.id)
    invoice = _get_invoice(session, gym_id=gym_id, invoice_id=body.invoice_id)
    if invoice.customer_user_id != user.id:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    refundable = _invoice_refundable_irr(session, invoice.id)
    if body.amount_irr > refundable:
        raise HTTPException(
            status_code=400, detail="refund_exceeds_refundable"
        )
    original_method = _refund_original_method(
        session, invoice_id=invoice.id, credit_id=None
    )
    method, override_reason = _resolve_refund_method(
        requested_method=body.method,
        original_method=original_method,
        override_reason=body.method_override_reason,
    )
    refund = FinanceRefund(
        gym_id=gym_id,
        customer_user_id=user.id,
        source="INVOICE",
        invoice_id=invoice.id,
        amount_irr=body.amount_irr,
        method=method,
        original_method=original_method,
        method_override_reason=override_reason,
        reason=body.reason,
        status="REQUESTED",
        requested_by_id=user.id,
    )
    session.add(refund)
    session.flush()
    record_audit(
        session,
        gym_id=gym_id,
        actor_id=user.id,
        action="finance.refund.requested",
        target_type="finance_refund",
        target_id=refund.id,
        reason=body.reason,
        detail={
            "amount_irr": body.amount_irr,
            "self_service": True,
            "method": method,
            "original_method": original_method,
            "method_override_reason": override_reason,
        },
    )
    session.commit()
    session.refresh(refund)
    return _refund_public(refund)


def _refund_original_method(
    session: Session,
    *,
    invoice_id: uuid.UUID | None,
    credit_id: uuid.UUID | None,
) -> str | None:
    """The method that actually brought the money in, when identifiable."""
    if invoice_id is not None:
        receipt = session.exec(
            select(FinanceReceipt)
            .join(
                FinanceReceiptAllocation,
                col(FinanceReceiptAllocation.receipt_id) == col(FinanceReceipt.id),
            )
            .where(FinanceReceiptAllocation.invoice_id == invoice_id)
            .order_by(col(FinanceReceipt.created_at).desc())
        ).first()
        if receipt is not None:
            return receipt.method
    if credit_id is not None:
        movement = session.exec(
            select(FinanceCreditMovement)
            .where(
                FinanceCreditMovement.credit_id == credit_id,
                FinanceCreditMovement.kind == "RECEIPT_EXCESS",
                col(FinanceCreditMovement.receipt_id).is_not(None),
            )
            .order_by(col(FinanceCreditMovement.created_at).desc())
        ).first()
        if movement is not None and movement.receipt_id is not None:
            receipt = session.get(FinanceReceipt, movement.receipt_id)
            if receipt is not None:
                return receipt.method
    return None


def _resolve_refund_method(
    *,
    requested_method: str | None,
    original_method: str | None,
    override_reason: str | None,
) -> tuple[str, str | None]:
    method = requested_method or original_method
    if method is None:
        raise HTTPException(status_code=400, detail="refund_method_required")
    if original_method is not None and method != original_method:
        if not override_reason or not override_reason.strip():
            raise HTTPException(
                status_code=400, detail="refund_method_reason_required"
            )
        return method, override_reason.strip()
    return method, None


def _invoice_reminder(
    session: Session, invoice: FinanceInvoice
) -> FinanceInstallmentReminder | None:
    today = utcnow().date()
    balance = invoice.total_irr - _invoice_paid_irr(session, invoice.id)
    if balance <= 0:
        return None
    installments = session.exec(
        select(FinanceInstallment)
        .where(FinanceInstallment.invoice_id == invoice.id)
        .order_by(col(FinanceInstallment.sequence))
    ).all()
    if installments:
        first = installments[0]
        due_date = first.due_date
        amount = min(first.amount_irr, balance)
    else:
        if invoice.due_date is None:
            return None
        due_date = invoice.due_date
        amount = balance
    customer = session.get(User, invoice.customer_user_id)
    days_until = (due_date - today).days
    return FinanceInstallmentReminder(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_user_id=invoice.customer_user_id,
        customer_name=invoice.customer_name
        or (customer.full_name or customer.email if customer else None),
        due_date=due_date,
        amount_irr=amount,
        overdue=days_until < 0,
        days_until=days_until,
    )


def _earning_settlement_irr(
    session: Session, earning_id: uuid.UUID, status: str
) -> int:
    value = session.exec(
        select(
            func.coalesce(func.sum(FinanceCoachSettlementItem.amount_irr), 0)
        )
        .join(
            FinanceCoachSettlement,
            col(FinanceCoachSettlementItem.settlement_id)
            == col(FinanceCoachSettlement.id),
        )
        .where(
            FinanceCoachSettlementItem.earning_id == earning_id,
            FinanceCoachSettlement.status == status,
        )
    ).one()
    return int(value)


def _earning_settled_irr(session: Session, earning_id: uuid.UUID) -> int:
    return _earning_settlement_irr(session, earning_id, "CONFIRMED")


def _earning_reserved_irr(session: Session, earning_id: uuid.UUID) -> int:
    return _earning_settlement_irr(session, earning_id, "RECORDED")


def _earning_public(
    session: Session, earning: FinanceCoachEarning, *, today: date | None = None
) -> FinanceCoachEarningPublic:
    today = today or utcnow().date()
    coach = session.get(User, earning.coach_user_id)
    invoice = session.get(FinanceInvoice, earning.invoice_id)
    line = session.get(FinanceInvoiceLine, earning.invoice_line_id)
    receipt = (
        session.get(FinanceReceipt, earning.receipt_id)
        if earning.receipt_id
        else None
    )
    settled = _earning_settled_irr(session, earning.id)
    reserved = _earning_reserved_irr(session, earning.id)
    adjusted = _earning_adjustment_irr(session, earning.id)
    if earning.status == "UNRESOLVED":
        status = "UNRESOLVED"
        vested = False
    else:
        vested = earning.vested_at is not None or (
            earning.vesting_mode == "ON_DATE"
            and earning.vesting_date is not None
            and earning.vesting_date <= today
        )
        status = (
            "SETTLED"
            if settled >= earning.coach_share_irr > 0
            else "VESTED"
            if vested
            else "CALCULATED"
        )
    vested_irr = earning.coach_share_irr if vested else 0
    return FinanceCoachEarningPublic(
        id=earning.id,
        coach_user_id=earning.coach_user_id,
        coach_name=(coach.full_name or coach.email) if coach else None,
        invoice_id=earning.invoice_id,
        invoice_number=invoice.invoice_number if invoice else None,
        line_description=line.description if line else None,
        receipt_id=earning.receipt_id,
        receipt_number=receipt.receipt_number if receipt else None,
        agreement_id=earning.agreement_id,
        agreement_version=earning.agreement_version,
        discount_funding=earning.discount_funding,
        base_irr=earning.base_irr,
        discount_irr=earning.discount_irr,
        coach_share_irr=earning.coach_share_irr,
        platform_share_irr=earning.platform_share_irr,
        gym_share_irr=earning.gym_share_irr,
        calculated_irr=earning.coach_share_irr,
        vested_irr=vested_irr,
        settled_irr=settled,
        reserved_irr=reserved,
        adjusted_irr=adjusted,
        eligible_irr=max(vested_irr - settled - reserved - adjusted, 0),
        status=status,  # type: ignore[arg-type]
        unresolved_reason=earning.unresolved_reason,
        vesting_mode=earning.vesting_mode,
        vesting_date=earning.vesting_date,
        vested_at=earning.vested_at,
        created_at=earning.created_at,
    )


def list_coach_earnings(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID | None = None,
) -> FinanceCoachEarningsPublic:
    filters: list[Any] = [FinanceCoachEarning.gym_id == gym_id]
    if coach_user_id is not None:
        filters.append(FinanceCoachEarning.coach_user_id == coach_user_id)
    rows = session.exec(
        select(FinanceCoachEarning)
        .where(*filters)
        .order_by(col(FinanceCoachEarning.created_at).desc())
    ).all()
    today = utcnow().date()
    return FinanceCoachEarningsPublic(
        data=[_earning_public(session, row, today=today) for row in rows],
        count=len(rows),
    )


def get_coach_earning(
    session: Session, *, gym_id: uuid.UUID, earning_id: uuid.UUID
) -> FinanceCoachEarningPublic:
    earning = session.get(FinanceCoachEarning, earning_id)
    if earning is None or earning.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_earning_not_found")
    return _earning_public(session, earning)


def vest_coach_earning(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    earning_id: uuid.UUID,
    body: FinanceCoachVestingCreate,
) -> FinanceCoachEarningPublic:
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    earning = session.get(FinanceCoachEarning, earning_id)
    if earning is None or earning.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="coach_earning_not_found")
    if earning.status == "UNRESOLVED":
        raise HTTPException(status_code=409, detail="coach_earning_unresolved")
    if earning.vesting_mode == "ON_DATE" and earning.vested_at is None:
        raise HTTPException(
            status_code=409, detail="coach_earning_not_manual_vesting"
        )
    if earning.vested_at is None:
        earning.vested_at = utcnow()
        earning.vested_by_id = actor.id
        earning.vesting_reason = body.reason
        session.add(earning)
        record_audit(
            session,
            gym_id=scope.gym_id,
            actor_id=actor.id,
            action="finance.coach_earning.vested",
            target_type="finance_coach_earning",
            target_id=earning.id,
            reason=body.reason,
            detail={"coach_share_irr": earning.coach_share_irr},
        )
        session.commit()
        session.refresh(earning)
    return _earning_public(session, earning)


def _earning_adjustment_irr(session: Session, earning_id: uuid.UUID) -> int:
    value = session.exec(
        select(
            func.coalesce(
                func.sum(FinanceCoachEarningAdjustment.applied_irr), 0
            )
        ).where(FinanceCoachEarningAdjustment.earning_id == earning_id)
    ).one()
    return int(value)


def _settlement_public(
    session: Session, settlement: FinanceCoachSettlement
) -> FinanceCoachSettlementPublic:
    coach = session.get(User, settlement.coach_user_id)
    items = session.exec(
        select(FinanceCoachSettlementItem).where(
            FinanceCoachSettlementItem.settlement_id == settlement.id
        )
    ).all()
    public_items: list[FinanceCoachSettlementItemPublic] = []
    for item in items:
        earning = session.get(FinanceCoachEarning, item.earning_id)
        invoice = (
            session.get(FinanceInvoice, earning.invoice_id) if earning else None
        )
        line = (
            session.get(FinanceInvoiceLine, earning.invoice_line_id)
            if earning
            else None
        )
        public_items.append(
            FinanceCoachSettlementItemPublic(
                earning_id=item.earning_id,
                invoice_id=earning.invoice_id if earning else item.earning_id,
                invoice_number=invoice.invoice_number if invoice else None,
                line_description=line.description if line else None,
                amount_irr=item.amount_irr,
            )
        )
    return FinanceCoachSettlementPublic(
        id=settlement.id,
        coach_user_id=settlement.coach_user_id,
        coach_name=(coach.full_name or coach.email) if coach else None,
        amount_irr=settlement.amount_irr,
        method=settlement.method,  # type: ignore[arg-type]
        reference=settlement.reference,
        paid_on=settlement.paid_on,
        notes=settlement.notes,
        status=settlement.status,  # type: ignore[arg-type]
        items=public_items,
        created_at=settlement.created_at,
        confirmed_at=settlement.confirmed_at,
        cancelled_at=settlement.cancelled_at,
        cancel_reason=settlement.cancel_reason,
    )


def _eligible_earnings(
    session: Session, *, gym_id: uuid.UUID, coach_user_id: uuid.UUID
) -> list[tuple[FinanceCoachEarning, int]]:
    today = utcnow().date()
    rows = session.exec(
        select(FinanceCoachEarning)
        .where(
            FinanceCoachEarning.gym_id == gym_id,
            FinanceCoachEarning.coach_user_id == coach_user_id,
            FinanceCoachEarning.status == "CALCULATED",
        )
        .order_by(col(FinanceCoachEarning.created_at))
    ).all()
    eligible: list[tuple[FinanceCoachEarning, int]] = []
    for row in rows:
        vested = row.vested_at is not None or (
            row.vesting_mode == "ON_DATE"
            and row.vesting_date is not None
            and row.vesting_date <= today
        )
        if not vested:
            continue
        remaining = (
            row.coach_share_irr
            - _earning_settled_irr(session, row.id)
            - _earning_reserved_irr(session, row.id)
            - _earning_adjustment_irr(session, row.id)
        )
        if remaining > 0:
            eligible.append((row, remaining))
    return eligible


def create_coach_settlement(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceCoachSettlementCreate,
    operation_key: str,
) -> FinanceCoachSettlementPublic:
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    if not _is_gym_coach(
        session, gym_id=scope.gym_id, user_id=body.coach_user_id
    ):
        raise HTTPException(status_code=400, detail="invalid_settlement_coach")
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        settlement = session.get(FinanceCoachSettlement, operation.result_id)
        if settlement is None or settlement.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _settlement_public(session, settlement)

    eligible = _eligible_earnings(
        session, gym_id=scope.gym_id, coach_user_id=body.coach_user_id
    )
    total = sum(value for _, value in eligible)
    if body.amount_irr > total:
        raise HTTPException(
            status_code=400, detail="settlement_exceeds_eligible"
        )

    accounts = ensure_accounts(session, scope.gym_id)
    settlement = FinanceCoachSettlement(
        gym_id=scope.gym_id,
        coach_user_id=body.coach_user_id,
        amount_irr=body.amount_irr,
        method=body.method,
        reference=body.reference,
        paid_on=body.paid_on,
        notes=body.notes,
        status="RECORDED",
        created_by_id=actor.id,
    )
    session.add(settlement)
    session.flush()
    remaining = body.amount_irr
    for earning, available in eligible:
        if remaining == 0:
            break
        take = min(available, remaining)
        session.add(
            FinanceCoachSettlementItem(
                settlement_id=settlement.id,
                earning_id=earning.id,
                amount_irr=take,
            )
        )
        remaining -= take
    if remaining:
        raise HTTPException(
            status_code=400, detail="settlement_exceeds_eligible"
        )
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=body.paid_on,
        event_type="COACH_SETTLEMENT",
        description="Coach settlement",
        lines=[
            (accounts["2100"].id, body.amount_irr, 0, "Coach payable"),
            (accounts["2200"].id, 0, body.amount_irr, "Pending coach payout"),
        ],
        created_by_id=actor.id,
        source_type="finance_coach_settlement",
        source_id=settlement.id,
    )
    settlement.journal_id = journal.id
    session.add(settlement)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_settlement.recorded",
        target_type="finance_coach_settlement",
        target_id=settlement.id,
        detail={
            "coach_user_id": str(body.coach_user_id),
            "amount_irr": body.amount_irr,
            "journal_id": str(journal.id),
        },
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_coach_settlement",
        result_id=settlement.id,
    )
    session.commit()
    session.refresh(settlement)
    return _settlement_public(session, settlement)


def confirm_coach_settlement(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    settlement_id: uuid.UUID,
) -> FinanceCoachSettlementPublic:
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    settlement = session.get(FinanceCoachSettlement, settlement_id)
    if settlement is None or settlement.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if settlement.status == "CONFIRMED":
        return _settlement_public(session, settlement)
    if settlement.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="settlement_cancelled")
    if settlement.status != "RECORDED":
        raise HTTPException(status_code=409, detail="settlement_not_recorded")
    items = session.exec(
        select(FinanceCoachSettlementItem).where(
            FinanceCoachSettlementItem.settlement_id == settlement.id
        )
    ).all()
    earned_ids = {item.earning_id for item in items}
    for earning_id in earned_ids:
        earning = session.get(FinanceCoachEarning, earning_id)
        if earning is None:
            raise HTTPException(status_code=409, detail="settlement_stale")
        available = (
            earning.coach_share_irr
            - _earning_settled_irr(session, earning.id)
            - _earning_reserved_irr(session, earning.id)
            - _earning_adjustment_irr(session, earning.id)
        )
        if available < 0:
            raise HTTPException(status_code=409, detail="settlement_stale")
    accounts = ensure_accounts(session, scope.gym_id)
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=settlement.paid_on,
        event_type="COACH_SETTLED",
        description="Coach settlement confirmed",
        lines=[
            (accounts["2200"].id, settlement.amount_irr, 0, "Pending coach payout"),
            (accounts["1000"].id, 0, settlement.amount_irr, "Coach payout"),
        ],
        created_by_id=actor.id,
        source_type="finance_coach_settlement",
        source_id=settlement.id,
    )
    settlement.status = "CONFIRMED"
    settlement.confirmed_by_id = actor.id
    settlement.confirmed_at = utcnow()
    settlement.confirmed_journal_id = journal.id
    session.add(settlement)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_settlement.confirmed",
        target_type="finance_coach_settlement",
        target_id=settlement.id,
        detail={"journal_id": str(journal.id)},
    )
    session.commit()
    session.refresh(settlement)
    return _settlement_public(session, settlement)


def cancel_coach_settlement(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    settlement_id: uuid.UUID,
    body: FinanceCoachSettlementCancel,
) -> FinanceCoachSettlementPublic:
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    settlement = session.get(FinanceCoachSettlement, settlement_id)
    if settlement is None or settlement.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if settlement.status == "CANCELLED":
        return _settlement_public(session, settlement)
    if settlement.status != "RECORDED":
        raise HTTPException(status_code=409, detail="settlement_not_recorded")
    accounts = ensure_accounts(session, scope.gym_id)
    journal = post_journal(
        session,
        gym_id=scope.gym_id,
        posting_date=utcnow().date(),
        event_type="COACH_SETTLE_CANCEL",
        description="Coach settlement cancelled",
        lines=[
            (accounts["2200"].id, settlement.amount_irr, 0, "Pending coach payout"),
            (accounts["2100"].id, 0, settlement.amount_irr, "Coach payable"),
        ],
        created_by_id=actor.id,
        source_type="finance_coach_settlement",
        source_id=settlement.id,
    )
    settlement.status = "CANCELLED"
    settlement.cancelled_by_id = actor.id
    settlement.cancelled_at = utcnow()
    settlement.cancel_reason = body.reason
    settlement.cancel_journal_id = journal.id
    session.add(settlement)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_settlement.cancelled",
        target_type="finance_coach_settlement",
        target_id=settlement.id,
        reason=body.reason,
        detail={"journal_id": str(journal.id)},
    )
    session.commit()
    session.refresh(settlement)
    return _settlement_public(session, settlement)


def list_coach_settlements(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID | None = None,
) -> FinanceCoachSettlementsPublic:
    filters: list[Any] = [FinanceCoachSettlement.gym_id == gym_id]
    if coach_user_id is not None:
        filters.append(FinanceCoachSettlement.coach_user_id == coach_user_id)
    rows = session.exec(
        select(FinanceCoachSettlement)
        .where(*filters)
        .order_by(col(FinanceCoachSettlement.created_at).desc())
    ).all()
    return FinanceCoachSettlementsPublic(
        data=[_settlement_public(session, row) for row in rows],
        count=len(rows),
    )


def get_coach_settlement(
    session: Session, *, gym_id: uuid.UUID, settlement_id: uuid.UUID
) -> FinanceCoachSettlementPublic:
    settlement = session.get(FinanceCoachSettlement, settlement_id)
    if settlement is None or settlement.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    return _settlement_public(session, settlement)


def _apply_coach_refund(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    refund: FinanceRefund,
    posting_date: date,
) -> int:
    if refund.source != "INVOICE" or refund.invoice_id is None:
        return 0
    paid = _invoice_paid_irr(session, refund.invoice_id)
    if paid <= 0:
        return 0
    earnings = session.exec(
        select(FinanceCoachEarning)
        .where(
            FinanceCoachEarning.gym_id == scope.gym_id,
            FinanceCoachEarning.invoice_id == refund.invoice_id,
            FinanceCoachEarning.coach_share_irr > 0,
        )
        .order_by(col(FinanceCoachEarning.created_at))
    ).all()
    if not earnings:
        return 0
    shares = [row.coach_share_irr for row in earnings]
    total_share = sum(shares)
    reversal_total = total_share * refund.amount_irr // paid
    if reversal_total <= 0:
        return 0
    reversals = _split_proportional(reversal_total, shares)
    adjustments: list[FinanceCoachEarningAdjustment] = []
    applied_total = 0
    for earning, reversal in zip(earnings, reversals, strict=True):
        if reversal <= 0:
            continue
        settled = _earning_settled_irr(session, earning.id)
        previous = _earning_adjustment_irr(session, earning.id)
        unsettled = max(earning.coach_share_irr - settled - previous, 0)
        applied = min(reversal, unsettled)
        discrepancy = reversal - applied
        adjustment = FinanceCoachEarningAdjustment(
            gym_id=scope.gym_id,
            earning_id=earning.id,
            refund_id=refund.id,
            amount_irr=reversal,
            applied_irr=applied,
            discrepancy_irr=discrepancy,
        )
        session.add(adjustment)
        adjustments.append(adjustment)
        applied_total += applied
        if discrepancy > 0:
            session.add(
                FinanceCoachDiscrepancy(
                    gym_id=scope.gym_id,
                    coach_user_id=earning.coach_user_id,
                    invoice_id=earning.invoice_id,
                    earning_id=earning.id,
                    refund_id=refund.id,
                    amount_irr=discrepancy,
                    status="OPEN",
                )
            )
    if not adjustments:
        return 0
    session.flush()
    if applied_total > 0:
        accounts = ensure_accounts(session, scope.gym_id)
        journal = post_journal(
            session,
            gym_id=scope.gym_id,
            posting_date=posting_date,
            event_type="COACH_ADJUSTMENT",
            description=f"Coach refund adjustment: {refund.reason}",
            lines=[
                (accounts["2100"].id, applied_total, 0, "Coach payable reversal"),
                (accounts["5100"].id, 0, applied_total, "Coach share reversal"),
            ],
            created_by_id=actor.id,
            source_type="finance_refund",
            source_id=refund.id,
        )
        for adjustment in adjustments:
            if adjustment.applied_irr > 0:
                adjustment.journal_id = journal.id
                session.add(adjustment)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_refund.adjusted",
        target_type="finance_refund",
        target_id=refund.id,
        detail={
            "reversal_irr": reversal_total,
            "applied_irr": applied_total,
            "discrepancy_irr": reversal_total - applied_total,
        },
    )
    return reversal_total - applied_total


def _discrepancy_public(
    session: Session, row: FinanceCoachDiscrepancy
) -> FinanceCoachDiscrepancyPublic:
    coach = session.get(User, row.coach_user_id)
    invoice = session.get(FinanceInvoice, row.invoice_id)
    return FinanceCoachDiscrepancyPublic(
        id=row.id,
        coach_user_id=row.coach_user_id,
        coach_name=(coach.full_name or coach.email) if coach else None,
        invoice_id=row.invoice_id,
        invoice_number=invoice.invoice_number if invoice else None,
        earning_id=row.earning_id,
        refund_id=row.refund_id,
        amount_irr=row.amount_irr,
        status=row.status,  # type: ignore[arg-type]
        resolution_note=row.resolution_note,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
    )


def list_coach_discrepancies(
    session: Session, *, gym_id: uuid.UUID, status: str | None = None
) -> FinanceCoachDiscrepanciesPublic:
    filters: list[Any] = [FinanceCoachDiscrepancy.gym_id == gym_id]
    if status is not None:
        filters.append(FinanceCoachDiscrepancy.status == status)
    rows = session.exec(
        select(FinanceCoachDiscrepancy)
        .where(*filters)
        .order_by(col(FinanceCoachDiscrepancy.created_at).desc())
    ).all()
    return FinanceCoachDiscrepanciesPublic(
        data=[_discrepancy_public(session, row) for row in rows],
        count=len(rows),
    )


def resolve_coach_discrepancy(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    discrepancy_id: uuid.UUID,
    body: FinanceCoachDiscrepancyResolve,
) -> FinanceCoachDiscrepancyPublic:
    scope.require(FINANCE_SETTLEMENT_MANAGE)
    row = session.get(FinanceCoachDiscrepancy, discrepancy_id)
    if row is None or row.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="coach_discrepancy_not_found")
    if row.status == "RESOLVED":
        raise HTTPException(
            status_code=409, detail="coach_discrepancy_already_resolved"
        )
    row.status = "RESOLVED"
    row.resolution_note = body.resolution_note
    row.resolved_by_id = actor.id
    row.resolved_at = utcnow()
    session.add(row)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_discrepancy.resolved",
        target_type="finance_coach_discrepancy",
        target_id=row.id,
        reason=body.resolution_note,
        detail={"amount_irr": row.amount_irr},
    )
    session.commit()
    session.refresh(row)
    return _discrepancy_public(session, row)


def resolve_coach_earning(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    earning_id: uuid.UUID,
    body: FinanceCoachEarningResolve,
) -> FinanceCoachEarningPublic:
    scope.require(FINANCE_COACH_AGREEMENT_MANAGE)
    earning = session.get(FinanceCoachEarning, earning_id)
    if earning is None or earning.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="coach_earning_not_found")
    if earning.status != "UNRESOLVED":
        raise HTTPException(status_code=409, detail="coach_earning_not_unresolved")
    agreement = session.get(FinanceCoachAgreement, body.agreement_id)
    if (
        agreement is None
        or agreement.gym_id != scope.gym_id
        or agreement.coach_user_id != earning.coach_user_id
        or agreement.status != "ACTIVE"
    ):
        raise HTTPException(status_code=400, detail="invalid_coach_agreement")
    snapshot = _agreement_snapshot(session, agreement)
    coach, platform, gym = _allocate_coach_shares(
        snapshot,
        base_irr=earning.base_irr,
        discount_irr=earning.discount_irr,
        discount_funding=earning.discount_funding,
    )
    earning.agreement_id = agreement.id
    earning.agreement_version = agreement.version
    earning.coach_share_irr = coach
    earning.platform_share_irr = platform
    earning.gym_share_irr = gym
    earning.status = "CALCULATED"
    earning.unresolved_reason = None
    earning.vesting_mode = agreement.vesting_mode
    earning.vesting_date = (
        earning.created_at.date() + timedelta(days=agreement.vesting_days)
        if agreement.vesting_mode == "ON_DATE"
        else None
    )
    session.add(earning)
    if coach > 0:
        accounts = ensure_accounts(session, scope.gym_id)
        journal = post_journal(
            session,
            gym_id=scope.gym_id,
            posting_date=earning.created_at.date(),
            event_type="COACH_ALLOCATION",
            description="Coach allocation resolved manually",
            lines=[
                (accounts["5100"].id, coach, 0, "Coach share"),
                (accounts["2100"].id, 0, coach, "Coach payable"),
            ],
            created_by_id=actor.id,
            source_type="finance_coach_earning",
            source_id=earning.id,
        )
        earning.journal_id = journal.id
        session.add(earning)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_earning.resolved",
        target_type="finance_coach_earning",
        target_id=earning.id,
        reason=body.reason,
        detail={"agreement_id": str(agreement.id), "coach_share_irr": coach},
    )
    session.commit()
    session.refresh(earning)
    return _earning_public(session, earning)


def accrue_coach_period(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    agreement_id: uuid.UUID,
    body: FinanceCoachPeriodAccrual,
    operation_key: str,
) -> FinanceExpensePublic:
    scope.require(FINANCE_COACH_AGREEMENT_MANAGE)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_COACH_AGREEMENT_MANAGE)
    agreement = session.get(FinanceCoachAgreement, agreement_id)
    if agreement is None or agreement.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="coach_agreement_not_found")
    if agreement.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="coach_agreement_not_active")
    if (
        agreement.periodic_interval != "MONTHLY"
        or agreement.periodic_fixed_irr <= 0
    ):
        raise HTTPException(status_code=400, detail="coach_periodic_not_configured")
    try:
        year, month = (int(part) for part in body.period.split("-"))
        spent_on = date(year, month, 1)
        month_end = date(
            year, month, calendar.monthrange(year, month)[1]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_coach_period") from exc
    if spent_on < agreement.effective_from or (
        agreement.effective_to is not None
        and month_end > agreement.effective_to
    ):
        raise HTTPException(
            status_code=400, detail="coach_period_outside_agreement"
        )
    payload = {"agreement_id": str(agreement.id), "period": body.period}
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        expense = session.get(FinanceExpense, operation.result_id)
        if expense is None or expense.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _expense_public(expense)
    duplicate = session.exec(
        select(FinanceExpense).where(
            FinanceExpense.gym_id == scope.gym_id,
            FinanceExpense.recurrence_key == agreement.id,
            FinanceExpense.period_key == body.period,
        )
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=409, detail="expense_recurrence_exists"
        )
    coach = session.get(User, agreement.coach_user_id)
    expense = FinanceExpense(
        gym_id=scope.gym_id,
        category="حقوق ثابت مربی",
        counterparty=(coach.full_name or coach.email) if coach else None,
        description=f"Periodic coach compensation {body.period}",
        amount_irr=agreement.periodic_fixed_irr,
        spent_on=spent_on,
        status="UNPAID",
        method=None,
        paid_at=None,
        recurrence_key=agreement.id,
        period_key=body.period,
        created_by_id=actor.id,
    )
    session.add(expense)
    session.flush()
    _post_expense_accrual(session, scope=scope, actor=actor, expense=expense)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_periodic.accrued",
        target_type="finance_coach_agreement",
        target_id=agreement.id,
        detail={"period": body.period, "expense_id": str(expense.id)},
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_expense",
        result_id=expense.id,
    )
    session.commit()
    session.refresh(expense)
    return _expense_public(expense)

def _reconciliation_public(
    session: Session, row: FinanceBankStatementLine
) -> FinanceBankStatementLinePublic:
    receipt = (
        session.get(FinanceReceipt, row.receipt_id) if row.receipt_id else None
    )
    return FinanceBankStatementLinePublic(
        id=row.id,
        statement_on=row.statement_on,
        amount_irr=row.amount_irr,
        reference=row.reference,
        description=row.description,
        status=row.status,  # type: ignore[arg-type]
        receipt_id=row.receipt_id,
        receipt_number=receipt.receipt_number if receipt else None,
        matched_at=row.matched_at,
        created_at=row.created_at,
    )


def list_bank_statement_lines(
    session: Session, *, gym_id: uuid.UUID, status: str | None = None
) -> FinanceBankStatementLinesPublic:
    filters: list[Any] = [FinanceBankStatementLine.gym_id == gym_id]
    if status is not None:
        filters.append(FinanceBankStatementLine.status == status)
    rows = session.exec(
        select(FinanceBankStatementLine)
        .where(*filters)
        .order_by(
            col(FinanceBankStatementLine.statement_on).desc(),
            col(FinanceBankStatementLine.created_at).desc(),
        )
    ).all()
    return FinanceBankStatementLinesPublic(
        data=[_reconciliation_public(session, row) for row in rows],
        count=len(rows),
    )


def create_bank_statement_line(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceBankStatementLineCreate,
    operation_key: str,
) -> FinanceBankStatementLinePublic:
    scope.require(FINANCE_PAYMENT_RECORD)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_PAYMENT_RECORD)
    payload = body.model_dump(mode="json")
    operation = find_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if operation is not None:
        row = session.get(FinanceBankStatementLine, operation.result_id)
        if row is None or row.gym_id != scope.gym_id:
            raise HTTPException(status_code=409, detail="idempotency_key_reused")
        return _reconciliation_public(session, row)
    row = FinanceBankStatementLine(
        gym_id=scope.gym_id,
        statement_on=body.statement_on,
        amount_irr=body.amount_irr,
        reference=body.reference,
        description=body.description,
        created_by_id=actor.id,
    )
    session.add(row)
    session.flush()
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.reconciliation.imported",
        target_type="finance_bank_statement_line",
        target_id=row.id,
        detail={"amount_irr": body.amount_irr},
    )
    remember_operation(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
        result_type="finance_bank_statement_line",
        result_id=row.id,
    )
    session.commit()
    session.refresh(row)
    return _reconciliation_public(session, row)


def match_bank_statement_line(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    line_id: uuid.UUID,
    body: FinanceReconciliationMatchCreate,
) -> FinanceBankStatementLinePublic:
    scope.require(FINANCE_PAYMENT_RECORD)
    lock_finance_gym(session, scope.gym_id)
    scope = reload_finance_scope(session, scope)
    scope.require_enabled()
    scope.require(FINANCE_PAYMENT_RECORD)
    row = session.get(FinanceBankStatementLine, line_id)
    if row is None or row.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="reconciliation_line_not_found")
    if row.status == "MATCHED":
        if row.receipt_id == body.receipt_id:
            return _reconciliation_public(session, row)
        raise HTTPException(status_code=409, detail="reconciliation_already_matched")
    receipt = session.get(FinanceReceipt, body.receipt_id)
    if receipt is None or receipt.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="receipt_not_found")
    if receipt.status != "CONFIRMED":
        raise HTTPException(status_code=409, detail="receipt_not_confirmed")
    if receipt.amount_irr != row.amount_irr:
        raise HTTPException(
            status_code=400, detail="reconciliation_amount_mismatch"
        )
    already = session.exec(
        select(FinanceBankStatementLine).where(
            FinanceBankStatementLine.receipt_id == body.receipt_id
        )
    ).first()
    if already is not None and already.id != row.id:
        raise HTTPException(status_code=409, detail="reconciliation_already_matched")
    row.status = "MATCHED"
    row.receipt_id = receipt.id
    row.matched_by_id = actor.id
    row.matched_at = utcnow()
    receipt.reconciled_at = utcnow()
    session.add(row)
    session.add(receipt)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.reconciliation.matched",
        target_type="finance_bank_statement_line",
        target_id=row.id,
        detail={
            "receipt_id": str(receipt.id),
            "receipt_number": receipt.receipt_number,
            "amount_irr": row.amount_irr,
        },
    )
    session.commit()
    session.refresh(row)
    return _reconciliation_public(session, row)


def list_reminders(
    session: Session,
    *,
    gym_id: uuid.UUID,
    within_days: int,
    customer_user_id: uuid.UUID | None = None,
) -> FinanceRemindersPublic:
    """Compute due installments and renewals on read; no scheduler is used."""
    today = utcnow().date()
    horizon = today + timedelta(days=within_days)
    invoice_filters: list[Any] = [
        FinanceInvoice.gym_id == gym_id,
        FinanceInvoice.status == "ISSUED",
    ]
    if customer_user_id is not None:
        invoice_filters.append(
            FinanceInvoice.customer_user_id == customer_user_id
        )
    invoices = session.exec(select(FinanceInvoice).where(*invoice_filters)).all()
    installment_reminders: list[FinanceInstallmentReminder] = []
    for invoice in invoices:
        reminder = _invoice_reminder(session, invoice)
        if reminder is not None and reminder.due_date <= horizon:
            installment_reminders.append(reminder)

    membership_filters: list[Any] = [
        FinanceMembership.gym_id == gym_id,
        FinanceMembership.status == "ACTIVE",
        FinanceMembership.end_date <= horizon,
    ]
    if customer_user_id is not None:
        membership_filters.append(
            FinanceMembership.athlete_user_id == customer_user_id
        )
    memberships = session.exec(
        select(FinanceMembership).where(*membership_filters)
    ).all()
    renewal_reminders: list[FinanceRenewalReminder] = []
    for membership in memberships:
        athlete = session.get(User, membership.athlete_user_id)
        days_until = (membership.end_date - today).days
        renewal_reminders.append(
            FinanceRenewalReminder(
                membership_id=membership.id,
                athlete_user_id=membership.athlete_user_id,
                athlete_name=(athlete.full_name or athlete.email)
                if athlete
                else None,
                end_date=membership.end_date,
                days_until=days_until,
                overdue=days_until < 0,
            )
        )

    installment_reminders.sort(key=lambda item: item.due_date)
    renewal_reminders.sort(key=lambda item: item.end_date)
    return FinanceRemindersPublic(
        within_days=within_days,
        installments=installment_reminders,
        renewals=renewal_reminders,
    )


# ---------------------------------------------------------------------------
# Versioned coach agreements (Phase 3)
# ---------------------------------------------------------------------------


def _agreement_public(
    session: Session, agreement: FinanceCoachAgreement
) -> FinanceCoachAgreementPublic:
    coach = session.get(User, agreement.coach_user_id)
    terms = session.exec(
        select(FinanceCoachAgreementTerm)
        .where(FinanceCoachAgreementTerm.agreement_id == agreement.id)
        .order_by(col(FinanceCoachAgreementTerm.sequence))
    ).all()
    return FinanceCoachAgreementPublic(
        id=agreement.id,
        coach_user_id=agreement.coach_user_id,
        coach_name=(coach.full_name or coach.email) if coach else None,
        version=agreement.version,
        status=agreement.status,  # type: ignore[arg-type]
        mode=agreement.mode,  # type: ignore[arg-type]
        vesting_mode=agreement.vesting_mode,  # type: ignore[arg-type]
        vesting_days=agreement.vesting_days,
        periodic_fixed_irr=agreement.periodic_fixed_irr,
        periodic_interval=agreement.periodic_interval,
        effective_from=agreement.effective_from,
        effective_to=agreement.effective_to,
        notes=agreement.notes,
        terms=[
            FinanceCoachAgreementTermPublic(
                id=term.id,
                sequence=term.sequence,
                recipient=term.recipient,  # type: ignore[arg-type]
                basis=term.basis,  # type: ignore[arg-type]
                percent_bp=term.percent_bp,
                fixed_irr=term.fixed_irr,
                label=term.label,
            )
            for term in terms
        ],
        created_at=agreement.created_at,
        activated_at=agreement.activated_at,
    )


def _is_gym_coach(session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return (
        session.exec(
            select(GymMembership)
            .join(
                GymMembershipRole,
                col(GymMembershipRole.membership_id) == col(GymMembership.id),
            )
            .where(
                GymMembership.gym_id == gym_id,
                GymMembership.user_id == user_id,
                col(GymMembership.is_active).is_(True),
                GymMembershipRole.role == "COACH",
            )
        ).first()
        is not None
    )


def _validate_agreement_terms(
    terms: Sequence[Any],
) -> None:
    if not any(term.recipient == "COACH" for term in terms):
        raise HTTPException(status_code=400, detail="coach_term_required")
    for term in terms:
        if term.basis == "PERCENT":
            if term.percent_bp <= 0 or term.percent_bp > 10_000 or term.fixed_irr:
                raise HTTPException(status_code=400, detail="invalid_coach_term")
        elif term.fixed_irr <= 0 or term.percent_bp:
            raise HTTPException(status_code=400, detail="invalid_coach_term")


def create_coach_agreement(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceCoachAgreementCreate,
) -> FinanceCoachAgreementPublic:
    scope.require(FINANCE_COACH_AGREEMENT_MANAGE)
    if not _is_gym_coach(session, gym_id=scope.gym_id, user_id=body.coach_user_id):
        raise HTTPException(
            status_code=400, detail="invalid_coach_agreement_coach"
        )
    if body.effective_to is not None and body.effective_to < body.effective_from:
        raise HTTPException(
            status_code=400, detail="invalid_coach_agreement_dates"
        )
    _validate_agreement_terms(body.terms)
    if body.periodic_interval == "MONTHLY" and body.periodic_fixed_irr <= 0:
        raise HTTPException(status_code=400, detail="invalid_coach_periodic")
    if body.periodic_interval == "NONE" and body.periodic_fixed_irr:
        raise HTTPException(status_code=400, detail="invalid_coach_periodic")
    if any(term.recipient == "ASCORA" for term in body.terms) and not (
        scope.is_superuser
    ):
        raise HTTPException(status_code=403, detail="superuser_required")
    latest = session.exec(
        select(FinanceCoachAgreement)
        .where(
            FinanceCoachAgreement.gym_id == scope.gym_id,
            FinanceCoachAgreement.coach_user_id == body.coach_user_id,
        )
        .order_by(col(FinanceCoachAgreement.version).desc())
    ).first()
    agreement = FinanceCoachAgreement(
        gym_id=scope.gym_id,
        coach_user_id=body.coach_user_id,
        version=(latest.version + 1) if latest else 1,
        mode=body.mode,
        vesting_mode=body.vesting_mode,
        vesting_days=body.vesting_days,
        periodic_fixed_irr=body.periodic_fixed_irr,
        periodic_interval=body.periodic_interval,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        notes=body.notes,
        created_by_id=actor.id,
    )
    session.add(agreement)
    session.flush()
    for sequence, item in enumerate(body.terms, start=1):
        session.add(
            FinanceCoachAgreementTerm(
                agreement_id=agreement.id,
                sequence=sequence,
                recipient=item.recipient,
                basis=item.basis,
                percent_bp=item.percent_bp,
                fixed_irr=item.fixed_irr,
                label=item.label,
            )
        )
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_agreement.created",
        target_type="finance_coach_agreement",
        target_id=agreement.id,
        detail={"version": agreement.version, "coach_user_id": str(body.coach_user_id)},
    )
    session.commit()
    session.refresh(agreement)
    return _agreement_public(session, agreement)


def list_coach_agreements(
    session: Session,
    *,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID | None = None,
) -> FinanceCoachAgreementsPublic:
    filters: list[Any] = [FinanceCoachAgreement.gym_id == gym_id]
    if coach_user_id is not None:
        filters.append(FinanceCoachAgreement.coach_user_id == coach_user_id)
    agreements = session.exec(
        select(FinanceCoachAgreement)
        .where(*filters)
        .order_by(
            col(FinanceCoachAgreement.coach_user_id),
            col(FinanceCoachAgreement.version).desc(),
        )
    ).all()
    return FinanceCoachAgreementsPublic(
        data=[_agreement_public(session, row) for row in agreements],
        count=len(agreements),
    )


def get_coach_agreement(
    session: Session, *, gym_id: uuid.UUID, agreement_id: uuid.UUID
) -> FinanceCoachAgreementPublic:
    agreement = session.get(FinanceCoachAgreement, agreement_id)
    if agreement is None or agreement.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_agreement_not_found")
    return _agreement_public(session, agreement)


def activate_coach_agreement(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    agreement_id: uuid.UUID,
) -> FinanceCoachAgreementPublic:
    scope.require(FINANCE_COACH_AGREEMENT_MANAGE)
    agreement = session.get(FinanceCoachAgreement, agreement_id)
    if agreement is None or agreement.gym_id != scope.gym_id:
        raise HTTPException(status_code=404, detail="coach_agreement_not_found")
    if agreement.status != "DRAFT":
        raise HTTPException(status_code=409, detail="coach_agreement_not_draft")
    terms = session.exec(
        select(FinanceCoachAgreementTerm).where(
            FinanceCoachAgreementTerm.agreement_id == agreement.id
        )
    ).all()
    _validate_agreement_terms(terms)
    if any(term.recipient == "ASCORA" for term in terms) and not (
        scope.is_superuser
    ):
        raise HTTPException(status_code=403, detail="superuser_required")
    agreement.status = "ACTIVE"
    agreement.activated_by_id = actor.id
    agreement.activated_at = utcnow()
    session.add(agreement)
    record_audit(
        session,
        gym_id=scope.gym_id,
        actor_id=actor.id,
        action="finance.coach_agreement.activated",
        target_type="finance_coach_agreement",
        target_id=agreement.id,
        detail={"version": agreement.version},
    )
    session.commit()
    session.refresh(agreement)
    return _agreement_public(session, agreement)


def gym_summary(
    session: Session,
    *,
    gym_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> Any:
    from app.platform_models import PlatformReceivable

    def journal_totals(codes: tuple[str, ...]) -> tuple[int, int]:
        rows = session.exec(
            select(
                func.coalesce(func.sum(FinanceJournalLine.debit_irr), 0),
                func.coalesce(func.sum(FinanceJournalLine.credit_irr), 0),
            )
            .join(
                FinanceAccount,
                col(FinanceJournalLine.account_id) == col(FinanceAccount.id),
            )
            .join(
                FinanceJournal,
                col(FinanceJournalLine.journal_id) == col(FinanceJournal.id),
            )
            .where(
                FinanceJournal.gym_id == gym_id,
                col(FinanceAccount.code).in_(codes),
                FinanceJournal.posting_date >= from_date,
                FinanceJournal.posting_date <= to_date,
                FinanceJournal.event_type != "OPENING_BALANCE",
            )
        ).one()
        return int(rows[0]), int(rows[1])

    def cash_event(event_type: str) -> int:
        rows = session.exec(
            select(
                func.coalesce(func.sum(FinanceJournalLine.debit_irr), 0),
                func.coalesce(func.sum(FinanceJournalLine.credit_irr), 0),
            )
            .join(
                FinanceAccount,
                col(FinanceJournalLine.account_id) == col(FinanceAccount.id),
            )
            .join(
                FinanceJournal,
                col(FinanceJournalLine.journal_id) == col(FinanceJournal.id),
            )
            .where(
                FinanceJournal.gym_id == gym_id,
                FinanceJournal.event_type == event_type,
                FinanceJournal.posting_date >= from_date,
                FinanceJournal.posting_date <= to_date,
                FinanceAccount.code == "1000",
            )
        ).one()
        return int(rows[0]) - int(rows[1])

    cash_collected = cash_event("RECEIPT_CONFIRMED")
    cash_refunded = -cash_event("REFUND_RECORDED")
    cash_expenses = -cash_event("EXPENSE_PAID")
    cash_settlements = -cash_event("COACH_SETTLED")

    revenue_debit, revenue_credit = journal_totals(("4000", "4100"))
    expense_debit, expense_credit = journal_totals(("5000", "5100"))
    recognized_revenue = revenue_credit - revenue_debit
    platform_rows = session.exec(
        select(PlatformReceivable).where(PlatformReceivable.gym_id == gym_id)
    ).all()
    platform_accrued = sum(
        row.amount_irr
        for row in platform_rows
        if from_date <= row.created_at.date() <= to_date
    )
    recognized_expenses = max(expense_debit - expense_credit, 0) + platform_accrued
    estimated_profit = recognized_revenue - recognized_expenses

    invoices = session.exec(
        select(FinanceInvoice).where(
            FinanceInvoice.gym_id == gym_id,
            col(FinanceInvoice.status).in_(("ISSUED", "VOID")),
        )
    ).all()
    sales = sum(
        row.total_irr
        for row in invoices
        if row.issue_date is not None
        and from_date <= row.issue_date <= to_date
        and row.status == "ISSUED"
    )
    receivable = 0
    overdue = 0
    today = utcnow().date()
    for invoice in invoices:
        if invoice.status != "ISSUED":
            continue
        paid = _invoice_paid_irr(session, invoice.id)
        balance = max(invoice.total_irr - paid, 0)
        receivable += balance
        if invoice.due_date is not None and invoice.due_date < today:
            overdue += balance
    renewals = session.exec(
        select(FinanceMembership).where(
            FinanceMembership.gym_id == gym_id,
            col(FinanceMembership.status).in_(("ACTIVE", "FROZEN")),
            FinanceMembership.end_date >= today,
            FinanceMembership.end_date <= today + timedelta(days=30),
        )
    ).all()
    earnings = session.exec(
        select(FinanceCoachEarning).where(FinanceCoachEarning.gym_id == gym_id)
    ).all()
    coach_payable = sum(
        max(
            row.coach_share_irr
            - _earning_settled_irr(session, row.id)
            - _earning_reserved_irr(session, row.id)
            - _earning_adjustment_irr(session, row.id),
            0,
        )
        for row in earnings
    )
    platform_payable = sum(
        max(row.amount_irr - row.paid_irr, 0)
        for row in platform_rows
        if row.status in ("OPEN", "INVOICED", "PARTIAL")
    )
    from app.finance_models import FinanceGymSummaryPublic

    return FinanceGymSummaryPublic(
        cash_collected_irr=cash_collected,
        cash_refunded_irr=cash_refunded,
        cash_expenses_paid_irr=cash_expenses,
        cash_coach_settlements_irr=cash_settlements,
        net_cashflow_irr=(
            cash_collected
            - cash_refunded
            - cash_expenses
            - cash_settlements
        ),
        recognized_revenue_irr=recognized_revenue,
        recognized_expenses_irr=recognized_expenses,
        estimated_operating_profit_irr=estimated_profit,
        sales_irr=sales,
        receivable_irr=receivable,
        overdue_irr=overdue,
        renewals_due=len(renewals),
        coach_payable_irr=coach_payable,
        platform_payable_irr=platform_payable,
    )
