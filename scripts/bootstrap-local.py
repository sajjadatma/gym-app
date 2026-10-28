# ruff: noqa: T201
#!/usr/bin/env python3
"""Create and prepare a local development or staging database.

Usage:
    uv run --project backend python scripts/bootstrap-local.py --env dev
    uv run --project backend python scripts/bootstrap-local.py --env stage --no-seed

The command refuses remote databases. It creates the app and test databases,
applies migrations, bootstraps the superuser, and seeds deterministic demo data.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def connect_url(database_url: str) -> tuple[str, str, str]:
    """Return a maintenance URL and the app/test database names."""
    normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parts = urlsplit(normalized)
    if parts.hostname not in LOCAL_HOSTS:
        raise SystemExit(
            f"Refusing to prepare a non-local database host: {parts.hostname!r}"
        )
    database = parts.path.lstrip("/")
    if not database:
        raise SystemExit("DATABASE_URL must include a database name")
    maintenance = urlunsplit(parts._replace(path="/postgres"))
    return maintenance, database, parts


def ensure_database(maintenance_url: str, database: str) -> None:
    with psycopg.connect(maintenance_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if exists:
            print(f"[bootstrap] database exists: {database}")
            return
        print(f"[bootstrap] creating database: {database}")
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )


def verify_test_database(values: dict[str, str], maintenance_url: str) -> None:
    test_url = values.get("TEST_DATABASE_URL")
    if not test_url:
        return
    normalized = test_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parts = urlsplit(normalized)
    if parts.hostname not in LOCAL_HOSTS:
        raise SystemExit(
            f"Refusing non-local TEST_DATABASE_URL host: {parts.hostname!r}"
        )
    test_database = parts.path.lstrip("/")
    if test_database:
        ensure_database(maintenance_url, test_database)


def run_checked(args: list[str], environment: dict[str, str]) -> None:
    print(f"[bootstrap] {' '.join(args)}")
    subprocess.run(args, cwd=BACKEND, env=environment, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=("dev", "stage"), default="dev")
    parser.add_argument("--no-seed", action="store_true")
    args = parser.parse_args()

    env_file = ROOT / f".env.{args.env}"
    if not env_file.is_file():
        raise SystemExit(
            f"{env_file.name} is missing. Copy {env_file.name}.example and fill it in."
        )

    values = read_env(env_file)
    database_url = values.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing from the environment file")

    maintenance_url, database, _ = connect_url(database_url)
    ensure_database(maintenance_url, database)
    verify_test_database(values, maintenance_url)

    environment = {**os.environ, **values, "ENV_FILE": str(env_file)}
    for name in ("development-body-analysis", "staging-body-analysis"):
        (ROOT / "backend" / "uploads" / name).mkdir(parents=True, exist_ok=True)

    run_checked(["uv", "run", "alembic", "upgrade", "head"], environment)
    run_checked(["uv", "run", "python", "-m", "app.initial_data"], environment)
    if not args.no_seed:
        run_checked(["uv", "run", "python", "scripts/seed_demo.py"], environment)

    print(
        f"[bootstrap] {args.env} ready: {database} "
        f"(superuser: {values.get('FIRST_SUPERUSER')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
