"""capture sale snapshots, refund method origin and reminder support

Revision ID: e5f7a9b1c3d6
Revises: d4e6f8a0b2c5
Create Date: 2026-11-03 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f7a9b1c3d6"
down_revision: str | None = "d4e6f8a0b2c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "finance_invoice",
        sa.Column(
            "acquisition_source",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="GYM",
        ),
    )
    op.add_column(
        "finance_invoice",
        sa.Column(
            "discount_funding",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="GYM",
        ),
    )
    op.create_check_constraint(
        "ck_finance_invoice_source",
        "finance_invoice",
        "acquisition_source IN ('GYM', 'ASCORA')",
    )
    op.create_check_constraint(
        "ck_finance_invoice_discount_funding",
        "finance_invoice",
        "discount_funding IN ('GYM', 'COACH', 'ASCORA', 'MIXED')",
    )

    op.add_column(
        "finance_refund",
        sa.Column(
            "original_method",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "finance_refund",
        sa.Column(
            "method_override_reason",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("finance_refund", "method_override_reason")
    op.drop_column("finance_refund", "original_method")
    op.drop_constraint(
        "ck_finance_invoice_discount_funding",
        "finance_invoice",
        type_="check",
    )
    op.drop_constraint(
        "ck_finance_invoice_source", "finance_invoice", type_="check"
    )
    op.drop_column("finance_invoice", "discount_funding")
    op.drop_column("finance_invoice", "acquisition_source")
