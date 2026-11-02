"""snapshot coach agreement terms on invoice lines

Revision ID: a8c0d2e4f6b8
Revises: f7a9b1c3d5e7
Create Date: 2026-11-03 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c0d2e4f6b8"
down_revision: str | None = "f7a9b1c3d5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "finance_invoice_line",
        sa.Column("coach_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("coach_agreement_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("coach_agreement_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column(
            "coach_allocation_status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="NOT_APPLICABLE",
        ),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("agreement_snapshot", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_finance_invoice_line_coach_user",
        "finance_invoice_line",
        "user",
        ["coach_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_finance_invoice_line_coach_agreement",
        "finance_invoice_line",
        "finance_coach_agreement",
        ["coach_agreement_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_finance_invoice_line_coach_user_id"),
        "finance_invoice_line",
        ["coach_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_finance_invoice_line_coach_user_id"),
        table_name="finance_invoice_line",
    )
    op.drop_constraint(
        "fk_finance_invoice_line_coach_agreement",
        "finance_invoice_line",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_finance_invoice_line_coach_user",
        "finance_invoice_line",
        type_="foreignkey",
    )
    op.drop_column("finance_invoice_line", "agreement_snapshot")
    op.drop_column("finance_invoice_line", "coach_allocation_status")
    op.drop_column("finance_invoice_line", "coach_agreement_version")
    op.drop_column("finance_invoice_line", "coach_agreement_id")
    op.drop_column("finance_invoice_line", "coach_user_id")
