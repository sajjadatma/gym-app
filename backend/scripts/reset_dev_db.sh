#!/usr/bin/env bash
# Destructive reset for the dedicated local gym_app development database only.
# Refuses to run unless CONFIRM_RESET_GYM_APP=YES and the target DB is exactly gym_app.
set -euo pipefail

if [ "${CONFIRM_RESET_GYM_APP:-}" != "YES" ]; then
  echo "Refusing to reset: set CONFIRM_RESET_GYM_APP=YES for the disposable gym_app dev database." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

uv run python - <<'PY'
from sqlalchemy import text

from app.core.config import settings

database_name = str(settings.DATABASE_URL).rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
if database_name != "gym_app":
    raise SystemExit(
        f"Refusing to reset database '{database_name}'. Only the dedicated local 'gym_app' database is disposable."
    )
from app.core.db import engine

with engine.begin() as connection:
    connection.execute(text("DROP SCHEMA public CASCADE"))
    connection.execute(text("CREATE SCHEMA public"))
upload_dir = settings.BODY_ANALYSIS_DIR
if upload_dir.exists():
    for upload in upload_dir.iterdir():
        if upload.is_file():
            upload.unlink()
print("Dropped and recreated the gym_app public schema.")
print("Cleared local body-analysis uploads.")
PY

uv run alembic upgrade head
uv run python -m app.initial_data

if [ "${SEED_DEMO_DATA:-}" = "YES" ]; then
  uv run python scripts/seed_demo.py
fi

echo "Local development database reset complete."
