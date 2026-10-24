"""Bind each workout day to an optional weekday key.

Revision ID: f1a2c3d4e5f6
Revises: c9324e715a60
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2c3d4e5f6"
down_revision = "c9324e715a60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workout_day",
        sa.Column("weekday", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workout_day", "weekday")
