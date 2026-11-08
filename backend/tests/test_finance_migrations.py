from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from tests.test_migrations import (
    _alembic_config,
    _drop_database,
    _migration_database_url,
    _recreate_database,
    _set_alembic_database,
)

pytestmark = pytest.mark.migrations

FOUNDATION_REVISION = "b2d4e6f8a0c1"
PRE_FINANCE_REVISION = "c1d2e3f4a5b6"


@pytest.fixture()
def migrated_database() -> Generator[URL]:
    migration_url = _migration_database_url()
    _recreate_database(migration_url)
    try:
        yield migration_url
    finally:
        _drop_database(migration_url)


def _seed_gym(engine: URL) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    gym_id = uuid.uuid4()
    seed = create_engine(engine)
    try:
        with seed.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, full_name, hashed_password, is_active,
                        is_superuser, must_change_password, created_at)
                       VALUES (:id, :email, 'Finance Owner',
                               'hash', true, false, false, now())"""
                ),
                {"id": user_id, "email": f"finance-{user_id.hex[:8]}@example.com"},
            )
            connection.execute(
                text(
                    """INSERT INTO gym (id, name, owner_id, is_active, created_at)
                       VALUES (:id, 'Finance Gym', :owner_id, true, now())"""
                ),
                {"id": gym_id, "owner_id": user_id},
            )
    finally:
        seed.dispose()
    return gym_id, user_id


def _gym_at_head(
    database: URL, monkeypatch: pytest.MonkeyPatch
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a gym between migrations so the chart backfill covers it."""
    _set_alembic_database(monkeypatch, database)
    config = _alembic_config()
    command.upgrade(config, FOUNDATION_REVISION)
    gym_id, user_id = _seed_gym(database)
    command.upgrade(config, "head")
    return gym_id, user_id


def _post_journal(
    engine: URL, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a balanced opening journal directly, returning (journal, line)."""
    period_id = uuid.uuid4()
    journal_id = uuid.uuid4()
    debit_line_id = uuid.uuid4()
    credit_line_id = uuid.uuid4()
    insert = create_engine(engine)
    try:
        with insert.begin() as connection:
            accounts = dict(
                connection.execute(
                    text(
                        "SELECT code, id FROM finance_account WHERE gym_id = :gym"
                    ),
                    {"gym": gym_id},
                ).all()
            )
            connection.execute(
                text(
                    """INSERT INTO finance_period
                       (id, gym_id, opened_at, closed_at, closed_by_id, created_at)
                       VALUES (:id, :gym, now(), NULL, NULL, now())"""
                ),
                {"id": period_id, "gym": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal
                       (id, gym_id, period_id, entry_number, posting_date,
                        event_type, description, reversal_of_id,
                        created_by_id, created_at)
                       VALUES (:id, :gym, :period, 1, DATE '2026-11-01',
                               'OPENING_BALANCE', 'Opening', NULL, :actor, now())"""
                ),
                {
                    "id": journal_id,
                    "gym": gym_id,
                    "period": period_id,
                    "actor": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal_line
                       (id, journal_id, account_id, debit_irr, credit_irr, memo)
                       VALUES (:debit_id, :journal, :debit_account, 500000, 0, NULL),
                              (:credit_id, :journal, :credit_account, 0, 500000, NULL)"""
                ),
                {
                    "debit_id": debit_line_id,
                    "credit_id": credit_line_id,
                    "journal": journal_id,
                    "debit_account": accounts["1000"],
                    "credit_account": accounts["3000"],
                },
            )
    finally:
        insert.dispose()
    return journal_id, debit_line_id


def test_finance_migration_creates_schema_and_role_then_rolls_back(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(migrated_database)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "finance_settings",
            "finance_audit",
            "finance_account",
            "finance_period",
            "finance_sequence",
            "finance_journal",
            "finance_journal_line",
            "finance_grant",
            "finance_operation",
            "finance_catalog_item",
            "finance_invoice",
            "finance_invoice_line",
            "finance_installment",
            "finance_receipt",
            "finance_receipt_allocation",
            "finance_customer_credit",
            "finance_credit_movement",
            "finance_refund",
            "finance_expense",
            "finance_membership",
        }.issubset(tables)

        with engine.connect() as connection:
            definition = connection.execute(
                text(
                    """SELECT pg_get_constraintdef(oid)
                       FROM pg_constraint
                       WHERE conname = 'ck_membership_role'"""
                )
            ).scalar_one()
        assert "FINANCE_STAFF" in definition
        assert "GYM_ADMIN" in definition
    finally:
        engine.dispose()

    # Downgrade past the journal, then re-upgrade: the migrations are
    # repeatable on a disposable database with no finance rows.
    command.downgrade(config, FOUNDATION_REVISION)
    command.upgrade(config, "head")
    command.check(config)


def test_existing_gyms_receive_the_minimal_chart(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, FOUNDATION_REVISION)
    gym_id, _user_id = _seed_gym(migrated_database)

    command.upgrade(config, "head")

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            codes = [
                row[0]
                for row in connection.execute(
                    text(
                        """SELECT code FROM finance_account
                           WHERE gym_id = :gym ORDER BY code"""
                    ),
                    {"gym": gym_id},
                )
            ]
    finally:
        engine.dispose()
    assert codes == [
        "1000", "1100", "2000", "2100", "2200", "3000", "4000", "4100",
        "5000", "5100"
    ]


def test_posted_journal_and_audit_rows_are_immutable(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    gym_id, user_id = _gym_at_head(migrated_database, monkeypatch)
    journal_id, line_id = _post_journal(
        migrated_database, gym_id=gym_id, user_id=user_id
    )

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_audit
                       (id, gym_id, actor_id, action, target_type, target_id,
                        reason, detail, created_at)
                       VALUES (:id, :gym, :actor, 'finance.opening_balance.posted',
                               'finance_journal', :journal, NULL, '{}'::json, now())"""
                ),
                {"id": uuid.uuid4(), "gym": gym_id, "actor": user_id, "journal": journal_id},
            )
        audit_id = uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_audit
                       (id, gym_id, actor_id, action, target_type, target_id,
                        reason, detail, created_at)
                       VALUES (:id, :gym, :actor, 'finance.period.closed',
                               'finance_period', NULL, NULL, '{}'::json, now())"""
                ),
                {"id": audit_id, "gym": gym_id, "actor": user_id},
            )

        attempts = [
            ("UPDATE finance_journal SET description = 'tampered' WHERE id = :id", journal_id),
            ("DELETE FROM finance_journal WHERE id = :id", journal_id),
            ("UPDATE finance_journal_line SET debit_irr = 1 WHERE id = :id", line_id),
            ("DELETE FROM finance_journal_line WHERE id = :id", line_id),
            ("UPDATE finance_audit SET reason = 'tampered' WHERE id = :id", audit_id),
            ("DELETE FROM finance_audit WHERE id = :id", audit_id),
        ]
        for statement, target in attempts:
            with pytest.raises(DBAPIError) as failure:
                with engine.begin() as connection:
                    connection.execute(text(statement), {"id": target})
            assert "immutable" in str(failure.value)
    finally:
        engine.dispose()


def test_journal_line_requires_exactly_one_positive_side(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    gym_id, user_id = _gym_at_head(migrated_database, monkeypatch)
    journal_id, _line_id = _post_journal(
        migrated_database, gym_id=gym_id, user_id=user_id
    )

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            account_id = connection.execute(
                text(
                    """SELECT id FROM finance_account
                       WHERE gym_id = :gym AND code = '3000'"""
                ),
                {"gym": gym_id},
            ).scalar_one()

        for debit, credit in ((0, 0), (10, 10), (-1, 0)):
            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            """INSERT INTO finance_journal_line
                               (id, journal_id, account_id, debit_irr,
                                credit_irr, memo)
                               VALUES (:id, :journal, :account, :debit, :credit,
                                       NULL)"""
                        ),
                        {
                            "id": uuid.uuid4(),
                            "journal": journal_id,
                            "account": account_id,
                            "debit": debit,
                            "credit": credit,
                        },
                    )
    finally:
        engine.dispose()


def test_database_rejects_an_unbalanced_journal(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, _user_id = _gym_at_head(migrated_database, monkeypatch)

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            cash_id = connection.execute(
                text(
                    """SELECT id FROM finance_account
                       WHERE gym_id = :gym AND code = '1000'"""
                ),
                {"gym": gym_id},
            ).scalar_one()

        with pytest.raises(DBAPIError) as failure:
            with engine.begin() as connection:
                period_id = connection.execute(
                    text(
                        """INSERT INTO finance_period
                           (id, gym_id, opened_at, created_at)
                           VALUES (gen_random_uuid(), :gym, now(), now())
                           RETURNING id"""
                    ),
                    {"gym": gym_id},
                ).scalar_one()
                journal_id = connection.execute(
                    text(
                        """INSERT INTO finance_journal
                           (id, gym_id, period_id, entry_number, posting_date,
                            event_type, description, created_at)
                           VALUES (gen_random_uuid(), :gym, :period, 1,
                                   current_date, 'OPENING_BALANCE', 'bad', now())
                           RETURNING id"""
                    ),
                    {"gym": gym_id, "period": period_id},
                ).scalar_one()
                connection.execute(
                    text(
                        """INSERT INTO finance_journal_line
                           (id, journal_id, account_id, debit_irr, credit_irr,
                            memo)
                           VALUES (gen_random_uuid(), :journal, :account,
                                   1000, 0, NULL)"""
                    ),
                    {"journal": journal_id, "account": cash_id},
                )
        assert "not balanced" in str(failure.value)
    finally:
        engine.dispose()


def test_finance_migrations_downgrade_to_pre_finance_and_back(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, PRE_FINANCE_REVISION)

    engine = create_engine(migrated_database)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {table for table in tables if table.startswith("finance_")} == set()
        with engine.connect() as connection:
            definition = connection.execute(
                text(
                    """SELECT pg_get_constraintdef(oid)
                       FROM pg_constraint
                       WHERE conname = 'ck_membership_role'"""
                )
            ).scalar_one()
        assert "FINANCE_STAFF" not in definition
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.check(config)


def test_reporting_date_migration_backfills_existing_rows(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "f1a2b3c4d5e6")
    gym_id, user_id = _seed_gym(migrated_database)

    period_id = uuid.uuid4()
    journal_id = uuid.uuid4()
    invoice_id = uuid.uuid4()
    receivable_id = uuid.uuid4()
    credit_id = uuid.uuid4()
    debit_account = uuid.uuid4()
    credit_account = uuid.uuid4()
    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_account
                       (id, gym_id, code, name, type, created_at)
                       VALUES (:debit, :gym_id, '1000', 'Cash', 'ASSET', now()),
                              (:credit, :gym_id, '3000', 'Equity', 'EQUITY', now())"""
                ),
                {
                    "debit": debit_account,
                    "credit": credit_account,
                    "gym_id": gym_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_period
                       (id, gym_id, opened_at, closed_at, closed_by_id, created_at)
                       VALUES (:id, :gym_id, '2026-11-01T00:00:00Z',
                               '2026-11-30T00:00:00Z', :user_id,
                               '2026-11-01T00:00:00Z')"""
                ),
                {"id": period_id, "gym_id": gym_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal
                       (id, gym_id, period_id, entry_number, posting_date,
                        event_type, description, created_by_id, created_at)
                       VALUES (:journal_id, :gym_id, :period_id, 1,
                               '2026-11-10', 'OPENING_BALANCE', 'backfill',
                               :user_id, '2026-11-10T00:00:00Z')"""
                ),
                {
                    "journal_id": journal_id,
                    "gym_id": gym_id,
                    "period_id": period_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal_line
                       (id, journal_id, account_id, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal_id, :debit, 1000, 0, NULL),
                              (gen_random_uuid(), :journal_id, :credit, 0, 1000, NULL)"""
                ),
                {
                    "journal_id": journal_id,
                    "debit": debit_account,
                    "credit": credit_account,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_receivable
                       (id, gym_id, agreement_id, source_type, source_id,
                        source_key, amount_irr, paid_irr, due_on, status,
                        snapshot, created_at)
                       VALUES (:id, :gym_id, NULL, 'SUBSCRIPTION', NULL,
                               'backfill-receivable', 1000, 0, '2026-11-01',
                               'OPEN', '{}', '2026-11-02T00:00:00Z')"""
                ),
                {"id": receivable_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_credit
                       (id, gym_id, source_type, source_id, source_key,
                        amount_irr, reason, created_by_id, created_at)
                       VALUES (gen_random_uuid(), :gym_id, 'MANUAL', NULL,
                               'backfill-credit', 100, 'backfill', NULL,
                               '2026-11-03T21:00:00Z')"""
                ),
                {"gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_customer_credit
                       (id, gym_id, customer_user_id, balance_irr, updated_at)
                       VALUES (:id, :gym_id, :user_id, 0,
                               '2026-11-03T00:00:00Z')"""
                ),
                {"id": credit_id, "gym_id": gym_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_credit_movement
                       (id, credit_id, kind, amount_irr, receipt_id, invoice_id,
                        created_by_id, created_at)
                       VALUES (gen_random_uuid(), :credit_id, 'APPLIED', 100,
                               NULL, NULL, NULL, '2026-11-03T21:00:00Z')"""
                ),
                {"credit_id": credit_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice
                       (id, gym_id, group_id, invoice_number, period_start,
                        period_end, issued_on, due_on, status, discount_irr,
                        total_irr, created_by_id, created_at)
                       VALUES (:id, :gym_id, NULL, 1, '2026-11-01',
                               '2026-11-30', '2026-11-04', '2026-11-30',
                               'ISSUED', 0, 1000, NULL,
                               '2026-11-04T00:00:00Z')"""
                ),
                {"id": invoice_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice_cancellation
                       (id, invoice_id, reason, journal_id, created_by_id,
                        created_at)
                       VALUES (gen_random_uuid(), :invoice_id, 'backfill',
                               NULL, NULL, '2026-11-05T00:00:00Z')"""
                ),
                {"invoice_id": invoice_id},
            )
            connection.execute(
                text(
                    "UPDATE platform_invoice SET status = 'CANCELLED' "
                    "WHERE id = :id"
                ),
                {"id": invoice_id},
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            receivable = connection.execute(
                text(
                    "SELECT recognized_on FROM platform_receivable "
                    "WHERE id = :id"
                ),
                {"id": receivable_id},
            ).one()
            credit = connection.execute(
                text(
                    "SELECT recognized_on FROM platform_credit "
                    "WHERE source_key = 'backfill-credit'"
                )
            ).one()
            invoice = connection.execute(
                text(
                    "SELECT cancelled_on FROM platform_invoice "
                    "WHERE id = :id"
                ),
                {"id": invoice_id},
            ).one()
            period = connection.execute(
                text(
                    "SELECT period_start, period_end FROM finance_period "
                    "WHERE id = :id"
                ),
                {"id": period_id},
            ).one()
            movement = connection.execute(
                text(
                    "SELECT applied_on FROM finance_credit_movement "
                    "WHERE credit_id = :id"
                ),
                {"id": credit_id},
            ).one()
        assert str(receivable[0]) == "2026-11-02"
        assert str(credit[0]) == "2026-11-04"
        assert str(invoice[0]) == "2026-11-05"
        assert str(period[0]) == "2026-11-10"
        assert str(period[1]) == "2026-11-30"
        assert str(movement[0]) == "2026-11-04"
    finally:
        engine.dispose()


def test_reporting_date_migration_preserves_immutable_rows(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "f1a2b3c4d5e6")
    gym_id, user_id = _seed_gym(migrated_database)

    period_id = uuid.uuid4()
    journal_id = uuid.uuid4()
    receivable_id = uuid.uuid4()
    invoice_id = uuid.uuid4()
    line_id = uuid.uuid4()
    payment_id = uuid.uuid4()
    platform_journal_id = uuid.uuid4()
    platform_credit_id = uuid.uuid4()
    platform_application_id = uuid.uuid4()
    finance_invoice_id = uuid.uuid4()
    finance_line_id = uuid.uuid4()
    finance_receipt_id = uuid.uuid4()
    finance_allocation_id = uuid.uuid4()
    finance_credit_id = uuid.uuid4()
    finance_movement_id = uuid.uuid4()
    debit_account = uuid.uuid4()
    credit_account = uuid.uuid4()

    def snapshot(connection: object) -> dict[str, object]:
        return {
            "finance_journal": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, gym_id, period_id, entry_number, posting_date, "
                    "event_type, description, reversal_of_id, source_type, "
                    "source_id, created_by_id, created_at), '|' ORDER BY id), '')) "
                    "FROM finance_journal"
                )
            ).one(),
            "finance_lines": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, journal_id, account_id, debit_irr, credit_irr, memo), "
                    "'|' ORDER BY id), '')) FROM finance_journal_line"
                )
            ).one(),
            "platform_journal": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, entry_number, posting_date, event_type, description, "
                    "source_type, source_id, created_by_id, created_at), "
                    "'|' ORDER BY id), '')) FROM platform_journal"
                )
            ).one(),
            "platform_lines": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, journal_id, account_code, debit_irr, credit_irr, memo), "
                    "'|' ORDER BY id), '')) FROM platform_journal_line"
                )
            ).one(),
            "payments": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, invoice_id, amount_irr, method, reference, received_on, "
                    "operation_key, created_by_id, created_at), '|' ORDER BY id), '')) "
                    "FROM platform_payment"
                )
            ).one(),
            "allocations": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, payment_id, invoice_line_id, amount_irr), '|' ORDER BY id), '')) "
                    "FROM platform_payment_allocation"
                )
            ).one(),
            "invoice_lines": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, invoice_id, gym_id, receivable_id, source_key, description, "
                    "gross_irr, discount_irr, credit_irr, amount_irr, paid_irr), "
                    "'|' ORDER BY id), '')) FROM platform_invoice_line"
                )
            ).one(),
            "platform_credit": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, gym_id, source_type, source_id, source_key, amount_irr, "
                    "reason, created_by_id, created_at), '|' ORDER BY id), '')) "
                    "FROM platform_credit"
                )
            ).one(),
            "platform_credit_applications": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, credit_id, invoice_line_id, amount_irr, created_at), "
                    "'|' ORDER BY id), '')) FROM platform_credit_application"
                )
            ).one(),
            "finance_invoice": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, gym_id, customer_user_id, status, invoice_number, "
                    "issue_date, due_date, subtotal_irr, discount_irr, total_irr, "
                    "journal_id, created_at), '|' ORDER BY id), '')) FROM finance_invoice"
                )
            ).one(),
            "finance_invoice_lines": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, invoice_id, line_number, kind, quantity, unit_price_irr, "
                    "line_discount_irr, net_irr, discount_share_irr, payable_irr), "
                    "'|' ORDER BY id), '')) FROM finance_invoice_line"
                )
            ).one(),
            "finance_receipts": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, gym_id, customer_user_id, receipt_number, method, "
                    "amount_irr, received_on, status, journal_id, created_at), "
                    "'|' ORDER BY id), '')) FROM finance_receipt"
                )
            ).one(),
            "finance_allocations": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, receipt_id, invoice_id, amount_irr), '|' ORDER BY id), '')) "
                    "FROM finance_receipt_allocation"
                )
            ).one(),
            "finance_credits": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, gym_id, customer_user_id, balance_irr, updated_at), "
                    "'|' ORDER BY id), '')) FROM finance_customer_credit"
                )
            ).one(),
            "finance_movements": connection.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(concat_ws('|', "
                    "id, credit_id, kind, amount_irr, receipt_id, invoice_id, "
                    "created_at), '|' ORDER BY id), '')) FROM finance_credit_movement"
                )
            ).one(),
            "finance_sequences": connection.execute(
                text(
                    "SELECT count(*), coalesce(sum(last_value), 0) "
                    "FROM finance_sequence"
                )
            ).one(),
            "platform_sequences": connection.execute(
                text(
                    "SELECT count(*), coalesce(sum(last_value), 0) "
                    "FROM platform_sequence"
                )
            ).one(),
        }

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_account
                       (id, gym_id, code, name, type, created_at)
                       VALUES (:debit, :gym_id, '1000', 'Cash', 'ASSET', now()),
                              (:credit, :gym_id, '3000', 'Equity', 'EQUITY', now())"""
                ),
                {
                    "debit": debit_account,
                    "credit": credit_account,
                    "gym_id": gym_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_period
                       (id, gym_id, opened_at, created_at)
                       VALUES (:id, :gym_id, now(), now())"""
                ),
                {"id": period_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal
                       (id, gym_id, period_id, entry_number, posting_date,
                        event_type, description, created_by_id, created_at)
                       VALUES (:id, :gym_id, :period_id, 1, current_date,
                               'OPENING_BALANCE', 'preserve', :user_id, now())"""
                ),
                {
                    "id": journal_id,
                    "gym_id": gym_id,
                    "period_id": period_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal_line
                       (id, journal_id, account_id, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal, :debit, 1000, 0, NULL),
                              (gen_random_uuid(), :journal, :credit, 0, 1000, NULL)"""
                ),
                {
                    "journal": journal_id,
                    "debit": debit_account,
                    "credit": credit_account,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_sequence
                       (id, gym_id, doc_type, last_value)
                       VALUES (gen_random_uuid(), :gym_id, 'JOURNAL', 1)"""
                ),
                {"gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_invoice
                       (id, gym_id, customer_user_id, status, acquisition_source,
                        discount_funding, invoice_number, issue_date, due_date,
                        subtotal_irr, discount_irr, total_irr, created_by_id,
                        created_at, issued_at)
                       VALUES (:id, :gym_id, :user_id, 'ISSUED', 'GYM', 'GYM',
                               1, current_date, current_date, 1000, 0, 1000,
                               NULL, now(), now())"""
                ),
                {
                    "id": finance_invoice_id,
                    "gym_id": gym_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_invoice_line
                       (id, invoice_id, line_number, kind, description, quantity,
                        unit_price_irr, line_discount_irr, net_irr,
                        discount_share_irr, payable_irr, coach_allocation_status,
                        platform_allocation_status, platform_fee_irr,
                        platform_ascora_term_share_irr)
                       VALUES (:id, :invoice_id, 1, 'PROGRAM', 'preserve', 1,
                               1000, 0, 1000, 0, 1000, 'NOT_APPLICABLE',
                               'NOT_APPLICABLE', 0, 0)"""
                ),
                {"id": finance_line_id, "invoice_id": finance_invoice_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_receipt
                       (id, gym_id, customer_user_id, receipt_number, method,
                        amount_irr, reference, received_on, status,
                        verification_source, created_at)
                       VALUES (:id, :gym_id, :user_id, 1, 'CASH', 1100,
                               'PRESERVE', current_date, 'CONFIRMED',
                               'STAFF_ATTESTATION', now())"""
                ),
                {
                    "id": finance_receipt_id,
                    "gym_id": gym_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_receipt_allocation
                       (id, receipt_id, invoice_id, amount_irr)
                       VALUES (:id, :receipt_id, :invoice_id, 1000)"""
                ),
                {
                    "id": finance_allocation_id,
                    "receipt_id": finance_receipt_id,
                    "invoice_id": finance_invoice_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_customer_credit
                       (id, gym_id, customer_user_id, balance_irr, updated_at)
                       VALUES (:id, :gym_id, :user_id, 100, now())"""
                ),
                {
                    "id": finance_credit_id,
                    "gym_id": gym_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_credit_movement
                       (id, credit_id, kind, amount_irr, receipt_id, created_at)
                       VALUES (:id, :credit_id, 'RECEIPT_EXCESS', 100,
                               :receipt_id, now())"""
                ),
                {
                    "id": finance_movement_id,
                    "credit_id": finance_credit_id,
                    "receipt_id": finance_receipt_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_receivable
                       (id, gym_id, agreement_id, source_type, source_id,
                        source_key, amount_irr, paid_irr, due_on, status,
                        snapshot, created_at)
                       VALUES (:id, :gym_id, NULL, 'SUBSCRIPTION', NULL,
                               'preserve-receivable', 1000, 1000, current_date,
                               'PAID', '{}', now())"""
                ),
                {"id": receivable_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice
                       (id, gym_id, group_id, invoice_number, period_start,
                        period_end, issued_on, due_on, status, discount_irr,
                        total_irr, created_by_id, created_at)
                       VALUES (:id, :gym_id, NULL, 1, current_date, current_date,
                               current_date, current_date, 'PAID', 0, 1000,
                               NULL, now())"""
                ),
                {"id": invoice_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice_line
                       (id, invoice_id, gym_id, receivable_id, source_key,
                        description, gross_irr, discount_irr, credit_irr,
                        amount_irr, paid_irr)
                       VALUES (:id, :invoice_id, :gym_id, :receivable_id,
                               'preserve-line', 'preserve', 1000, 0, 0,
                               1000, 1000)"""
                ),
                {
                    "id": line_id,
                    "invoice_id": invoice_id,
                    "gym_id": gym_id,
                    "receivable_id": receivable_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_payment
                       (id, invoice_id, amount_irr, method, reference,
                        received_on, operation_key, created_by_id, created_at)
                       VALUES (:id, :invoice_id, 1000, 'CASH', 'PRESERVE',
                               current_date, 'preserve-payment', NULL, now())"""
                ),
                {"id": payment_id, "invoice_id": invoice_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_payment_allocation
                       (id, payment_id, invoice_line_id, amount_irr)
                       VALUES (gen_random_uuid(), :payment_id, :line_id, 1000)"""
                ),
                {"payment_id": payment_id, "line_id": line_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_credit
                       (id, gym_id, source_type, source_id, source_key,
                        amount_irr, reason, created_by_id, created_at)
                       VALUES (:id, :gym_id, 'MANUAL', NULL, 'preserve-credit',
                               100, 'preserve', NULL, now())"""
                ),
                {"id": platform_credit_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_credit_application
                       (id, credit_id, invoice_line_id, amount_irr, created_at)
                       VALUES (:id, :credit_id, :line_id, 100, now())"""
                ),
                {
                    "id": platform_application_id,
                    "credit_id": platform_credit_id,
                    "line_id": line_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_journal
                       (id, entry_number, posting_date, event_type, description,
                        source_type, source_id, created_by_id, created_at)
                       VALUES (:id, 1, current_date, 'PLATFORM_FEE', 'preserve',
                               'platform_receivable', :receivable_id, NULL, now())"""
                ),
                {"id": platform_journal_id, "receivable_id": receivable_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_journal_line
                       (id, journal_id, account_code, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal, '1100', 1000, 0, NULL),
                              (gen_random_uuid(), :journal, '4100', 0, 1000, NULL)"""
                ),
                {"journal": platform_journal_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_sequence
                       (id, doc_type, last_value)
                       VALUES (gen_random_uuid(), 'PLATFORM_INVOICE', 1),
                              (gen_random_uuid(), 'PLATFORM_JOURNAL', 1)"""
                )
            )
            before = snapshot(connection)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            after_upgrade = snapshot(connection)
        assert after_upgrade == before
    finally:
        engine.dispose()

    command.downgrade(config, "f1a2b3c4d5e6")
    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            after_downgrade = snapshot(connection)
        assert after_downgrade == before
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            after_reupgrade = snapshot(connection)
        assert after_reupgrade == before
    finally:
        engine.dispose()


def test_platform_credit_immutability_trigger_survives_migration(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, _user_id = _gym_at_head(migrated_database, monkeypatch)
    config = _alembic_config()
    credit_id = uuid.uuid4()
    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO platform_credit
                       (id, gym_id, source_type, source_key, amount_irr, reason,
                        created_at)
                       VALUES (:id, :gym, 'MANUAL', :source_key, 1000,
                               'original', now())"""
                ),
                {
                    "id": credit_id,
                    "gym": gym_id,
                    "source_key": f"immutable-{credit_id.hex}",
                },
            )

        def assert_trigger_active() -> None:
            with engine.connect() as connection:
                state = connection.execute(
                    text(
                        "SELECT tgenabled FROM pg_trigger "
                        "WHERE tgname = 'platform_credit_immutable'"
                    )
                ).scalar_one()
            assert state in {"O", "A"}, state
            with pytest.raises(
                DBAPIError, match="platform posted records are immutable"
            ):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE platform_credit SET reason = 'changed' "
                            "WHERE id = :id"
                        ),
                        {"id": credit_id},
                    )
            with engine.connect() as connection:
                reason = connection.execute(
                    text("SELECT reason FROM platform_credit WHERE id = :id"),
                    {"id": credit_id},
                ).scalar_one()
            assert reason == "original"

        assert_trigger_active()

        # The reporting-date migration disables and re-enables this trigger.
        # A downgrade/upgrade cycle must leave it enabled and enforcing.
        command.downgrade(config, "f1a2b3c4d5e6")
        command.upgrade(config, "head")
        assert_trigger_active()
    finally:
        engine.dispose()


def test_reporting_date_repair_uses_authoritative_source_events(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "a7b8c9d0e1f2")
    gym_id, user_id = _seed_gym(migrated_database)

    subscription_id = uuid.uuid4()
    commission_id = uuid.uuid4()
    manual_id = uuid.uuid4()
    receipt_id = uuid.uuid4()
    line_id = uuid.uuid4()
    invoice_id = uuid.uuid4()
    period_id = uuid.uuid4()
    account_id = uuid.uuid4()
    credit_account_id = uuid.uuid4()
    advance_journal_id = uuid.uuid4()
    refund_journal_id = uuid.uuid4()
    customer_credit_id = uuid.uuid4()
    movement_id = uuid.uuid4()
    refund_id = uuid.uuid4()
    refund_credit_id = uuid.uuid4()
    cancellation_id = uuid.uuid4()
    cancellation_credit_id = uuid.uuid4()

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_account
                       (id, gym_id, code, name, type, created_at)
                       VALUES (:debit, :gym_id, '1000', 'Cash', 'ASSET', now()),
                              (:credit, :gym_id, '3000', 'Equity', 'EQUITY', now())"""
                ),
                {
                    "debit": account_id,
                    "credit": credit_account_id,
                    "gym_id": gym_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_period
                       (id, gym_id, opened_at, closed_at, closed_by_id, created_at)
                       VALUES (:id, :gym_id, now(), NULL, NULL, now())"""
                ),
                {"id": period_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_invoice
                       (id, gym_id, customer_user_id, status, acquisition_source,
                        discount_funding, invoice_number, issue_date, due_date,
                        description, subtotal_irr, discount_irr, total_irr,
                        created_at)
                       VALUES (:id, :gym_id, :user_id, 'ISSUED', 'GYM', 'GYM',
                               1, '2026-11-01', '2026-11-30', 'legacy invoice',
                               100, 0, 100, '2026-11-01T00:00:00Z')"""
                ),
                {"id": invoice_id, "gym_id": gym_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_receipt
                       (id, gym_id, customer_user_id, receipt_number, method,
                        amount_irr, reference, received_on, status,
                        verification_source, created_at)
                       VALUES (:id, :gym_id, :user_id, 1, 'CASH', 100,
                               'legacy-receipt', '2026-11-03', 'CONFIRMED',
                               'STAFF_ATTESTATION', '2026-11-10T00:00:00Z')"""
                ),
                {"id": receipt_id, "gym_id": gym_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_customer_credit
                       (id, gym_id, customer_user_id, balance_irr, updated_at)
                       VALUES (:id, :gym_id, :user_id, 0, now())"""
                ),
                {
                    "id": customer_credit_id,
                    "gym_id": gym_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal
                       (id, gym_id, period_id, entry_number, posting_date,
                        event_type, description, source_type, source_id,
                        created_at)
                       VALUES (:id, :gym_id, :period_id, 1, '2026-11-04',
                               'ADVANCE_APPLIED', 'legacy advance',
                               'finance_invoice', :invoice_id,
                               '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": advance_journal_id,
                    "gym_id": gym_id,
                    "period_id": period_id,
                    "invoice_id": invoice_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal_line
                       (id, journal_id, account_id, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal_id, :debit_account,
                               100, 0, 'legacy advance'),
                              (gen_random_uuid(), :journal_id, :credit_account,
                               0, 100, 'legacy advance')"""
                ),
                {
                    "journal_id": advance_journal_id,
                    "debit_account": account_id,
                    "credit_account": credit_account_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_credit_movement
                       (id, credit_id, kind, amount_irr, receipt_id, invoice_id,
                        created_by_id, created_at)
                       VALUES (:id, :credit_id, 'APPLIED', 100, NULL,
                               :invoice_id, NULL, '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": movement_id,
                    "credit_id": customer_credit_id,
                    "invoice_id": invoice_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal
                       (id, gym_id, period_id, entry_number, posting_date,
                        event_type, description, created_at)
                       VALUES (:id, :gym_id, :period_id, 2, '2026-11-07',
                               'REFUND_RECORDED', 'legacy refund',
                               '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": refund_journal_id,
                    "gym_id": gym_id,
                    "period_id": period_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_journal_line
                       (id, journal_id, account_id, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal_id, :debit_account,
                               100, 0, 'legacy refund'),
                              (gen_random_uuid(), :journal_id, :credit_account,
                               0, 100, 'legacy refund')"""
                ),
                {
                    "journal_id": refund_journal_id,
                    "debit_account": credit_account_id,
                    "credit_account": account_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_refund
                       (id, gym_id, customer_user_id, source, invoice_id,
                        amount_irr, method, reason, status, journal_id,
                        created_at)
                       VALUES (:id, :gym_id, :user_id, 'INVOICE', :invoice_id,
                               100, 'CASH', 'legacy refund', 'RECORDED',
                               :journal_id, '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": refund_id,
                    "gym_id": gym_id,
                    "user_id": user_id,
                    "invoice_id": invoice_id,
                    "journal_id": refund_journal_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_receivable
                       (id, gym_id, agreement_id, source_type, source_id,
                        source_key, amount_irr, paid_irr, recognized_on,
                        due_on, status, snapshot, created_at)
                       VALUES (:id, :gym_id, NULL, 'SUBSCRIPTION', NULL,
                               :source_key, 100, 0, NULL, '2026-11-01',
                               'OPEN', '{}', '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": subscription_id,
                    "gym_id": gym_id,
                    "source_key": f"subscription:{uuid.uuid4()}:{gym_id}:2026-11",
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_receivable
                       (id, gym_id, agreement_id, source_type, source_id,
                        source_key, amount_irr, paid_irr, recognized_on,
                        due_on, status, snapshot, created_at)
                       VALUES (:id, :gym_id, NULL, 'COMMISSION', :line_id,
                               :source_key, 100, 0, NULL, '2026-11-30',
                               'OPEN', '{}', '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": commission_id,
                    "gym_id": gym_id,
                    "line_id": line_id,
                    "source_key": f"receipt:{receipt_id}:{line_id}",
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_receivable
                       (id, gym_id, agreement_id, source_type, source_id,
                        source_key, amount_irr, paid_irr, recognized_on,
                        due_on, status, snapshot, created_at)
                       VALUES (:id, :gym_id, NULL, 'MANUAL', NULL,
                               'legacy-manual', 100, 0, '2026-11-10',
                               '2026-11-30', 'OPEN', '{}',
                               '2026-11-10T00:00:00Z')"""
                ),
                {"id": manual_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice
                       (id, gym_id, group_id, invoice_number, period_start,
                        period_end, issued_on, due_on, status, discount_irr,
                        total_irr, cancelled_on, created_at)
                       VALUES (:id, :gym_id, NULL, 1, '2026-11-01',
                               '2026-11-30', '2026-11-01', '2026-11-30',
                               'ISSUED', 0, 100, NULL,
                               '2026-11-01T00:00:00Z')"""
                ),
                {"id": invoice_id, "gym_id": gym_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_invoice_cancellation
                       (id, invoice_id, reason, journal_id, created_by_id,
                        created_at)
                       VALUES (:id, :invoice_id, 'legacy cancellation', NULL,
                               NULL, '2026-11-10T00:00:00Z')"""
                ),
                {"id": cancellation_id, "invoice_id": invoice_id},
            )
            connection.execute(
                text(
                    "UPDATE platform_invoice SET status = 'CANCELLED', "
                    "cancelled_on = '2026-11-06' WHERE id = :id"
                ),
                {"id": invoice_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_credit
                       (id, gym_id, source_type, source_id, source_key,
                        amount_irr, recognized_on, reason, created_at)
                       VALUES (:id, :gym_id, 'REFUND', :refund_id,
                               'legacy-refund-credit', 100, NULL,
                               'legacy refund', '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": refund_credit_id,
                    "gym_id": gym_id,
                    "refund_id": refund_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO platform_credit
                       (id, gym_id, source_type, source_id, source_key,
                        amount_irr, recognized_on, reason, created_at)
                       VALUES (:id, :gym_id, 'INVOICE_CANCELLATION',
                               :cancellation_id, 'legacy-cancel-credit', 100,
                               NULL, 'legacy cancellation',
                               '2026-11-10T00:00:00Z')"""
                ),
                {
                    "id": cancellation_credit_id,
                    "gym_id": gym_id,
                    "cancellation_id": cancellation_id,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            values = {
                "subscription": connection.execute(
                    text(
                        "SELECT recognized_on FROM platform_receivable "
                        "WHERE id = :id"
                    ),
                    {"id": subscription_id},
                ).scalar_one(),
                "commission": connection.execute(
                    text(
                        "SELECT recognized_on FROM platform_receivable "
                        "WHERE id = :id"
                    ),
                    {"id": commission_id},
                ).scalar_one(),
                "manual": connection.execute(
                    text(
                        "SELECT recognized_on FROM platform_receivable "
                        "WHERE id = :id"
                    ),
                    {"id": manual_id},
                ).scalar_one(),
                "refund_credit": connection.execute(
                    text(
                        "SELECT recognized_on FROM platform_credit "
                        "WHERE id = :id"
                    ),
                    {"id": refund_credit_id},
                ).scalar_one(),
                "cancel_credit": connection.execute(
                    text(
                        "SELECT recognized_on FROM platform_credit "
                        "WHERE id = :id"
                    ),
                    {"id": cancellation_credit_id},
                ).scalar_one(),
                "movement": connection.execute(
                    text(
                        "SELECT applied_on FROM finance_credit_movement "
                        "WHERE id = :id"
                    ),
                    {"id": movement_id},
                ).scalar_one(),
                "credit_amount": connection.execute(
                    text(
                        "SELECT amount_irr FROM platform_credit "
                        "WHERE id = :id"
                    ),
                    {"id": refund_credit_id},
                ).scalar_one(),
                "refund_journal_date": connection.execute(
                    text(
                        "SELECT posting_date FROM finance_journal "
                        "WHERE id = :id"
                    ),
                    {"id": refund_journal_id},
                ).scalar_one(),
            }
    finally:
        engine.dispose()

    assert str(values["subscription"]) == "2026-11-01"
    assert str(values["commission"]) == "2026-11-03"
    assert str(values["manual"]) == "2026-11-10"
    assert str(values["refund_credit"]) == "2026-11-07"
    assert str(values["cancel_credit"]) == "2026-11-06"
    assert str(values["movement"]) == "2026-11-04"
    assert values["credit_amount"] == 100
    assert str(values["refund_journal_date"]) == "2026-11-07"
