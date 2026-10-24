from __future__ import annotations

import re
import uuid
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
