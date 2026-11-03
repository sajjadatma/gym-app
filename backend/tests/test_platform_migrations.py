from __future__ import annotations

from collections.abc import Generator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

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
    finally:
        engine.dispose()
