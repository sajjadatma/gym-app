#!/usr/bin/env bash
# Exit non-zero when the newest successful backup is older than MAX_AGE_HOURS.
# Intended for an external monitor or cron alert wrapper.
set -euo pipefail
: "${BACKUP_DIR:?BACKUP_DIR must be set}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-26}"
MARKER="$BACKUP_DIR/last_success"

if [ ! -f "$MARKER" ]; then
  echo "backup freshness: FAIL no successful backup marker" >&2
  exit 1
fi
if [ -n "$(find "$MARKER" -mmin "+$((MAX_AGE_HOURS * 60))" -print -quit)" ]; then
  echo "backup freshness: FAIL marker older than ${MAX_AGE_HOURS}h" >&2
  exit 1
fi
echo "backup freshness: OK ($(cat "$MARKER"))"
