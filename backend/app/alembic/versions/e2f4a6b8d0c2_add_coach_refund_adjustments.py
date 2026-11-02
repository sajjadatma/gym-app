"""add coach refund adjustments and manual discrepancies

Revision ID: e2f4a6b8d0c2
Revises: d1e3f5a7c9b1
Create Date: 2026-11-03 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4a6b8d0c2"
down_revision: str | None = "d1e3f5a7c9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_coach_earning_adjustment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("earning_id", sa.Uuid(), nullable=False),
        sa.Column("refund_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column("applied_irr", sa.BigInteger(), nullable=False),
        sa.Column("discrepancy_irr", sa.BigInteger(), nullable=False),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "amount_irr >= 0 AND applied_irr >= 0 AND discrepancy_irr >= 0 "
            "AND applied_irr + discrepancy_irr = amount_irr",
            name="ck_finance_coach_adjustment_amounts",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["earning_id"], ["finance_coach_earning.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["refund_id"], ["finance_refund.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "earning_id",
            "refund_id",
            name="uq_finance_coach_adjustment_refund",
        ),
    )
    op.create_index(
        op.f("ix_finance_coach_earning_adjustment_gym_id"),
        "finance_coach_earning_adjustment",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_coach_earning_adjustment_earning_id"),
        "finance_coach_earning_adjustment",
        ["earning_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_coach_earning_adjustment_refund_id"),
        "finance_coach_earning_adjustment",
        ["refund_id"],
        unique=False,
    )

    op.create_table(
        "finance_coach_discrepancy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("coach_user_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("earning_id", sa.Uuid(), nullable=False),
        sa.Column("refund_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "resolution_note",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column("resolved_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "resolved_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_coach_discrepancy_amount"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'RESOLVED')",
            name="ck_finance_coach_discrepancy_status",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["coach_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["earning_id"], ["finance_coach_earning.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["refund_id"], ["finance_refund.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("gym_id", "coach_user_id", "invoice_id"):
        op.create_index(
            op.f(f"ix_finance_coach_discrepancy_{column}"),
            "finance_coach_discrepancy",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("invoice_id", "coach_user_id", "gym_id"):
        op.drop_index(
            op.f(f"ix_finance_coach_discrepancy_{column}"),
            table_name="finance_coach_discrepancy",
        )
    op.drop_table("finance_coach_discrepancy")
    for column in ("refund_id", "earning_id", "gym_id"):
        op.drop_index(
            op.f(f"ix_finance_coach_earning_adjustment_{column}"),
            table_name="finance_coach_earning_adjustment",
        )
    op.drop_table("finance_coach_earning_adjustment")
