"""add finance journal, accounts, periods and idempotency

Revision ID: c3e5f7a9b1d2
Revises: b2d4e6f8a0c1
Create Date: 2026-11-02 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e5f7a9b1d2"
down_revision: str | None = "b2d4e6f8a0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABLE_TABLES = (
    "finance_journal",
    "finance_journal_line",
    "finance_audit",
)


def upgrade() -> None:
    op.create_table(
        "finance_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "code", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False
        ),
        sa.Column(
            "type", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "type IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')",
            name="ck_finance_account_type",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gym_id", "code", name="uq_finance_account_gym_code"),
    )
    op.create_index(
        op.f("ix_finance_account_gym_id"),
        "finance_account",
        ["gym_id"],
        unique=False,
    )
    # Existing gyms need the same minimal chart as newly created ones.
    op.execute(
        """
        INSERT INTO finance_account (id, gym_id, code, name, type, created_at)
        SELECT gen_random_uuid(), gym.id, defaults.code, defaults.name,
               defaults.type, now()
        FROM gym
        CROSS JOIN (
            VALUES ('1000', 'نقد و بانک', 'ASSET'),
                   ('1100', 'مطالبات', 'ASSET'),
                   ('2000', 'بدهی‌ها', 'LIABILITY'),
                   ('3000', 'سرمایه افتتاحیه', 'EQUITY'),
                   ('4000', 'درآمد', 'INCOME'),
                   ('5000', 'هزینه‌ها', 'EXPENSE')
        ) AS defaults(code, name, type)
        """
    )

    op.create_table(
        "finance_period",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "opened_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.Column(
            "closed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True
        ),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["closed_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_period_gym_id"),
        "finance_period",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        "uq_finance_period_open",
        "finance_period",
        ["gym_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )

    op.create_table(
        "finance_sequence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "doc_type",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "doc_type", name="uq_finance_sequence_doc"
        ),
    )
    op.create_index(
        op.f("ix_finance_sequence_gym_id"),
        "finance_sequence",
        ["gym_id"],
        unique=False,
    )

    op.create_table(
        "finance_journal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column("period_id", sa.Uuid(), nullable=False),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        sa.Column(
            "event_type",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("reversal_of_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('OPENING_BALANCE', 'CORRECTION')",
            name="ck_finance_journal_event",
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["period_id"], ["finance_period.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"], ["finance_journal.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "entry_number", name="uq_finance_journal_number"
        ),
    )
    op.create_index(
        op.f("ix_finance_journal_gym_id"),
        "finance_journal",
        ["gym_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_journal_period_id"),
        "finance_journal",
        ["period_id"],
        unique=False,
    )
    op.create_index(
        "uq_finance_journal_opening",
        "finance_journal",
        ["gym_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'OPENING_BALANCE'"),
    )
    op.create_index(
        "uq_finance_journal_reversal",
        "finance_journal",
        ["reversal_of_id"],
        unique=True,
        postgresql_where=sa.text("reversal_of_id IS NOT NULL"),
    )

    op.create_table(
        "finance_journal_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("debit_irr", sa.BigInteger(), nullable=False),
        sa.Column("credit_irr", sa.BigInteger(), nullable=False),
        sa.Column(
            "memo", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True
        ),
        sa.CheckConstraint(
            "debit_irr >= 0 AND credit_irr >= 0",
            name="ck_finance_line_nonnegative",
        ),
        sa.CheckConstraint(
            "(debit_irr > 0) <> (credit_irr > 0)",
            name="ck_finance_line_single_side",
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["finance_journal.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["finance_account.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_journal_line_journal_id"),
        "finance_journal_line",
        ["journal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finance_journal_line_account_id"),
        "finance_journal_line",
        ["account_id"],
        unique=False,
    )

    op.create_table(
        "finance_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gym_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation_key",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=False,
        ),
        sa.Column(
            "request_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column(
            "result_type",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gym_id", "operation_key", name="uq_finance_operation_key"
        ),
    )
    op.create_index(
        op.f("ix_finance_operation_gym_id"),
        "finance_operation",
        ["gym_id"],
        unique=False,
    )

    # Posted financial rows are append-only. The API offers no edit/delete
    # path; this trigger makes the guarantee hold for direct SQL as well.
    op.execute(
        """
        CREATE FUNCTION finance_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'finance posted records are immutable';
        END;
        $$;
        """
    )
    for table in IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION finance_reject_mutation();
            """
        )


def downgrade() -> None:
    for table in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION finance_reject_mutation()")

    op.drop_index(
        op.f("ix_finance_operation_gym_id"), table_name="finance_operation"
    )
    op.drop_table("finance_operation")
    op.drop_index(
        op.f("ix_finance_journal_line_account_id"),
        table_name="finance_journal_line",
    )
    op.drop_index(
        op.f("ix_finance_journal_line_journal_id"),
        table_name="finance_journal_line",
    )
    op.drop_table("finance_journal_line")
    op.drop_index(
        "uq_finance_journal_reversal", table_name="finance_journal"
    )
    op.drop_index(
        "uq_finance_journal_opening", table_name="finance_journal"
    )
    op.drop_index(
        op.f("ix_finance_journal_period_id"), table_name="finance_journal"
    )
    op.drop_index(
        op.f("ix_finance_journal_gym_id"), table_name="finance_journal"
    )
    op.drop_table("finance_journal")
    op.drop_index(
        op.f("ix_finance_sequence_gym_id"), table_name="finance_sequence"
    )
    op.drop_table("finance_sequence")
    op.drop_index("uq_finance_period_open", table_name="finance_period")
    op.drop_index(
        op.f("ix_finance_period_gym_id"), table_name="finance_period"
    )
    op.drop_table("finance_period")
    op.drop_index(
        op.f("ix_finance_account_gym_id"), table_name="finance_account"
    )
    op.drop_table("finance_account")
