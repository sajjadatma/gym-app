"""stage coach settlements and add pending settlement account

Revision ID: b5c7d9e1f3a5
Revises: a4b6c8d0e2f4
Create Date: 2026-11-03 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c7d9e1f3a5"
down_revision: str | None = "a4b6c8d0e2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENTS = (
    "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
    "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
    "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
    "'EXPENSE_PAID', 'COACH_ALLOCATION', 'COACH_SETTLEMENT', "
    "'COACH_SETTLED', 'COACH_ADJUSTMENT')"
)
OLD_EVENTS = (
    "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
    "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
    "'ADVANCE_APPLIED', 'REFUND_RECORDED', 'EXPENSE_RECORDED', "
    "'EXPENSE_PAID', 'COACH_ALLOCATION', 'COACH_SETTLEMENT', "
    "'COACH_ADJUSTMENT')"
)


def upgrade() -> None:
    op.add_column(
        "finance_coach_settlement",
        sa.Column("confirmed_journal_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_finance_coach_settlement_confirmed_journal",
        "finance_coach_settlement",
        "finance_journal",
        ["confirmed_journal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            """
            INSERT INTO finance_account
                (id, gym_id, code, name, type, created_at)
            SELECT gen_random_uuid(), gym.id, '2200', 'تسویه‌های در انتظار',
                   'LIABILITY', now()
            FROM gym
            ON CONFLICT (gym_id, code) DO NOTHING
            """
        )
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event", "finance_journal", NEW_EVENTS
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM finance_journal WHERE event_type = 'COACH_SETTLED'"
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event", "finance_journal", OLD_EVENTS
    )
    op.drop_constraint(
        "fk_finance_coach_settlement_confirmed_journal",
        "finance_coach_settlement",
        type_="foreignkey",
    )
    op.drop_column("finance_coach_settlement", "confirmed_journal_id")
