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
    line_id = uuid.uuid4()
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
                       VALUES (:id, :journal, :account, 500000, 0, NULL)"""
                ),
                {
                    "id": line_id,
                    "journal": journal_id,
                    "account": accounts["1000"],
                },
            )
    finally:
        insert.dispose()
    return journal_id, line_id


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
    assert codes == ["1000", "1100", "2000", "3000", "4000", "5000"]


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


def test_database_prevents_two_opening_balances_for_one_gym(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    gym_id, user_id = _gym_at_head(migrated_database, monkeypatch)
    _journal_id, _line_id = _post_journal(
        migrated_database, gym_id=gym_id, user_id=user_id
    )

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            period_id = connection.execute(
                text("SELECT id FROM finance_period WHERE gym_id = :gym"),
                {"gym": gym_id},
            ).scalar_one()

        with pytest.raises(DBAPIError) as failure:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """INSERT INTO finance_journal
                           (id, gym_id, period_id, entry_number, posting_date,
                            event_type, description, reversal_of_id,
                            created_by_id, created_at)
                           VALUES (:id, :gym, :period, 2, DATE '2026-11-02',
                                   'OPENING_BALANCE', 'Second', NULL, :actor, now())"""
                    ),
                    {
                        "id": uuid.uuid4(),
                        "gym": gym_id,
                        "period": period_id,
                        "actor": user_id,
                    },
                )
        assert "uq_finance_journal_opening" in str(failure.value)
    finally:
        engine.dispose()


def test_database_allows_only_one_active_grant_per_permission(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")
    gym_id, user_id = _gym_at_head(migrated_database, monkeypatch)

    engine = create_engine(migrated_database)
    try:
        first_id = uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_grant
                       (id, gym_id, user_id, permission, amount_limit_irr,
                        granted_by_id, created_at, revoked_at)
                       VALUES (:id, :gym, :user, 'finance.opening.manage',
                               NULL, :user, now(), NULL)"""
                ),
                {"id": first_id, "gym": gym_id, "user": user_id},
            )

        with pytest.raises(DBAPIError) as failure:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """INSERT INTO finance_grant
                           (id, gym_id, user_id, permission, amount_limit_irr,
                            granted_by_id, created_at, revoked_at)
                           VALUES (:id, :gym, :user, 'finance.opening.manage',
                                   NULL, :user, now(), NULL)"""
                    ),
                    {"id": uuid.uuid4(), "gym": gym_id, "user": user_id},
                )
        assert "uq_finance_grant_active" in str(failure.value)

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE finance_grant SET revoked_at = now() WHERE id = :id"
                ),
                {"id": first_id},
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO finance_grant
                       (id, gym_id, user_id, permission, amount_limit_irr,
                        granted_by_id, created_at, revoked_at)
                       VALUES (:id, :gym, :user, 'finance.opening.manage',
                               NULL, :user, now(), NULL)"""
                ),
                {"id": uuid.uuid4(), "gym": gym_id, "user": user_id},
            )
    finally:
        engine.dispose()
