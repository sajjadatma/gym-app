# Production Hardening Plan

**Date:** 2026-10-25
**Base commit:** prior release audit at `fbb9a22`
**Scope:** resolve applicable release blockers/high findings without changing MVP1 product behavior.

## 1. Findings and dispositions

| ID | Finding | Disposition | Implementation / rationale |
|---|---|---|---|
| B-1 | No login/recovery abuse limits | **Confirmed — Must Fix** | Added in-process sliding-window limiter with separate per-IP and per-identity keys, `429` + `Retry-After`, generic detail, tested for login and recovery (including username rotation from one IP). |
| B-2 | No backup/restore or restore proof | **Confirmed — Must Fix** | Added `scripts/backup.sh`, `restore.sh`, `verify_restore.py`; completed an isolated drill with count and file-byte checks. |
| B-3 | No TLS/HTTPS deployment | **Confirmed — Must Fix (partial verification)** | Added production Compose with Traefik HTTP→HTTPS, ACME and HSTS config; verified HTTPS + HSTS locally with a self-signed certificate. Public ACME/DNS remains an operator verification step. |
| B-4 | `localStorage` token, no CSP/security headers, no server logout | **Confirmed — Must Fix** | Browser sessions now use HttpOnly/SameSite cookies plus double-submit CSRF; bearer remains for API clients. Added logout/revocation, CSP and security headers, and updated all browser tests. |
| H-1 | Docker/Compose does not migrate; dev services exposed | **Confirmed — Must Fix (partial verification)** | Docker entrypoint runs migrations + bootstrap; production Compose uses TLS, no DB/Adminer exposure, persistent uploads and readiness health. Compose config validates; image build not verified because Docker daemon is unavailable. |
| H-2 | Health ignores DB | **Confirmed — Must Fix** | Added `/api/v1/utils/ready/` DB probe; kept `/utils/health-check/` as liveness. Tests cover healthy and broken-session paths. |
| H-3 | Email HTML injection | **Confirmed — Must Fix** | Jinja2 environment now enables autoescaping; regression test uses markup in gym/user names. |
| H-4 | No explicit production mode | **Confirmed — Must Fix** | `FASTAPI_ENV` now accepts `development/staging/production`; production requires a 32+ char secret and secure cookies; startup verified with `FASTAPI_ENV=production`. |
| M-1 | Authoritative v1.6 spec missing | **Not applicable to code; remaining documentation gap** | No source text available. Section 14 criteria and feature specs remain the baseline. |
| M-2 | No audit log | **Partially resolved** | Structured `app.audit` logs for ownership, membership, coach/athlete lifecycle and program version changes; no queryable audit table/retention. |
| M-3 | No monitoring/PII handling | **Partially resolved** | Request ID/timing/status logs; no query/body logging; Sentry PII disabled with `max_request_body_size="never"`. Metrics/alerting remain external. |
| M-4 | Unbounded collections | **Confirmed — Acceptable Risk for MVP** | Measured global sort ~33 ms for 50k rows; remaining small collections left unchanged rather than adding speculative pagination. |
| M-5 | No JSON request-size cap | **Partially resolved** | Content-Length cap for JSON requests; import route keeps its bounded 5 MB read; reverse proxy must enforce streaming/chunked limits. |
| M-6 | Blocking work in async routes | **Confirmed — Acceptable Risk for MVP** | Existing upload/import paths remain synchronous; no measured incident at MVP scale. |
| M-7 | CI excludes Playwright/PWA/Docker | **Accepted operational gap** | Local full suites run and are documented; CI remains lint/type/backend-build oriented. |
| M-8 | Documentation drift | **Resolved in this hardening** | Reports and progress counts updated; runbook added. |
| L-1 | Real-looking Super Admin email in docs | **Accepted** | No password exposed; local bootstrap requires a real owner identity. |
| L-2 | Unused legacy `item` table | **Accepted** | No behavior dependency; avoid unrelated migration. |
| L-3 | Search wildcard semantics | **Accepted** | Not injection; parameterized query. |
| L-4 | PWA full-refresh update | **Accepted** | Minimal PWA scope; build-scoped cache tests pass. |

## 2. Stages and dependencies

1. **Session/auth foundation**
   - Config fields, cookie helpers, CSRF verification, login/logout routes, frontend credential handling, route guards.
   - Depends on B-4; must land before browser tests are updated.
2. **Abuse protection**
   - Limiter module, login/recovery/reset/invitation integration, tests.
   - Depends on the auth routes.
3. **HTTP hardening and readiness**
   - Security headers/CSP, request-size cap, request logs, Sentry PII setting, DB-aware readiness.
   - Independent; required before deployment checks.
4. **Email safety and audit visibility**
   - Autoescaping and structured audit logs.
   - Independent.
5. **Deployment and recovery**
   - Container entrypoint, production Compose, backup/restore scripts, restore drill.
   - Depends on migrations and readiness.
6. **Verification and documentation**
   - Full backend/frontend/Playwright/PWA runs, local HTTPS/production-config checks, runbook and reports.
   - Depends on all preceding stages.

## 3. Architecture decisions

- Keep FastAPI + SQLModel + PostgreSQL + React/Vite/TanStack Query.
- Keep bearer-token support for API clients and tests; use HttpOnly cookies for browser sessions.
- Use CSRF double-submit (`gym_csrf_token` + `X-CSRF-Token`) for cookie-authenticated unsafe requests.
- Use an in-process limiter with `WEB_CONCURRENCY=1` for the MVP; document the shared-limiter requirement before horizontal scaling.
- Use host-run `pg_dump`/`pg_restore` and tar for uploads; no backup service or cloud dependency.
- Use Traefik/ACME in a production Compose template; do not claim a public certificate until verified on the target host.

## 4. Acceptance criteria

- Login/recovery throttling returns `429` with `Retry-After`; successful login resets the per-identity counter.
- Login sets HttpOnly/SameSite cookies and a readable CSRF cookie; cookie mutations require the CSRF header.
- Logout revokes the token generation and clears cookies; old bearer/cookie tokens fail with `401`.
- Security headers are present on runtime responses; HTTPS/HSTS is verified locally and configured for production.
- `FASTAPI_ENV=production` starts with secure cookies and rejects missing insecure configuration.
- `/utils/ready/` returns `503` when the DB is unavailable; liveness remains independent.
- Backup produces a verified dump, uploads archive and checksums; restore into an isolated DB passes count and file-byte checks; backup failure exits non-zero.
- Oversized JSON gets `413`; import uploads keep the existing bounded `400` contract.
- Email markup is escaped; audit events contain IDs, not PII.
- Backend tests, migration tests, frontend lint/type/build, Playwright, PWA smoke and Compose config checks pass.

## 5. Remaining external work

- Verify ACME/DNS/TLS on the real public host; local self-signed HTTPS is not a production certificate test.
- Build and run the Docker image on a machine with Docker available; only Compose interpolation was verified here.
- Choose and configure monitoring/alerting and durable audit-log storage.
- Add Playwright/PWA/Docker checks to CI if the project wants a single automated release gate.
- Run the documented backup/restore drill against the real target storage before relying on it for real data.
