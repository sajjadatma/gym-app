#!/usr/bin/env bash
# Run critical or full Playwright suites against the CI stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/frontend"

export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://localhost:8000}"
export PLAYWRIGHT_API_URL="${PLAYWRIGHT_API_URL:-http://localhost:8000}"

case "${1:-critical}" in
  critical)
    bunx playwright test \
      tests/auth.spec.ts \
      tests/program-authoring.spec.ts \
      tests/athlete.spec.ts \
      tests/superuser-context.spec.ts \
      --reporter=line
    ;;
  full)
    bunx playwright test --reporter=line
    ;;
  pwa)
    PWA_PROD=1 bunx playwright test tests/pwa.spec.ts \
      --project=chromium --no-deps --reporter=line
    ;;
  *)
    echo "Usage: $0 [critical|full|pwa]" >&2
    exit 2
    ;;
esac
