"""add periodic fixed coach compensation to agreements

Revision ID: c6d8e0f2a4b6
Revises: b5c7d9e1f3a5
Create Date: 2026-11-03 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d8e0f2a4b6"
down_revision: str | None = "b5c7d9e1f3a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "finance_coach_agreement",
        sa.Column(
            "periodic_fixed_irr",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "finance_coach_agreement",
        sa.Column(
            "periodic_interval",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="NONE",
        ),
    )
    op.create_check_constraint(
        "ck_finance_coach_agreement_periodic",
        "finance_coach_agreement",
        "periodic_interval IN ('NONE', 'MONTHLY')",
    )
    op.create_check_constraint(
        "ck_finance_coach_agreement_periodic_amount",
        "finance_coach_agreement",
        "periodic_fixed_irr >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_finance_coach_agreement_periodic_amount",
        "finance_coach_agreement",
        type_="check",
    )
    op.drop_constraint(
        "ck_finance_coach_agreement_periodic",
        "finance_coach_agreement",
        type_="check",
    )
    op.drop_column("finance_coach_agreement", "periodic_interval")
    op.drop_column("finance_coach_agreement", "periodic_fixed_irr")
