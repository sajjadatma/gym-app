# MVP1 Security and Operations Audit

**Audit date:** 2026-10-25
**Audited commit:** `fbb9a22`
**Scope:** Authentication, authorization, tenant isolation, data integrity, deployment and recovery.

## 1. Executive security posture

The API-level authorization model is materially stronger than a typical MVP:

- Gym-scoped endpoints require an explicit active `X-Gym-ID` and an active membership.
- Coach access is derived from the current `CoachAssignment`; ended assignments lose access immediately.
- Cross-gym read/mutation probes returned `404`, and non-superusers received `403` on global endpoints.
- Superuser endpoints require `CurrentSuperuser` independently of the UI.
- File downloads are permission-checked and stored outside static serving; magic bytes, MIME/extension and a 10 MB cap are enforced.
- Access and reset tokens carry a per-user `token_version`; password changes/resets invalidate old tokens and reset links.
- One active program per athlete/gym and one current coach assignment are enforced by partial unique indexes.
- Invitations and reset links are purpose-bound JWTs; reset replay is tested, including concurrent redemption.
- No `dangerouslySetInnerHTML`, raw `innerHTML`, `eval` or equivalent sink was found in application source.

However, the deployment/security envelope is not ready for networked real-user use: there is no abuse throttling, no HTTPS, no backup/restore proof, no CSP/security headers, and the browser token is stored in `localStorage`.

## 2. Findings

### BLOCKER

| ID | Category | Evidence | Impact | Minimal remediation | Blocks |
|---|---|---|---|---|---|
| **B-1** | Authentication abuse | `backend/app/api/routes/login.py:36-71`; no limiter/middleware in `backend/app/main.py`. Runtime: 12 consecutive bad logins all returned `400`; 6 password-recovery requests all returned `200`; no `429` or `Retry-After`. | Unlimited credential guessing, password spraying, account lockout avoidance, email bombing, and recovery-email abuse. | Add IP + account/email rate limits and lockout/backoff for login, reset and invitation endpoints. Keep generic responses and test `429`/backoff behavior. | Private pilot with real users; public production |
| **B-2** | Recovery / data loss | No `pg_dump`/`pg_restore` or upload-directory backup/restore procedure in `README.md`, `backend/scripts` or `docs/`; HARD-05 is explicitly deferred in `docs/technical-hardening-audit.md:205,282`. No restoration test. | A database volume loss or bad migration permanently destroys gyms, programs, files, and history. The reset script is destructive by design and is not a backup. | Document and test a full backup/restore runbook for PostgreSQL **and** `BODY_ANALYSIS_DIR`, on a disposable database, including verification of row counts and downloaded file bytes. | Private pilot with real data; public production |
| **B-3** | Transport security | `compose.yml` Traefik exposes only an HTTP entrypoint; no TLS/ACME configuration. Runtime response has no `Strict-Transport-Security`. README targets localhost only. | Bearer tokens, passwords and athlete data travel in clear text if the app is exposed beyond localhost. | Terminate TLS at a reviewed reverse proxy or add Traefik TLS/ACME with HSTS; redirect HTTP to HTTPS; restrict admin/database ports. | Private pilot over a network; public production |
| **B-4** | Session/XSS hardening | `frontend/src/auth.tsx:54,172,179` stores the JWT in `localStorage`; `logout` only clears local state. `backend/app/main.py` adds no security headers. Runtime `/` response lacks `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` and HSTS. | Any XSS or malicious extension can exfiltrate a long-lived bearer token; clickjacking and referrer leakage are unmitigated. Server-side logout/revocation is absent. | Prefer HttpOnly/Secure/SameSite cookies with CSRF protection, or add a strict CSP plus a token-storage/threat-model review. Add security headers and a logout/revocation strategy. | Public production; private pilot if browser threat model includes untrusted content |

### HIGH

| ID | Category | Evidence | Impact | Minimal remediation | Blocks |
|---|---|---|---|---|---|
| **H-1** | Deployment reproducibility | `backend/Dockerfile:65` runs `fastapi run`; `backend/scripts/prestart.sh` (migrations + initial data) is not referenced by the Dockerfile or Compose. `compose.override.yml:20-24,41-46,66` enables dev mode, insecure Traefik API, Adminer and host DB ports. | A fresh Compose deployment starts without schema; the app fails at first DB request. The override exposes administrative surfaces and uses non-production settings. | Add a migration/bootstrap entrypoint (or a documented deploy job) before the app starts; separate production Compose; remove Adminer/DB exposure and insecure Traefik from production. | Production; any Compose-based pilot |
| **H-2** | Health/readiness | `backend/app/api/routes/utils.py:7-8` returns `True` without touching the DB. Runtime with `DATABASE_URL` pointing at a missing database: health returned `200`, while login returned `500`. | Orchestrators and operators see “healthy” during a database outage; failures are discovered by users. | Split liveness from readiness; readiness must execute `SELECT 1`, report dependency status, and return non-200 on failure. | Pilot; production |
| **H-3** | Output injection | `backend/app/utils.py:34-38` renders Jinja2 templates with a plain `Template` (autoescape off). `gym_name` and `full_name` are interpolated into HTML emails. Probe with `<img src=x onerror="alert(1)">` preserved raw markup (`raw_gym_markup_present=True`). | A gym admin/owner can inject HTML into invitation/reset emails, enabling phishing or spoofed content. | Enable autoescaping for HTML email templates and escape all interpolated values; add a regression test with markup in gym/user names. | Pilot/production |
| **H-4** | Production configuration | `backend/app/core/config.py:28` restricts `FASTAPI_ENV` to `"development"` or `None`. Runtime `FASTAPI_ENV=production` raises a Pydantic `literal_error`. | There is no supported explicit production mode; operators must run with an ambiguous unset value, and configuration checks/Sentry behavior are unclear. | Allow and validate an explicit `production` environment; document required production values and test startup with production settings. | Production; pilot if environment-specific config is used |

### MEDIUM

| ID | Category | Evidence | Impact | Minimal remediation |
|---|---|---|---|---|
| **M-1** | Audit baseline | Original MVP1 v1.6 document is absent; only `README.md`, `docs/implementation-progress.md` and feature specs exist. | Requirements cannot be reconciled to the authoritative wording; future changes can silently diverge from approved scope. | Commit the approved v1.6 specification (or a dated immutable copy) and mark feature specs approved/final. |
| **M-2** | Auditability | No audit-log model/table; role, membership, archive/restore/delete and ownership changes are not recorded with actor/time. | Disputes and destructive incidents cannot be reconstructed; admin actions are not accountable. | Add a minimal append-only audit log for privileged mutations, with actor, gym, target and outcome. |
| **M-3** | Monitoring/failure visibility | `logging.basicConfig(level=INFO)`; Sentry is optional and has no explicit PII/body scrubbing config. No metrics, request IDs or alerting. | Production failures, 500 spikes and DB outages are not visible to operators; optional Sentry may capture sensitive request data. | Add structured logs with request IDs, error-rate/latency metrics, alerting and Sentry PII/body scrubbing. |
| **M-4** | Unbounded collections | `exercises.py::list_exercises`, `templates.py::list_templates`, `gyms.py::list_gyms`, `list_body_files` return full collections. Global athlete/coach lists still sort the full joined set; 50k-row measurement was ~33 ms. | Exercise/template/gym lists can grow unbounded; global sorting degrades with scale; memory/response size grows. | Add pagination to remaining collections; keep measuring the global sort; document the accepted MVP limit. |
| **M-5** | Request-size limits | Uploads are bounded (5 MB import, 10 MB body file), but no global JSON body limit exists for program/template payloads. | An authenticated staff account can send very large day/set arrays and consume memory/CPU. | Add a reverse-proxy/server body-size cap and a reasonable schema/depth limit for program structures. |
| **M-6** | Blocking work in async routes | Async upload/import endpoints call synchronous `Path.write_bytes`, CSV/XLSX parsing and DB work; `upload_body_file` and import handlers are `async`. | Concurrent uploads/imports block the event loop and degrade all requests. | Move CPU/file work to a threadpool or make the route synchronous; add a small concurrency test. |
| **M-7** | CI gate coverage | `.github/workflows/ci.yml` intentionally excludes Playwright/PWA and Docker image build. | Green CI does not prove the browser journeys, PWA behavior or deployable image; regressions can merge. | Add a scheduled/required Playwright job with disposable data, PWA production smoke, and a Docker build/start smoke. |
| **M-8** | Documentation drift | `docs/implementation-progress.md` still reports old counts (93 backend / 67 Playwright) versus this audit’s 102 / 69; `README.md` says no public CI while `.github/workflows/ci.yml` exists; feature specs still say “awaiting approval”. | Operators and reviewers cannot trust the runbook/verification record. | Refresh counts and statuses; mark approved specs final; make docs part of the release checklist. |

### LOW

| ID | Category | Evidence | Impact |
|---|---|---|---|
| **L-1** | Privacy in tracked files | Real-looking Super Admin email appears in `.env.example`, `README.md` and `docs/local-testing.md`. | Minor personal-data exposure in a public repository; no password is exposed. |
| **L-2** | Dead schema | `item` table and legacy item migrations remain although the MVP no longer uses items. | Confusing schema surface and backup noise. |
| **L-3** | Search semantics | Search terms are interpolated into `ILIKE '%term%'` without escaping `%`/`_`. | A search for `%` matches everything; not an injection, but surprising behavior. |
| **L-4** | PWA update UX | Service worker updates require a full refresh; no in-app update prompt. | Users may keep an older shell until refresh; accepted for the minimal PWA scope. |

## 3. Security evidence that passed

| Control | Evidence |
|---|---|
| Authentication | Login, invitation activation, password reset, first-login password change and token revocation tests pass (`test_auth_onboarding.py`, `test_token_invalidation.py`). |
| Authorization | Non-superuser global endpoints returned `403`; cross-gym athlete read returned `404`; coach access is assignment-derived. |
| Tenant isolation | `test_gym_isolation.py` and lifecycle/privacy suites pass; runtime probes confirm cross-gym denial. |
| Data integrity | One active version and one current assignment enforced by partial unique indexes; concurrent version/reset tests pass. |
| File upload/download | Magic-byte/MIME/size validation, private storage, permission-checked download, cross-gym denial and rollback cleanup tests pass. |
| Secrets | `.env` is tracked? **No** (`git ls-files .env` empty); no `.pem`/`.key` tracked; no `.env` in Git history. |
| CORS | Only the configured frontend origin is allowed; a foreign origin received no `Access-Control-Allow-Origin`. |
| HTML sinks | No `dangerouslySetInnerHTML`, `innerHTML`, `eval` or equivalent in application source; React escapes rendered data. |
| PWA privacy | Production worker test confirms the shell cache is used and no `/api/` URLs are cached. |

## 4. Operational readiness

| Area | Local demo | Private pilot (real data) | Public production |
|---|---|---|---|
| Functional workflows | Ready | Ready after security/ops blockers | Not ready |
| TLS | localhost only | Required | Required |
| Database migrations | Manual Alembic commands documented and CI-tested | Automation + rollback runbook required | Required |
| Backups/restore | Not needed for disposable demo | **Blocker** | **Blocker** |
| Login/recovery throttling | Not needed for localhost | **Blocker** | **Blocker** |
| CSP/security headers/session storage | Accepted local risk | Required or formal risk acceptance | **Blocker** |
| Health/readiness | Constant health check acceptable locally | DB-aware readiness required | Required |
| Monitoring/alerting | Not required | Required for real users | Required |
| Audit logging | Not required | Recommended | Required |
| Secrets/HTTPS/ports | Local `.env`, localhost | Review required | Required |

## 5. Security assessment

**CONDITIONAL for local/demo use; FAIL for public production.**

The core tenant and role authorization is sound and independently exercised. The application is not safe to expose to real users or an untrusted network until the four blockers and the deployment/health/configuration highs are resolved.
