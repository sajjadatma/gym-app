from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Final, Literal

from pydantic import EmailStr, model_validator
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc

FinanceDisplayUnit = Literal["RIAL", "TOMAN"]
FinanceAccountType = Literal["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"]
FinanceJournalEvent = Literal[
    "OPENING_BALANCE",
    "CORRECTION",
    "INVOICE_ISSUED",
    "INVOICE_VOID",
    "RECEIPT_CONFIRMED",
    "ADVANCE_APPLIED",
    "REFUND_RECORDED",
    "EXPENSE_RECORDED",
    "EXPENSE_PAID",
]

FinancePermissionName = Literal[
    "finance.view",
    "finance.opening.manage",
    "finance.period.manage",
    "finance.catalog.manage",
    "finance.invoice.manage",
    "finance.payment.record",
    "finance.refund.manage",
    "finance.expense.manage",
    "finance.membership.manage",
    "finance.coach_agreement.manage",
    "finance.settlement.manage",
]

GrantableFinancePermission = Literal[
    "finance.opening.manage",
    "finance.period.manage",
    "finance.catalog.manage",
    "finance.invoice.manage",
    "finance.payment.record",
    "finance.refund.manage",
    "finance.expense.manage",
    "finance.membership.manage",
    "finance.coach_agreement.manage",
    "finance.settlement.manage",
]

FINANCE_VIEW: Final[FinancePermissionName] = "finance.view"
FINANCE_OPENING_MANAGE: Final[FinancePermissionName] = "finance.opening.manage"
FINANCE_PERIOD_MANAGE: Final[FinancePermissionName] = "finance.period.manage"
FINANCE_CATALOG_MANAGE: Final[FinancePermissionName] = "finance.catalog.manage"
FINANCE_INVOICE_MANAGE: Final[FinancePermissionName] = "finance.invoice.manage"
FINANCE_PAYMENT_RECORD: Final[FinancePermissionName] = "finance.payment.record"
FINANCE_REFUND_MANAGE: Final[FinancePermissionName] = "finance.refund.manage"
FINANCE_EXPENSE_MANAGE: Final[FinancePermissionName] = "finance.expense.manage"
FINANCE_MEMBERSHIP_MANAGE: Final[FinancePermissionName] = "finance.membership.manage"
FINANCE_COACH_AGREEMENT_MANAGE: Final[FinancePermissionName] = "finance.coach_agreement.manage"
FINANCE_SETTLEMENT_MANAGE: Final[FinancePermissionName] = "finance.settlement.manage"

# Guardrail for the JavaScript-safe integer transport. 10^15 IRR is one
# hundred trillion toman, far above any gym amount and below 2^53.
MAX_FINANCE_IRR = 10**15


class FinanceSettings(SQLModel, table=True):
    __tablename__ = "finance_settings"
    __table_args__ = (
        CheckConstraint(
            "display_unit IN ('RIAL', 'TOMAN')",
            name="ck_finance_settings_display_unit",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", unique=True, index=True
    )
    enabled: bool = Field(default=True)
    display_unit: str = Field(default="RIAL", max_length=10)
    timezone: str = Field(default="Asia/Tehran", max_length=64)
    updated_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceAudit(SQLModel, table=True):
    """Durable, append-only record of financially sensitive mutations.

    Rows are written in the same transaction as the mutation they describe;
    the log-based ``app.audit`` event remains the security-monitoring trail.
    """

    __tablename__ = "finance_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    action: str = Field(max_length=64, index=True)
    target_type: str = Field(max_length=32)
    target_id: uuid.UUID | None = Field(default=None)
    reason: str | None = Field(default=None, max_length=500)
    detail: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)



class FinanceSettingsUpdate(SQLModel):
    enabled: bool | None = None
    display_unit: FinanceDisplayUnit | None = None


class FinanceSettingsPublic(SQLModel):
    enabled: bool
    display_unit: FinanceDisplayUnit
    timezone: str
    can_manage: bool
    can_toggle: bool
    permissions: list[str]


# ---------------------------------------------------------------------------
# Chart of accounts, periods and sequence
# ---------------------------------------------------------------------------


class FinanceAccount(SQLModel, table=True):
    __tablename__ = "finance_account"
    __table_args__ = (
        UniqueConstraint("gym_id", "code", name="uq_finance_account_gym_code"),
        CheckConstraint(
            "type IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')",
            name="ck_finance_account_type",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    code: str = Field(max_length=20)
    name: str = Field(max_length=100)
    type: str = Field(max_length=20)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinancePeriod(SQLModel, table=True):
    """A running accounting period. Closing it starts the next one lazily."""

    __tablename__ = "finance_period"
    __table_args__ = (
        Index(
            "uq_finance_period_open",
            "gym_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    opened_at: datetime = Field(default_factory=get_datetime_utc)
    closed_at: datetime | None = Field(default=None)
    closed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceSequence(SQLModel, table=True):
    __tablename__ = "finance_sequence"
    __table_args__ = (
        UniqueConstraint("gym_id", "doc_type", name="uq_finance_sequence_doc"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    doc_type: str = Field(max_length=20)
    last_value: int = Field(default=0)


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


class FinanceJournal(SQLModel, table=True):
    __tablename__ = "finance_journal"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "entry_number", name="uq_finance_journal_number"
        ),
        # A gym may have several opening journals across corrections. Only
        # one may be un-reversed at a time; the service enforces that under
        # the per-gym finance lock because SQL cannot express it here.
        Index(
            "uq_finance_journal_reversal",
            "reversal_of_id",
            unique=True,
            postgresql_where=text("reversal_of_id IS NOT NULL"),
        ),
        CheckConstraint(
            "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
            "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
            "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
            "'EXPENSE_PAID')",
            name="ck_finance_journal_event",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    period_id: uuid.UUID = Field(
        foreign_key="finance_period.id", ondelete="RESTRICT", index=True
    )
    entry_number: int
    posting_date: date
    event_type: str = Field(max_length=20)
    description: str | None = Field(default=None, max_length=500)
    reversal_of_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_journal.id", ondelete="RESTRICT"
    )
    source_type: str | None = Field(default=None, max_length=32)
    source_id: uuid.UUID | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceJournalLine(SQLModel, table=True):
    __tablename__ = "finance_journal_line"
    __table_args__ = (
        CheckConstraint(
            "debit_irr >= 0 AND credit_irr >= 0",
            name="ck_finance_line_nonnegative",
        ),
        CheckConstraint(
            "(debit_irr > 0) <> (credit_irr > 0)",
            name="ck_finance_line_single_side",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    journal_id: uuid.UUID = Field(
        foreign_key="finance_journal.id", ondelete="CASCADE", index=True
    )
    account_id: uuid.UUID = Field(
        foreign_key="finance_account.id", ondelete="RESTRICT", index=True
    )
    debit_irr: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    credit_irr: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    memo: str | None = Field(default=None, max_length=200)


class FinanceGrant(SQLModel, table=True):
    """A gym-scoped finance action grant for a finance staff member.

    ``finance.view`` is implicit for the role; only actions are granted, with
    an optional per-grant IRR ceiling.
    """

    __tablename__ = "finance_grant"
    __table_args__ = (
        Index(
            "uq_finance_grant_active",
            "gym_id",
            "user_id",
            "permission",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        CheckConstraint(
            "permission IN ('finance.opening.manage', "
            "'finance.period.manage', 'finance.catalog.manage', "
            "'finance.invoice.manage', 'finance.payment.record', "
            "'finance.refund.manage', 'finance.expense.manage', "
            "'finance.membership.manage')",
            name="ck_finance_grant_permission",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    permission: str = Field(max_length=40)
    amount_limit_irr: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    granted_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    revoked_at: datetime | None = Field(default=None)


class FinanceOperation(SQLModel, table=True):
    """Idempotency record: one stored result per gym and client key."""

    __tablename__ = "finance_operation"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "operation_key", name="uq_finance_operation_key"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    operation_key: str = Field(max_length=100)
    request_hash: str = Field(max_length=64)
    result_type: str = Field(max_length=32)
    result_id: uuid.UUID
    created_at: datetime = Field(default_factory=get_datetime_utc)


# ---------------------------------------------------------------------------
# Public/input models
# ---------------------------------------------------------------------------


class FinanceAccountPublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    type: FinanceAccountType


class FinanceAccountsPublic(SQLModel):
    data: list[FinanceAccountPublic]
    count: int


class FinanceJournalLinePublic(SQLModel):
    id: uuid.UUID
    account_code: str
    account_name: str
    debit_irr: int
    credit_irr: int
    memo: str | None = None


class FinanceJournalPublic(SQLModel):
    id: uuid.UUID
    entry_number: int
    posting_date: date
    event_type: FinanceJournalEvent
    description: str | None = None
    reversal_of_id: uuid.UUID | None = None
    source_type: str | None = None
    source_id: uuid.UUID | None = None
    period_id: uuid.UUID
    created_by_id: uuid.UUID | None = None
    created_by_name: str | None = None
    created_at: datetime
    lines: list[FinanceJournalLinePublic]


class FinanceJournalsPublic(SQLModel):
    data: list[FinanceJournalPublic]
    count: int


class FinanceOpeningBalanceLine(SQLModel):
    account_code: str = Field(min_length=1, max_length=20)
    debit_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)
    credit_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)
    memo: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def exactly_one_side(self) -> FinanceOpeningBalanceLine:
        if (self.debit_irr > 0) == (self.credit_irr > 0):
            raise ValueError(
                "exactly one of debit_irr or credit_irr must be positive"
            )
        return self


class FinanceOpeningBalanceCreate(SQLModel):
    posting_date: date
    description: str | None = Field(default=None, max_length=500)
    lines: list[FinanceOpeningBalanceLine] = Field(min_length=2)


class FinanceJournalCorrectionCreate(SQLModel):
    reason: str = Field(min_length=3, max_length=500)
    # Posting dates are explicit gym-local calendar dates supplied by the
    # authorized operator; instants stay in UTC. Reporting-range conversion
    # using the gym timezone arrives with Phase 4 reports.
    posting_date: date


class FinanceGrantItem(SQLModel):
    permission: GrantableFinancePermission
    amount_limit_irr: int | None = Field(
        default=None, ge=0, le=MAX_FINANCE_IRR
    )


class FinanceGrantUpdate(SQLModel):
    grants: list[FinanceGrantItem]

    @model_validator(mode="after")
    def unique_permissions(self) -> FinanceGrantUpdate:
        permissions = [item.permission for item in self.grants]
        if len(permissions) != len(set(permissions)):
            raise ValueError("duplicate finance permission")
        return self


class FinanceGrantRow(SQLModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    grants: list[FinanceGrantItem]


class FinanceGrantsPublic(SQLModel):
    data: list[FinanceGrantRow]
    count: int


class FinancePeriodPublic(SQLModel):
    id: uuid.UUID
    opened_at: datetime
    closed_at: datetime | None = None
    status: Literal["OPEN", "CLOSED"]


class FinancePeriodsPublic(SQLModel):
    data: list[FinancePeriodPublic]
    count: int



# ---------------------------------------------------------------------------
# Commercial catalog and customer invoices (Phase 2)
# ---------------------------------------------------------------------------

FinanceLineKind = Literal[
    "MEMBERSHIP",
    "PROGRAM",
    "SESSION",
    "PACK",
    "PRODUCT",
    "SERVICE",
    "CUSTOM",
]
FinanceInvoiceStatus = Literal["DRAFT", "ISSUED", "VOID"]
FinanceAcquisitionSource = Literal["GYM", "ASCORA"]
FinanceDiscountFunding = Literal["GYM", "COACH", "ASCORA", "MIXED"]


class FinanceCatalogItem(SQLModel, table=True):
    __tablename__ = "finance_catalog_item"
    __table_args__ = (
        UniqueConstraint("gym_id", "name", name="uq_finance_catalog_gym_name"),
        CheckConstraint(
            "kind IN ('MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', 'PRODUCT', "
            "'SERVICE', 'CUSTOM')",
            name="ck_finance_catalog_kind",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(max_length=20)
    default_price_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    is_active: bool = Field(default=True)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceCatalogItemCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    kind: FinanceLineKind
    default_price_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)


class FinanceCatalogItemUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: FinanceLineKind | None = None
    default_price_irr: int | None = Field(
        default=None, ge=0, le=MAX_FINANCE_IRR
    )
    is_active: bool | None = None


class FinanceCatalogItemPublic(SQLModel):
    id: uuid.UUID
    name: str
    kind: FinanceLineKind
    default_price_irr: int
    is_active: bool


class FinanceCatalogPublic(SQLModel):
    data: list[FinanceCatalogItemPublic]
    count: int


class FinanceInvoice(SQLModel, table=True):
    __tablename__ = "finance_invoice"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "invoice_number", name="uq_finance_invoice_number"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'VOID')",
            name="ck_finance_invoice_status",
        ),
        CheckConstraint(
            "acquisition_source IN ('GYM', 'ASCORA')",
            name="ck_finance_invoice_source",
        ),
        CheckConstraint(
            "discount_funding IN ('GYM', 'COACH', 'ASCORA', 'MIXED')",
            name="ck_finance_invoice_discount_funding",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    customer_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    customer_name: str | None = Field(default=None, max_length=255)
    status: str = Field(default="DRAFT", max_length=20, index=True)
    # Snapshotted at sale time; Phase 3 uses these for allocation.
    acquisition_source: str = Field(default="GYM", max_length=20)
    discount_funding: str = Field(default="GYM", max_length=20)
    invoice_number: int | None = Field(default=None)
    issue_date: date | None = Field(default=None)
    due_date: date | None = Field(default=None)
    description: str | None = Field(default=None, max_length=1000)
    subtotal_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    discount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    total_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    void_reason: str | None = Field(default=None, max_length=500)
    voided_at: datetime | None = Field(default=None)
    journal_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_journal.id", ondelete="RESTRICT"
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    issued_at: datetime | None = Field(default=None)


class FinanceInvoiceLine(SQLModel, table=True):
    __tablename__ = "finance_invoice_line"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "line_number", name="uq_finance_invoice_line_number"
        ),
        CheckConstraint("quantity > 0", name="ck_finance_invoice_line_qty"),
        CheckConstraint(
            "unit_price_irr >= 0 AND line_discount_irr >= 0 "
            "AND net_irr >= 0 AND discount_share_irr >= 0 AND payable_irr >= 0",
            name="ck_finance_invoice_line_amounts",
        ),
        CheckConstraint(
            "kind IN ('MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', 'PRODUCT', "
            "'SERVICE', 'CUSTOM')",
            name="ck_finance_invoice_line_kind",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    invoice_id: uuid.UUID = Field(
        foreign_key="finance_invoice.id", ondelete="CASCADE", index=True
    )
    line_number: int
    catalog_item_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_catalog_item.id", ondelete="RESTRICT"
    )
    kind: str = Field(max_length=20)
    description: str = Field(max_length=255)
    quantity: int = Field(default=1)
    unit_price_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    line_discount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    net_irr: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    discount_share_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    payable_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )


class FinanceInstallment(SQLModel, table=True):
    __tablename__ = "finance_installment"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "sequence", name="uq_finance_installment_sequence"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    invoice_id: uuid.UUID = Field(
        foreign_key="finance_invoice.id", ondelete="CASCADE", index=True
    )
    sequence: int
    due_date: date
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )


class FinanceInvoiceLineInput(SQLModel):
    catalog_item_id: uuid.UUID | None = None
    kind: FinanceLineKind
    description: str = Field(min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1, le=10_000)
    unit_price_irr: int = Field(ge=0, le=MAX_FINANCE_IRR)
    line_discount_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)
    # Optional explicit share of the invoice-level bundle discount. When one
    # line provides it, every line must, and the shares must sum exactly.
    bundle_discount_irr: int | None = Field(default=None, ge=0, le=MAX_FINANCE_IRR)


class FinanceInstallmentInput(SQLModel):
    due_date: date
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)


class FinanceInvoiceCreate(SQLModel):
    customer_user_id: uuid.UUID
    acquisition_source: FinanceAcquisitionSource = "GYM"
    discount_funding: FinanceDiscountFunding = "GYM"
    description: str | None = Field(default=None, max_length=1000)
    due_date: date | None = None
    discount_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)
    lines: list[FinanceInvoiceLineInput] = Field(min_length=1)
    installments: list[FinanceInstallmentInput] | None = None


class FinanceInvoiceUpdate(FinanceInvoiceCreate):
    pass


class FinanceInvoiceIssueCreate(SQLModel):
    posting_date: date


class FinanceInvoiceVoidCreate(SQLModel):
    reason: str = Field(min_length=3, max_length=500)
    posting_date: date


class FinanceInvoiceLinePublic(SQLModel):
    id: uuid.UUID
    line_number: int
    catalog_item_id: uuid.UUID | None = None
    kind: FinanceLineKind
    description: str
    quantity: int
    unit_price_irr: int
    line_discount_irr: int
    net_irr: int
    discount_share_irr: int
    payable_irr: int


class FinanceInstallmentPublic(SQLModel):
    id: uuid.UUID
    sequence: int
    due_date: date
    amount_irr: int


class FinanceInvoicePublic(SQLModel):
    id: uuid.UUID
    status: FinanceInvoiceStatus
    acquisition_source: FinanceAcquisitionSource = "GYM"
    discount_funding: FinanceDiscountFunding = "GYM"
    invoice_number: int | None = None
    customer_user_id: uuid.UUID
    customer_name: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    description: str | None = None
    subtotal_irr: int
    discount_irr: int
    total_irr: int
    paid_irr: int
    balance_irr: int
    overdue: bool
    void_reason: str | None = None
    created_at: datetime
    issued_at: datetime | None = None
    lines: list[FinanceInvoiceLinePublic]
    installments: list[FinanceInstallmentPublic]


class FinanceInvoicesPublic(SQLModel):
    data: list[FinanceInvoicePublic]
    count: int


# ---------------------------------------------------------------------------
# Manual receipts, allocations and customer advances (Phase 2)
# ---------------------------------------------------------------------------

FinancePaymentMethod = Literal["CASH", "POS", "TRANSFER"]
FinanceReceiptStatus = Literal["CONFIRMED", "REVERSED"]
FinanceCreditMovementKind = Literal["RECEIPT_EXCESS", "APPLIED", "REFUNDED"]


class FinanceReceipt(SQLModel, table=True):
    __tablename__ = "finance_receipt"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "receipt_number", name="uq_finance_receipt_number"
        ),
        CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_receipt_method",
        ),
        CheckConstraint(
            "status IN ('CONFIRMED', 'REVERSED')",
            name="ck_finance_receipt_status",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_receipt_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    customer_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    customer_name: str | None = Field(default=None, max_length=255)
    receipt_number: int
    method: str = Field(max_length=20)
    amount_irr: int = Field(sa_column=Column(BigInteger, nullable=False))
    reference: str | None = Field(default=None, max_length=255)
    received_on: date
    status: str = Field(default="CONFIRMED", max_length=20)
    # Declared by an authorized operator (manual cash/POS/transfer). Online
    # gateway verification is a separate, later source.
    verification_source: str = Field(default="STAFF_ATTESTATION", max_length=32)
    reconciled_at: datetime | None = Field(default=None)
    journal_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_journal.id", ondelete="RESTRICT"
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceReceiptAllocation(SQLModel, table=True):
    __tablename__ = "finance_receipt_allocation"
    __table_args__ = (
        UniqueConstraint(
            "receipt_id", "invoice_id", name="uq_finance_allocation_receipt_invoice"
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_allocation_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    receipt_id: uuid.UUID = Field(
        foreign_key="finance_receipt.id", ondelete="CASCADE", index=True
    )
    invoice_id: uuid.UUID = Field(
        foreign_key="finance_invoice.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int = Field(sa_column=Column(BigInteger, nullable=False))


class FinanceCustomerCredit(SQLModel, table=True):
    """A refundable, non-transferable advance inside one gym."""

    __tablename__ = "finance_customer_credit"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "customer_user_id", name="uq_finance_credit_gym_customer"
        ),
        CheckConstraint("balance_irr >= 0", name="ck_finance_credit_balance"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    customer_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    balance_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceCreditMovement(SQLModel, table=True):
    __tablename__ = "finance_credit_movement"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('RECEIPT_EXCESS', 'APPLIED', 'REFUNDED')",
            name="ck_finance_credit_movement_kind",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_credit_movement_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    credit_id: uuid.UUID = Field(
        foreign_key="finance_customer_credit.id", ondelete="CASCADE", index=True
    )
    kind: str = Field(max_length=20)
    amount_irr: int = Field(sa_column=Column(BigInteger, nullable=False))
    receipt_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_receipt.id", ondelete="RESTRICT"
    )
    invoice_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_invoice.id", ondelete="RESTRICT"
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceReceiptAllocationInput(SQLModel):
    invoice_id: uuid.UUID
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)


class FinanceReceiptCreate(SQLModel):
    customer_user_id: uuid.UUID
    method: FinancePaymentMethod
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)
    reference: str | None = Field(default=None, max_length=255)
    received_on: date
    allocations: list[FinanceReceiptAllocationInput] = Field(
        default_factory=list
    )


class FinanceCreditApplyCreate(SQLModel):
    customer_user_id: uuid.UUID
    invoice_id: uuid.UUID
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)
    received_on: date


class FinanceReceiptAllocationPublic(SQLModel):
    invoice_id: uuid.UUID
    invoice_number: int | None = None
    amount_irr: int


class FinanceReceiptPublic(SQLModel):
    id: uuid.UUID
    receipt_number: int
    customer_user_id: uuid.UUID
    customer_name: str | None = None
    method: FinancePaymentMethod
    amount_irr: int
    allocated_irr: int
    excess_irr: int
    reference: str | None = None
    received_on: date
    status: FinanceReceiptStatus
    verification_source: str
    reconciled: bool
    created_at: datetime
    allocations: list[FinanceReceiptAllocationPublic]


class FinanceReceiptsPublic(SQLModel):
    data: list[FinanceReceiptPublic]
    count: int


class FinanceCreditPublic(SQLModel):
    customer_user_id: uuid.UUID
    customer_name: str | None = None
    balance_irr: int


class FinanceCreditsPublic(SQLModel):
    data: list[FinanceCreditPublic]
    count: int


# ---------------------------------------------------------------------------
# Refunds and operating expenses (Phase 2)
# ---------------------------------------------------------------------------

FinanceRefundSource = Literal["INVOICE", "ADVANCE"]
FinanceRefundStatus = Literal["REQUESTED", "APPROVED", "RECORDED", "REJECTED"]
FinanceExpenseStatus = Literal["UNPAID", "PAID"]


class FinanceRefund(SQLModel, table=True):
    __tablename__ = "finance_refund"
    __table_args__ = (
        CheckConstraint(
            "source IN ('INVOICE', 'ADVANCE')", name="ck_finance_refund_source"
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'RECORDED', 'REJECTED')",
            name="ck_finance_refund_status",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_refund_amount"),
        CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_refund_method",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    customer_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    source: str = Field(max_length=20)
    invoice_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_invoice.id", ondelete="RESTRICT"
    )
    credit_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_customer_credit.id", ondelete="RESTRICT"
    )
    amount_irr: int = Field(sa_column=Column(BigInteger, nullable=False))
    method: str = Field(max_length=20)
    original_method: str | None = Field(default=None, max_length=20)
    method_override_reason: str | None = Field(default=None, max_length=500)
    reason: str = Field(max_length=500)
    status: str = Field(default="REQUESTED", max_length=20)
    requested_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    approved_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    approved_at: datetime | None = Field(default=None)
    recorded_at: datetime | None = Field(default=None)
    journal_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_journal.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceExpense(SQLModel, table=True):
    __tablename__ = "finance_expense"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UNPAID', 'PAID')", name="ck_finance_expense_status"
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_expense_amount"),
        CheckConstraint(
            "method IS NULL OR method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_expense_method",
        ),
        UniqueConstraint(
            "gym_id",
            "recurrence_key",
            "period_key",
            name="uq_finance_expense_recurrence",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    category: str = Field(max_length=100)
    counterparty: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    amount_irr: int = Field(sa_column=Column(BigInteger, nullable=False))
    spent_on: date
    status: str = Field(default="UNPAID", max_length=20)
    method: str | None = Field(default=None, max_length=20)
    paid_at: datetime | None = Field(default=None)
    recurrence_key: uuid.UUID | None = Field(default=None)
    period_key: str | None = Field(default=None, max_length=7)
    journal_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_journal.id", ondelete="RESTRICT"
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceRefundCreate(SQLModel):
    source: FinanceRefundSource
    customer_user_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)
    method: FinancePaymentMethod | None = None
    method_override_reason: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class FinanceRefundRecordCreate(SQLModel):
    posting_date: date


class FinanceRefundRejectCreate(SQLModel):
    reason: str = Field(min_length=3, max_length=500)


class FinanceExpenseCreate(SQLModel):
    category: str = Field(min_length=1, max_length=100)
    counterparty: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)
    spent_on: date
    paid: bool = False
    method: FinancePaymentMethod | None = None
    recurrence_key: uuid.UUID | None = None


class FinanceExpensePayCreate(SQLModel):
    paid_on: date
    method: FinancePaymentMethod


class FinanceExpenseRepeatCreate(SQLModel):
    spent_on: date


class FinanceRefundPublic(SQLModel):
    id: uuid.UUID
    source: FinanceRefundSource
    status: FinanceRefundStatus
    customer_user_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount_irr: int
    method: FinancePaymentMethod
    original_method: str | None = None
    method_override_reason: str | None = None
    reason: str
    created_at: datetime
    recorded_at: datetime | None = None


class FinanceRefundsPublic(SQLModel):
    data: list[FinanceRefundPublic]
    count: int


class FinanceExpensePublic(SQLModel):
    id: uuid.UUID
    category: str
    counterparty: str | None = None
    description: str | None = None
    amount_irr: int
    spent_on: date
    status: FinanceExpenseStatus
    method: FinancePaymentMethod | None = None
    paid_at: datetime | None = None
    recurrence_key: uuid.UUID | None = None
    created_at: datetime


class FinanceExpensesPublic(SQLModel):
    data: list[FinanceExpensePublic]
    count: int


# ---------------------------------------------------------------------------
# Paid gym membership and athlete self-service (Phase 2)
# ---------------------------------------------------------------------------

FinanceMembershipStatus = Literal["ACTIVE", "FROZEN", "CANCELLED", "EXPIRED"]


class FinanceMembership(SQLModel, table=True):
    """A paid commercial membership period, separate from GymMembership."""

    __tablename__ = "finance_membership"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'FROZEN', 'CANCELLED', 'EXPIRED')",
            name="ck_finance_membership_status",
        ),
        CheckConstraint(
            "end_date >= start_date", name="ck_finance_membership_dates"
        ),
        CheckConstraint(
            "access_required_irr >= 0",
            name="ck_finance_membership_access_amount",
        ),
        Index(
            "uq_finance_membership_active",
            "gym_id",
            "athlete_user_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'FROZEN')"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    athlete_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    invoice_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_invoice.id", ondelete="RESTRICT"
    )
    start_date: date
    end_date: date
    status: str = Field(default="ACTIVE", max_length=20)
    access_required_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    frozen_at: date | None = Field(default=None)
    frozen_days: int = Field(default=0)
    cancelled_at: date | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class FinanceMembershipCreate(SQLModel):
    athlete_user_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    start_date: date
    end_date: date
    access_required_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)


class FinanceMembershipFreezeCreate(SQLModel):
    frozen_on: date


class FinanceMembershipResumeCreate(SQLModel):
    resume_on: date


class FinanceMembershipCancelCreate(SQLModel):
    cancelled_on: date
    reason: str | None = Field(default=None, max_length=500)


class FinanceMembershipTransferCreate(SQLModel):
    athlete_user_id: uuid.UUID


class FinanceMembershipPublic(SQLModel):
    id: uuid.UUID
    athlete_user_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    start_date: date
    end_date: date
    status: FinanceMembershipStatus
    access_required_irr: int
    paid_irr: int
    access_granted: bool
    frozen_at: date | None = None
    frozen_days: int
    cancelled_at: date | None = None
    updated_at: datetime


class FinanceMembershipsPublic(SQLModel):
    data: list[FinanceMembershipPublic]
    count: int


class FinanceRefundPreview(SQLModel):
    refundable_paid_irr: int
    unused_days: int
    total_days: int
    proposed_refund_irr: int


class FinanceMyInvoicePublic(FinanceInvoicePublic):
    pass


class FinanceMyInvoicesPublic(SQLModel):
    data: list[FinanceInvoicePublic]
    count: int


class FinanceMyReceiptsPublic(SQLModel):
    data: list[FinanceReceiptPublic]
    count: int


class FinanceMyAccountPublic(SQLModel):
    invoices: list[FinanceInvoicePublic]
    receipts: list[FinanceReceiptPublic]
    memberships: list[FinanceMembershipPublic]
    refunds: list[FinanceRefundPublic]
    advance_balance_irr: int
    reminders: FinanceRemindersPublic


class FinanceMyRefundCreate(SQLModel):
    invoice_id: uuid.UUID
    amount_irr: int = Field(ge=1, le=MAX_FINANCE_IRR)
    method: FinancePaymentMethod | None = None
    method_override_reason: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


# ---------------------------------------------------------------------------
# Reminders (computed; no scheduler or automation engine)
# ---------------------------------------------------------------------------


class FinanceInstallmentReminder(SQLModel):
    invoice_id: uuid.UUID
    invoice_number: int | None = None
    customer_user_id: uuid.UUID
    customer_name: str | None = None
    due_date: date
    amount_irr: int
    overdue: bool
    days_until: int


class FinanceRenewalReminder(SQLModel):
    membership_id: uuid.UUID
    athlete_user_id: uuid.UUID
    athlete_name: str | None = None
    end_date: date
    days_until: int
    overdue: bool


class FinanceRemindersPublic(SQLModel):
    within_days: int
    installments: list[FinanceInstallmentReminder]
    renewals: list[FinanceRenewalReminder]


# ---------------------------------------------------------------------------
# Coach agreements, allocation and settlements (Phase 3)
# ---------------------------------------------------------------------------

FinanceCoachAgreementStatus = Literal["DRAFT", "ACTIVE", "ENDED"]
FinanceCoachAgreementMode = Literal["DIRECT", "WATERFALL"]
FinanceCoachVestingMode = Literal["ON_DATE", "MANUAL"]
FinanceCoachTermBasis = Literal["PERCENT", "FIXED"]
FinanceCoachRecipient = Literal["COACH", "ASCORA", "GYM"]


class FinanceCoachAgreement(SQLModel, table=True):
    __tablename__ = "finance_coach_agreement"
    __table_args__ = (
        UniqueConstraint(
            "gym_id",
            "coach_user_id",
            "version",
            name="uq_finance_coach_agreement_version",
        ),
        CheckConstraint("version > 0", name="ck_finance_coach_agreement_version"),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ENDED')",
            name="ck_finance_coach_agreement_status",
        ),
        CheckConstraint(
            "mode IN ('DIRECT', 'WATERFALL')",
            name="ck_finance_coach_agreement_mode",
        ),
        CheckConstraint(
            "vesting_mode IN ('ON_DATE', 'MANUAL')",
            name="ck_finance_coach_agreement_vesting",
        ),
        CheckConstraint(
            "vesting_days >= 0", name="ck_finance_coach_agreement_days"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_finance_coach_agreement_dates",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    coach_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    version: int
    status: str = Field(default="DRAFT", max_length=20)
    mode: str = Field(default="DIRECT", max_length=20)
    vesting_mode: str = Field(default="MANUAL", max_length=20)
    vesting_days: int = Field(default=0)
    effective_from: date
    effective_to: date | None = Field(default=None)
    notes: str | None = Field(default=None, max_length=1000)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    activated_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    activated_at: datetime | None = Field(default=None)


class FinanceCoachAgreementTerm(SQLModel, table=True):
    __tablename__ = "finance_coach_agreement_term"
    __table_args__ = (
        UniqueConstraint(
            "agreement_id", "sequence", name="uq_finance_coach_term_sequence"
        ),
        CheckConstraint(
            "recipient IN ('COACH', 'ASCORA', 'GYM')",
            name="ck_finance_coach_term_recipient",
        ),
        CheckConstraint(
            "basis IN ('PERCENT', 'FIXED')",
            name="ck_finance_coach_term_basis",
        ),
        CheckConstraint(
            "percent_bp >= 0 AND percent_bp <= 10000",
            name="ck_finance_coach_term_percent",
        ),
        CheckConstraint(
            "fixed_irr >= 0", name="ck_finance_coach_term_fixed"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    agreement_id: uuid.UUID = Field(
        foreign_key="finance_coach_agreement.id",
        ondelete="CASCADE",
        index=True,
    )
    sequence: int
    recipient: str = Field(max_length=20)
    basis: str = Field(max_length=20)
    percent_bp: int = Field(default=0)
    fixed_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    label: str | None = Field(default=None, max_length=100)


class FinanceCoachAgreementTermInput(SQLModel):
    recipient: FinanceCoachRecipient
    basis: FinanceCoachTermBasis
    percent_bp: int = Field(default=0, ge=0, le=10_000)
    fixed_irr: int = Field(default=0, ge=0, le=MAX_FINANCE_IRR)
    label: str | None = Field(default=None, max_length=100)


class FinanceCoachAgreementCreate(SQLModel):
    coach_user_id: uuid.UUID
    effective_from: date
    effective_to: date | None = None
    mode: FinanceCoachAgreementMode = "DIRECT"
    vesting_mode: FinanceCoachVestingMode = "MANUAL"
    vesting_days: int = Field(default=0, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=1000)
    terms: list[FinanceCoachAgreementTermInput] = Field(min_length=1)


class FinanceCoachAgreementTermPublic(SQLModel):
    id: uuid.UUID
    sequence: int
    recipient: FinanceCoachRecipient
    basis: FinanceCoachTermBasis
    percent_bp: int
    fixed_irr: int
    label: str | None = None


class FinanceCoachAgreementPublic(SQLModel):
    id: uuid.UUID
    coach_user_id: uuid.UUID
    coach_name: str | None = None
    version: int
    status: FinanceCoachAgreementStatus
    mode: FinanceCoachAgreementMode
    vesting_mode: FinanceCoachVestingMode
    vesting_days: int
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    terms: list[FinanceCoachAgreementTermPublic]
    created_at: datetime
    activated_at: datetime | None = None


class FinanceCoachAgreementsPublic(SQLModel):
    data: list[FinanceCoachAgreementPublic]
    count: int
