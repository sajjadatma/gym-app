from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.deps import GymContext
from app.finance_models import (
    FINANCE_OPENING_MANAGE,
    FINANCE_PERIOD_MANAGE,
    FINANCE_VIEW,
    FinanceAccount,
    FinanceAudit,
    FinanceGrant,
    FinanceGrantItem,
    FinanceGrantRow,
    FinanceGrantsPublic,
    FinanceGrantUpdate,
    FinanceJournal,
    FinanceJournalLine,
    FinanceJournalLinePublic,
    FinanceJournalPublic,
    FinanceJournalsPublic,
    FinanceOpeningBalanceCreate,
    FinanceOperation,
    FinancePeriod,
    FinancePeriodPublic,
    FinancePeriodsPublic,
    FinancePermissionName,
    FinanceSequence,
    FinanceSettings,
    FinanceSettingsPublic,
    GrantableFinancePermission,
)
from app.models import User

ADMIN_PERMISSIONS: tuple[FinancePermissionName, ...] = (
    FINANCE_VIEW,
    FINANCE_OPENING_MANAGE,
    FINANCE_PERIOD_MANAGE,
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
    ("3000", "سرمایه افتتاحیه", "EQUITY"),
    ("4000", "درآمد", "INCOME"),
    ("5000", "هزینه‌ها", "EXPENSE"),
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
            settings=settings,
            is_admin=True,
            is_superuser=current_user.is_superuser,
            grants={},
        )
    if "FINANCE_STAFF" in ctx.roles:
        return FinanceScope(
            gym_id=ctx.gym.id,
            settings=settings,
            is_admin=False,
            is_superuser=False,
            grants=_grants_for(session, ctx.gym.id, current_user.id),
        )
    raise HTTPException(status_code=403, detail="finance_access_denied")


@dataclass(frozen=True)
class FinanceScope:
    gym_id: uuid.UUID
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


def _lock_finance_gym(session: Session, gym_id: uuid.UUID) -> None:
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


def _allocate_entry_number(session: Session, gym_id: uuid.UUID) -> int:
    sequence = session.exec(
        select(FinanceSequence).where(
            FinanceSequence.gym_id == gym_id,
            FinanceSequence.doc_type == JOURNAL_DOC_TYPE,
        )
    ).first()
    if sequence is None:
        sequence = FinanceSequence(
            gym_id=gym_id, doc_type=JOURNAL_DOC_TYPE, last_value=0
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
) -> FinanceJournal:
    _lock_finance_gym(session, gym_id)
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
        entry_number=_allocate_entry_number(session, gym_id),
        posting_date=posting_date,
        event_type=event_type,
        description=description,
        reversal_of_id=reversal_of_id,
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


def _replay(
    session: Session, *, gym_id: uuid.UUID, operation_key: str, payload: dict[str, Any]
) -> FinanceJournal | None:
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
    session.add(
        FinanceOperation(
            gym_id=gym_id,
            operation_key=operation_key,
            request_hash=_request_hash(payload),
            result_type="finance_journal",
            result_id=journal.id,
        )
    )


def post_opening_balance(
    session: Session,
    *,
    scope: FinanceScope,
    actor: User,
    body: FinanceOpeningBalanceCreate,
    operation_key: str,
) -> FinanceJournalPublic:
    scope.require_enabled()
    scope.require(FINANCE_OPENING_MANAGE)
    _lock_finance_gym(session, scope.gym_id)
    payload = body.model_dump(mode="json")
    replay = _replay(
        session,
        gym_id=scope.gym_id,
        operation_key=operation_key,
        payload=payload,
    )
    if replay is not None:
        return journal_public(session, replay)

    existing = session.exec(
        select(FinanceJournal).where(
            FinanceJournal.gym_id == scope.gym_id,
            FinanceJournal.event_type == "OPENING_BALANCE",
        )
    ).first()
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
    posting_date: date | None,
    operation_key: str,
) -> FinanceJournalPublic:
    scope.require_enabled()
    if not actor.is_superuser:
        raise HTTPException(status_code=403, detail="superuser_required")
    _lock_finance_gym(session, scope.gym_id)
    payload = {
        "journal_id": str(journal_id),
        "reason": reason,
        "posting_date": posting_date.isoformat() if posting_date else None,
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
        posting_date=posting_date or utcnow().date(),
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
    scope.require_enabled()
    scope.require(FINANCE_PERIOD_MANAGE)
    _lock_finance_gym(session, scope.gym_id)
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
    if not active_finance_staff(
        session, gym_id=scope.gym_id, user_id=target_user_id
    ):
        raise HTTPException(status_code=400, detail="finance_staff_required")

    _lock_finance_gym(session, scope.gym_id)
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
