"""add refunds, operating expenses and the sales-returns account

Revision ID: c3d5e7f9a1b4
Revises: b2c4d6e8f0a3
Create Date: 2026-11-03 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d5e7f9a1b4"
down_revision: str | None = "b2c4d6e8f0a3"
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
        "'EXPENSE_PAID')",
    )
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage', "
        "'finance.catalog.manage', 'finance.invoice.manage', "
        "'finance.payment.record', 'finance.refund.manage', "
        "'finance.expense.manage')",
    )
    op.drop_constraint(
        "ck_finance_credit_movement_kind", "finance_credit_movement", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_credit_movement_kind",
        "finance_credit_movement",
        "kind IN ('RECEIPT_EXCESS', 'APPLIED', 'REFUNDED')",
    )

    op.execute(
        """
        INSERT INTO finance_account (id, gym_id, code, name, type, created_at)
        SELECT gen_random_uuid(), gym.id, '4100', 'برگشت از فروش',
               'INCOME', now()
        FROM gym
        """
    )

    op.create_table(
        "finance_refund",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("customer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("invoice_id", sa.Uuid(), nullable=True),
        sa.Column("credit_id", sa.Uuid(), nullable=True),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "method", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False
        ),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "approved_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column(
            "recorded_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "source IN ('INVOICE', 'ADVANCE')", name="ck_finance_refund_source"
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'RECORDED', 'REJECTED')",
            name="ck_finance_refund_status",
        ),
        sa.CheckConstraint("amount_irr > 0", name="ck_finance_refund_amount"),
        sa.CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_refund_method",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["credit_id"], ["finance_customer_credit.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_refund_gym_id"),
        "finance_refund",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_refund_customer_user_id"),
        "finance_refund",
        ["customer_user_id"],
        unique=False,
    )

    op.create_table(
        "finance_expense",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "category",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=False,
        ),
        sa.Column(
            "counterparty",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "method", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True
        ),
        sa.Column(
            "paid_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("recurrence_key", sa.Uuid(), nullable=True),
        sa.Column(
            "period_key",
            sqlmodel.sql.sqltypes.AutoString(length=7),
            nullable=True,
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('UNPAID', 'PAID')", name="ck_finance_expense_status"
        ),
        sa.CheckConstraint("amount_irr > 0", name="ck_finance_expense_amount"),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_expense_method",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id",
            "recurrence_key",
            "period_key",
            name="uq_finance_expense_recurrence",
        ),
    )
    op.create_index(
        op.f("ix_finance_expense_gym_id"),
        "finance_expense",
        ["gym_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_expense_gym_id"), table_name="finance_expense"
    )
    op.drop_table("finance_expense")
    op.drop_index(
        op.f("ix_finance_refund_customer_user_id"), table_name="finance_refund"
    )
    op.drop_index(
        op.f("ix_finance_refund_gym_id"), table_name="finance_refund"
    )
    op.drop_table("finance_refund")

    op.execute("DELETE FROM finance_account WHERE code = '4100'")

    op.drop_constraint(
        "ck_finance_credit_movement_kind", "finance_credit_movement", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_credit_movement_kind",
        "finance_credit_movement",
        "kind IN ('RECEIPT_EXCESS', 'APPLIED')",
    )
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage', "
        "'finance.catalog.manage', 'finance.invoice.manage', "
        "'finance.payment.record')",
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event",
        "finance_journal",
        "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
        "'INVOICE_ISSUED', 'INVOICE_VOID', 'RECEIPT_CONFIRMED', "
        "'ADVANCE_APPLIED')",
    )
