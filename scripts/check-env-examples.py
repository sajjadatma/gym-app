# ruff: noqa: T201
#!/usr/bin/env python3
"""Verify the committed local environment examples stay isolated.

This is a fast CI contract check. It never reads .env.dev or .env.stage.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "PROJECT_NAME",
    "FASTAPI_ENV",
    "SECRET_KEY",
    "FRONTEND_HOST",
    "FIRST_SUPERUSER",
    "FIRST_SUPERUSER_PASSWORD",
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "FRONTEND_PORT",
    "BACKEND_PORT",
    "VITE_API_URL",
    "COOKIE_SECURE",
    "HSTS_ENABLED",
    "RATE_LIMIT_BACKEND",
}


def parse_env(path: Path) -> dict[str, str]:
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
    environments = {
        "dev": parse_env(ROOT / ".env.dev.example"),
        "stage": parse_env(ROOT / ".env.stage.example"),
    }
    errors: list[str] = []
    expected = {
        "dev": ("development", "gym_dev", "5173", "8000"),
        "stage": ("staging", "gym_stage", "5174", "8001"),
    }

    for name, values in environments.items():
        missing = sorted(REQUIRED - values.keys())
        if missing:
            errors.append(f"{name}: missing keys: {', '.join(missing)}")
            continue
        fastapi_env, database, frontend_port, backend_port = expected[name]
        if values["FASTAPI_ENV"] != fastapi_env:
            errors.append(f"{name}: FASTAPI_ENV must be {fastapi_env}")
        parsed = urlsplit(
            values["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
        )
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            errors.append(f"{name}: DATABASE_URL must use a local host")
        if parsed.path.lstrip("/") != database:
            errors.append(f"{name}: DATABASE_URL must use {database}")
        if values["FRONTEND_PORT"] != frontend_port:
            errors.append(f"{name}: FRONTEND_PORT must be {frontend_port}")
        if values["BACKEND_PORT"] != backend_port:
            errors.append(f"{name}: BACKEND_PORT must be {backend_port}")
        if values["COOKIE_SECURE"].lower() != "false":
            errors.append(f"{name}: COOKIE_SECURE must be false locally")
        if values["HSTS_ENABLED"].lower() != "false":
            errors.append(f"{name}: HSTS_ENABLED must be false locally")
        if values["RATE_LIMIT_BACKEND"] != "memory":
            errors.append(f"{name}: RATE_LIMIT_BACKEND must be memory locally")

    if environments["dev"]["DATABASE_URL"] == environments["stage"]["DATABASE_URL"]:
        errors.append("dev and stage must use different databases")
    if environments["dev"]["SECRET_KEY"] == environments["stage"]["SECRET_KEY"]:
        errors.append("dev and stage must use different secrets")

    if errors:
        for error in errors:
            print(f"env-contract: FAIL: {error}", file=sys.stderr)
        return 1
    print("env-contract: OK (dev and stage are isolated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
