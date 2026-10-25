# MVP1 Release Readiness

**Audit date:** 2026-10-25
**Audited commit:** `fbb9a22`
**Decision owner:** Independent audit (Principal Architect / Product / Security / QA perspective)

## 1. Executive summary

The approved **local** MVP1 is functionally complete and now hardened. Post-hardening verification: backend **112 passed**, migration tests **4 passed**, Ruff/mypy clean, `alembic check` clean, frontend lint/type/build clean, service-worker unit tests **6 passed**, full Playwright **69 passed / 1 skipped**, and production PWA smoke **2 passed**.

Confirmed authentication, session, abuse-protection, deployment-readiness, email-escaping, and backup/restore blockers are resolved and verified locally. An isolated backup/restore drill passed with matching row counts and byte-identical uploads. Two environment-dependent checks remain **NOT VERIFIED**: Docker image execution (no Docker daemon available) and public TLS/ACME/DNS (local self-signed HTTPS verified only).

Detailed evidence: `production-hardening-results.md`. Deployment procedure: `production-deployment-runbook.md`.

## 2. Release verdicts

| Target | Verdict | Reason |
|---|---|---|
| **Local MVP Readiness** | **GO** | Approved local scope is complete; hardened suites are green. Use disposable/demo data. |
| **Controlled Private Pilot** | **CONDITIONAL GO** for real user data | All applicable BLOCKER/HIGH findings are resolved and locally verified. Conditions: verify TLS/ACME on the real host, build/run the Docker image on a Docker-capable host, configure SMTP and monitoring, and run the restore drill against target storage. |
| **Public Production** | **NO-GO** | Pilot conditions plus durable monitoring/alerting, audit retention, target-environment restore verification, and public TLS proof are still required. |

## 3. Feature completeness

**COMPLETE against the tracked MVP1 acceptance criteria.** No missing or broken approved local feature was found. The original v1.6 specification is not in the repository, so exact wording-level reconciliation is not possible; this is a documentation/audit limitation, not evidence of a functional gap.

Verified workflows include:

- Super Admin global mode, gym creation, ownership transfer and multiple admins.
- Gym-scoped admin/coach/athlete separation and cross-gym isolation.
- Coach and athlete invitation/initial-password onboarding and lifecycle.
- Multi-club memberships and independent profiles/programs.
- Exercise catalog and categories with role enforcement.
- Program authoring with per-set reps/weight/intensity/rest/ duration/note.
- Draft/active/archived lifecycle, one active program, history and coach reassignment.
- Templates and independent copies.
- Athlete program view and Persian A4 print/PDF.
- Global coach/athlete pages, search, filters, server pagination, URL state and async pickers.
- PWA, RTL/LTR, Jalali/Gregorian conversion and responsive layouts.

Correctly excluded: attendance, workout logging/analytics, chat, nutrition, payments, AI generation, native apps, public hosting, real SMTP and cloud storage.

## 4. Findings summary and final dispositions

**Original: 4 BLOCKER, 4 HIGH, 8 MEDIUM, 4 LOW.** Each was reproduced before correction. Final status:

### BLOCKER

| ID | Finding (baseline) | Final disposition |
|---|---|---|
| B-1 | No login/recovery throttling or backoff. | **Resolved — verified locally.** Server-side per-IP and per-identity sliding-window limits return `429` + `Retry-After`; successful login resets the identity counter; covered by tests and a runtime probe. |
| B-2 | No backup/restore procedure or restoration test. | **Resolved — verified locally.** Scripts cover PostgreSQL + uploads + checksums; isolated drill passed with matching counts and byte-identical file. Target-storage drill remains a pilot condition. |
| B-3 | No TLS/HTTPS deployment; HTTP-only Compose. | **Partially resolved — public TLS NOT VERIFIED.** Production Compose adds Traefik, HTTP→HTTPS redirect, ACME and HSTS; HTTPS + HSTS verified locally with a self-signed certificate. Real DNS/ACME must be proven on the host. |
| B-4 | JWT in `localStorage`; no CSP/security headers; client-only logout. | **Resolved — verified locally.** HttpOnly/SameSite cookies + double-submit CSRF; Bearer retained for API clients; server logout revokes `token_version`; CSP and security headers enforced and tested; full regression green. |

### HIGH

| ID | Finding (baseline) | Final disposition |
|---|---|---|
| H-1 | Docker/Compose does not run migrations; dev services exposed. | **Partially resolved — image build NOT VERIFIED.** Container entrypoint migrates and bootstraps; production Compose has no public DB/Adminer and uses internal networks; Compose config validates. Docker daemon unavailable for build/run. |
| H-2 | Health endpoint ignores the database. | **Resolved — verified locally.** `/utils/ready/` returns `503` when the DB probe fails; liveness stays independent; covered by tests. |
| H-3 | Email templates do not escape user HTML. | **Resolved — verified locally.** Jinja2 autoescaping plus a markup regression test. |
| H-4 | `production` is not an accepted environment. | **Resolved — verified locally.** `development`/`staging`/`production`; production requires a 32+ char secret and secure cookies; insecure startup rejected in tests. |

### MEDIUM

| ID | Disposition |
|---|---|
| M-1 | **Open documentation gap.** Authoritative v1.6 spec absent; Section 14 criteria used as baseline. |
| M-2 | **Partially resolved.** Structured audit logs for privileged mutations; no queryable audit table or retention. |
| M-3 | **Partially resolved.** Request IDs/timing, Sentry PII/body disabled; no metrics/alerting backend. |
| M-4 | **Accepted for MVP.** Measured global sort ~33 ms at 50k rows; no speculative pagination added. |
| M-5 | **Partially resolved.** JSON `Content-Length` cap enforced; proxy must enforce streamed body limits. |
| M-6 | **Accepted for MVP.** Blocking upload/import work remains; no measured incident at MVP scale; single worker. |
| M-7 | **Accepted operational gap.** CI still excludes Playwright/PWA/Docker; they are manual release gates. |
| M-8 | **Resolved.** Counts, verdicts and deployment docs refreshed. |

### LOW

L-1 (real-looking email in docs), L-2 (legacy `item` table), L-3 (search wildcard semantics), and L-4 (PWA full-refresh update) remain **accepted**. None affects pilot safety; see `mvp1-security-operations-audit.md`.

## 5. Remaining conditions before pilot/public production

All code-level BLOCKER/HIGH corrections are implemented and locally verified. The following are environment or operational gates that cannot be satisfied from the development host.

**Required before a controlled private pilot with real data:**

1. **B-3:** Deploy to the target host with real DNS; confirm ACME issuance, certificate chain, HTTP→HTTPS redirect and HSTS with the commands in the runbook §5.
2. **H-1:** Build and start the Docker image on a Docker-capable host; confirm the entrypoint migrates and readiness becomes healthy.
3. Configure SMTP and verify an actual invitation and password-recovery email.
4. Run the backup/restore drill against the target storage and retain the evidence.
5. Configure an external readiness check, log collection, and a certificate-expiry alert.

**Required before public production, in addition:**

6. Ship logs (including `audit event=...`) to durable, access-controlled storage with retention.
7. Add metrics/alerting for error rate, latency, `429` volume, DB health, disk and certificate expiry.
8. Ensure the edge proxy enforces streaming/chunked body limits (M-5).
9. Add Playwright/PWA/Docker/restore checks to CI or the release checklist (M-7).
10. Commit the authoritative MVP1 specification and reconcile docs (M-1).
11. Replace the in-process limiter with a shared store before raising `WEB_CONCURRENCY` above 1.
12. Decide and document the scale limit for remaining unbounded collections (M-4).

## 6. Accepted MVP limitations

These are consistent with the approved local scope and are **not** release-blockers for the Local GO:

- Local development/manual acceptance only; no hosting, real SMTP/email provider or cloud storage in the local environment.
- Browser sessions use HttpOnly cookies; Bearer tokens remain for API clients/tests. Access tokens last 12 hours by default.
- Rate limiting is in-process and therefore per worker; the Compose default is one worker.
- Browser print-to-PDF instead of a server PDF renderer.
- Minimal PWA shell caching; no offline data synchronization.
- Permanent deletion of any program-version status and permanent athlete deletion are deliberate/approved behaviors.
- Attendance, workout-performance logging, analytics, chat, nutrition, payments, AI generation and native apps are excluded.
- Desktop and emulated mobile viewports are the approved test matrix; no physical iPhone requirement.
- Offset pagination is live, not a snapshot; concurrent mutations can shift page boundaries.
- Import default-coach picker is capped at 50 with an explicit hint; main pickers are server-searched.

## 7. Evidence appendix

### Automated gates (disposable `gym_app_hardening_test`)

| Command | Result |
|---|---|
| `cd backend && uv run ruff check app tests` | All checks passed |
| `cd backend && uv run mypy app` | Success, 39 source files |
| `cd backend && uv run pytest -q` | **112 passed** |
| `cd backend && uv run pytest -q -m migrations` | **4 passed**, 108 deselected |
| `cd backend && uv run alembic check` | No new upgrade operations detected |
| `cd frontend && bun run lint:check` | 129 files, no fixes |
| `cd frontend && bunx tsc -p tsconfig.build.json --noEmit` | Pass |
| `cd frontend && bun run build` | Pass |
| `cd frontend && node --test tests-unit/...` | **6 passed** |
| `cd frontend && bunx playwright test` | **69 passed**, 1 skipped (70 total) |
| Production PWA smoke (`PWA_PROD=1 --no-deps`) | **2 passed** |
| `docker compose -f compose.production.yml config` | Valid with required env |

### Runtime probes

- Rate limiting: bad logins → `400`, `400`, then `429 too_many_attempts` with `Retry-After: 60`.
- Production mode: `FASTAPI_ENV=production COOKIE_SECURE=true HSTS_ENABLED=true` starts and serves health/readiness `200`.
- Local HTTPS (self-signed): all security headers including `Strict-Transport-Security: max-age=31536000; includeSubDomains`; readiness `200`.
- Browser session: `gym_access_token` is HttpOnly; `gym_csrf_token` is readable; unsafe cookie requests without the header → `403 csrf_failed`.
- Logout: cookie session and the previously issued bearer token both return `401` afterward.
- Missing database: readiness → `503`; liveness → `200`.
- Email template with markup in gym/user names is escaped.
- Missing/insecure production configuration fails startup.
- Backup failure (nonexistent DB) → exit code `1`.
- Restore drill: `user=12, gym=3, athlete_profile=5, body_analysis_file=1, workout_program_version=5`, `ok:true`; restored upload byte-identical (SHA-256 `49fda3c9684ceeb3409884d600018bb303c1b9dd48ff4cb9fabb14be72784d5a`).
- Cross-gym isolation and non-superuser `403` behavior remain covered by the backend suite.
- CORS: configured frontend origin allowed; foreign origin receives no allow-origin header.
- `.env` not tracked and absent from Git history; no `.pem`/`.key` tracked.
- PWA worker production test: shell cached; no `/api/` cache entries.
- Docker image build/run: **NOT VERIFIED** — Docker daemon unavailable.
- Public ACME/DNS/TLS: **NOT VERIFIED** — no real domain tested.

## 8. Final decision

**Local MVP: GO. Controlled private pilot with real user data: CONDITIONAL GO. Public production: NO-GO.**

The application is functionally complete for approved MVP1 scope, its authorization/isolation core remains sound, and all applicable BLOCKER/HIGH findings are corrected and locally verified. The pilot remains conditional on completing the target-environment gates in §5; public production additionally requires operational monitoring/audit durability and public TLS proof.
