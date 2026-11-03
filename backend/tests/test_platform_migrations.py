from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.test_finance_migrations import _seed_gym
from tests.test_migrations import (
    _alembic_config,
    _drop_database,
    _migration_database_url,
    _recreate_database,
    _set_alembic_database,
)

pytestmark = pytest.mark.migrations

LATEST_FINANCE_REVISION = "e8f0a2b4c6d8"


@pytest.fixture()
def migrated_database() -> Generator[URL]:
    migration_url = _migration_database_url()
    _recreate_database(migration_url)
    try:
        yield migration_url
    finally:
        _drop_database(migration_url)


def test_platform_migration_creates_separate_schema_and_rolls_back(
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
            "platform_plan",
            "platform_plan_version",
            "platform_group",
            "platform_group_member",
            "platform_agreement",
            "platform_commission_term",
            "platform_receivable",
            "platform_credit",
            "platform_credit_application",
            "platform_invoice",
            "platform_invoice_line",
            "platform_invoice_cancellation",
            "platform_invoice_line_reversal",
            "platform_payment",
            "platform_payment_allocation",
            "platform_journal",
            "platform_journal_line",
            "platform_audit",
            "platform_cost",
            "platform_sequence",
            "platform_operation",
        }.issubset(tables)

        with engine.connect() as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'finance_invoice_line'"
                    )
                )
            }
        assert {
            "platform_agreement_id",
            "platform_agreement_version",
            "platform_allocation_status",
            "platform_snapshot",
            "platform_fee_irr",
            "platform_ascora_term_share_irr",
        }.issubset(columns)
    finally:
        engine.dispose()

    command.downgrade(config, LATEST_FINANCE_REVISION)

    engine = create_engine(migrated_database)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "platform_plan" not in tables
        assert "platform_agreement" not in tables
        assert "platform_invoice" not in tables
        with engine.connect() as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'finance_invoice_line'"
                    )
                )
            }
        assert "platform_agreement_id" not in columns
        assert "platform_fee_irr" not in columns
    finally:
        engine.dispose()

    _upgrade_head(migrated_database, monkeypatch)
    command.check(_alembic_config())


def _upgrade_head(database: URL, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_alembic_database(monkeypatch, database)
    command.upgrade(_alembic_config(), "head")


def test_platform_migration_enforces_unique_scope_and_balanced_append_only_journal(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _upgrade_head(migrated_database, monkeypatch)
    _, user_id = _seed_gym(migrated_database)
    gym_id = uuid.uuid4()
    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO gym (id, name, owner_id, is_active, created_at)
                       VALUES (:id, 'Platform Gym', :owner, true, now())"""
                ),
                {"id": gym_id, "owner": user_id},
            )
            duplicate = text(
                """INSERT INTO platform_agreement
                   (id, gym_id, group_id, version, supersedes_id, mode, status,
                    effective_from, effective_to, plan_version_id,
                    subscription_amount_irr, billing_interval,
                    volume_discount_bp, grace_days, restrict_after_days,
                    created_by_id, created_at, activated_at)
                   VALUES (gen_random_uuid(), :gym, NULL, 1, NULL, 'FREE',
                           'DRAFT', DATE '2026-11-01', NULL, NULL, 0,
                           'MONTHLY', 0, 7, 21, :actor, now(), NULL)"""
            )
            connection.execute(duplicate, {"gym": gym_id, "actor": user_id})

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(duplicate, {"gym": gym_id, "actor": user_id})

        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """INSERT INTO platform_journal
                           (id, entry_number, posting_date, event_type,
                            description, source_type, source_id, created_by_id,
                            created_at)
                           VALUES (gen_random_uuid(), 1, DATE '2026-11-01',
                                   'PLATFORM_FEE', 'unbalanced', 'test', NULL,
                                   :actor, now())"""
                    ),
                    {"actor": user_id},
                )

        journal_id = uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO platform_journal
                       (id, entry_number, posting_date, event_type, description,
                        source_type, source_id, created_by_id, created_at)
                       VALUES (:id, 2, DATE '2026-11-01', 'PLATFORM_FEE',
                               'balanced', 'test', NULL, :actor, now())"""
                ),
                {"id": journal_id, "actor": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO platform_journal_line
                       (id, journal_id, account_code, debit_irr, credit_irr, memo)
                       VALUES (gen_random_uuid(), :journal, '1100', 1000, 0, NULL),
                              (gen_random_uuid(), :journal, '4100', 0, 1000, NULL)"""
                ),
                {"journal": journal_id},
            )

        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE platform_journal_line SET debit_irr = 999 "
                        "WHERE journal_id = :journal AND debit_irr = 1000"
                    ),
                    {"journal": journal_id},
                )
    finally:
        engine.dispose()
