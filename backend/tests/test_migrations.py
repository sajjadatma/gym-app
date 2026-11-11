from __future__ import annotations

import re
import uuid
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlmodel import Session

from app.core.config import settings
from app.services import finance as svc

pytestmark = pytest.mark.migrations

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_DATABASE_NAME = "gym_app_migration_test"


def _migration_database_url() -> URL:
    """Build the disposable migration database URL from TEST_DATABASE_URL."""
    if not settings.TEST_DATABASE_URL:
        pytest.fail("TEST_DATABASE_URL must be configured for the migration test")
    test_url = make_url(str(settings.TEST_DATABASE_URL))
    dev_url = make_url(str(settings.DATABASE_URL))
    migration_url = test_url.set(database=MIGRATION_DATABASE_NAME)

    database = migration_url.database or ""
    if not database.endswith("_test"):
        pytest.fail(f"Refusing to use non-test migration database: {database}")
    if database in {test_url.database, dev_url.database}:
        pytest.fail(f"Migration database {database!r} is not disposable")
    if str(migration_url) == str(dev_url):
        pytest.fail("Refusing to run the migration test against DATABASE_URL")
    return migration_url


def _maintenance_url(url: URL) -> URL:
    return url.set(database="postgres")


def _recreate_database(url: URL) -> None:
    admin_engine = create_engine(_maintenance_url(url), isolation_level="AUTOCOMMIT")
    database = url.database or ""
    if not re.fullmatch(r"[a-z0-9_]+", database):
        raise RuntimeError(f"Unsafe migration database name: {database!r}")
    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            )
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    finally:
        admin_engine.dispose()


def _drop_database(url: URL) -> None:
    admin_engine = create_engine(_maintenance_url(url), isolation_level="AUTOCOMMIT")
    database = url.database or ""
    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            )
    finally:
        admin_engine.dispose()


@pytest.fixture()
def migrated_database() -> Generator[URL]:
    migration_url = _migration_database_url()
    _recreate_database(migration_url)
    try:
        yield migration_url
    finally:
        _drop_database(migration_url)


def _alembic_config() -> Config:
    config = Config(f"{BACKEND_DIR}/alembic.ini")
    config.set_main_option("script_location", f"{BACKEND_DIR}/app/alembic")
    return config


def _database_url_string(url: URL) -> str:
    """Render a URL for config/env use without SQLAlchemy hiding the password.

    ``str(URL)`` masks the password as ``***``; a password-protected server
    then rejects the connection. Local trust-auth PostgreSQL hides the bug.
    """
    return url.render_as_string(hide_password=False)


def _set_alembic_database(monkeypatch: pytest.MonkeyPatch, url: URL) -> None:
    # alembic/env.py reads settings.DATABASE_URL at migration time.
    monkeypatch.setattr(settings, "DATABASE_URL", _database_url_string(url))


def test_database_url_string_preserves_password() -> None:
    url = make_url(
        "postgresql+psycopg://migration_user:s3cret@localhost:5432/gym_app_test"
    )
    assert make_url(_database_url_string(url)).password == "s3cret"


def test_alembic_database_setting_preserves_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "TEST_DATABASE_URL",
        "postgresql://migration_user:s3cret@localhost:5432/gym_app_test",
    )
    migration_url = _migration_database_url()
    _set_alembic_database(monkeypatch, migration_url)
    assert make_url(str(settings.DATABASE_URL)).password == "s3cret"


def test_fresh_database_upgrades_to_head_and_matches_models(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(migrated_database)
    try:
        head = ScriptDirectory.from_config(config).get_current_head()
        with engine.connect() as connection:
            applied = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert applied == head

        inspector = inspect(engine)
        user_columns = {
            column["name"]: column for column in inspector.get_columns("user")
        }
        token_version = user_columns["token_version"]
        assert token_version["nullable"] is False
        assert token_version["default"] == "0"

        version_columns = {
            column["name"]: column
            for column in inspector.get_columns("workout_program_version")
        }
        revision = version_columns["revision"]
        assert revision["nullable"] is False
        assert revision["default"] == "0"
    finally:
        engine.dispose()


def test_finance_money_columns_are_bigint_and_contracts_have_archive_metadata(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(migrated_database)
    try:
        inspector = inspect(engine)
        expected = {
            "finance_tax_definition": ["fixed_amount_irr"],
            "finance_coach_plan": ["base_price_irr"],
            "finance_program_request": ["base_price_irr", "total_amount_irr"],
            "finance_sale": [
                "base_amount_irr",
                "tax_amount_irr",
                "total_amount_irr",
                "platform_amount_irr",
                "gym_amount_irr",
                "coach_amount_irr",
            ],
            "finance_sale_tax": ["fixed_amount_irr", "amount_irr"],
            "finance_payment": ["amount_irr"],
            "finance_allocation": ["amount_irr"],
            "finance_settlement": ["amount_irr"],
            "finance_settlement_item": ["amount_irr"],
            "finance_refund": ["amount_irr"],
            "finance_refund_adjustment": ["amount_irr"],
        }
        for table, columns in expected.items():
            actual = {column["name"]: column for column in inspector.get_columns(table)}
            for column in columns:
                assert actual[column]["type"].__class__.__name__ == "BIGINT"
        for table in (
            "finance_platform_contract",
            "finance_coach_contract",
        ):
            columns = {
                column["name"]: column for column in inspector.get_columns(table)
            }
            assert "archived_at" in columns
    finally:
        engine.dispose()


def test_upgrade_with_existing_data_backfills_new_columns(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upgrade a database that already contains rows through the two migrations
    that add non-null columns: token_version on user and revision on
    workout_program_version."""
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "2a61e7c0b94a")

    user_id = uuid.uuid4()
    gym_id = uuid.uuid4()
    program_id = uuid.uuid4()
    version_id = uuid.uuid4()
    hashed_password = "legacy-hash-preserved-by-migration"
    legacy_title = "Legacy program version"

    insert_engine = create_engine(migrated_database)
    try:
        with insert_engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, full_name, hashed_password, is_active,
                        is_superuser, must_change_password, created_at)
                       VALUES (:id, :email, :full_name, :hashed_password, true,
                               false, false, now())"""
                ),
                {
                    "id": user_id,
                    "email": "legacy-migration@example.com",
                    "full_name": "Legacy User",
                    "hashed_password": hashed_password,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO gym
                       (id, name, owner_id, is_active, created_at)
                       VALUES (:id, :name, :owner_id, true, now())"""
                ),
                {"id": gym_id, "name": "Legacy Gym", "owner_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO workout_program
                       (id, gym_id, athlete_user_id, created_by_id, created_at)
                       VALUES (:id, :gym_id, :athlete_user_id, :created_by_id,
                               now())"""
                ),
                {
                    "id": program_id,
                    "gym_id": gym_id,
                    "athlete_user_id": user_id,
                    "created_by_id": user_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO workout_program_version
                       (id, program_id, version_number, status, title, created_at)
                       VALUES (:id, :program_id, 1, 'DRAFT', :title, now())"""
                ),
                {
                    "id": version_id,
                    "program_id": program_id,
                    "title": legacy_title,
                },
            )
    finally:
        insert_engine.dispose()

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            user_row = connection.execute(
                text(
                    'SELECT token_version, hashed_password FROM "user" WHERE id = :id'
                ),
                {"id": user_id},
            ).one()
            assert user_row.token_version == 0
            assert user_row.hashed_password == hashed_password

            version_row = connection.execute(
                text(
                    """SELECT revision, title FROM workout_program_version
                       WHERE id = :id"""
                ),
                {"id": version_id},
            ).one()
            assert version_row.revision == 0
            assert version_row.title == legacy_title

        inspector = inspect(engine)
        user_columns = {
            column["name"]: column for column in inspector.get_columns("user")
        }
        assert user_columns["token_version"]["nullable"] is False
        assert user_columns["token_version"]["default"] == "0"

        version_columns = {
            column["name"]: column
            for column in inspector.get_columns("workout_program_version")
        }
        assert version_columns["revision"]["nullable"] is False
        assert version_columns["revision"]["default"] == "0"
    finally:
        engine.dispose()


def test_finance_amounts_survive_bigint_upgrade(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "b8d1e2f3a4c5")

    user_id = uuid.uuid4()
    gym_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    amount = 2_147_483_647

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, hashed_password, is_active, is_superuser,
                        must_change_password, created_at)
                       VALUES (:id, :email, 'x', true, false, false, now())"""
                ),
                {"id": user_id, "email": "finance-migration@example.com"},
            )
            connection.execute(
                text(
                    """INSERT INTO gym (id, name, owner_id, is_active, created_at)
                       VALUES (:id, 'Finance Migration Gym', :owner_id, true, now())"""
                ),
                {"id": gym_id, "owner_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_platform_contract
                       (id, name, scope, gym_id, version, status, effective_from,
                        effective_to, created_by_id, created_at, activated_at)
                       VALUES (:id, 'Legacy default', 'DEFAULT', NULL, 1, 'ACTIVE',
                               current_date, NULL, :created_by, now(), now())"""
                ),
                {"id": contract_id, "created_by": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_sale
                       (id, gym_id, category, description, sold_on,
                        base_amount_irr, tax_amount_irr, total_amount_irr, status,
                        platform_bp, gym_bp, coach_bp, platform_amount_irr,
                        gym_amount_irr, coach_amount_irr, coach_user_id,
                        coach_contract_id, platform_contract_id, platform_source,
                        contract_snapshot, created_by_id, created_at)
                       VALUES (:id, :gym_id, 'MEMBERSHIP', 'Legacy sale', current_date,
                               :amount, 0, :amount, 'PAID', 1000, 9000, 0,
                               214748364, 1932735283, 0, NULL, NULL, :contract_id,
                               'PLATFORM_DEFAULT', '{}', :created_by, now())"""
                ),
                {
                    "id": sale_id,
                    "gym_id": gym_id,
                    "amount": amount,
                    "contract_id": contract_id,
                    "created_by": user_id,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT base_amount_irr, total_amount_irr FROM finance_sale WHERE id = :id"
                ),
                {"id": sale_id},
            ).one()
            assert row.base_amount_irr == amount
            assert row.total_amount_irr == amount
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("finance_sale")
        }
        assert columns["base_amount_irr"]["type"].__class__.__name__ == "BIGINT"
    finally:
        engine.dispose()


def test_finance_legacy_archived_overrides_are_historical_after_upgrade(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-archive-metadata override must not become current on upgrade.

    Older rows have status ARCHIVED but no archived_at timestamp. They may only
    be resolved for dates covered by an explicit effective_to, never for today.
    """
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "b8d1e2f3a4c5")

    today = svc.finance_today()
    owner_id = uuid.uuid4()
    coach_id = uuid.uuid4()
    gym_id = uuid.uuid4()
    default_contract_id = uuid.uuid4()
    legacy_override_id = uuid.uuid4()
    historical_override_id = uuid.uuid4()
    legacy_coach_contract_id = uuid.uuid4()

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, hashed_password, is_active, is_superuser,
                        must_change_password, created_at)
                       VALUES (:id, :email, 'x', true, false, false, now())"""
                ),
                {"id": owner_id, "email": "legacy-archive-owner@example.com"},
            )
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, hashed_password, is_active, is_superuser,
                        must_change_password, created_at)
                       VALUES (:id, :email, 'x', true, false, false, now())"""
                ),
                {"id": coach_id, "email": "legacy-archive-coach@example.com"},
            )
            connection.execute(
                text(
                    """INSERT INTO gym (id, name, owner_id, is_active, created_at)
                       VALUES (:id, 'Legacy Archive Gym', :owner_id, true, now())"""
                ),
                {"id": gym_id, "owner_id": owner_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_platform_contract
                       (id, name, scope, gym_id, version, status, effective_from,
                        effective_to, created_by_id, created_at, activated_at)
                       VALUES (:id, 'Default before archive metadata', 'DEFAULT',
                               NULL, 1, 'ACTIVE', :effective_from, NULL, :created_by,
                               now(), now())"""
                ),
                {
                    "id": default_contract_id,
                    "effective_from": today - timedelta(days=3650),
                    "created_by": owner_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_platform_contract
                       (id, name, scope, gym_id, version, status, effective_from,
                        effective_to, created_by_id, created_at, activated_at)
                       VALUES (:id, 'Legacy archived override', 'GYM', :gym_id, 1,
                               'ARCHIVED', :effective_from, NULL, :created_by,
                               now(), now())"""
                ),
                {
                    "id": legacy_override_id,
                    "gym_id": gym_id,
                    "effective_from": today - timedelta(days=2),
                    "created_by": owner_id,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO finance_platform_contract
                       (id, name, scope, gym_id, version, status, effective_from,
                        effective_to, created_by_id, created_at, activated_at)
                       VALUES (:id, 'Legacy historical override', 'GYM', :gym_id, 2,
                               'ARCHIVED', :effective_from, :effective_to,
                               :created_by, now(), now())"""
                ),
                {
                    "id": historical_override_id,
                    "gym_id": gym_id,
                    "effective_from": today - timedelta(days=3),
                    "effective_to": today - timedelta(days=1),
                    "created_by": owner_id,
                },
            )
            for contract_id, percent_bp in (
                (default_contract_id, 1000),
                (legacy_override_id, 3000),
                (historical_override_id, 3000),
            ):
                connection.execute(
                    text(
                        """INSERT INTO finance_platform_rate
                           (id, contract_id, category, percent_bp)
                           VALUES (:id, :contract_id, 'MEMBERSHIP', :percent_bp)"""
                    ),
                    {
                        "id": uuid.uuid4(),
                        "contract_id": contract_id,
                        "percent_bp": percent_bp,
                    },
                )
            connection.execute(
                text(
                    """INSERT INTO finance_coach_contract
                       (id, gym_id, coach_user_id, category, version, status,
                        effective_from, effective_to, platform_bp, gym_bp, coach_bp,
                        platform_contract_id, platform_source, created_by_id,
                        created_at, activated_at)
                       VALUES (:id, :gym_id, :coach_user_id, 'TRAINING', 1,
                               'ARCHIVED', :effective_from, NULL, 1000, 4000, 5000,
                               :platform_contract_id, 'PLATFORM_DEFAULT',
                               :created_by, now(), now())"""
                ),
                {
                    "id": legacy_coach_contract_id,
                    "gym_id": gym_id,
                    "coach_user_id": coach_id,
                    "effective_from": today - timedelta(days=2),
                    "platform_contract_id": default_contract_id,
                    "created_by": owner_id,
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT id, status, effective_to, archived_at
                       FROM finance_platform_contract
                       WHERE id IN (:legacy_id, :historical_id)"""
                ),
                {
                    "legacy_id": legacy_override_id,
                    "historical_id": historical_override_id,
                },
            ).all()
            by_id = {row.id: row for row in rows}
            assert by_id[legacy_override_id].status == "ARCHIVED"
            assert by_id[legacy_override_id].effective_to is None
            assert by_id[legacy_override_id].archived_at is None
            assert by_id[historical_override_id].status == "ARCHIVED"
            assert by_id[historical_override_id].effective_to == today - timedelta(
                days=1
            )
            assert by_id[historical_override_id].archived_at is None

        with Session(engine) as session:
            current = svc.resolve_platform_policy(
                session, gym_id=gym_id, category="MEMBERSHIP", on_date=today
            )
            assert current["source"] == "PLATFORM_DEFAULT"
            assert current["platform_bp"] == 1000

            historical = svc.resolve_platform_policy(
                session,
                gym_id=gym_id,
                category="MEMBERSHIP",
                on_date=today - timedelta(days=2),
            )
            assert historical["source"] == "GYM_OVERRIDE"
            assert historical["platform_bp"] == 3000
            assert historical["contract_id"] == historical_override_id

            assert (
                svc.resolve_coach_contract(
                    session,
                    gym_id=gym_id,
                    coach_user_id=coach_id,
                    category="TRAINING",
                    on_date=today,
                )
                is None
            )
    finally:
        engine.dispose()


def test_finance_bigint_downgrade_refuses_to_truncate_large_values(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")

    user_id = uuid.uuid4()
    gym_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    amount = 3_000_000_000

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO "user"
                       (id, email, hashed_password, is_active, is_superuser,
                        must_change_password, created_at)
                       VALUES (:id, :email, 'x', true, false, false, now())"""
                ),
                {"id": user_id, "email": "finance-downgrade@example.com"},
            )
            connection.execute(
                text(
                    """INSERT INTO gym (id, name, owner_id, is_active, created_at)
                       VALUES (:id, 'Finance Downgrade Gym', :owner_id, true, now())"""
                ),
                {"id": gym_id, "owner_id": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_platform_contract
                       (id, name, scope, gym_id, version, status, effective_from,
                        effective_to, created_by_id, created_at, activated_at)
                       VALUES (:id, 'Legacy default', 'DEFAULT', NULL, 1, 'ACTIVE',
                               current_date, NULL, :created_by, now(), now())"""
                ),
                {"id": contract_id, "created_by": user_id},
            )
            connection.execute(
                text(
                    """INSERT INTO finance_sale
                       (id, gym_id, category, description, sold_on,
                        base_amount_irr, tax_amount_irr, total_amount_irr, status,
                        platform_bp, gym_bp, coach_bp, platform_amount_irr,
                        gym_amount_irr, coach_amount_irr, coach_user_id,
                        coach_contract_id, platform_contract_id, platform_source,
                        contract_snapshot, created_by_id, created_at)
                       VALUES (:id, :gym_id, 'MEMBERSHIP', 'Large sale', current_date,
                               :amount, 0, :amount, 'PAID', 1000, 9000, 0,
                               300000000, 2700000000, 0, NULL, NULL, :contract_id,
                               'PLATFORM_DEFAULT', '{}', :created_by, now())"""
                ),
                {
                    "id": sale_id,
                    "gym_id": gym_id,
                    "amount": amount,
                    "contract_id": contract_id,
                    "created_by": user_id,
                },
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="Refusing finance downgrade"):
        command.downgrade(config, "b8d1e2f3a4c5")
