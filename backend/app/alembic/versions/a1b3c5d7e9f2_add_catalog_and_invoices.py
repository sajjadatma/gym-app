"""add commercial catalog, invoices and journal source links

Revision ID: a1b3c5d7e9f2
Revises: f6b8c0d2e4a6
Create Date: 2026-11-03 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b3c5d7e9f2"
down_revision: str | None = "f6b8c0d2e4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINE_KINDS = (
    "('MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', 'PRODUCT', 'SERVICE', "
    "'CUSTOM')"
)


def upgrade() -> None:
    op.add_column(
        "finance_journal",
        sa.Column(
            "source_type",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        "finance_journal", sa.Column("source_id", sa.Uuid(), nullable=True)
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
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage', "
        "'finance.catalog.manage', 'finance.invoice.manage')",
    )

    op.create_table(
        "finance_catalog_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "kind", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("default_price_irr", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(f"kind IN {LINE_KINDS}", name="ck_finance_catalog_kind"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gym_id", "name", name="uq_finance_catalog_gym_name"),
    )
    op.create_index(
        op.f("ix_finance_catalog_item_gym_id"),
        "finance_catalog_item",
        ["gym_id"],
        unique=False,
    )

    op.create_table(
        "finance_invoice",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("customer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "customer_name",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("invoice_number", sa.Integer(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column("subtotal_irr", sa.BigInteger(), nullable=False),
        sa.Column("discount_irr", sa.BigInteger(), nullable=False),
        sa.Column("total_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "void_reason",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column(
            "voided_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column(
            "issued_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'VOID')",
            name="ck_finance_invoice_status",
        ),
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
            "gym_id", "invoice_number", name="uq_finance_invoice_number"
        ),
    )
    op.create_index(
        op.f("ix_finance_invoice_gym_id"),
        "finance_invoice",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_invoice_customer_user_id"),
        "finance_invoice",
        ["customer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_invoice_status"),
        "finance_invoice",
        ["status"],
        unique=False,
    )

    op.create_table(
        "finance_invoice_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_irr", sa.BigInteger(), nullable=False),
        sa.Column("line_discount_irr", sa.BigInteger(), nullable=False),
        sa.Column("net_irr", sa.BigInteger(), nullable=False),
        sa.Column("discount_share_irr", sa.BigInteger(), nullable=False),
        sa.Column("payable_irr", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_finance_invoice_line_qty"),
        sa.CheckConstraint(
            "unit_price_irr >= 0 AND line_discount_irr >= 0 "
            "AND net_irr >= 0 AND discount_share_irr >= 0 AND payable_irr >= 0",
            name="ck_finance_invoice_line_amounts",
        ),
        sa.CheckConstraint(
            f"kind IN {LINE_KINDS}", name="ck_finance_invoice_line_kind"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"],
            ["finance_catalog_item.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id", "line_number", name="uq_finance_invoice_line_number"
        ),
    )
    op.create_index(
        op.f("ix_finance_invoice_line_invoice_id"),
        "finance_invoice_line",
        ["invoice_id"],
        unique=False,
    )

    op.create_table(
        "finance_installment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id", "sequence", name="uq_finance_installment_sequence"
        ),
    )
    op.create_index(
        op.f("ix_finance_installment_invoice_id"),
        "finance_installment",
        ["invoice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_installment_invoice_id"), table_name="finance_installment"
    )
    op.drop_table("finance_installment")
    op.drop_index(
        op.f("ix_finance_invoice_line_invoice_id"),
        table_name="finance_invoice_line",
    )
    op.drop_table("finance_invoice_line")
    op.drop_index(op.f("ix_finance_invoice_status"), table_name="finance_invoice")
    op.drop_index(
        op.f("ix_finance_invoice_customer_user_id"),
        table_name="finance_invoice",
    )
    op.drop_index(op.f("ix_finance_invoice_gym_id"), table_name="finance_invoice")
    op.drop_table("finance_invoice")
    op.drop_index(
        op.f("ix_finance_catalog_item_gym_id"),
        table_name="finance_catalog_item",
    )
    op.drop_table("finance_catalog_item")

    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage')",
    )
    op.drop_constraint(
        "ck_finance_journal_event", "finance_journal", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_journal_event",
        "finance_journal",
        "event_type IN ('OPENING_BALANCE', 'CORRECTION')",
    )
    op.drop_column("finance_journal", "source_id")
    op.drop_column("finance_journal", "source_type")
