"""add coach plans, program purchases and program origin

Revision ID: b8d1e2f3a4c5
Revises: a7c3d9e1b2f4
Create Date: 2026-11-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b8d1e2f3a4c5'
down_revision = 'a7c3d9e1b2f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'finance_coach_plan',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('gym_id', sa.Uuid(), nullable=False),
        sa.Column('coach_user_id', sa.Uuid(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column('base_price_irr', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column('updated_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.CheckConstraint("category = 'TRAINING'", name='ck_finance_coach_plan_category'),
        sa.CheckConstraint('base_price_irr > 0', name='ck_finance_coach_plan_price'),
        sa.ForeignKeyConstraint(['coach_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['gym_id'], ['gym.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_finance_coach_plan_coach_user_id'), 'finance_coach_plan', ['coach_user_id'], unique=False)
    op.create_index(op.f('ix_finance_coach_plan_gym_id'), 'finance_coach_plan', ['gym_id'], unique=False)
    op.create_index(
        'uq_finance_coach_plan_active',
        'finance_coach_plan',
        ['gym_id', 'coach_user_id', 'category'],
        unique=True,
        postgresql_where=sa.text('is_active'),
    )

    op.create_table(
        'finance_program_request',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('gym_id', sa.Uuid(), nullable=False),
        sa.Column('athlete_user_id', sa.Uuid(), nullable=False),
        sa.Column('coach_user_id', sa.Uuid(), nullable=False),
        sa.Column('plan_id', sa.Uuid(), nullable=False),
        sa.Column('sale_id', sa.Uuid(), nullable=False),
        sa.Column('plan_title', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column('base_price_irr', sa.Integer(), nullable=False),
        sa.Column('total_amount_irr', sa.Integer(), nullable=False),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column('fulfilled_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.CheckConstraint("status IN ('REQUESTED', 'FULFILLED', 'CANCELLED')", name='ck_finance_program_request_status'),
        sa.CheckConstraint('base_price_irr >= 0 AND total_amount_irr >= 0', name='ck_finance_program_request_amounts'),
        sa.ForeignKeyConstraint(['athlete_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['coach_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['gym_id'], ['gym.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['finance_coach_plan.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['sale_id'], ['finance_sale.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sale_id', name='uq_finance_program_request_sale'),
    )
    op.create_index(op.f('ix_finance_program_request_athlete_user_id'), 'finance_program_request', ['athlete_user_id'], unique=False)
    op.create_index(op.f('ix_finance_program_request_coach_user_id'), 'finance_program_request', ['coach_user_id'], unique=False)
    op.create_index(op.f('ix_finance_program_request_gym_id'), 'finance_program_request', ['gym_id'], unique=False)
    op.create_index(op.f('ix_finance_program_request_plan_id'), 'finance_program_request', ['plan_id'], unique=False)
    op.create_index(op.f('ix_finance_program_request_sale_id'), 'finance_program_request', ['sale_id'], unique=False)

    op.add_column('finance_sale', sa.Column('athlete_user_id', sa.Uuid(), nullable=True))
    op.add_column('finance_sale', sa.Column('coach_plan_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_finance_sale_athlete_user_id'), 'finance_sale', ['athlete_user_id'], unique=False)
    op.create_index(op.f('ix_finance_sale_coach_plan_id'), 'finance_sale', ['coach_plan_id'], unique=False)
    op.create_foreign_key('fk_finance_sale_athlete_user', 'finance_sale', 'user', ['athlete_user_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_finance_sale_coach_plan', 'finance_sale', 'finance_coach_plan', ['coach_plan_id'], ['id'], ondelete='RESTRICT')

    op.add_column(
        'workout_program_version',
        sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=20), server_default='LEGACY', nullable=False),
    )
    op.add_column('workout_program_version', sa.Column('purchase_request_id', sa.Uuid(), nullable=True))
    op.add_column('workout_program_version', sa.Column('free_reason', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))
    op.add_column('workout_program_version', sa.Column('free_granted_by_id', sa.Uuid(), nullable=True))
    op.create_check_constraint(
        'ck_program_version_origin',
        'workout_program_version',
        "origin IN ('LEGACY', 'PURCHASED', 'FREE')",
    )
    op.create_index(
        'uq_program_version_purchase_request',
        'workout_program_version',
        ['purchase_request_id'],
        unique=True,
        postgresql_where=sa.text('purchase_request_id IS NOT NULL'),
    )
    op.create_foreign_key(
        'fk_program_version_purchase_request',
        'workout_program_version',
        'finance_program_request',
        ['purchase_request_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_program_version_free_granted_by',
        'workout_program_version',
        'user',
        ['free_granted_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_program_version_free_granted_by', 'workout_program_version', type_='foreignkey')
    op.drop_constraint('fk_program_version_purchase_request', 'workout_program_version', type_='foreignkey')
    op.drop_index('uq_program_version_purchase_request', table_name='workout_program_version')
    op.drop_constraint('ck_program_version_origin', 'workout_program_version', type_='check')
    op.drop_column('workout_program_version', 'free_granted_by_id')
    op.drop_column('workout_program_version', 'free_reason')
    op.drop_column('workout_program_version', 'purchase_request_id')
    op.drop_column('workout_program_version', 'origin')

    op.drop_constraint('fk_finance_sale_coach_plan', 'finance_sale', type_='foreignkey')
    op.drop_constraint('fk_finance_sale_athlete_user', 'finance_sale', type_='foreignkey')
    op.drop_index(op.f('ix_finance_sale_coach_plan_id'), table_name='finance_sale')
    op.drop_index(op.f('ix_finance_sale_athlete_user_id'), table_name='finance_sale')
    op.drop_column('finance_sale', 'coach_plan_id')
    op.drop_column('finance_sale', 'athlete_user_id')

    op.drop_index(op.f('ix_finance_program_request_sale_id'), table_name='finance_program_request')
    op.drop_index(op.f('ix_finance_program_request_plan_id'), table_name='finance_program_request')
    op.drop_index(op.f('ix_finance_program_request_gym_id'), table_name='finance_program_request')
    op.drop_index(op.f('ix_finance_program_request_coach_user_id'), table_name='finance_program_request')
    op.drop_index(op.f('ix_finance_program_request_athlete_user_id'), table_name='finance_program_request')
    op.drop_table('finance_program_request')

    op.drop_index('uq_finance_coach_plan_active', table_name='finance_coach_plan')
    op.drop_index(op.f('ix_finance_coach_plan_gym_id'), table_name='finance_coach_plan')
    op.drop_index(op.f('ix_finance_coach_plan_coach_user_id'), table_name='finance_coach_plan')
    op.drop_table('finance_coach_plan')
