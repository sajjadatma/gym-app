#!/usr/bin/env bash
# Production/container entrypoint: migrate, bootstrap, then start the API.
set -euo pipefail

cd "$(dirname "$0")/.."

attempt=1
until alembic upgrade head; do
  if [ "$attempt" -ge 30 ]; then
    echo "Database migrations failed after ${attempt} attempts." >&2
    exit 1
  fi
  echo "Waiting for database/migrations (attempt ${attempt}/30)..." >&2
  attempt=$((attempt + 1))
  sleep 2
done

python -m app.initial_data

exec fastapi run \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
