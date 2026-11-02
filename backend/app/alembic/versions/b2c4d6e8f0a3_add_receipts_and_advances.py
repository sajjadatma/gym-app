"""add manual receipts, allocations and customer advances

Revision ID: b2c4d6e8f0a3
Revises: a1b3c5d7e9f2
Create Date: 2026-11-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c4d6e8f0a3"
down_revision: str | None = "a1b3c5d7e9f2"
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
        "'ADVANCE_APPLIED')",
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

    op.create_table(
        "finance_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("customer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "customer_name",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("receipt_number", sa.Integer(), nullable=False),
        sa.Column(
            "method", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "reference",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "verification_source",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column(
            "reconciled_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_finance_receipt_method",
        ),
        sa.CheckConstraint(
            "status IN ('CONFIRMED', 'REVERSED')",
            name="ck_finance_receipt_status",
        ),
        sa.CheckConstraint("amount_irr > 0", name="ck_finance_receipt_amount"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "receipt_number", name="uq_finance_receipt_number"
        ),
    )
    op.create_index(
        op.f("ix_finance_receipt_gym_id"),
        "finance_receipt",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_receipt_customer_user_id"),
        "finance_receipt",
        ["customer_user_id"],
        unique=False,
    )

    op.create_table(
        "finance_receipt_allocation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_allocation_amount"
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["finance_receipt.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id",
            "invoice_id",
            name="uq_finance_allocation_receipt_invoice",
        ),
    )
    op.create_index(
        op.f("ix_finance_receipt_allocation_receipt_id"),
        "finance_receipt_allocation",
        ["receipt_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_receipt_allocation_invoice_id"),
        "finance_receipt_allocation",
        ["invoice_id"],
        unique=False,
    )

    op.create_table(
        "finance_customer_credit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("customer_user_id", sa.Uuid(), nullable=False),
        sa.Column("balance_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "balance_irr >= 0", name="ck_finance_credit_balance"
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "customer_user_id", name="uq_finance_credit_gym_customer"
        ),
    )
    op.create_index(
        op.f("ix_finance_customer_credit_gym_id"),
        "finance_customer_credit",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_customer_credit_customer_user_id"),
        "finance_customer_credit",
        ["customer_user_id"],
        unique=False,
    )

    op.create_table(
        "finance_credit_movement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("credit_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('RECEIPT_EXCESS', 'APPLIED')",
            name="ck_finance_credit_movement_kind",
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_credit_movement_amount"
        ),
        sa.ForeignKeyConstraint(
            ["credit_id"], ["finance_customer_credit.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["finance_receipt.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_credit_movement_credit_id"),
        "finance_credit_movement",
        ["credit_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_credit_movement_credit_id"),
        table_name="finance_credit_movement",
    )
    op.drop_table("finance_credit_movement")
    op.drop_index(
        op.f("ix_finance_customer_credit_customer_user_id"),
        table_name="finance_customer_credit",
    )
    op.drop_index(
        op.f("ix_finance_customer_credit_gym_id"),
        table_name="finance_customer_credit",
    )
    op.drop_table("finance_customer_credit")
    op.drop_index(
        op.f("ix_finance_receipt_allocation_invoice_id"),
        table_name="finance_receipt_allocation",
    )
    op.drop_index(
        op.f("ix_finance_receipt_allocation_receipt_id"),
        table_name="finance_receipt_allocation",
    )
    op.drop_table("finance_receipt_allocation")
    op.drop_index(
        op.f("ix_finance_receipt_customer_user_id"),
        table_name="finance_receipt",
    )
    op.drop_index(op.f("ix_finance_receipt_gym_id"), table_name="finance_receipt")
    op.drop_table("finance_receipt")

    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage', "
        "'finance.catalog.manage', 'finance.invoice.manage')",
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event",
        "finance_journal",
        "event_type IN ('OPENING_BALANCE', 'CORRECTION', "
        "'INVOICE_ISSUED', 'INVOICE_VOID')",
    )
