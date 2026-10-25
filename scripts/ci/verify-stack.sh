#!/usr/bin/env bash
# Restart/persistence, config-failure, and concurrent-migration checks.
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
COMPOSE=(docker compose -f compose.deploy.yml -f compose.ci.yml)
NETWORK="${COMPOSE_PROJECT_NAME}_internal"

wait_ready() {
  local container="$1"
  for _ in $(seq 1 45); do
    if docker exec "$container" python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/utils/ready/')" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

echo "verify: configuration failure is rejected"
if docker run --rm \
  -e FASTAPI_ENV=production \
  -e SECRET_KEY=short \
  -e COOKIE_SECURE=true \
  -e DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app" \
  -e FIRST_SUPERUSER="$FIRST_SUPERUSER" \
  -e FIRST_SUPERUSER_PASSWORD="$FIRST_SUPERUSER_PASSWORD" \
  "$BACKEND_IMAGE" >/dev/null 2>&1; then
  echo "verify: FAIL insecure configuration started" >&2
  exit 1
fi
echo "verify: insecure configuration rejected"

echo "verify: restart preserves database and uploads"
before="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc 'SELECT count(*) FROM "user";')"
"${COMPOSE[@]}" exec -T backend sh -c \
  'mkdir -p /app/backend/uploads/body-analysis && printf ci-marker > /app/backend/uploads/body-analysis/ci-marker.txt'
"${COMPOSE[@]}" restart backend
ready=0
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/v1/utils/ready/ >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
[ "$ready" = "1" ] || { echo "verify: FAIL backend did not recover" >&2; exit 1; }
after="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc 'SELECT count(*) FROM "user";')"
if [ "$before" != "$after" ]; then
  echo "verify: FAIL user count changed across restart: $before -> $after" >&2
  exit 1
fi
"${COMPOSE[@]}" exec -T backend test -f /app/backend/uploads/body-analysis/ci-marker.txt
echo "verify: restart persistence OK"


echo "verify: runtime rate limiting returns 429"
docker rm -f ci-rate-limit >/dev/null 2>&1 || true
docker run -d --name ci-rate-limit --network "${COMPOSE_PROJECT_NAME}_edge" \
  --network "$NETWORK" -p 8001:8000 \
  -e FASTAPI_ENV=development \
  -e FRONTEND_HOST=http://localhost:8001 \
  -e SECRET_KEY="$SECRET_KEY" \
  -e COOKIE_SECURE=false \
  -e DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app" \
  -e FIRST_SUPERUSER="$FIRST_SUPERUSER" \
  -e FIRST_SUPERUSER_PASSWORD="$FIRST_SUPERUSER_PASSWORD" \
  -e RATE_LIMIT_ENABLED=true \
  -e LOGIN_RATE_LIMIT=2 \
  -e LOGIN_IP_RATE_LIMIT=100 \
  "$BACKEND_IMAGE" >/dev/null
rate_ready=0
for _ in $(seq 1 45); do
  if curl -fsS http://localhost:8001/api/v1/utils/ready/ >/dev/null 2>&1; then
    rate_ready=1
    break
  fi
  sleep 2
done
if [ "$rate_ready" != "1" ]; then
  docker ps -a --filter name=ci-rate-limit || true
  docker logs ci-rate-limit || true
  docker rm -f ci-rate-limit >/dev/null 2>&1 || true
  echo "verify: FAIL rate-limit container did not become ready" >&2
  exit 1
fi
codes=()
for _ in 1 2 3; do
  codes+=("$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    http://localhost:8001/api/v1/login/access-token \
    -d 'username=rate-limit@example.com&password=wrong-password' || true)")
done
if [ "${codes[0]:-}" != "400" ] || [ "${codes[1]:-}" != "400" ] || [ "${codes[2]:-}" != "429" ]; then
  echo "verify: FAIL runtime rate limit codes: ${codes[*]:-none}" >&2
  docker logs ci-rate-limit || true
  docker rm -f ci-rate-limit >/dev/null 2>&1 || true
  exit 1
fi
retry_after="$(curl -sS -D - -o /dev/null -X POST \
  http://localhost:8001/api/v1/login/access-token \
  -d 'username=rate-limit@example.com&password=wrong-password' | grep -i '^retry-after:' || true)"
if [ -z "$retry_after" ]; then
  echo "verify: FAIL missing Retry-After" >&2
  docker logs ci-rate-limit || true
  docker rm -f ci-rate-limit >/dev/null 2>&1 || true
  exit 1
fi
docker rm -f ci-rate-limit >/dev/null
echo "verify: runtime rate limit OK (${codes[*]}, $retry_after)"

echo "verify: concurrent startup serializes migrations"
"${COMPOSE[@]}" exec -T db psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c 'DROP DATABASE IF EXISTS app_concurrent' \
  -c 'CREATE DATABASE app_concurrent'
docker rm -f ci-concurrent-a ci-concurrent-b >/dev/null 2>&1 || true
"${COMPOSE[@]}" run -d --name ci-concurrent-a \
  -e DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app_concurrent" \
  backend >/dev/null
"${COMPOSE[@]}" run -d --name ci-concurrent-b \
  -e DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app_concurrent" \
  backend >/dev/null
if ! wait_ready ci-concurrent-a || ! wait_ready ci-concurrent-b; then
  docker logs ci-concurrent-a || true
  docker logs ci-concurrent-b || true
  docker rm -f ci-concurrent-a ci-concurrent-b >/dev/null 2>&1 || true
  echo "verify: FAIL concurrent startup did not converge" >&2
  exit 1
fi
versions="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app_concurrent -Atc \
  'SELECT count(*), count(DISTINCT version_num) FROM alembic_version;')"
if [ "$versions" != "1|1" ]; then
  echo "verify: FAIL unexpected alembic_version state: $versions" >&2
  exit 1
fi
docker rm -f ci-concurrent-a ci-concurrent-b >/dev/null
echo "verify: concurrent startup OK ($versions)"
