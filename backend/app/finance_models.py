from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

FinanceCategory = Literal["MEMBERSHIP", "NUTRITION", "TRAINING"]
PlatformContractScope = Literal["DEFAULT", "GYM"]
ContractStatus = Literal["DRAFT", "ACTIVE", "ARCHIVED"]
TaxCalculation = Literal["PERCENT", "FIXED"]
SaleStatus = Literal[
    "DRAFT",
    "AWAITING_PAYMENT",
    "PAID",
    "PARTIALLY_REFUNDED",
    "REFUNDED",
    "CANCELLED",
]
PaymentStatus = Literal["SUCCEEDED", "FAILED", "CANCELLED"]
PaymentOutcome = Literal["SUCCESS", "FAILURE", "CANCELLATION"]
AllocationParty = Literal["PLATFORM", "GYM", "COACH"]
SettlementStatus = Literal["PENDING", "COMPLETED", "CANCELLED"]


def finance_now() -> datetime:
    return datetime.now(UTC)


class FinancePlatformContract(SQLModel, table=True):
    __tablename__ = "finance_platform_contract"
    __table_args__ = (
        UniqueConstraint(
            "scope", "gym_id", "version", name="uq_finance_platform_contract_version"
        ),
        CheckConstraint(
            "scope IN ('DEFAULT', 'GYM')",
            name="ck_finance_platform_contract_scope",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')",
            name="ck_finance_platform_contract_status",
        ),
        CheckConstraint(
            "(scope = 'DEFAULT' AND gym_id IS NULL) OR "
            "(scope = 'GYM' AND gym_id IS NOT NULL)",
            name="ck_finance_platform_contract_scope_gym",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_finance_platform_contract_dates",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200)
    scope: str = Field(max_length=20)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    version: int = Field(default=1)
    status: str = Field(default="DRAFT", max_length=20)
    effective_from: date
    effective_to: date | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)
    activated_at: datetime | None = Field(default=None)


class FinancePlatformRate(SQLModel, table=True):
    __tablename__ = "finance_platform_rate"
    __table_args__ = (
        UniqueConstraint("contract_id", "category", name="uq_finance_platform_rate"),
        CheckConstraint(
            "category IN ('MEMBERSHIP', 'NUTRITION', 'TRAINING')",
            name="ck_finance_platform_rate_category",
        ),
        CheckConstraint(
            "percent_bp >= 0 AND percent_bp <= 10000",
            name="ck_finance_platform_rate_percent",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contract_id: uuid.UUID = Field(
        foreign_key="finance_platform_contract.id",
        ondelete="CASCADE",
        index=True,
    )
    category: str = Field(max_length=20)
    percent_bp: int = Field(default=0)


class FinanceTaxDefinition(SQLModel, table=True):
    __tablename__ = "finance_tax_definition"
    __table_args__ = (
        CheckConstraint(
            "calculation IN ('PERCENT', 'FIXED')",
            name="ck_finance_tax_calculation",
        ),
        CheckConstraint(
            "(calculation = 'PERCENT' AND percent_bp IS NOT NULL "
            "AND percent_bp >= 0 AND percent_bp <= 10000 "
            "AND fixed_amount_irr IS NULL) OR "
            "(calculation = 'FIXED' AND percent_bp IS NULL "
            "AND fixed_amount_irr IS NOT NULL AND fixed_amount_irr > 0)",
            name="ck_finance_tax_value",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    calculation: str = Field(max_length=20)
    percent_bp: int | None = Field(default=None)
    fixed_amount_irr: int | None = Field(default=None)
    is_active: bool = Field(default=True)
    is_default_vat: bool = Field(default=False)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)


class FinanceCoachContract(SQLModel, table=True):
    __tablename__ = "finance_coach_contract"
    __table_args__ = (
        UniqueConstraint(
            "gym_id",
            "coach_user_id",
            "category",
            "version",
            name="uq_finance_coach_contract_version",
        ),
        CheckConstraint(
            "category IN ('MEMBERSHIP', 'NUTRITION', 'TRAINING')",
            name="ck_finance_coach_contract_category",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')",
            name="ck_finance_coach_contract_status",
        ),
        CheckConstraint(
            "platform_bp >= 0 AND platform_bp <= 10000 AND "
            "gym_bp >= 0 AND gym_bp <= 10000 AND "
            "coach_bp >= 0 AND coach_bp <= 10000",
            name="ck_finance_coach_contract_percent",
        ),
        CheckConstraint(
            "platform_bp + gym_bp + coach_bp = 10000",
            name="ck_finance_coach_contract_total",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_finance_coach_contract_dates",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    coach_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    category: str = Field(max_length=20)
    version: int = Field(default=1)
    status: str = Field(default="DRAFT", max_length=20)
    effective_from: date
    effective_to: date | None = Field(default=None)
    platform_bp: int
    gym_bp: int
    coach_bp: int
    platform_contract_id: uuid.UUID = Field(
        foreign_key="finance_platform_contract.id", ondelete="RESTRICT"
    )
    platform_source: str = Field(default="PLATFORM_DEFAULT", max_length=30)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)
    activated_at: datetime | None = Field(default=None)


class FinanceSale(SQLModel, table=True):
    __tablename__ = "finance_sale"
    __table_args__ = (
        CheckConstraint(
            "category IN ('MEMBERSHIP', 'NUTRITION', 'TRAINING')",
            name="ck_finance_sale_category",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'AWAITING_PAYMENT', 'PAID', "
            "'PARTIALLY_REFUNDED', 'REFUNDED', 'CANCELLED')",
            name="ck_finance_sale_status",
        ),
        CheckConstraint(
            "base_amount_irr >= 0 AND tax_amount_irr >= 0 AND "
            "total_amount_irr >= 0 AND platform_amount_irr >= 0 AND "
            "gym_amount_irr >= 0 AND coach_amount_irr >= 0",
            name="ck_finance_sale_amounts",
        ),
        CheckConstraint(
            "platform_amount_irr + gym_amount_irr + coach_amount_irr = "
            "total_amount_irr",
            name="ck_finance_sale_allocation_total",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    category: str = Field(max_length=20)
    description: str = Field(max_length=255)
    sold_on: date
    base_amount_irr: int
    tax_amount_irr: int = Field(default=0)
    total_amount_irr: int
    status: str = Field(default="AWAITING_PAYMENT", max_length=30)
    platform_bp: int
    gym_bp: int
    coach_bp: int
    platform_amount_irr: int
    gym_amount_irr: int
    coach_amount_irr: int
    coach_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    coach_contract_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_coach_contract.id", ondelete="RESTRICT"
    )
    platform_contract_id: uuid.UUID = Field(
        foreign_key="finance_platform_contract.id", ondelete="RESTRICT"
    )
    platform_source: str = Field(max_length=30)
    contract_snapshot: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)


class FinanceSaleTax(SQLModel, table=True):
    __tablename__ = "finance_sale_tax"
    __table_args__ = (
        CheckConstraint("amount_irr >= 0", name="ck_finance_sale_tax_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sale_id: uuid.UUID = Field(
        foreign_key="finance_sale.id", ondelete="CASCADE", index=True
    )
    tax_definition_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_tax_definition.id", ondelete="RESTRICT"
    )
    name: str = Field(max_length=100)
    calculation: str = Field(max_length=20)
    percent_bp: int | None = Field(default=None)
    fixed_amount_irr: int | None = Field(default=None)
    amount_irr: int
    created_at: datetime = Field(default_factory=finance_now)


class FinancePayment(SQLModel, table=True):
    __tablename__ = "finance_payment"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "idempotency_key", name="uq_finance_payment_idempotency"
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="ck_finance_payment_status",
        ),
        CheckConstraint(
            "outcome IN ('SUCCESS', 'FAILURE', 'CANCELLATION')",
            name="ck_finance_payment_outcome",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_payment_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    sale_id: uuid.UUID = Field(
        foreign_key="finance_sale.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int
    status: str = Field(max_length=20)
    outcome: str = Field(max_length=20)
    idempotency_key: str = Field(max_length=100)
    note: str | None = Field(default=None, max_length=500)
    paid_at: datetime | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)


class FinanceAllocation(SQLModel, table=True):
    __tablename__ = "finance_allocation"
    __table_args__ = (
        CheckConstraint(
            "party IN ('PLATFORM', 'GYM', 'COACH')",
            name="ck_finance_allocation_party",
        ),
        CheckConstraint("amount_irr >= 0", name="ck_finance_allocation_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    payment_id: uuid.UUID = Field(
        foreign_key="finance_payment.id", ondelete="CASCADE", index=True
    )
    sale_id: uuid.UUID = Field(
        foreign_key="finance_sale.id", ondelete="RESTRICT", index=True
    )
    party: str = Field(max_length=20)
    party_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int
    created_at: datetime = Field(default_factory=finance_now)


class FinanceSettlement(SQLModel, table=True):
    __tablename__ = "finance_settlement"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "idempotency_key", name="uq_finance_settlement_idempotency"
        ),
        CheckConstraint(
            "party IN ('PLATFORM', 'GYM', 'COACH')",
            name="ck_finance_settlement_party",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED')",
            name="ck_finance_settlement_status",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_settlement_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    party: str = Field(max_length=20)
    party_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int
    status: str = Field(default="PENDING", max_length=20)
    idempotency_key: str = Field(max_length=100)
    requested_at: datetime = Field(default_factory=finance_now)
    completed_at: datetime | None = Field(default=None)
    cancelled_at: datetime | None = Field(default=None)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)


class FinanceSettlementItem(SQLModel, table=True):
    __tablename__ = "finance_settlement_item"
    __table_args__ = (
        UniqueConstraint(
            "settlement_id", "allocation_id", name="uq_finance_settlement_item"
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_settlement_item_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    settlement_id: uuid.UUID = Field(
        foreign_key="finance_settlement.id", ondelete="CASCADE", index=True
    )
    allocation_id: uuid.UUID = Field(
        foreign_key="finance_allocation.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int


class FinanceRefund(SQLModel, table=True):
    __tablename__ = "finance_refund"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "idempotency_key", name="uq_finance_refund_idempotency"
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_refund_amount"),
        CheckConstraint("status IN ('COMPLETED')", name="ck_finance_refund_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(
        foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    payment_id: uuid.UUID = Field(
        foreign_key="finance_payment.id", ondelete="RESTRICT", index=True
    )
    sale_id: uuid.UUID = Field(
        foreign_key="finance_sale.id", ondelete="RESTRICT", index=True
    )
    amount_irr: int
    status: str = Field(default="COMPLETED", max_length=20)
    idempotency_key: str = Field(max_length=100)
    reason: str = Field(max_length=500)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(default_factory=finance_now)


class FinanceRefundAdjustment(SQLModel, table=True):
    __tablename__ = "finance_refund_adjustment"
    __table_args__ = (
        CheckConstraint(
            "party IN ('PLATFORM', 'GYM', 'COACH')",
            name="ck_finance_refund_adjustment_party",
        ),
        CheckConstraint("amount_irr > 0", name="ck_finance_refund_adjustment_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    refund_id: uuid.UUID = Field(
        foreign_key="finance_refund.id", ondelete="CASCADE", index=True
    )
    allocation_id: uuid.UUID = Field(
        foreign_key="finance_allocation.id", ondelete="RESTRICT", index=True
    )
    settlement_id: uuid.UUID | None = Field(
        default=None, foreign_key="finance_settlement.id", ondelete="RESTRICT"
    )
    party: str = Field(max_length=20)
    party_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    amount_irr: int
    created_at: datetime = Field(default_factory=finance_now)


class FinanceAudit(SQLModel, table=True):
    __tablename__ = "finance_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT", index=True
    )
    action: str = Field(max_length=80, index=True)
    entity_type: str = Field(max_length=50)
    entity_id: uuid.UUID | None = Field(default=None)
    detail: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=finance_now)


# ---------------------------------------------------------------------------
# Public read models
# ---------------------------------------------------------------------------


class FinancePlatformRatePublic(SQLModel):
    category: FinanceCategory
    percent_bp: int


class FinancePlatformContractPublic(SQLModel):
    id: uuid.UUID
    name: str
    scope: PlatformContractScope
    gym_id: uuid.UUID | None = None
    version: int
    status: ContractStatus
    effective_from: date
    effective_to: date | None = None
    rates: list[FinancePlatformRatePublic]
    activated_at: datetime | None = None
    created_at: datetime


class FinancePlatformPolicyPublic(SQLModel):
    gym_id: uuid.UUID
    category: FinanceCategory
    on_date: date
    platform_bp: int
    source: str
    contract_id: uuid.UUID
    contract_version: int


class FinanceTaxPublic(SQLModel):
    id: uuid.UUID
    name: str
    calculation: TaxCalculation
    percent_bp: int | None = None
    fixed_amount_irr: int | None = None
    is_active: bool
    is_default_vat: bool


class FinanceTaxLinePublic(SQLModel):
    name: str
    calculation: TaxCalculation
    percent_bp: int | None = None
    fixed_amount_irr: int | None = None
    amount_irr: int


class FinanceCoachContractPublic(SQLModel):
    id: uuid.UUID
    gym_id: uuid.UUID
    coach_user_id: uuid.UUID
    coach_name: str | None = None
    category: FinanceCategory
    version: int
    status: ContractStatus
    effective_from: date
    effective_to: date | None = None
    platform_bp: int
    gym_bp: int
    coach_bp: int
    platform_source: str
    platform_contract_id: uuid.UUID
    activated_at: datetime | None = None
    created_at: datetime


class FinanceCoachOptionPublic(SQLModel):
    user_id: uuid.UUID
    name: str
    email: str


class FinanceSalePreviewPublic(SQLModel):
    gym_id: uuid.UUID
    category: FinanceCategory
    base_amount_irr: int
    taxes: list[FinanceTaxLinePublic]
    tax_amount_irr: int
    total_amount_irr: int
    platform_bp: int
    gym_bp: int
    coach_bp: int
    platform_amount_irr: int
    gym_amount_irr: int
    coach_amount_irr: int
    coach_user_id: uuid.UUID | None = None
    platform_source: str
    platform_contract_id: uuid.UUID
    platform_contract_version: int
    coach_contract_id: uuid.UUID | None = None
    coach_contract_version: int | None = None


class FinanceSalePublic(SQLModel):
    id: uuid.UUID
    gym_id: uuid.UUID
    category: FinanceCategory
    description: str
    sold_on: date
    base_amount_irr: int
    taxes: list[FinanceTaxLinePublic] = Field(default_factory=list)
    tax_amount_irr: int
    total_amount_irr: int
    status: str
    platform_bp: int
    gym_bp: int
    coach_bp: int
    platform_amount_irr: int
    gym_amount_irr: int
    coach_amount_irr: int
    coach_user_id: uuid.UUID | None = None
    coach_name: str | None = None
    coach_contract_id: uuid.UUID | None = None
    platform_contract_id: uuid.UUID
    platform_source: str
    refunded_irr: int = 0
    payment_status: str | None = None
    created_at: datetime


class FinancePaymentAllocationPublic(SQLModel):
    id: uuid.UUID
    party: AllocationParty
    party_user_id: uuid.UUID | None = None
    party_name: str | None = None
    amount_irr: int
    refunded_irr: int
    settled_irr: int


class FinancePaymentPublic(SQLModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    gym_id: uuid.UUID
    amount_irr: int
    status: PaymentStatus
    outcome: PaymentOutcome
    note: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    allocations: list[FinancePaymentAllocationPublic] = Field(default_factory=list)


class FinanceSettlementItemPublic(SQLModel):
    allocation_id: uuid.UUID
    party: AllocationParty
    amount_irr: int


class FinanceSettlementPublic(SQLModel):
    id: uuid.UUID
    gym_id: uuid.UUID
    party: AllocationParty
    party_user_id: uuid.UUID | None = None
    party_name: str | None = None
    amount_irr: int
    status: SettlementStatus
    requested_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    items: list[FinanceSettlementItemPublic] = Field(default_factory=list)


class FinanceRefundAdjustmentPublic(SQLModel):
    allocation_id: uuid.UUID
    settlement_id: uuid.UUID | None = None
    party: AllocationParty
    amount_irr: int


class FinanceRefundPublic(SQLModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    sale_id: uuid.UUID
    amount_irr: int
    status: str
    reason: str
    created_at: datetime
    adjustments: list[FinanceRefundAdjustmentPublic] = Field(default_factory=list)


class FinanceReportActivityPublic(SQLModel):
    base_sales_irr: int
    taxes_irr: int
    total_payments_irr: int
    platform_share_irr: int
    gym_share_irr: int
    coach_share_irr: int
    refunds_irr: int
    completed_settlements_irr: int


class FinanceReportAsOfPublic(SQLModel):
    date: date
    unsettled_platform_irr: int
    unsettled_gym_irr: int
    unsettled_coach_irr: int
    pending_settlements_irr: int
    completed_settlements_irr: int


class FinanceReportGymPublic(SQLModel):
    gym_id: uuid.UUID
    gym_name: str
    activity: FinanceReportActivityPublic
    as_of: FinanceReportAsOfPublic


class FinanceReportPublic(SQLModel):
    gym_id: uuid.UUID | None = None
    from_date: date
    to_date: date
    activity: FinanceReportActivityPublic
    as_of: FinanceReportAsOfPublic
    by_gym: list[FinanceReportGymPublic] = Field(default_factory=list)


class FinanceAuditPublic(SQLModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class FinancePlatformRateInput(SQLModel):
    category: FinanceCategory
    percent_bp: int = Field(ge=0, le=10000)


class FinancePlatformContractCreate(SQLModel):
    name: str = Field(min_length=1, max_length=200)
    scope: PlatformContractScope
    gym_id: uuid.UUID | None = None
    effective_from: date
    effective_to: date | None = None
    rates: list[FinancePlatformRateInput]


class FinanceTaxCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    calculation: TaxCalculation
    percent_bp: int | None = Field(default=None, ge=0, le=10000)
    fixed_amount_irr: int | None = Field(default=None, gt=0)
    is_active: bool = True
    is_default_vat: bool = False


class FinanceTaxUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    calculation: TaxCalculation | None = None
    percent_bp: int | None = Field(default=None, ge=0, le=10000)
    fixed_amount_irr: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    is_default_vat: bool | None = None


class FinanceCoachContractCreate(SQLModel):
    coach_user_id: uuid.UUID
    category: FinanceCategory
    effective_from: date
    effective_to: date | None = None
    platform_bp: int = Field(ge=0, le=10000)
    gym_bp: int = Field(ge=0, le=10000)
    coach_bp: int = Field(ge=0, le=10000)


class FinanceSalePreviewRequest(SQLModel):
    category: FinanceCategory
    description: str = Field(default="", max_length=255)
    base_amount_irr: int = Field(gt=0)
    tax_ids: list[uuid.UUID] = Field(default_factory=list)
    coach_user_id: uuid.UUID | None = None
    sold_on: date


class FinanceSaleCreate(FinanceSalePreviewRequest):
    description: str = Field(min_length=1, max_length=255)


class FinancePaymentSimulate(SQLModel):
    outcome: PaymentOutcome
    idempotency_key: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class FinanceSettlementCreate(SQLModel):
    party: AllocationParty
    party_user_id: uuid.UUID | None = None
    amount_irr: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=100)


class FinanceRefundCreate(SQLModel):
    amount_irr: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=500)
