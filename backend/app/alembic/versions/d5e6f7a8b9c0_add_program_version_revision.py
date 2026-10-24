"""Add revision to workout program versions for optimistic concurrency.

Revision ID: d5e6f7a8b9c0
Revises: c4a7d9e2b135
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4a7d9e2b135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workout_program_version",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("workout_program_version", "revision")
