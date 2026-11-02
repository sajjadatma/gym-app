"""allow coach agreement and settlement grants

Revision ID: a4b6c8d0e2f4
Revises: f3a5c7e9b1d3
Create Date: 2026-11-03 13:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b6c8d0e2f4"
down_revision: str | None = "f3a5c7e9b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = (
    "permission IN ('finance.opening.manage', 'finance.period.manage', "
    "'finance.catalog.manage', 'finance.invoice.manage', "
    "'finance.payment.record', 'finance.refund.manage', "
    "'finance.expense.manage', 'finance.membership.manage')"
)
NEW = (
    "permission IN ('finance.opening.manage', 'finance.period.manage', "
    "'finance.catalog.manage', 'finance.invoice.manage', "
    "'finance.payment.record', 'finance.refund.manage', "
    "'finance.expense.manage', 'finance.membership.manage', "
    "'finance.coach_agreement.manage', 'finance.settlement.manage')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission", "finance_grant", NEW
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM finance_grant WHERE permission IN "
        "('finance.coach_agreement.manage', 'finance.settlement.manage')"
    )
    op.drop_constraint(
        "ck_finance_grant_permission", "finance_grant", type_="check"
    )
    op.create_check_constraint(
        "ck_finance_grant_permission", "finance_grant", OLD
    )
