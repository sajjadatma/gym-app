"""add finance staff action grants

Revision ID: d4f6a8b0c2e3
Revises: c3e5f7a9b1d2
Create Date: 2026-11-02 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f6a8b0c2e3"
down_revision: str | None = "c3e5f7a9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_grant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "permission",
            sqlmodel.sql.sqltypes.AutoString(length=40),
            nullable=False,
        ),
        sa.Column("amount_limit_irr", sa.BigInteger(), nullable=True),
        sa.Column("granted_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column(
            "revoked_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.CheckConstraint(
            "permission IN ('finance.opening.manage', 'finance.period.manage')",
            name="ck_finance_grant_permission",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["granted_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_grant_gym_id"),
        "finance_grant",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_grant_user_id"),
        "finance_grant",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "uq_finance_grant_active",
        "finance_grant",
        ["gym_id", "user_id", "permission"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_finance_grant_active", table_name="finance_grant")
    op.drop_index(op.f("ix_finance_grant_user_id"), table_name="finance_grant")
    op.drop_index(op.f("ix_finance_grant_gym_id"), table_name="finance_grant")
    op.drop_table("finance_grant")
