"""add user phone

Revision ID: f0a1b2c3d4e5
Revises: d5e6f7a8b9c0
Create Date: 2026-10-25 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user", sa.Column("phone", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user", "phone")
