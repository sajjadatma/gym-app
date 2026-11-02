"""allow an opening balance to be restated after a reversal

Revision ID: e5a7b9c1d3f4
Revises: d4f6a8b0c2e3
Create Date: 2026-11-02 21:00:00.000000

The "one opening balance per gym" rule is now "one *unreversed* opening
balance per gym", which SQL cannot express without a mutable flag on posted
rows. The service enforces it under the per-gym finance advisory lock, the
same serialization used for entry numbers and periods. Reversal uniqueness
still guarantees a journal can only be reversed once.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7b9c1d3f4"
down_revision: str | None = "d4f6a8b0c2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_finance_journal_opening", table_name="finance_journal"
    )


def downgrade() -> None:
    # Fails loudly if a gym has more than one opening balance, which is the
    # correct refusal: the old schema could not represent this history.
    op.create_index(
        "uq_finance_journal_opening",
        "finance_journal",
        ["gym_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'OPENING_BALANCE'"),
    )
