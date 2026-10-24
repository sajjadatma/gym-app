"""Add token version to user for credential rotation.

Revision ID: c4a7d9e2b135
Revises: 2a61e7c0b94a
"""

import sqlalchemy as sa
from alembic import op

revision = "c4a7d9e2b135"
down_revision = "2a61e7c0b94a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user", "token_version")
