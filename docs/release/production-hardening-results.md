# Production Hardening Results

**Date:** 2026-10-25
**Scope:** MVP1 release hardening (no feature or business-rule changes)
**Baseline audit:** `mvp1-security-operations-audit.md` at `fbb9a22`
**Plan:** `production-hardening-plan.md`

> **Update 2026-10-25:** Docker image build/startup, migrations, restart persistence, config failure, rate limiting, concurrent migrations and backup/restore are now verified in CI. Staging/production Compose and preflight validation are also verified. See `staging-production-readiness.md` and `release-candidate-report.md`; the Docker/TLS lines below describe the earlier local-only verification state.

## 1. Status summary

Implementation and local verification of every confirmed BLOCKER/HIGH finding are complete. All automated suites pass on a disposable database. The isolated backup/restore drill passed with verified row counts and byte-identical upload data.

Two verification gaps remain and are reported as **NOT VERIFIED**, not as passed:

- **Docker image build/run:** the Docker daemon is unavailable on the verification host. Only Compose interpolation/config validation was performed.
- **Public TLS/ACME/DNS:** verified locally with a self-signed certificate (HTTPS + HSTS headers), but no real domain or ACME issuance was tested. Public HTTPS must be verified by the operator on the target host.

## 2. Implemented changes

### 2.1 Authentication, sessions, and abuse protection

| Area | Change |
|---|---|
| Browser session transport | Login now sets `gym_access_token` as `HttpOnly`, `SameSite=Lax`, `Secure` when configured, and a readable `gym_csrf_token`. Browser code no longer reads or stores bearer tokens. Bearer tokens remain supported for API clients and tests. |
| CSRF | Cookie-authenticated unsafe requests require `X-CSRF-Token` matching the CSRF cookie (double submit, `secrets.compare_digest`). Missing/mismatched header → `403 csrf_failed`. |
| Origin check | Login, recovery, reset, and invitation flows reject a foreign `Origin` with `403 origin_not_allowed`. |
| Logout/revocation | `POST /api/v1/auth/logout` increments `token_version`, revoking all previously issued access/reset tokens for that user, then clears cookies. |
| Rate limiting | In-process sliding-window limiter with separate per-IP (`LOGIN_IP_RATE_LIMIT`, `RECOVERY_IP_RATE_LIMIT`) and per-identity limits for login and recovery, so rotating usernames/emails from one IP does not bypass protection. Endpoint-level limits apply to reset and invitation. Returns `429` with `Retry-After` and generic `detail`. Successful login resets the per-identity counter (not the IP counter). Idle keys are pruned to bound memory. |
| Token lifetime | Default access-token lifetime reduced from 8 days to 12 hours. |
| Frontend | `api.ts` uses `withCredentials`, attaches `X-CSRF-Token`, and avoids redirect loops on the `/users/me` probe. Route guards now rely on loaded identity instead of `localStorage`. |

### 2.2 Production configuration and deployment

| Area | Change |
|---|---|
| Environment model | `FASTAPI_ENV` accepts `development`, `staging`, `production`. In `staging`/`production`, `SECRET_KEY` must be ≥32 chars and `COOKIE_SECURE` must be true; invalid combinations fail startup. `SameSite=None` without `Secure` is rejected. |
| Startup | `backend/scripts/start.sh` waits for the DB, runs `alembic upgrade head` (bounded retries), bootstraps initial data, then starts `fastapi run` with proxy headers. The Dockerfile uses this entrypoint. |
| Readiness | `GET /api/v1/utils/ready/` executes `SELECT 1` and returns `503 database_unavailable` on failure. `GET /api/v1/utils/health-check/` remains a process-liveness probe. Compose healthchecks target readiness. |
| Production Compose | `compose.production.yml` adds Traefik with HTTP→HTTPS redirect, ACME HTTP challenge, HSTS configured at the app, internal-only DB network, no DB/Adminer ports, persistent uploads volume, and readiness healthcheck. Missing required variables fail interpolation. |
| Security headers | Runtime responses include CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `X-Request-ID`; `Strict-Transport-Security` when enabled. |
| Request limits | JSON bodies above `MAX_JSON_BODY_BYTES` are rejected with `413 request_too_large` before handlers. Body-analysis uploads and athlete imports retain their existing bounded reads. |
| Logging | Per-request ID, method, redacted path (recovery email redacted), status, and duration. Sentry has PII disabled and request bodies disabled. |

### 2.3 Application security and data safety

| Area | Change |
|---|---|
| Email escaping | Jinja2 environment enables autoescaping; regression test injects markup into gym/user names. |
| Audit visibility | Structured `app.audit` events for ownership transfer, membership changes, coach archive/restore/removal, athlete archive/restore/delete, and program-version publish/archive/delete. IDs only; no names or secrets. |
| Backup | `scripts/backup.sh` creates a custom-format `pg_dump`, verified archive listing, uploads `tar.gz`, row counts, and SHA-256 checksums. Failure exits non-zero. |
| Restore | `scripts/restore.sh` requires an explicit target DB/dir and `CONFIRM_RESTORE=YES`, verifies checksums, restores, and runs `scripts/verify_restore.py` for row counts, file presence, and size consistency. Non-empty upload targets are refused unless explicitly allowed. |

## 3. Evidence of remediation

### 3.1 Automated tests (final run)

| Check | Result |
|---|---|
| `cd backend && uv run ruff check app tests` | All checks passed |
| `cd backend && uv run mypy app` | Success, 39 source files |
| `cd backend && uv run pytest -q` | **112 passed** |
| `cd backend && uv run pytest -q -m migrations` | **4 passed**, 108 deselected |
| `cd backend && uv run alembic check` | No new upgrade operations detected |
| `cd frontend && bun run lint:check` | 129 files, no fixes |
| `cd frontend && bunx tsc -p tsconfig.build.json --noEmit` | Pass |
| `cd frontend && bun run build` | Pass |
| `cd frontend && node --test tests-unit/*.test.mjs` | **6 passed** |
| Full Playwright (desktop + emulated mobile + superuser) | **69 passed**, 1 skipped (70 total) |
| Production PWA smoke (`PWA_PROD=1 --no-deps`) | **2 passed** |
| `docker compose -f compose.production.yml config` (with required env) | Valid |
| Docker image build/start | **NOT VERIFIED** — daemon unavailable |

Playwright was run against a disposable database on `:8001`/`:5174` with a disposable superuser. The one skip is the production-service-worker test, which is covered separately by the PWA run.

New focused regression tests (`backend/tests/api/routes/test_auth_security.py`, 10 tests) cover:

- HttpOnly access cookie + readable CSRF cookie attributes;
- CSRF rejection and successful logout revocation of both cookie and old bearer token;
- login per-identity and per-IP `429` + `Retry-After` (including username rotation from one IP);
- recovery per-email and per-IP `429` + `Retry-After`;
- security headers and request ID;
- readiness success/`503` behavior;
- oversized JSON `413`;
- email HTML escaping;
- production mode rejecting insecure cookies.

### 3.2 Runtime probes

- Repeated failed logins → `400`, `400`, then `429 too_many_attempts` with `Retry-After: 60` (limit lowered to 2 for the probe).
- Production-mode startup with `FASTAPI_ENV=production COOKIE_SECURE=true HSTS_ENABLED=true` succeeded and served health/readiness `200`.
- Local self-signed HTTPS served all security headers including `Strict-Transport-Security: max-age=31536000; includeSubDomains`; readiness returned `200`.
- Missing/insufficient production configuration fails startup (covered by tests).

### 3.3 Backup/restore drill

Environment: disposable database `gym_app_hardening_test`, isolated restore database, isolated upload directories under a temp path.

| Step | Result |
|---|---|
| Backup | Dump + uploads archive + checksums produced |
| Backup failure probe (nonexistent DB) | exit code **1** |
| Restore into isolated DB | Completed |
| Integrity output | `{"counts": {"user": 12, "gym": 3, "athlete_profile": 5, "body_analysis_file": 1, "workout_program_version": 5}, "files_checked": 1, "ok": true, "failures": []}` |
| Upload byte check | Source and restored SHA-256 both `49fda3c9684ceeb3409884d600018bb303c1b9dd48ff4cb9fabb14be72784d5a`; `cmp` identical |

## 4. Finding dispositions after hardening

| ID | Final disposition |
|---|---|
| B-1 | **Resolved — verified locally** (separate per-IP and per-identity server-side limits, `429`/`Retry-After`, tests + runtime probe) |
| B-2 | **Resolved — verified locally** (isolated restore drill with count/file checks) |
| B-3 | **Partially resolved** — TLS/ACME/HSTS implemented and locally verified over self-signed HTTPS; public certificate/DNS **NOT VERIFIED** |
| B-4 | **Resolved — verified locally** (cookie session, CSRF, server logout/revocation, CSP/headers, full regression) |
| H-1 | **Partially resolved** — entrypoint, migrations, production Compose validated; image build **NOT VERIFIED** (no Docker daemon) |
| H-2 | **Resolved — verified locally** (DB-aware readiness with `503` test) |
| H-3 | **Resolved — verified locally** (autoescaping + regression test) |
| H-4 | **Resolved — verified locally** (explicit environments, startup validation test) |
| M-1 | **Open documentation gap** — authoritative v1.6 spec absent; Section 14 criteria used |
| M-2 | **Partially resolved** — structured audit logs; no queryable audit table/retention |
| M-3 | **Partially resolved** — request/Sentry hygiene; no metrics/alerting backend |
| M-4 | **Accepted for MVP** — measured risk acceptable; no speculative pagination added |
| M-5 | **Partially resolved** — Content-Length cap; proxy must enforce chunked limits |
| M-6 | **Accepted for MVP** — blocking upload/import work remains; no measured incident at MVP scale |
| M-7 | **Accepted operational gap** — CI still lacks Playwright/PWA/Docker |
| M-8 | **Resolved in this hardening** — counts and verdicts refreshed |
| L-1..L-4 | **Accepted** — unchanged |

## 5. Remaining risks

1. **Single-process rate limiter.** Limits are per worker. Production Compose sets `WEB_CONCURRENCY=1`; horizontal scaling requires a shared limiter (e.g. Redis) first.
2. **Public TLS unverified.** ACME/DNS must be proven on the real domain; local self-signed HTTPS is not equivalent.
3. **Docker image unverified.** Build and container startup must be exercised on a Docker-capable host.
4. **Request-size enforcement.** Only `Content-Length` is checked for general JSON; a proxy must reject streamed/chunked oversized bodies.
5. **Monitoring/audit durability.** Logs are stdout-only; no alerting, metrics, or queryable audit retention.
6. **Blocking I/O.** Large uploads/imports still occupy the worker; single-worker deployment limits concurrency impact but is not a scale solution.
7. **CI coverage.** Playwright, PWA, backup drill, and Docker are manual release checks.
8. **Specification gap.** No authoritative v1.6 specification in the repository.
9. **Backup storage.** Scripts produce local backups; encryption/off-site retention is an operator responsibility and is documented in the runbook.

## 6. Conclusion

All applicable BLOCKER/HIGH findings are resolved in code and verified locally, except the two environment-dependent verifications explicitly marked **NOT VERIFIED**: public TLS/ACME and Docker image execution. Those must be completed on the target environment before a pilot or public launch.
