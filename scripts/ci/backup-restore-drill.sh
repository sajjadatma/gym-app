#!/usr/bin/env bash
# Isolated restore drill against the disposable CI stack.
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
export DEPLOY_ENV=ci
COMPOSE=(docker compose -f compose.deploy.yml -f compose.ci.yml)
NETWORK="${COMPOSE_PROJECT_NAME}_internal"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; "${COMPOSE[@]}" exec -T db psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS app_restore" >/dev/null 2>&1 || true' EXIT

athlete_id="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  'SELECT user_id FROM athlete_profile ORDER BY created_at LIMIT 1;')"
gym_id="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  "SELECT gym_id FROM athlete_profile WHERE user_id='$athlete_id';")"
[ -n "$athlete_id" ] && [ -n "$gym_id" ] || { echo "drill: FAIL no seeded athlete" >&2; exit 1; }

"${COMPOSE[@]}" exec -T backend sh -c \
  'printf drill-pdf-bytes > /app/backend/uploads/body-analysis/ci-drill.pdf'
"${COMPOSE[@]}" exec -T db psql -U postgres -d app -v ON_ERROR_STOP=1 -c \
  "INSERT INTO body_analysis_file (id,gym_id,athlete_user_id,uploaded_by_id,original_name,stored_name,content_type,size_bytes,created_at) VALUES (gen_random_uuid(),'$gym_id','$athlete_id',NULL,'ci-drill.pdf','ci-drill.pdf','application/pdf',15,now());"

output="$(BACKUP_DIR="$TMP/backups" bash scripts/backup_compose.sh)"
backup_path="${output#backup_path=}"
[ -d "$backup_path" ] || { echo "drill: FAIL backup was not produced" >&2; exit 1; }
(cd "$backup_path" && shasum -a 256 -c checksums.txt)

"${COMPOSE[@]}" exec -T db psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c 'CREATE DATABASE app_restore'
docker run --rm --network "$NETWORK" -e PGPASSWORD="$POSTGRES_PASSWORD" \
  -v "$backup_path:/backup:ro" postgres:17 \
  pg_restore --clean --if-exists --no-owner --no-privileges \
  -U postgres -d postgresql://postgres@db:5432/app_restore /backup/db.dump

mkdir -p "$TMP/restored-uploads"
tar -xzf "$backup_path/uploads.tar.gz" -C "$TMP/restored-uploads"
docker run --rm --network "$NETWORK" \
  -v "$TMP/restored-uploads/body-analysis:/uploads:ro" \
  -v "$backup_path/counts.txt:/counts.txt:ro" \
  "$BACKEND_IMAGE" python /app/backend/scripts/verify_restore.py \
  --database-url "postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app_restore" \
  --upload-dir /uploads --expected-counts /counts.txt

echo "drill: PASS"
