"""Run migrations and bootstrap under a PostgreSQL advisory lock.

Multiple application containers may start at the same time. The lock makes
schema migration and initial-data creation serial, so only one instance can
apply them; the others wait and then start against the migrated schema.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import psycopg  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402

configure_logging()
logger = logging.getLogger("app.bootstrap")

# Stable application-specific key; changing it would break cross-version
# startup coordination during a rolling deploy.
MIGRATION_LOCK_ID = 0x67796D5F6D696772


def _run(*args: str) -> None:
    subprocess.run(args, cwd=BACKEND_DIR, check=True)


def main() -> int:
    database_url = str(settings.DATABASE_URL).replace("+psycopg", "")
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("SET lock_timeout = '120s'")
        logger.info("startup_lock_acquiring")
        connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        try:
            logger.info("startup_migrating")
            _run(sys.executable, "-m", "alembic", "upgrade", "head")
            logger.info("startup_bootstrapping")
            _run(sys.executable, "-m", "app.initial_data")
        finally:
            connection.execute(
                "SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,)
            )
            logger.info("startup_lock_released")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
