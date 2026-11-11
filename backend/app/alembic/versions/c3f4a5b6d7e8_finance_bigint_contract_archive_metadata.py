"""finance bigint amounts and contract archive metadata

Revision ID: c3f4a5b6d7e8
Revises: b8d1e2f3a4c5
Create Date: 2026-11-10 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "c3f4a5b6d7e8"
down_revision = "b8d1e2f3a4c5"
branch_labels = None
depends_on = None


MONEY_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("finance_tax_definition", "fixed_amount_irr", True),
    ("finance_coach_plan", "base_price_irr", False),
    ("finance_program_request", "base_price_irr", False),
    ("finance_program_request", "total_amount_irr", False),
    ("finance_sale", "base_amount_irr", False),
    ("finance_sale", "tax_amount_irr", False),
    ("finance_sale", "total_amount_irr", False),
    ("finance_sale", "platform_amount_irr", False),
    ("finance_sale", "gym_amount_irr", False),
    ("finance_sale", "coach_amount_irr", False),
    ("finance_sale_tax", "fixed_amount_irr", True),
    ("finance_sale_tax", "amount_irr", False),
    ("finance_payment", "amount_irr", False),
    ("finance_allocation", "amount_irr", False),
    ("finance_settlement", "amount_irr", False),
    ("finance_settlement_item", "amount_irr", False),
    ("finance_refund", "amount_irr", False),
    ("finance_refund_adjustment", "amount_irr", False),
)


def upgrade() -> None:
    for table, column, nullable in MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=nullable,
        )

    op.add_column(
        "finance_platform_contract",
        sa.Column("archived_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    )
    op.add_column(
        "finance_coach_contract",
        sa.Column("archived_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    )


def _assert_downgrade_is_safe() -> None:
    """Refuse a lossy downgrade when a stored amount exceeds INTEGER."""
    connection = op.get_bind()
    for table, column, _nullable in MONEY_COLUMNS:
        unsafe = connection.execute(
            sa.text(
                f'SELECT 1 FROM "{table}" '
                f'WHERE "{column}" > 2147483647 LIMIT 1'
            )
        ).first()
        if unsafe is not None:
            raise RuntimeError(
                "Refusing finance downgrade: "
                f"{table}.{column} contains values larger than INTEGER. "
                "Keep BIGINT or migrate the data explicitly."
            )


def downgrade() -> None:
    _assert_downgrade_is_safe()

    op.drop_column("finance_coach_contract", "archived_at")
    op.drop_column("finance_platform_contract", "archived_at")

    for table, column, nullable in reversed(MONEY_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=nullable,
        )
