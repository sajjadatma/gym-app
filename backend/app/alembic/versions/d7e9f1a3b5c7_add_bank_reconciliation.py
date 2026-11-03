"""add manual bank statement reconciliation

Revision ID: d7e9f1a3b5c7
Revises: c6d8e0f2a4b6
Create Date: 2026-11-03 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e9f1a3b5c7"
down_revision: str | None = "c6d8e0f2a4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_bank_statement_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("statement_on", sa.Date(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "reference",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("matched_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "matched_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_reconciliation_amount"
        ),
        sa.CheckConstraint(
            "status IN ('UNMATCHED', 'MATCHED')",
            name="ck_finance_reconciliation_status",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["finance_receipt.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["matched_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id", name="uq_finance_reconciliation_receipt"
        ),
    )
    op.create_index(
        op.f("ix_finance_bank_statement_line_gym_id"),
        "finance_bank_statement_line",
        ["gym_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_bank_statement_line_gym_id"),
        table_name="finance_bank_statement_line",
    )
    op.drop_table("finance_bank_statement_line")
