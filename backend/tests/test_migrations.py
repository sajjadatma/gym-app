from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from app.core.config import settings

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


@pytest.fixture(scope="module")
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


def test_fresh_database_upgrades_to_head_and_matches_models(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", str(migrated_database))
    config = _alembic_config()

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(str(migrated_database))
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
