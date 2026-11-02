"""allow coach journal event types

Revision ID: b9d1e3f5a7c9
Revises: a8c0d2e4f6b8
Create Date: 2026-11-03 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9d1e3f5a7c9"
down_revision: str | None = "a8c0d2e4f6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event",
        "finance_journal",
        "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
        "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
        "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
        "'EXPENSE_PAID', 'COACH_ALLOCATION', 'COACH_SETTLEMENT', "
        "'COACH_ADJUSTMENT')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event",
        "finance_journal",
        "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
        "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
        "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
        "'EXPENSE_PAID')",
    )
