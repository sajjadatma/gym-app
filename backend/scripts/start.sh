#!/usr/bin/env bash
# Production/container entrypoint: bootstrap (migrate + seed under a DB lock),
# then start the API.
set -euo pipefail

cd "$(dirname "$0")/.."

# Fail fast on invalid configuration instead of retrying for a minute.
python -c "from app.core.config import settings" || {
  echo "Configuration validation failed." >&2
  exit 1
}

attempt=1
until python scripts/bootstrap.py; do
  if [ "$attempt" -ge 30 ]; then
    echo "Database bootstrap failed after ${attempt} attempts." >&2
    exit 1
  fi
  echo "Waiting for database/bootstrap (attempt ${attempt}/30)..." >&2
  attempt=$((attempt + 1))
  sleep 2
done

exec fastapi run \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
