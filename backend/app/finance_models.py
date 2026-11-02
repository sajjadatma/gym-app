from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import CheckConstraint, Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc

FinanceDisplayUnit = Literal["RIAL", "TOMAN"]

FINANCE_VIEW = "finance.view"
FINANCE_OPENING_MANAGE = "finance.opening.manage"
FINANCE_PERIOD_MANAGE = "finance.period.manage"

FinancePermissionName = Literal[
    "finance.view",
    "finance.opening.manage",
    "finance.period.manage",
]

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
        default=None, foreign_key="user.id", ondelete="SET NULL"
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
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
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
