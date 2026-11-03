from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Final, Literal

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

PlatformMode = Literal["FREE", "SUBSCRIPTION", "COMMISSION", "HYBRID", "CUSTOM"]
PlatformAgreementStatus = Literal["DRAFT", "EFFECTIVE", "REPLACED", "DISABLED"]
PlatformInvoiceStatus = Literal[
    "ISSUED", "PARTIALLY_PAID", "PAID", "CREDITED", "CANCELLED"
]
PlatformReceivableStatus = Literal[
    "OPEN", "INVOICED", "PARTIAL", "PAID", "CREDITED", "VOID"
]
PlatformPaymentMethod = Literal["CASH", "POS", "TRANSFER"]

PLATFORM_CASH_ACCOUNT: Final = "1000"
PLATFORM_RECEIVABLE_ACCOUNT: Final = "1100"
PLATFORM_SUBSCRIPTION_ACCOUNT: Final = "4000"
PLATFORM_COMMISSION_ACCOUNT: Final = "4100"
PLATFORM_CUSTOM_ACCOUNT: Final = "4200"

MAX_PLATFORM_IRR = 10**15


class PlatformPlan(SQLModel, table=True):
    __tablename__ = "platform_plan"
    __table_args__ = (UniqueConstraint("code", name="uq_platform_plan_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=50)
    name: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformPlanVersion(SQLModel, table=True):
    __tablename__ = "platform_plan_version"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "version_number", name="uq_platform_plan_version"
        ),
        UniqueConstraint(
            "plan_id", "effective_from", name="uq_platform_plan_effective"
        ),
        CheckConstraint(
            "version_number > 0", name="ck_platform_plan_version_number"
        ),
        CheckConstraint(
            "monthly_price_irr >= 0", name="ck_platform_plan_price"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name="ck_platform_plan_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_platform_plan_dates",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(
        foreign_key="platform_plan.id", ondelete="CASCADE"
    )
    version_number: int
    effective_from: date
    effective_to: date | None = Field(default=None)
    monthly_price_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    limits: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    status: str = Field(default="DRAFT", max_length=20)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformGroup(SQLModel, table=True):
    __tablename__ = "platform_group"
    __table_args__ = (UniqueConstraint("name", name="uq_platform_group_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformGroupMember(SQLModel, table=True):
    __tablename__ = "platform_group_member"
    __table_args__ = (
        UniqueConstraint("group_id", "gym_id", name="uq_platform_group_gym"),
        CheckConstraint(
            "allocation_bp >= 0 AND allocation_bp <= 10000",
            name="ck_platform_group_allocation",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: uuid.UUID = Field(
        foreign_key="platform_group.id", ondelete="CASCADE"
    )
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE"
    )
    allocation_bp: int = Field(default=10000)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformAgreement(SQLModel, table=True):
    __tablename__ = "platform_agreement"
    __table_args__ = (
        CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_agreement_scope",
        ),
        CheckConstraint(
            "mode IN ('FREE', 'SUBSCRIPTION', 'COMMISSION', 'HYBRID', 'CUSTOM')",
            name="ck_platform_agreement_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'EFFECTIVE', 'REPLACED', 'DISABLED')",
            name="ck_platform_agreement_status",
        ),
        CheckConstraint(
            "version > 0 AND subscription_amount_irr >= 0 "
            "AND volume_discount_bp >= 0 AND volume_discount_bp <= 10000 "
            "AND grace_days >= 0 AND restrict_after_days >= grace_days",
            name="ck_platform_agreement_amounts",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_platform_agreement_dates",
        ),
        Index(
            "uq_platform_agreement_gym_scope_version",
            "gym_id",
            "effective_from",
            "version",
            unique=True,
            postgresql_where=text("gym_id IS NOT NULL"),
        ),
        Index(
            "uq_platform_agreement_group_scope_version",
            "group_id",
            "effective_from",
            "version",
            unique=True,
            postgresql_where=text("group_id IS NOT NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE"
    )
    group_id: uuid.UUID | None = Field(
        default=None, foreign_key="platform_group.id", ondelete="CASCADE"
    )
    version: int = Field(default=1)
    supersedes_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="platform_agreement.id",
        ondelete="RESTRICT",
    )
    mode: str = Field(max_length=20)
    status: str = Field(default="DRAFT", max_length=20)
    effective_from: date
    effective_to: date | None = Field(default=None)
    plan_version_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="platform_plan_version.id",
        ondelete="RESTRICT",
    )
    subscription_amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    billing_interval: str = Field(default="MONTHLY", max_length=20)
    volume_discount_bp: int = Field(default=0)
    grace_days: int = Field(default=7)
    restrict_after_days: int = Field(default=21)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    activated_at: datetime | None = Field(default=None)


class PlatformCommissionTerm(SQLModel, table=True):
    __tablename__ = "platform_commission_term"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ANY', 'MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', "
            "'PRODUCT', 'SERVICE', 'CUSTOM')",
            name="ck_platform_term_kind",
        ),
        CheckConstraint(
            "acquisition_source IN ('ANY', 'GYM', 'ASCORA')",
            name="ck_platform_term_source",
        ),
        CheckConstraint(
            "basis IN ('PERCENT', 'FIXED', 'PERCENT_PLUS_FIXED')",
            name="ck_platform_term_basis",
        ),
        CheckConstraint(
            "percent_bp >= 0 AND percent_bp <= 10000 "
            "AND fixed_irr >= 0 AND max_fee_irr >= 0",
            name="ck_platform_term_amounts",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    agreement_id: uuid.UUID = Field(
        foreign_key="platform_agreement.id", ondelete="CASCADE"
    )
    kind: str = Field(default="ANY", max_length=20)
    acquisition_source: str = Field(default="ANY", max_length=20)
    basis: str = Field(max_length=30)
    percent_bp: int = Field(default=0)
    fixed_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    max_fee_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformReceivable(SQLModel, table=True):
    __tablename__ = "platform_receivable"
    __table_args__ = (
        CheckConstraint("amount_irr >= 0 AND paid_irr >= 0 AND paid_irr <= amount_irr", name="ck_platform_receivable_amount"),
        CheckConstraint(
            "status IN ('OPEN', 'INVOICED', 'PARTIAL', 'PAID', 'CREDITED', 'VOID')",
            name="ck_platform_receivable_status",
        ),
        UniqueConstraint("source_key", name="uq_platform_receivable_source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE"
    )
    agreement_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="platform_agreement.id",
        ondelete="RESTRICT",
    )
    source_type: str = Field(max_length=30)
    source_id: uuid.UUID | None = Field(default=None)
    source_key: str = Field(max_length=200)
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    paid_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    due_on: date
    status: str = Field(default="OPEN", max_length=20)
    snapshot: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformCredit(SQLModel, table=True):
    __tablename__ = "platform_credit"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="ck_platform_credit_amount"),
        UniqueConstraint("source_key", name="uq_platform_credit_source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE"
    )
    source_type: str = Field(max_length=30)
    source_id: uuid.UUID | None = Field(default=None)
    source_key: str = Field(max_length=200)
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    reason: str | None = Field(default=None, max_length=500)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformCreditApplication(SQLModel, table=True):
    __tablename__ = "platform_credit_application"
    __table_args__ = (
        UniqueConstraint(
            "credit_id", "invoice_line_id", name="uq_platform_credit_application"
        ),
        CheckConstraint(
            "amount_irr > 0", name="ck_platform_credit_application_amount"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    credit_id: uuid.UUID = Field(
        foreign_key="platform_credit.id", ondelete="CASCADE"
    )
    invoice_line_id: uuid.UUID = Field(
        foreign_key="platform_invoice_line.id", ondelete="CASCADE"
    )
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformInvoice(SQLModel, table=True):
    __tablename__ = "platform_invoice"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_platform_invoice_number"),
        CheckConstraint(
            "status IN ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'CREDITED', "
            "'CANCELLED')",
            name="ck_platform_invoice_status",
        ),
        CheckConstraint(
            "total_irr >= 0 AND discount_irr >= 0",
            name="ck_platform_invoice_total",
        ),
        CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_invoice_scope",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE"
    )
    group_id: uuid.UUID | None = Field(
        default=None, foreign_key="platform_group.id", ondelete="CASCADE"
    )
    invoice_number: int
    period_start: date
    period_end: date
    issued_on: date
    due_on: date
    status: str = Field(default="ISSUED", max_length=20)
    discount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    total_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformInvoiceLine(SQLModel, table=True):
    __tablename__ = "platform_invoice_line"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "gym_id", "source_key",
            name="uq_platform_invoice_line_source",
        ),
        CheckConstraint(
            "gross_irr >= 0 AND discount_irr >= 0 AND credit_irr >= 0 "
            "AND amount_irr >= 0 AND paid_irr >= 0 AND paid_irr <= amount_irr",
            name="ck_platform_invoice_line_amount",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    invoice_id: uuid.UUID = Field(
        foreign_key="platform_invoice.id", ondelete="CASCADE"
    )
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE"
    )
    receivable_id: uuid.UUID = Field(
        foreign_key="platform_receivable.id", ondelete="RESTRICT"
    )
    source_key: str = Field(max_length=200)
    description: str = Field(max_length=255)
    gross_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    discount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    credit_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    paid_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )


class PlatformInvoiceCancellation(SQLModel, table=True):
    __tablename__ = "platform_invoice_cancellation"
    __table_args__ = (
        UniqueConstraint("invoice_id", name="uq_platform_invoice_cancellation"),
        CheckConstraint(
            "length(reason) >= 3", name="ck_platform_invoice_cancel_reason"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    invoice_id: uuid.UUID = Field(
        foreign_key="platform_invoice.id", ondelete="CASCADE"
    )
    reason: str = Field(max_length=500)
    journal_id: uuid.UUID | None = Field(
        default=None, foreign_key="platform_journal.id", ondelete="RESTRICT"
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformInvoiceLineReversal(SQLModel, table=True):
    __tablename__ = "platform_invoice_line_reversal"
    __table_args__ = (
        UniqueConstraint(
            "cancellation_id",
            "invoice_line_id",
            name="uq_platform_invoice_line_reversal",
        ),
        CheckConstraint(
            "amount_irr > 0", name="ck_platform_invoice_line_reversal_amount"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cancellation_id: uuid.UUID = Field(
        foreign_key="platform_invoice_cancellation.id",
        ondelete="CASCADE",
    )
    invoice_line_id: uuid.UUID = Field(
        foreign_key="platform_invoice_line.id",
        ondelete="CASCADE",
    )
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformPayment(SQLModel, table=True):
    __tablename__ = "platform_payment"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="ck_platform_payment_amount"),
        CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_platform_payment_method",
        ),
        UniqueConstraint(
            "operation_key", name="uq_platform_payment_operation"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    invoice_id: uuid.UUID = Field(
        foreign_key="platform_invoice.id", ondelete="CASCADE"
    )
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    method: str = Field(max_length=20)
    reference: str | None = Field(default=None, max_length=255)
    received_on: date
    operation_key: str = Field(max_length=100)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformPaymentAllocation(SQLModel, table=True):
    __tablename__ = "platform_payment_allocation"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "invoice_line_id", name="uq_platform_payment_line"
        ),
        CheckConstraint(
            "amount_irr > 0", name="ck_platform_payment_allocation_amount"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    payment_id: uuid.UUID = Field(
        foreign_key="platform_payment.id", ondelete="CASCADE"
    )
    invoice_line_id: uuid.UUID = Field(
        foreign_key="platform_invoice_line.id",
        ondelete="CASCADE",
    )
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )


class PlatformJournal(SQLModel, table=True):
    __tablename__ = "platform_journal"
    __table_args__ = (
        UniqueConstraint("entry_number", name="uq_platform_journal_entry"),
        CheckConstraint(
            "event_type IN ('PLATFORM_FEE', 'PLATFORM_FEE_REVERSAL', "
            "'PLATFORM_PAYMENT', 'PLATFORM_INVOICE_CANCEL')",
            name="ck_platform_journal_event",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    entry_number: int
    posting_date: date
    event_type: str = Field(max_length=40)
    description: str = Field(max_length=255)
    source_type: str = Field(max_length=40)
    source_id: uuid.UUID | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformJournalLine(SQLModel, table=True):
    __tablename__ = "platform_journal_line"
    __table_args__ = (
        CheckConstraint(
            "debit_irr >= 0 AND credit_irr >= 0",
            name="ck_platform_journal_line_amounts",
        ),
        CheckConstraint(
            "(debit_irr = 0) <> (credit_irr = 0)",
            name="ck_platform_journal_line_side",
        ),
        CheckConstraint(
            "account_code IN ('1000', '1100', '4000', '4100', '4200')",
            name="ck_platform_journal_account",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    journal_id: uuid.UUID = Field(
        foreign_key="platform_journal.id", ondelete="CASCADE"
    )
    account_code: str = Field(max_length=10)
    debit_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    credit_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    memo: str | None = Field(default=None, max_length=255)


class PlatformAudit(SQLModel, table=True):
    __tablename__ = "platform_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="RESTRICT"
    )
    group_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="platform_group.id",
        ondelete="RESTRICT",
    )
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    action: str = Field(max_length=64)
    target_type: str = Field(max_length=40)
    target_id: uuid.UUID | None = Field(default=None)
    reason: str | None = Field(default=None, max_length=500)
    detail: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformCost(SQLModel, table=True):
    __tablename__ = "platform_cost"
    __table_args__ = (
        CheckConstraint("amount_irr >= 0", name="ck_platform_cost_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="SET NULL"
    )
    category: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    amount_irr: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False)
    )
    incurred_on: date
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlatformSequence(SQLModel, table=True):
    __tablename__ = "platform_sequence"
    __table_args__ = (UniqueConstraint("doc_type", name="uq_platform_sequence_doc"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    doc_type: str = Field(max_length=30)
    last_value: int = Field(default=0)


class PlatformOperation(SQLModel, table=True):
    __tablename__ = "platform_operation"
    __table_args__ = (
        UniqueConstraint("operation_key", name="uq_platform_operation_key"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    operation_key: str = Field(max_length=100)
    request_hash: str = Field(max_length=64)
    result_type: str = Field(max_length=40)
    result_id: uuid.UUID
    created_at: datetime = Field(default_factory=get_datetime_utc)
