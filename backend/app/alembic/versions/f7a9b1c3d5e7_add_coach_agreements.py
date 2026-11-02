"""add versioned coach agreements and terms

Revision ID: f7a9b1c3d5e7
Revises: e5f7a9b1c3d6
Create Date: 2026-11-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a9b1c3d5e7"
down_revision: str | None = "e5f7a9b1c3d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_coach_agreement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("coach_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "mode", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "vesting_mode",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("vesting_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "notes",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column("activated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "activated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ENDED')",
            name="ck_finance_coach_agreement_status",
        ),
        sa.CheckConstraint(
            "mode IN ('DIRECT', 'WATERFALL')",
            name="ck_finance_coach_agreement_mode",
        ),
        sa.CheckConstraint(
            "vesting_mode IN ('ON_DATE', 'MANUAL')",
            name="ck_finance_coach_agreement_vesting",
        ),
        sa.CheckConstraint(
            "vesting_days >= 0", name="ck_finance_coach_agreement_days"
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_finance_coach_agreement_dates",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["coach_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id",
            "coach_user_id",
            "version",
            name="uq_finance_coach_agreement_version",
        ),
    )
    op.create_index(
        op.f("ix_finance_coach_agreement_gym_id"),
        "finance_coach_agreement",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_coach_agreement_coach_user_id"),
        "finance_coach_agreement",
        ["coach_user_id"],
        unique=False,
    )

    op.create_table(
        "finance_coach_agreement_term",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "recipient",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "basis", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("percent_bp", sa.Integer(), nullable=False),
        sa.Column("fixed_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "label",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.CheckConstraint(
            "recipient IN ('COACH', 'ASCORA', 'GYM')",
            name="ck_finance_coach_term_recipient",
        ),
        sa.CheckConstraint(
            "basis IN ('PERCENT', 'FIXED')",
            name="ck_finance_coach_term_basis",
        ),
        sa.CheckConstraint(
            "percent_bp >= 0 AND percent_bp <= 10000",
            name="ck_finance_coach_term_percent",
        ),
        sa.CheckConstraint(
            "fixed_irr >= 0", name="ck_finance_coach_term_fixed"
        ),
        sa.ForeignKeyConstraint(
            ["agreement_id"],
            ["finance_coach_agreement.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agreement_id",
            "sequence",
            name="uq_finance_coach_term_sequence",
        ),
    )
    op.create_index(
        op.f("ix_finance_coach_agreement_term_agreement_id"),
        "finance_coach_agreement_term",
        ["agreement_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_coach_agreement_term_agreement_id"),
        table_name="finance_coach_agreement_term",
    )
    op.drop_table("finance_coach_agreement_term")
    op.drop_index(
        op.f("ix_finance_coach_agreement_coach_user_id"),
        table_name="finance_coach_agreement",
    )
    op.drop_index(
        op.f("ix_finance_coach_agreement_gym_id"),
        table_name="finance_coach_agreement",
    )
    op.drop_table("finance_coach_agreement")
