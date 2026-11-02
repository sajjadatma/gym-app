"""add coach payable and compensation accounts to existing gyms

Revision ID: f3a5c7e9b1d3
Revises: e2f4a6b8d0c2
Create Date: 2026-11-03 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a5c7e9b1d3"
down_revision: str | None = "e2f4a6b8d0c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO finance_account
                (id, gym_id, code, name, type, created_at)
            SELECT gen_random_uuid(), gym.id, '2100', 'بدهی به مربیان',
                   'LIABILITY', now()
            FROM gym
            ON CONFLICT (gym_id, code) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO finance_account
                (id, gym_id, code, name, type, created_at)
            SELECT gen_random_uuid(), gym.id, '5100', 'حق‌الزحمه مربیان',
                   'EXPENSE', now()
            FROM gym
            ON CONFLICT (gym_id, code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Keep the accounts: coach journals/earnings may still reference them and
    # account rows are harmless in an older schema. Deleting them would make
    # the downgrade fail on the RESTRICT foreign keys.
    pass
