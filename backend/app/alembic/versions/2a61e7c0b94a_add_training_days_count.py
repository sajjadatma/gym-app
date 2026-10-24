"""Store training frequency as a count instead of selected weekdays.

Revision ID: 2a61e7c0b94a
Revises: f1a2c3d4e5f6
"""

import sqlalchemy as sa
from alembic import op

revision = "2a61e7c0b94a"
down_revision = "f1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "athlete_profile",
        sa.Column("training_days_count", sa.Integer(), nullable=True),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """UPDATE athlete_profile
               SET training_days_count = json_array_length(training_days)
               WHERE json_array_length(training_days) BETWEEN 1 AND 7"""
        )
    )


def downgrade() -> None:
    op.drop_column("athlete_profile", "training_days_count")
