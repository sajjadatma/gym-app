"""add paid gym memberships and athlete self-service

Revision ID: d4e6f8a0b2c5
Revises: c3d5e7f9a1b4
Create Date: 2026-11-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0b2c5"
down_revision: str | None = "c3d5e7f9a1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission",
        "finance_grant",
        "permission IN ('finance.opening.manage', 'finance.period.manage', "
        "'finance.catalog.manage', 'finance.invoice.manage', "
        "'finance.payment.record', 'finance.refund.manage', "
        "'finance.expense.manage', 'finance.membership.manage')",
    )

    op.create_table(
        "finance_membership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("athlete_user_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("access_required_irr", sa.BigInteger(), nullable=False),
        sa.Column("frozen_at", sa.Date(), nullable=True),
        sa.Column("frozen_days", sa.Integer(), nullable=False),
        sa.Column("cancelled_at", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column(
            "updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'FROZEN', 'CANCELLED', 'EXPIRED')",
            name="ck_finance_membership_status",
        ),
        sa.CheckConstraint(
            "end_date >= start_date", name="ck_finance_membership_dates"
        ),
        sa.CheckConstraint(
            "access_required_irr >= 0",
            name="ck_finance_membership_access_amount",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["athlete_user_id"], ["user.id"], ondelete="RESTRICT"
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
        op.f("ix_finance_membership_gym_id"),
        "finance_membership",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_membership_athlete_user_id"),
        "finance_membership",
        ["athlete_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_finance_membership_active",
        "finance_membership",
        ["gym_id", "athlete_user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'FROZEN')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_finance_membership_active", table_name="finance_membership"
    )
    op.drop_index(
        op.f("ix_finance_membership_athlete_user_id"),
        table_name="finance_membership",
    )
    op.drop_index(
        op.f("ix_finance_membership_gym_id"), table_name="finance_membership"
    )
    op.drop_table("finance_membership")

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
