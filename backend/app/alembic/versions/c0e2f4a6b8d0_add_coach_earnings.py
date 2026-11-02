"""add coach earnings from confirmed collections

Revision ID: c0e2f4a6b8d0
Revises: b9d1e3f5a7c9
Create Date: 2026-11-03 11:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0e2f4a6b8d0"
down_revision: str | None = "b9d1e3f5a7c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_coach_earning",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("coach_user_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_line_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("credit_movement_id", sa.Uuid(), nullable=True),
        sa.Column(
            "source_key",
            sqlmodel.sql.sqltypes.AutoString(length=120),
            nullable=False,
        ),
        sa.Column("agreement_id", sa.Uuid(), nullable=True),
        sa.Column("agreement_version", sa.Integer(), nullable=True),
        sa.Column(
            "discount_funding",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("base_irr", sa.BigInteger(), nullable=False),
        sa.Column("discount_irr", sa.BigInteger(), nullable=False),
        sa.Column("coach_share_irr", sa.BigInteger(), nullable=False),
        sa.Column("platform_share_irr", sa.BigInteger(), nullable=False),
        sa.Column("gym_share_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "unresolved_reason",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.Column(
            "vesting_mode",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("vesting_date", sa.Date(), nullable=True),
        sa.Column(
            "vested_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("vested_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "vesting_reason",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "base_irr >= 0 AND discount_irr >= 0 AND coach_share_irr >= 0 "
            "AND platform_share_irr >= 0 AND gym_share_irr >= 0",
            name="ck_finance_coach_earning_amounts",
        ),
        sa.CheckConstraint(
            "status IN ('CALCULATED', 'UNRESOLVED')",
            name="ck_finance_coach_earning_status",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["coach_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["finance_invoice.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"],
            ["finance_invoice_line.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["finance_receipt.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["credit_movement_id"],
            ["finance_credit_movement.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["agreement_id"],
            ["finance_coach_agreement.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vested_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "source_key", name="uq_finance_coach_earning_source"
        ),
    )
    for column in (
        "gym_id",
        "coach_user_id",
        "invoice_id",
        "invoice_line_id",
        "receipt_id",
    ):
        op.create_index(
            op.f(f"ix_finance_coach_earning_{column}"),
            "finance_coach_earning",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "receipt_id",
        "invoice_line_id",
        "invoice_id",
        "coach_user_id",
        "gym_id",
    ):
        op.drop_index(
            op.f(f"ix_finance_coach_earning_{column}"),
            table_name="finance_coach_earning",
        )
    op.drop_table("finance_coach_earning")
