# MVP1 Release Readiness

**Audit date:** 2026-10-25
**Audited commit:** `fbb9a22`
**Release-engineering commit:** `12ef88f`
**Decision owner:** Independent audit (Principal Architect / Product / Security / QA perspective)

## 1. Executive summary

The approved MVP1 is functionally complete, hardened, and now deployable in a reproducible Docker topology. Verification: backend **124 passed** locally (CI: 120 + 4 migration tests), Ruff/mypy clean, `alembic check` clean, frontend lint/type/build clean, service-worker tests **6 passed**, full Playwright **69 passed / 1 skipped**, and production PWA smoke **2 passed** both locally and in CI.

The Docker image now builds and runs in CI. CI verifies startup, migrations at the expected revision, restart persistence, fail-fast configuration, runtime `429` rate limiting, concurrent-start migration serialization, 25 critical Playwright journeys, PWA smoke, and both isolated and live backup restores. Staging and production configuration templates validate and are isolated by Compose project.

Remaining **NOT VERIFIED** items are environment-specific: real DNS/ACME/TLS and Traefik runtime, real SMTP delivery, and an actual staging/production deployment with a target-storage restore drill.

Detailed evidence: `staging-production-readiness.md`, `release-candidate-report.md`, `production-hardening-results.md`. Deployment procedures: `staging-deployment-runbook.md`, `production-deployment-runbook.md`.

## 2. Release verdicts

| Target | Verdict | Reason |
|---|---|---|
| **Local MVP Readiness** | **GO** | Approved local scope is complete; hardened suites are green. Use disposable/demo data. |
| **Staging Configuration** | **GO** | Shared Compose + staging override, preflight, isolated project/volumes/secrets, Mailpit/email redirection, and CI Docker runtime are verified. |
| **Staging Deployment** | **NOT VERIFIED** | No staging host/DNS/ACME/SMTP credentials were provided. |
| **Controlled Private Pilot** | **CONDITIONAL GO** for real user data | BLOCKER/HIGH findings are resolved. Conditions: deploy staging, prove TLS/ACME and SMTP, run a target-storage restore drill, and enable monitoring. |
| **Public Production** | **NO-GO** | Pilot gates plus durable monitoring/audit retention and proven public production TLS are still required. |

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
| M-7 | **Resolved.** CI now builds/starts Docker, runs critical Playwright and PWA, checks migrations/restart/config failure/rate limits, and performs backup/restore drills. Full E2E remains a release-workflow gate. |
| M-8 | **Resolved.** Counts, verdicts and deployment docs refreshed. |

### LOW

L-1 (real-looking email in docs), L-2 (legacy `item` table), L-3 (search wildcard semantics), and L-4 (PWA full-refresh update) remain **accepted**. None affects pilot safety; see `mvp1-security-operations-audit.md`.

## 5. Remaining conditions before pilot/public production

The code-level BLOCKER/HIGH corrections and Docker runtime gates are complete. The following require real infrastructure or credentials.

**Required before a controlled private pilot with real data:**

1. Deploy staging to a real host with DNS; verify ACME (staging CA), certificate, HTTP→HTTPS redirect and security headers.
2. Deploy production with the tested image; verify public ACME/TLS, HSTS and proxy behavior.
3. Configure SMTP and verify an actual invitation and password-recovery email to a controlled recipient.
4. Run `scripts/backup_compose.sh` against target storage and complete an isolated restore drill with target volumes.
5. Configure external readiness checks, log shipping, Sentry, backup-freshness and certificate-expiry alerts.
6. Confirm staging and production use different projects, domains, secrets and volumes on the real host.

**Required before public production, in addition:**

7. Ship JSON logs (including `audit event=...`) to durable, access-controlled storage with retention.
8. Add metrics/alerting for error rate, latency, `429` volume, DB health, disk and certificate expiry.
9. Replace the in-process limiter with a shared store before raising `WEB_CONCURRENCY` above 1.
10. Commit the authoritative MVP1 specification and reconcile docs (M-1).
11. Decide and document the scale limit for remaining unbounded collections (M-4).
12. Verify a full disaster-recovery exercise (host loss + backup restore) on the target.

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

### Automated gates (release candidate `12ef88f`; final CI run `40209730702`)

| Command | Result |
|---|---|
| `cd backend && uv run ruff check app tests` | All checks passed |
| `cd backend && uv run mypy app` | Success, 40 source files |
| `cd backend && uv run pytest -q` | **124 passed** |
| CI backend (excluding migration marker) | **120 passed**, 4 deselected |
| `cd backend && uv run pytest -q -m migrations` | **4 passed** |
| `cd backend && uv run alembic check` | No new upgrade operations detected |
| `cd frontend && bun run lint:check` | 129 files, no fixes |
| `cd frontend && bunx tsc -p tsconfig.build.json --noEmit` | Pass |
| `cd frontend && bun run build` | Pass |
| `cd frontend && node --test tests-unit/...` | **6 passed** |
| Full Playwright (local) | **69 passed**, 1 skipped (70 total) |
| CI critical Playwright | **25 passed** |
| Production PWA smoke (local + CI) | **2 passed** |
| Staging/production/CI Compose config | Valid |
| CI Docker build + startup + migrations | Pass |
| CI restart/config-failure/rate-limit/migration-race | Pass |
| CI isolated + live backup restore | Pass |
| Release workflow | See `release-candidate-report.md` |

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
- CI Docker runtime: image built, stack ready, migrations at `f0a1b2c3d4e5`, restart persistence OK, invalid config rejected, runtime `400 400 429` with `Retry-After: 900`, concurrent migrations `(1|1)`.
- CI backup/restore: isolated and live restores `ok:true` with matching counts and upload file.
- Traefik/ACME/DNS/TLS: **NOT VERIFIED** — no real domain/host tested.
- Real SMTP delivery: **NOT VERIFIED** — Mailpit sandbox only.
- Actual staging/production deployment: **NOT VERIFIED** — no hosts provided.

## 8. Final decision

**Local MVP: GO. Staging configuration: GO. Staging/production deployment: NOT VERIFIED. Controlled private pilot: CONDITIONAL GO. Public production: NO-GO.**

The application is functionally complete for approved MVP1 scope, its authorization/isolation core remains sound, and all applicable BLOCKER/HIGH findings are corrected. Docker runtime, migrations, critical journeys and backup/restore are verified in CI. The pilot remains conditional on completing the real-host gates in §5; public production additionally requires operational monitoring/audit durability and public TLS proof.
