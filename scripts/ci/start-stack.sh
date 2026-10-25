#!/usr/bin/env bash
# Build and start the disposable CI stack, then verify startup and migrations.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-gym-ci}"
export BACKEND_IMAGE="${BACKEND_IMAGE:-gym-app-ci:local}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ci-postgres-password}"
export SECRET_KEY="${SECRET_KEY:-ci-only-secret-key-not-for-production-0123456789}"
export FIRST_SUPERUSER="${FIRST_SUPERUSER:-ci-superuser@example.com}"
export FIRST_SUPERUSER_PASSWORD="${FIRST_SUPERUSER_PASSWORD:-ci-only-superuser-password}"
export DOMAIN="${DOMAIN:-localhost}"
export ACME_EMAIL="${ACME_EMAIL:-ci@example.com}"
export ACME_CA_SERVER="${ACME_CA_SERVER:-https://acme-staging-v02.api.letsencrypt.org/directory}"
export HSTS_ENABLED=false
export LOG_JSON=false
export SENTRY_ENVIRONMENT=ci
export EMAIL_REDIRECT_TO=

COMPOSE=(docker compose -f compose.deploy.yml -f compose.ci.yml)
"${COMPOSE[@]}" config >/dev/null

if [ "${NO_BUILD:-0}" = "1" ]; then
  "${COMPOSE[@]}" up -d --no-build
else
  "${COMPOSE[@]}" up -d --build
fi

ready=0
for _ in $(seq 1 90); do
  if curl -fsS http://localhost:8000/api/v1/utils/ready/ >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != "1" ]; then
  "${COMPOSE[@]}" logs backend
  echo "stack: FAIL backend did not become ready" >&2
  exit 1
fi
echo "stack: ready"

"${COMPOSE[@]}" exec -T backend python scripts/seed_demo.py

head="$("${COMPOSE[@]}" exec -T backend alembic heads | awk '{print $1}' | head -n1)"
current="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc 'SELECT version_num FROM alembic_version;')"
if [ -z "$head" ] || [ "$head" != "$current" ]; then
  echo "stack: FAIL migration revision current=$current head=$head" >&2
  exit 1
fi
echo "stack: migrations at $current"
