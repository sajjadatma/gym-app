#!/usr/bin/env bash
# Post-deployment smoke checks. Usage:
#   bash scripts/smoke_stack.sh https://gym.example.com
# Optional: REQUIRE_HSTS=true CHECK_HTTP_REDIRECT=1 SMOKE_EMAIL=... SMOKE_PASSWORD=...
set -euo pipefail

BASE_URL="${1:-}"
: "${BASE_URL:?Usage: $0 https://host}"

headers="$(mktemp)"
trap 'rm -f "$headers"' EXIT

check_status() {
  local url="$1" expected="$2"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' "$url")"
  if [[ ! " $expected " =~ " $status " ]]; then
    echo "smoke: FAIL $url returned $status (expected $expected)" >&2
    exit 1
  fi
  echo "smoke: OK $url -> $status"
}

check_status "$BASE_URL/api/v1/utils/health-check/" "200"
check_status "$BASE_URL/api/v1/utils/ready/" "200"
check_status "$BASE_URL/" "200"

curl -sS -D "$headers" -o /dev/null "$BASE_URL/api/v1/utils/health-check/"
for header in x-content-type-options x-frame-options referrer-policy content-security-policy x-request-id; do
  if ! grep -qi "^$header:" "$headers"; then
    echo "smoke: FAIL missing security header: $header" >&2
    exit 1
  fi
done

if [ "${REQUIRE_HSTS:-true}" = "true" ]; then
  if ! grep -qi '^strict-transport-security:' "$headers"; then
    echo "smoke: FAIL missing Strict-Transport-Security" >&2
    exit 1
  fi
fi

if [ "${CHECK_HTTP_REDIRECT:-0}" = "1" ]; then
  http_url="${BASE_URL/https:\/\//http://}"
  redirect_status="$(curl -sS -o /dev/null -w '%{http_code}' "$http_url/")"
  if [[ "$redirect_status" != "301" && "$redirect_status" != "308" ]]; then
    echo "smoke: FAIL HTTP did not redirect to HTTPS ($redirect_status)" >&2
    exit 1
  fi
  echo "smoke: OK HTTP redirects to HTTPS"
fi

if [ -n "${SMOKE_EMAIL:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
  login_status="$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    "$BASE_URL/api/v1/login/access-token" \
    --data-urlencode "username=$SMOKE_EMAIL" \
    --data-urlencode "password=$SMOKE_PASSWORD")"
  if [ "$login_status" != "200" ]; then
    echo "smoke: FAIL login returned $login_status" >&2
    exit 1
  fi
  echo "smoke: OK login -> 200"
fi

echo "smoke: PASS"
