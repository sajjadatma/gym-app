#!/usr/bin/env bash
# Restore a backup produced by scripts/backup.sh into an explicitly named,
# already-created target database. Never drops or overwrites an existing DB.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${BACKUP_PATH:?BACKUP_PATH must point at a backup directory}"
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL must point at the target database}"
: "${RESTORE_UPLOAD_DIR:?RESTORE_UPLOAD_DIR must point at the target upload directory}"

if [ "${CONFIRM_RESTORE:-}" != "YES" ]; then
  echo "Refusing to restore: set CONFIRM_RESTORE=YES after verifying the target." >&2
  exit 1
fi

cd "$BACKUP_PATH"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c checksums.txt
else
  shasum -a 256 -c checksums.txt
fi
cd "$ROOT"

PG_URL="${RESTORE_DATABASE_URL/+psycopg/}"
echo "Restoring database into the explicitly supplied target..."
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$PG_URL" "$BACKUP_PATH/db.dump"

if [ -e "$RESTORE_UPLOAD_DIR" ] && [ -n "$(ls -A "$RESTORE_UPLOAD_DIR" 2>/dev/null || true)" ] && [ "${ALLOW_NON_EMPTY_UPLOADS:-}" != "YES" ]; then
  echo "Refusing to overwrite non-empty upload directory: $RESTORE_UPLOAD_DIR" >&2
  echo "Set ALLOW_NON_EMPTY_UPLOADS=YES only after verifying the target." >&2
  exit 1
fi
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
tar -xzf "$BACKUP_PATH/uploads.tar.gz" -C "$TMP_DIR"
SOURCE_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$SOURCE_DIR" ]; then
  echo "Backup archive did not contain an upload directory." >&2
  exit 1
fi
mkdir -p "$RESTORE_UPLOAD_DIR"
cp -a "$SOURCE_DIR"/. "$RESTORE_UPLOAD_DIR"/

PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN=python3
"$PYTHON_BIN" "$ROOT/scripts/verify_restore.py" \
  --database-url "$RESTORE_DATABASE_URL" \
  --upload-dir "$RESTORE_UPLOAD_DIR" \
  --expected-counts "$BACKUP_PATH/counts.txt"

echo "Restore and integrity checks completed."
