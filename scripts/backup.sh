#!/usr/bin/env bash
# Create a consistent backup of PostgreSQL and the body-analysis upload directory.
# Requires DATABASE_URL (or an exported equivalent) and pg_dump on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${DATABASE_URL:?DATABASE_URL must be set}"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
BODY_ANALYSIS_DIR="${BODY_ANALYSIS_DIR:-}"
if [ -z "$BODY_ANALYSIS_DIR" ]; then
  BODY_ANALYSIS_DIR="$(cd "$ROOT/backend" && uv run python -c 'from app.core.config import settings; print(settings.BODY_ANALYSIS_DIR)')"
fi

umask 077
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/$STAMP"
mkdir -p "$TARGET"
chmod 700 "$BACKUP_DIR" "$TARGET"

PG_URL="${DATABASE_URL/+psycopg/}"
echo "Backing up database..."
pg_dump --format=custom --no-owner --no-privileges --file="$TARGET/db.dump" "$PG_URL"
pg_restore --list "$TARGET/db.dump" >/dev/null

if [ ! -d "$BODY_ANALYSIS_DIR" ]; then
  echo "Body-analysis directory not found: $BODY_ANALYSIS_DIR" >&2
  exit 1
fi
echo "Backing up uploads..."
tar -C "$(dirname "$BODY_ANALYSIS_DIR")" -czf "$TARGET/uploads.tar.gz" "$(basename "$BODY_ANALYSIS_DIR")"

psql "$PG_URL" -Atc 'SELECT count(*) FROM "user";' > "$TARGET/counts.txt"
psql "$PG_URL" -Atc 'SELECT count(*) FROM gym;' >> "$TARGET/counts.txt"
psql "$PG_URL" -Atc 'SELECT count(*) FROM athlete_profile;' >> "$TARGET/counts.txt"
psql "$PG_URL" -Atc 'SELECT count(*) FROM body_analysis_file;' >> "$TARGET/counts.txt"
psql "$PG_URL" -Atc 'SELECT count(*) FROM workout_program_version;' >> "$TARGET/counts.txt"

sha() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}
{
  printf '%s  %s\n' "$(sha "$TARGET/db.dump")" "db.dump"
  printf '%s  %s\n' "$(sha "$TARGET/uploads.tar.gz")" "uploads.tar.gz"
  printf '%s  %s\n' "$(sha "$TARGET/counts.txt")" "counts.txt"
} > "$TARGET/checksums.txt"

chmod 600 "$TARGET"/*
echo "$TARGET"
