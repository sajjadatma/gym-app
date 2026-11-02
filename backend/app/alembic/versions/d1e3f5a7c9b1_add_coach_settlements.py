"""add coach settlements and settlement items

Revision ID: d1e3f5a7c9b1
Revises: c0e2f4a6b8d0
Create Date: 2026-11-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e3f5a7c9b1"
down_revision: str | None = "c0e2f4a6b8d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_coach_settlement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("coach_user_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "method", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "reference",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column(
            "notes",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("journal_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column("confirmed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "confirmed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_coach_settlement_amount"
        ),
        sa.CheckConstraint(
            "status IN ('RECORDED', 'CONFIRMED')",
            name="ck_finance_coach_settlement_status",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["coach_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_coach_settlement_gym_id"),
        "finance_coach_settlement",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_coach_settlement_coach_user_id"),
        "finance_coach_settlement",
        ["coach_user_id"],
        unique=False,
    )

    op.create_table(
        "finance_coach_settlement_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("settlement_id", sa.Uuid(), nullable=False),
        sa.Column("earning_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_finance_settlement_item_amount"
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["finance_coach_settlement.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["earning_id"],
            ["finance_coach_earning.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "settlement_id",
            "earning_id",
            name="uq_finance_settlement_earning",
        ),
    )
    op.create_index(
        op.f("ix_finance_coach_settlement_item_settlement_id"),
        "finance_coach_settlement_item",
        ["settlement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_coach_settlement_item_earning_id"),
        "finance_coach_settlement_item",
        ["earning_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_coach_settlement_item_earning_id"),
        table_name="finance_coach_settlement_item",
    )
    op.drop_index(
        op.f("ix_finance_coach_settlement_item_settlement_id"),
        table_name="finance_coach_settlement_item",
    )
    op.drop_table("finance_coach_settlement_item")
    op.drop_index(
        op.f("ix_finance_coach_settlement_coach_user_id"),
        table_name="finance_coach_settlement",
    )
    op.drop_index(
        op.f("ix_finance_coach_settlement_gym_id"),
        table_name="finance_coach_settlement",
    )
    op.drop_table("finance_coach_settlement")
