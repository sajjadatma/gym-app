#!/usr/bin/env bash
# Destructive restore of a backup created by scripts/backup_compose.sh into a
# running Compose deployment. Stops the backend, restores DB and uploads, then
# verifies counts and referenced files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${BACKUP_PATH:?BACKUP_PATH must point at a backup directory}"
DEPLOY_ENV="${DEPLOY_ENV:?DEPLOY_ENV must be staging, production or ci}"
if [ "${CONFIRM_RESTORE:-}" != "YES" ]; then
  echo "Refusing to restore: set CONFIRM_RESTORE=YES after verifying the target." >&2
  exit 1
fi

COMPOSE=(docker compose)
if [ -n "${ENV_FILE:-}" ] && [ -f "$ENV_FILE" ]; then
  COMPOSE+=(--env-file "$ENV_FILE")
fi
COMPOSE+=(-f compose.deploy.yml -f "compose.$DEPLOY_ENV.yml")
POSTGRES_DB="${POSTGRES_DB:-app}"

cd "$BACKUP_PATH"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c checksums.txt
else
  shasum -a 256 -c checksums.txt
fi
cd "$ROOT"

echo "Stopping backend..." >&2
"${COMPOSE[@]}" stop backend

echo "Restoring database..." >&2
"${COMPOSE[@]}" exec -T db pg_restore --clean --if-exists --no-owner \
  --no-privileges -U postgres -d "$POSTGRES_DB" < "$BACKUP_PATH/db.dump"

echo "Restoring uploads..." >&2
"${COMPOSE[@]}" exec -T backend sh -c \
  'find /app/backend/uploads -mindepth 1 -delete && tar -xzf - -C /app/backend/uploads' \
  < "$BACKUP_PATH/uploads.tar.gz"

echo "Starting backend..." >&2
"${COMPOSE[@]}" start backend

for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/utils/ready/')" \
    >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

"${COMPOSE[@]}" cp "$BACKUP_PATH/counts.txt" backend:/tmp/gym-counts.txt
"${COMPOSE[@]}" exec -T backend sh -c \
  'python /app/backend/scripts/verify_restore.py \
    --database-url "$DATABASE_URL" \
    --upload-dir /app/backend/uploads/body-analysis \
    --expected-counts /tmp/gym-counts.txt'

echo "Restore and integrity checks completed."
