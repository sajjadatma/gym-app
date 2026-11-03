"""add separate platform billing, credits and cancellations

Revision ID: f1a2b3c4d5e6
Revises: e8f0a2b4c6d8
Create Date: 2026-11-03 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e8f0a2b4c6d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, nullable: bool = False, primary_key: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.Uuid(),
        primary_key=primary_key,
        nullable=nullable,
    )


def _dt(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, sqlmodel.sql.sqltypes.UTCDateTime(), nullable=nullable
    )


def _str(name: str, length: int, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, sqlmodel.sql.sqltypes.AutoString(length=length), nullable=nullable
    )


def _int(name: str, *, nullable: bool = False, default: int | None = None) -> sa.Column:
    kwargs = {"nullable": nullable}
    if default is not None:
        kwargs["server_default"] = sa.text(str(default))
    return sa.Column(name, sa.BigInteger(), **kwargs)


def upgrade() -> None:
    op.create_table(
        "platform_plan",
        _uuid("id", primary_key=True),
        _str("code", 50),
        _str("name", 255),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_platform_plan_code"),
    )
    op.create_table(
        "platform_plan_version",
        _uuid("id", primary_key=True),
        _uuid("plan_id"),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        _int("monthly_price_irr", default=0),
        sa.Column("limits", sa.JSON(), nullable=False),
        _str("status", 20),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["plan_id"], ["platform_plan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "plan_id", "version_number", name="uq_platform_plan_version"
        ),
        sa.UniqueConstraint(
            "plan_id", "effective_from", name="uq_platform_plan_effective"
        ),
        sa.CheckConstraint(
            "version_number > 0", name="ck_platform_plan_version_number"
        ),
        sa.CheckConstraint("monthly_price_irr >= 0", name="ck_platform_plan_price"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name="ck_platform_plan_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_platform_plan_dates",
        ),
    )
    op.create_table(
        "platform_group",
        _uuid("id", primary_key=True),
        _str("name", 255),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("name", name="uq_platform_group_name"),
    )
    op.create_table(
        "platform_group_member",
        _uuid("id", primary_key=True),
        _uuid("group_id"),
        _uuid("gym_id"),
        sa.Column("allocation_bp", sa.Integer(), nullable=False),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["platform_group.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", "gym_id", name="uq_platform_group_gym"),
        sa.CheckConstraint(
            "allocation_bp >= 0 AND allocation_bp <= 10000",
            name="ck_platform_group_allocation",
        ),
    )
    op.create_table(
        "platform_agreement",
        _uuid("id", primary_key=True),
        _uuid("gym_id", nullable=True),
        _uuid("group_id", nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        _uuid("supersedes_id", nullable=True),
        _str("mode", 20),
        _str("status", 20),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        _uuid("plan_version_id", nullable=True),
        _int("subscription_amount_irr", default=0),
        _str("billing_interval", 20),
        sa.Column("volume_discount_bp", sa.Integer(), nullable=False),
        sa.Column("grace_days", sa.Integer(), nullable=False),
        sa.Column("restrict_after_days", sa.Integer(), nullable=False),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        _dt("activated_at", nullable=True),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["platform_group.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["plan_version_id"], ["platform_plan_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["platform_agreement.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_agreement_scope",
        ),
        sa.CheckConstraint(
            "mode IN ('FREE', 'SUBSCRIPTION', 'COMMISSION', 'HYBRID', 'CUSTOM')",
            name="ck_platform_agreement_mode",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'EFFECTIVE', 'REPLACED', 'DISABLED')",
            name="ck_platform_agreement_status",
        ),
        sa.CheckConstraint(
            "version > 0 AND subscription_amount_irr >= 0 "
            "AND volume_discount_bp >= 0 AND volume_discount_bp <= 10000 "
            "AND grace_days >= 0 AND restrict_after_days >= grace_days",
            name="ck_platform_agreement_amounts",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_platform_agreement_dates",
        ),
    )
    op.create_index(
        "uq_platform_agreement_gym_scope_version",
        "platform_agreement",
        ["gym_id", "effective_from", "version"],
        unique=True,
        postgresql_where=sa.text("gym_id IS NOT NULL"),
    )
    op.create_index(
        "uq_platform_agreement_group_scope_version",
        "platform_agreement",
        ["group_id", "effective_from", "version"],
        unique=True,
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )
    op.create_table(
        "platform_commission_term",
        _uuid("id", primary_key=True),
        _uuid("agreement_id"),
        _str("kind", 20),
        _str("acquisition_source", 20),
        _str("basis", 30),
        sa.Column("percent_bp", sa.Integer(), nullable=False),
        _int("fixed_irr", default=0),
        _int("max_fee_irr", default=0),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["agreement_id"], ["platform_agreement.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "kind IN ('ANY', 'MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', "
            "'PRODUCT', 'SERVICE', 'CUSTOM')",
            name="ck_platform_term_kind",
        ),
        sa.CheckConstraint(
            "acquisition_source IN ('ANY', 'GYM', 'ASCORA')",
            name="ck_platform_term_source",
        ),
        sa.CheckConstraint(
            "basis IN ('PERCENT', 'FIXED', 'PERCENT_PLUS_FIXED')",
            name="ck_platform_term_basis",
        ),
        sa.CheckConstraint(
            "percent_bp >= 0 AND percent_bp <= 10000 "
            "AND fixed_irr >= 0 AND max_fee_irr >= 0",
            name="ck_platform_term_amounts",
        ),
    )
    op.create_table(
        "platform_receivable",
        _uuid("id", primary_key=True),
        _uuid("gym_id"),
        _uuid("agreement_id", nullable=True),
        _str("source_type", 30),
        _uuid("source_id", nullable=True),
        _str("source_key", 200),
        _int("amount_irr", default=0),
        _int("paid_irr", default=0),
        sa.Column("due_on", sa.Date(), nullable=False),
        _str("status", 20),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agreement_id"], ["platform_agreement.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "amount_irr >= 0 AND paid_irr >= 0 AND paid_irr <= amount_irr",
            name="ck_platform_receivable_amount",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'INVOICED', 'PARTIAL', 'PAID', 'CREDITED', 'VOID')",
            name="ck_platform_receivable_status",
        ),
        sa.UniqueConstraint("source_key", name="uq_platform_receivable_source"),
    )
    op.create_table(
        "platform_credit",
        _uuid("id", primary_key=True),
        _uuid("gym_id"),
        _str("source_type", 30),
        _uuid("source_id", nullable=True),
        _str("source_key", 200),
        _int("amount_irr", default=0),
        _str("reason", 500, nullable=True),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_irr > 0", name="ck_platform_credit_amount"),
        sa.UniqueConstraint("source_key", name="uq_platform_credit_source"),
    )
    op.create_table(
        "platform_invoice",
        _uuid("id", primary_key=True),
        _uuid("gym_id", nullable=True),
        _uuid("group_id", nullable=True),
        sa.Column("invoice_number", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        _str("status", 20),
        _int("discount_irr", default=0),
        _int("total_irr", default=0),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["platform_group.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("invoice_number", name="uq_platform_invoice_number"),
        sa.CheckConstraint(
            "status IN ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'CREDITED', 'CANCELLED')",
            name="ck_platform_invoice_status",
        ),
        sa.CheckConstraint(
            "total_irr >= 0 AND discount_irr >= 0",
            name="ck_platform_invoice_total",
        ),
        sa.CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_invoice_scope",
        ),
    )
    op.create_table(
        "platform_invoice_line",
        _uuid("id", primary_key=True),
        _uuid("invoice_id"),
        _uuid("gym_id"),
        _uuid("receivable_id"),
        _str("source_key", 200),
        _str("description", 255),
        _int("gross_irr", default=0),
        _int("discount_irr", default=0),
        _int("credit_irr", default=0),
        _int("amount_irr", default=0),
        _int("paid_irr", default=0),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["platform_invoice.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["receivable_id"], ["platform_receivable.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "invoice_id", "gym_id", "source_key",
            name="uq_platform_invoice_line_source",
        ),
        sa.CheckConstraint(
            "gross_irr >= 0 AND discount_irr >= 0 AND credit_irr >= 0 "
            "AND amount_irr >= 0 AND paid_irr >= 0 AND paid_irr <= amount_irr",
            name="ck_platform_invoice_line_amount",
        ),
    )
    op.create_table(
        "platform_credit_application",
        _uuid("id", primary_key=True),
        _uuid("credit_id"),
        _uuid("invoice_line_id"),
        _int("amount_irr", default=0),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["credit_id"], ["platform_credit.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"], ["platform_invoice_line.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "credit_id", "invoice_line_id", name="uq_platform_credit_application"
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_platform_credit_application_amount"
        ),
    )
    op.create_table(
        "platform_journal",
        _uuid("id", primary_key=True),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        _str("event_type", 40),
        _str("description", 255),
        _str("source_type", 80),
        _uuid("source_id", nullable=True),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entry_number", name="uq_platform_journal_entry"),
        sa.CheckConstraint(
            "event_type IN ('PLATFORM_FEE', 'PLATFORM_FEE_REVERSAL', "
            "'PLATFORM_PAYMENT', 'PLATFORM_INVOICE_CANCEL')",
            name="ck_platform_journal_event",
        ),
    )
    op.create_table(
        "platform_journal_line",
        _uuid("id", primary_key=True),
        _uuid("journal_id"),
        _str("account_code", 10),
        _int("debit_irr", default=0),
        _int("credit_irr", default=0),
        _str("memo", 255, nullable=True),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["platform_journal.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "debit_irr >= 0 AND credit_irr >= 0",
            name="ck_platform_journal_line_amounts",
        ),
        sa.CheckConstraint(
            "(debit_irr = 0) <> (credit_irr = 0)",
            name="ck_platform_journal_line_side",
        ),
        sa.CheckConstraint(
            "account_code IN ('1000', '1100', '4000', '4100', '4200')",
            name="ck_platform_journal_account",
        ),
    )
    op.create_table(
        "platform_invoice_cancellation",
        _uuid("id", primary_key=True),
        _uuid("invoice_id"),
        _str("reason", 500),
        _uuid("journal_id", nullable=True),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["platform_invoice.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"], ["platform_journal.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "invoice_id", name="uq_platform_invoice_cancellation"
        ),
        sa.CheckConstraint(
            "length(reason) >= 3", name="ck_platform_invoice_cancel_reason"
        ),
    )
    op.create_table(
        "platform_invoice_line_reversal",
        _uuid("id", primary_key=True),
        _uuid("cancellation_id"),
        _uuid("invoice_line_id"),
        _int("amount_irr", default=0),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["cancellation_id"],
            ["platform_invoice_cancellation.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"], ["platform_invoice_line.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "cancellation_id",
            "invoice_line_id",
            name="uq_platform_invoice_line_reversal",
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_platform_invoice_line_reversal_amount"
        ),
    )
    op.create_table(
        "platform_payment",
        _uuid("id", primary_key=True),
        _uuid("invoice_id"),
        _int("amount_irr", default=0),
        _str("method", 20),
        _str("reference", 255, nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        _str("operation_key", 100),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["platform_invoice.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_irr > 0", name="ck_platform_payment_amount"),
        sa.CheckConstraint(
            "method IN ('CASH', 'POS', 'TRANSFER')",
            name="ck_platform_payment_method",
        ),
        sa.UniqueConstraint(
            "operation_key", name="uq_platform_payment_operation"
        ),
    )
    op.create_table(
        "platform_payment_allocation",
        _uuid("id", primary_key=True),
        _uuid("payment_id"),
        _uuid("invoice_line_id"),
        _int("amount_irr", default=0),
        sa.ForeignKeyConstraint(
            ["payment_id"], ["platform_payment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"], ["platform_invoice_line.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "payment_id", "invoice_line_id", name="uq_platform_payment_line"
        ),
        sa.CheckConstraint(
            "amount_irr > 0", name="ck_platform_payment_allocation_amount"
        ),
    )
    op.create_table(
        "platform_audit",
        _uuid("id", primary_key=True),
        _uuid("gym_id", nullable=True),
        _uuid("group_id", nullable=True),
        _uuid("actor_id", nullable=True),
        _str("action", 64),
        _str("target_type", 40),
        _uuid("target_id", nullable=True),
        _str("reason", 500, nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["platform_group.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "platform_cost",
        _uuid("id", primary_key=True),
        _uuid("gym_id", nullable=True),
        _str("category", 100),
        _str("description", 500, nullable=True),
        _int("amount_irr", default=0),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        _uuid("created_by_id", nullable=True),
        _dt("created_at"),
        sa.ForeignKeyConstraint(["gym_id"], ["gym.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_irr >= 0", name="ck_platform_cost_amount"),
    )
    op.create_table(
        "platform_sequence",
        _uuid("id", primary_key=True),
        _str("doc_type", 30),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.UniqueConstraint("doc_type", name="uq_platform_sequence_doc"),
    )
    op.create_table(
        "platform_operation",
        _uuid("id", primary_key=True),
        _str("operation_key", 100),
        _str("request_hash", 64),
        _str("result_type", 40),
        _uuid("result_id"),
        _dt("created_at"),
        sa.UniqueConstraint("operation_key", name="uq_platform_operation_key"),
    )


    # ------------------------------------------------------------------
    # Platform ledger integrity and append-only guards
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION platform_check_journal_balance() RETURNS trigger
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
              FROM platform_journal_line
             WHERE journal_id = NEW.id;
            IF total_debit <> total_credit
               OR total_debit <= 0
               OR line_count < 2 THEN
                RAISE EXCEPTION
                    'platform journal % is not balanced', NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER platform_journal_balanced
        AFTER INSERT ON platform_journal
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION platform_check_journal_balance();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'platform posted records are immutable';
        END;
        $$;
        """
    )
    for table_name in (
        "platform_journal",
        "platform_journal_line",
        "platform_audit",
        "platform_credit",
        "platform_credit_application",
        "platform_invoice_cancellation",
        "platform_invoice_line_reversal",
        "platform_payment",
        "platform_payment_allocation",
    ):
        op.execute(
            f"""
            CREATE TRIGGER {table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION platform_reject_mutation();
            """
        )
    op.execute(
        """
        CREATE FUNCTION platform_reject_receivable_amount_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'platform receivables are append-only';
            END IF;
            IF NEW.amount_irr <> OLD.amount_irr
               OR NEW.gym_id IS DISTINCT FROM OLD.gym_id
               OR NEW.agreement_id IS DISTINCT FROM OLD.agreement_id
               OR NEW.source_type <> OLD.source_type
               OR NEW.source_id IS DISTINCT FROM OLD.source_id
               OR NEW.source_key <> OLD.source_key
               OR NEW.due_on <> OLD.due_on
               OR NEW.snapshot::text <> OLD.snapshot::text
               OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'platform receivable amounts are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_receivable_amount_immutable
        BEFORE UPDATE OR DELETE ON platform_receivable
        FOR EACH ROW EXECUTE FUNCTION platform_reject_receivable_amount_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_reject_invoice_amount_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'platform invoices are append-only';
            END IF;
            IF NEW.gym_id IS DISTINCT FROM OLD.gym_id
               OR NEW.group_id IS DISTINCT FROM OLD.group_id
               OR NEW.invoice_number <> OLD.invoice_number
               OR NEW.period_start <> OLD.period_start
               OR NEW.period_end <> OLD.period_end
               OR NEW.issued_on <> OLD.issued_on
               OR NEW.due_on <> OLD.due_on
               OR NEW.discount_irr <> OLD.discount_irr
               OR NEW.total_irr <> OLD.total_irr
               OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'platform invoice amounts are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_invoice_amount_immutable
        BEFORE UPDATE OR DELETE ON platform_invoice
        FOR EACH ROW EXECUTE FUNCTION platform_reject_invoice_amount_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_reject_invoice_line_amount_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'platform invoice lines are append-only';
            END IF;
            IF NEW.invoice_id IS DISTINCT FROM OLD.invoice_id
               OR NEW.gym_id IS DISTINCT FROM OLD.gym_id
               OR NEW.receivable_id IS DISTINCT FROM OLD.receivable_id
               OR NEW.source_key <> OLD.source_key
               OR NEW.gross_irr <> OLD.gross_irr
               OR NEW.discount_irr <> OLD.discount_irr
               OR NEW.credit_irr <> OLD.credit_irr
               OR NEW.amount_irr <> OLD.amount_irr THEN
                RAISE EXCEPTION 'platform invoice line amounts are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_invoice_line_amount_immutable
        BEFORE UPDATE OR DELETE ON platform_invoice_line
        FOR EACH ROW EXECUTE FUNCTION platform_reject_invoice_line_amount_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_invoice_line() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            invoice_gym uuid;
            invoice_group uuid;
            receivable_gym uuid;
        BEGIN
            SELECT gym_id, group_id INTO invoice_gym, invoice_group
              FROM platform_invoice WHERE id = NEW.invoice_id;
            SELECT gym_id INTO receivable_gym
              FROM platform_receivable WHERE id = NEW.receivable_id;
            IF receivable_gym IS NULL OR receivable_gym <> NEW.gym_id THEN
                RAISE EXCEPTION 'platform invoice line tenant mismatch';
            END IF;
            IF invoice_gym IS NOT NULL AND invoice_gym <> NEW.gym_id THEN
                RAISE EXCEPTION 'platform invoice line gym mismatch';
            END IF;
            IF invoice_group IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM platform_group_member
                 WHERE group_id = invoice_group AND gym_id = NEW.gym_id
            ) THEN
                RAISE EXCEPTION 'platform invoice line not in group';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_invoice_line_tenant
        BEFORE INSERT OR UPDATE ON platform_invoice_line
        FOR EACH ROW EXECUTE FUNCTION platform_check_invoice_line();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_credit_application() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            credit_gym uuid;
            line_gym uuid;
        BEGIN
            SELECT gym_id INTO credit_gym FROM platform_credit WHERE id = NEW.credit_id;
            SELECT gym_id INTO line_gym FROM platform_invoice_line WHERE id = NEW.invoice_line_id;
            IF credit_gym IS NULL OR line_gym IS NULL OR credit_gym <> line_gym THEN
                RAISE EXCEPTION 'platform credit tenant mismatch';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_credit_application_tenant
        BEFORE INSERT ON platform_credit_application
        FOR EACH ROW EXECUTE FUNCTION platform_check_credit_application();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_payment_allocation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            payment_invoice uuid;
            line_invoice uuid;
        BEGIN
            SELECT invoice_id INTO payment_invoice FROM platform_payment WHERE id = NEW.payment_id;
            SELECT invoice_id INTO line_invoice FROM platform_invoice_line WHERE id = NEW.invoice_line_id;
            IF payment_invoice IS NULL OR line_invoice IS NULL OR payment_invoice <> line_invoice THEN
                RAISE EXCEPTION 'platform payment allocation invoice mismatch';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_payment_allocation_invoice
        BEFORE INSERT ON platform_payment_allocation
        FOR EACH ROW EXECUTE FUNCTION platform_check_payment_allocation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_line_reversal() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            cancellation_invoice uuid;
            line_invoice uuid;
        BEGIN
            SELECT invoice_id INTO cancellation_invoice
              FROM platform_invoice_cancellation WHERE id = NEW.cancellation_id;
            SELECT invoice_id INTO line_invoice
              FROM platform_invoice_line WHERE id = NEW.invoice_line_id;
            IF cancellation_invoice IS NULL OR line_invoice IS NULL
               OR cancellation_invoice <> line_invoice THEN
                RAISE EXCEPTION 'platform cancellation line mismatch';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_invoice_line_reversal_invoice
        BEFORE INSERT ON platform_invoice_line_reversal
        FOR EACH ROW EXECUTE FUNCTION platform_check_line_reversal();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_invoice_cancellation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            invoice_status text;
        BEGIN
            SELECT status INTO invoice_status
              FROM platform_invoice WHERE id = NEW.invoice_id;
            IF invoice_status <> 'ISSUED' OR EXISTS (
                SELECT 1 FROM platform_payment WHERE invoice_id = NEW.invoice_id
            ) THEN
                RAISE EXCEPTION 'platform invoice is not cancellable';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER platform_invoice_cancellation_status
        BEFORE INSERT ON platform_invoice_cancellation
        FOR EACH ROW EXECUTE FUNCTION platform_check_invoice_cancellation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_check_group_allocations() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            total_bp integer;
            target_group uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_group := OLD.group_id;
            ELSE
                target_group := NEW.group_id;
            END IF;
            SELECT COALESCE(SUM(allocation_bp), 0) INTO total_bp
              FROM platform_group_member
             WHERE group_id = target_group;
            IF total_bp <> 10000 THEN
                RAISE EXCEPTION 'platform group allocation must equal 10000 bp';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER platform_group_allocations
        AFTER INSERT OR UPDATE OR DELETE ON platform_group_member
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION platform_check_group_allocations();
        """
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("platform_agreement_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("platform_agreement_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column(
            "platform_allocation_status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="NOT_APPLICABLE",
        ),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column("platform_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column(
            "platform_fee_irr",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "finance_invoice_line",
        sa.Column(
            "platform_ascora_term_share_irr",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_foreign_key(
        "fk_finance_invoice_line_platform_agreement",
        "finance_invoice_line",
        "platform_agreement",
        ["platform_agreement_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS platform_group_allocations ON platform_group_member")
    op.execute("DROP FUNCTION IF EXISTS platform_check_group_allocations()")
    op.execute("DROP TRIGGER IF EXISTS platform_invoice_cancellation_status ON platform_invoice_cancellation")
    op.execute("DROP FUNCTION IF EXISTS platform_check_invoice_cancellation()")
    op.execute("DROP TRIGGER IF EXISTS platform_invoice_line_reversal_invoice ON platform_invoice_line_reversal")
    op.execute("DROP FUNCTION IF EXISTS platform_check_line_reversal()")
    op.execute("DROP TRIGGER IF EXISTS platform_payment_allocation_invoice ON platform_payment_allocation")
    op.execute("DROP FUNCTION IF EXISTS platform_check_payment_allocation()")
    op.execute("DROP TRIGGER IF EXISTS platform_credit_application_tenant ON platform_credit_application")
    op.execute("DROP FUNCTION IF EXISTS platform_check_credit_application()")
    op.execute("DROP TRIGGER IF EXISTS platform_invoice_line_tenant ON platform_invoice_line")
    op.execute("DROP FUNCTION IF EXISTS platform_check_invoice_line()")
    op.execute("DROP TRIGGER IF EXISTS platform_invoice_line_amount_immutable ON platform_invoice_line")
    op.execute("DROP FUNCTION IF EXISTS platform_reject_invoice_line_amount_mutation()")
    op.execute("DROP TRIGGER IF EXISTS platform_invoice_amount_immutable ON platform_invoice")
    op.execute("DROP FUNCTION IF EXISTS platform_reject_invoice_amount_mutation()")
    op.execute("DROP TRIGGER IF EXISTS platform_receivable_amount_immutable ON platform_receivable")
    op.execute("DROP FUNCTION IF EXISTS platform_reject_receivable_amount_mutation()")
    for table_name in (
        "platform_journal", "platform_journal_line", "platform_audit",
        "platform_credit", "platform_credit_application",
        "platform_invoice_cancellation", "platform_invoice_line_reversal",
        "platform_payment", "platform_payment_allocation",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS platform_reject_mutation()")
    op.execute("DROP TRIGGER IF EXISTS platform_journal_balanced ON platform_journal")
    op.execute("DROP FUNCTION IF EXISTS platform_check_journal_balance()")
    op.drop_constraint(
        "fk_finance_invoice_line_platform_agreement",
        "finance_invoice_line",
        type_="foreignkey",
    )
    op.drop_column("finance_invoice_line", "platform_ascora_term_share_irr")
    op.drop_column("finance_invoice_line", "platform_fee_irr")
    op.drop_column("finance_invoice_line", "platform_snapshot")
    op.drop_column("finance_invoice_line", "platform_allocation_status")
    op.drop_column("finance_invoice_line", "platform_agreement_version")
    op.drop_column("finance_invoice_line", "platform_agreement_id")

    for table in (
        "platform_operation",
        "platform_sequence",
        "platform_cost",
        "platform_audit",
        "platform_payment_allocation",
        "platform_payment",
        "platform_invoice_line_reversal",
        "platform_invoice_cancellation",
        "platform_journal_line",
        "platform_journal",
        "platform_credit_application",
        "platform_invoice_line",
        "platform_invoice",
        "platform_credit",
        "platform_receivable",
        "platform_commission_term",
        "platform_agreement",
        "platform_group_member",
        "platform_group",
        "platform_plan_version",
        "platform_plan",
    ):
        op.drop_table(table)
