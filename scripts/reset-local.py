# ruff: noqa: T201
#!/usr/bin/env python3
"""Reset a local development or staging database, then rebuild it.

Usage:
    uv run --project backend python scripts/reset-local.py --env dev --yes

Refuses non-local hosts. This is destructive and requires --yes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=("dev", "stage"), required=True)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.yes:
        raise SystemExit("Refusing to reset without --yes")

    env_file = ROOT / f".env.{args.env}"
    if not env_file.is_file():
        raise SystemExit(f"{env_file.name} is missing")

    values = read_env(env_file)
    normalized = (values.get("DATABASE_URL") or "").replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    parts = urlsplit(normalized)
    if parts.hostname not in LOCAL_HOSTS:
        raise SystemExit(
            f"Refusing to reset a non-local database host: {parts.hostname!r}"
        )
    database = parts.path.lstrip("/")
    if not database or not database.endswith(f"_{args.env}"):
        raise SystemExit(
            f"Refusing to reset database {database!r}; expected a name ending _{args.env}"
        )

    maintenance = parts._replace(path="/postgres").geturl()
    with psycopg.connect(maintenance, autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
        )
        print(f"[reset] dropped {database}")

    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "backend",
            "python",
            "scripts/bootstrap-local.py",
            "--env",
            args.env,
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
