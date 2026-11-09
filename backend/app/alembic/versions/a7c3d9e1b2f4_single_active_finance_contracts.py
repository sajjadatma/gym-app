"""single active finance contracts

Revision ID: a7c3d9e1b2f4
Revises: f98a3171880c
Create Date: 2026-11-09 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3d9e1b2f4'
down_revision = 'f98a3171880c'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY scope, gym_id
                       ORDER BY version DESC, created_at DESC, id DESC
                   ) AS rn
            FROM finance_platform_contract
            WHERE status = 'ACTIVE'
        )
        UPDATE finance_platform_contract AS contract
        SET status = 'ARCHIVED'
        FROM ranked
        WHERE contract.id = ranked.id AND ranked.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY gym_id, coach_user_id, category
                       ORDER BY version DESC, created_at DESC, id DESC
                   ) AS rn
            FROM finance_coach_contract
            WHERE status = 'ACTIVE'
        )
        UPDATE finance_coach_contract AS contract
        SET status = 'ARCHIVED'
        FROM ranked
        WHERE contract.id = ranked.id AND ranked.rn > 1
        """
    )
    op.create_index(
        'uq_finance_platform_contract_active_gym',
        'finance_platform_contract',
        ['gym_id'],
        unique=True,
        postgresql_where=sa.text("scope = 'GYM' AND status = 'ACTIVE'"),
    )
    op.create_index(
        'uq_finance_platform_contract_active_default',
        'finance_platform_contract',
        ['scope'],
        unique=True,
        postgresql_where=sa.text("scope = 'DEFAULT' AND status = 'ACTIVE'"),
    )
    op.create_index(
        'uq_finance_coach_contract_active',
        'finance_coach_contract',
        ['gym_id', 'coach_user_id', 'category'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade():
    op.drop_index(
        'uq_finance_coach_contract_active',
        table_name='finance_coach_contract',
    )
    op.drop_index(
        'uq_finance_platform_contract_active_default',
        table_name='finance_platform_contract',
    )
    op.drop_index(
        'uq_finance_platform_contract_active_gym',
        table_name='finance_platform_contract',
    )
