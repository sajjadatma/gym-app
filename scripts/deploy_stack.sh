#!/usr/bin/env bash
# Deploy staging or production from an environment file.
# Requires explicit confirmation to avoid accidental production deploys:
#   CONFIRM_DEPLOY=staging bash scripts/deploy_stack.sh staging
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENVIRONMENT="${1:-}"
case "$ENVIRONMENT" in
  staging|production) ;;
  *) echo "Usage: CONFIRM_DEPLOY=<staging|production> $0 <staging|production>" >&2; exit 2 ;;
esac

if [ "${CONFIRM_DEPLOY:-}" != "$ENVIRONMENT" ]; then
  echo "Refusing to deploy: set CONFIRM_DEPLOY=$ENVIRONMENT after reviewing the target." >&2
  exit 1
fi

ENV_FILE="${ENV_FILE:-.env.$ENVIRONMENT}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f compose.deploy.yml -f "compose.$ENVIRONMENT.yml")

python3 scripts/preflight_env.py --env-file "$ENV_FILE" --environment "$ENVIRONMENT"
"${COMPOSE[@]}" config >/dev/null

echo "Deploying $ENVIRONMENT..."
if [ "${NO_BUILD:-0}" = "1" ]; then
  "${COMPOSE[@]}" pull backend
  "${COMPOSE[@]}" up -d --no-build
else
  "${COMPOSE[@]}" up -d --build
fi

DOMAIN="$(grep -E '^DOMAIN=' "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
HSTS_ENABLED="$(grep -E '^HSTS_ENABLED=' "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
REQUIRE_HSTS="$HSTS_ENABLED" CHECK_HTTP_REDIRECT=1 \
  bash scripts/smoke_stack.sh "https://$DOMAIN"

echo "Deployment completed. Review: docker compose logs -f backend"
