"""add finance settings, audit and finance staff role

Revision ID: b2d4e6f8a0c1
Revises: c1d2e3f4a5b6
Create Date: 2026-11-02 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d4e6f8a0c1"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_membership_role", "gym_membership_role", type_="check"
    )
    op.create_check_constraint(
        "ck_membership_role",
        "gym_membership_role",
        "role IN ('GYM_ADMIN', 'COACH', 'ATHLETE', 'FINANCE_STAFF')",
    )

    op.create_table(
        "finance_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "display_unit",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "display_unit IN ('RIAL', 'TOMAN')",
            name="ck_finance_settings_display_unit",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_settings_gym_id"),
        "finance_settings",
        ["gym_id"],
        unique=True,
    )

    op.create_table(
        "finance_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column(
            "target_type",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_audit_action"), "finance_audit", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_finance_audit_actor_id"),
        "finance_audit",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_audit_gym_id"),
        "finance_audit",
        ["gym_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_finance_audit_gym_id"), table_name="finance_audit")
    op.drop_index(op.f("ix_finance_audit_actor_id"), table_name="finance_audit")
    op.drop_index(op.f("ix_finance_audit_action"), table_name="finance_audit")
    op.drop_table("finance_audit")
    op.drop_index(
        op.f("ix_finance_settings_gym_id"), table_name="finance_settings"
    )
    op.drop_table("finance_settings")

    op.drop_constraint(
        "ck_membership_role", "gym_membership_role", type_="check"
    )
    # Fails loudly if FINANCE_STAFF rows still exist: silently deleting role
    # assignments during a downgrade would remove access without review.
    op.create_check_constraint(
        "ck_membership_role",
        "gym_membership_role",
        "role IN ('GYM_ADMIN', 'COACH', 'ATHLETE')",
    )
