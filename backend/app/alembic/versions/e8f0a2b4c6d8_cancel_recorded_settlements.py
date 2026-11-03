"""allow cancellation of recorded coach settlements

Revision ID: e8f0a2b4c6d8
Revises: d7e9f1a3b5c7
Create Date: 2026-11-03 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f0a2b4c6d8"
down_revision: str | None = "d7e9f1a3b5c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENTS = (
    "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
    "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
    "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
    "'EXPENSE_PAID', 'COACH_ALLOCATION', 'COACH_SETTLEMENT', "
    "'COACH_SETTLED', 'COACH_SETTLE_CANCEL', 'COACH_ADJUSTMENT')"
)
OLD_EVENTS = (
    "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
    "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
    "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
    "'EXPENSE_PAID', 'COACH_ALLOCATION', 'COACH_SETTLEMENT', "
    "'COACH_SETTLED', 'COACH_ADJUSTMENT')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_finance_coach_settlement_status",
        "finance_coach_settlement",
        type_="check",
    )
    op.create_check_constraint(
        "ck_finance_coach_settlement_status",
        "finance_coach_settlement",
        "status IN ('RECORDED', 'CONFIRMED', 'CANCELLED')",
    )
    op.add_column(
        "finance_coach_settlement",
        sa.Column("cancelled_by_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "finance_coach_settlement",
        sa.Column(
            "cancelled_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
    )
    op.add_column(
        "finance_coach_settlement",
        sa.Column(
            "cancel_reason",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "finance_coach_settlement",
        sa.Column("cancel_journal_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_finance_coach_settlement_cancelled_by",
        "finance_coach_settlement",
        "user",
        ["cancelled_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_finance_coach_settlement_cancel_journal",
        "finance_coach_settlement",
        "finance_journal",
        ["cancel_journal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event", "finance_journal", NEW_EVENTS
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM finance_journal WHERE event_type = 'COACH_SETTLE_CANCEL'"
    )
    op.execute(
        "DELETE FROM finance_coach_settlement WHERE status = 'CANCELLED'"
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event", "finance_journal", OLD_EVENTS
    )
    op.drop_constraint(
        "fk_finance_coach_settlement_cancel_journal",
        "finance_coach_settlement",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_finance_coach_settlement_cancelled_by",
        "finance_coach_settlement",
        type_="foreignkey",
    )
    op.drop_column("finance_coach_settlement", "cancel_journal_id")
    op.drop_column("finance_coach_settlement", "cancel_reason")
    op.drop_column("finance_coach_settlement", "cancelled_at")
    op.drop_column("finance_coach_settlement", "cancelled_by_id")
    op.drop_constraint(
        "ck_finance_coach_settlement_status",
        "finance_coach_settlement",
        type_="check",
    )
    op.create_check_constraint(
        "ck_finance_coach_settlement_status",
        "finance_coach_settlement",
        "status IN ('RECORDED', 'CONFIRMED')",
    )
