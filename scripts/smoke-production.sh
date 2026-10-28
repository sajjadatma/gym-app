#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:?usage: scripts/smoke-production.sh https://example.com}"

check_status() {
  local path="$1"
  local expected="$2"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}${path}")"
  if [[ "$status" != "$expected" ]]; then
    echo "smoke: ${path} expected ${expected}, got ${status}" >&2
    exit 1
  fi
  echo "smoke: ${path} ${status}"
}

check_status /health 200
check_status /api/v1/utils/ready/ 200
check_status /login 200
check_status /manifest.webmanifest 200
check_status /sw.js 200
check_status /assets/definitely-missing.js 404

cache_control="$(curl -sS -D - -o /dev/null "${BASE_URL}/login" | tr -d '\r' | awk -F': ' 'tolower($1)=="cache-control"{print $2}')"
if [[ "$cache_control" != *"no-store"* ]]; then
  echo "smoke: /login must be served with Cache-Control: no-store (got '${cache_control}')" >&2
  exit 1
fi
echo "smoke: /login cache-control ok"

echo "smoke: production checks passed"
