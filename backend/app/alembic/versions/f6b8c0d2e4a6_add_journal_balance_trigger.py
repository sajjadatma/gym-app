"""reject unbalanced journals at the database boundary

Revision ID: f6b8c0d2e4a6
Revises: e5a7b9c1d3f4
Create Date: 2026-11-02 22:00:00.000000

The service already rejects unbalanced journals with a clean error. This
deferred constraint trigger makes the ledger itself refuse an unbalanced or
single-line journal, including direct SQL writes, at transaction end when the
header and its lines are both present.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b8c0d2e4a6"
down_revision: str | None = "e5a7b9c1d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION finance_check_journal_balance() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            total_debit bigint;
            total_credit bigint;
            line_count integer;
        BEGIN
            SELECT COALESCE(SUM(debit_irr), 0),
                   COALESCE(SUM(credit_irr), 0),
                   COUNT(*)
              INTO total_debit, total_credit, line_count
              FROM finance_journal_line
             WHERE journal_id = NEW.id;
            IF total_debit <> total_credit
               OR total_debit <= 0
               OR line_count < 2 THEN
                RAISE EXCEPTION
                    'finance journal % is not balanced', NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER finance_journal_balanced
        AFTER INSERT ON finance_journal
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION finance_check_journal_balance();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER finance_journal_balanced ON finance_journal"
    )
    op.execute("DROP FUNCTION finance_check_journal_balance()")
