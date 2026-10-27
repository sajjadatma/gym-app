"""add gym branding

Revision ID: c1d2e3f4a5b6
Revises: a9b8c7d6e5f4
Create Date: 2026-10-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gym", sa.Column("brand_primary_color", sa.String(length=7), nullable=True)
    )
    op.add_column(
        "gym", sa.Column("brand_accent_color", sa.String(length=7), nullable=True)
    )
    op.add_column(
        "gym", sa.Column("logo_key", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "gym",
        sa.Column("logo_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "gym",
        sa.Column(
            "logo_updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("gym", "logo_updated_at")
    op.drop_column("gym", "logo_content_type")
    op.drop_column("gym", "logo_key")
    op.drop_column("gym", "brand_accent_color")
    op.drop_column("gym", "brand_primary_color")
