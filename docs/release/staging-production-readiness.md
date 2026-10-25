# Staging & Production Readiness

**Date:** 2026-10-25
**Release candidate commit:** `12ef88fc805263966f32557b528d6b8ecfbf7a8c`
**CI evidence:** [CI run 40209730702](https://github.com/sajjadatma/gym-app/actions/runs/40209730702) and [release run 40209148181](https://github.com/sajjadatma/gym-app/actions/runs/40209148181) — both success
**Scope:** deployment/security/release engineering only; MVP1 remains feature-frozen.

## 1. Environment architecture

| | Local | CI | Staging | Production |
|---|---|---|---|---|
| Purpose | development | disposable runtime gate | production mirror | real users |
| App env | `development` | `development` | `staging` | `production` |
| Compose | `compose.yml` | `compose.deploy.yml` + `compose.ci.yml` | `compose.deploy.yml` + `compose.staging.yml` | `compose.deploy.yml` + `compose.production.yml` |
| Project | local | `gym-ci` | `gym-staging` | `gym-production` |
| Traffic | localhost | direct `:8000` | Traefik + LE **staging** CA | Traefik + LE production CA |
| Data | disposable | seeded demo | fake/test only | real |
| Email | Mailpit | Mailpit | redirected sandbox | real SMTP |
| HSTS | off | off | off (untrusted CA) | on |

Staging and production are isolated by Compose project name, networks, named volumes, database password, `SECRET_KEY`, domain, sessions and email behavior. The database is never published. `scripts/preflight_env.py` rejects project/domain/secret reuse, production ACME use in staging, staging CA use in production, HSTS mismatches, placeholder values, email redirection in production, missing staging redirection, and `WEB_CONCURRENCY > 1`.

## 2. Completed implementation

- Shared `compose.deploy.yml` plus small staging/production/CI overrides.
- `.env.staging.example` and `.env.production.example`; hidden env files remain git-ignored.
- Traefik HTTP→HTTPS redirect, ACME directory per environment, JSON access logs, 12 MiB request-body buffer cap, and no public DB/Adminer.
- PostgreSQL advisory-lock bootstrap: migrations + initial data serialize across concurrent containers.
- Fail-fast configuration validation in the container entrypoint.
- Trusted-proxy client-IP hardening: only the rightmost `X-Forwarded-For` value is used, validated as an IP; malformed/missing headers fall back to the socket peer.
- Structured JSON application logs (`LOG_JSON=true` in staging/production) with request IDs and audit fields; text logs remain readable in development.
- Sentry environment tagging; PII and request bodies remain disabled.
- Staging email redirection enforced at config load; production rejects redirection.
- Compose backup script (DB + uploads + counts + checksums + freshness marker + retention + optional rclone offsite).
- Compose restore script with explicit confirmation, checksum verification, DB + uploads restore, and post-restore count/file verification.
- systemd backup service/timer examples and a backup-freshness check.
- Deployment preflight, deploy wrapper, and post-deploy smoke script.
- CI Docker gate: image build, startup, migrations, restart persistence, config-failure rejection, runtime 429, concurrent migration convergence, 25 critical Playwright journeys, PWA smoke, isolated restore, and live restore.
- Release workflow: builds one image, runs the full suite against it, and can publish that same image to GHCR for promotion by digest.

## 3. Readiness checklist

| Gate | Status |
|---|---|
| Staging environment template + validation | **READY** |
| Production environment template + validation | **READY** |
| Compose config renders for staging/production/CI | **VERIFIED** |
| Docker image builds | **VERIFIED IN CI** |
| Container starts and reaches readiness | **VERIFIED IN CI** |
| Migration/bootstrap at expected revision | **VERIFIED IN CI** (`f0a1b2c3d4e5`) |
| Concurrent startup migration race | **VERIFIED IN CI** (single `alembic_version`, both instances ready) |
| Invalid production config fails fast | **VERIFIED IN CI** |
| Restart preserves DB + uploads | **VERIFIED IN CI** |
| Runtime rate limiting | **VERIFIED IN CI** (`400, 400, 429`, `Retry-After: 900`) |
| Critical user journeys | **VERIFIED IN CI** (25 passed) |
| Full MVP1 regression | **VERIFIED LOCALLY** (69 passed, 1 skipped) |
| Production PWA smoke | **VERIFIED IN CI** (2 passed) |
| Isolated backup/restore | **VERIFIED IN CI** (counts + file match) |
| Live Compose restore/recovery | **VERIFIED IN CI** (corrupted row reverted; counts + file pass) |
| Secrets not committed | **VERIFIED** (templates only; `.env.*` ignored) |
| Staging cannot reach production | **CONFIGURED** by project-scoped networks/volumes/credentials; not tested on a shared host |
| Traefik/ACME/TLS runtime | **NOT VERIFIED** — requires a real domain/host |
| SMTP delivery | **NOT VERIFIED** — Mailpit exercised; no real provider credentials |
| Actual staging deployment | **NOT VERIFIED** — no staging host/DNS provided |
| Actual production deployment | **NOT VERIFIED** — no production host/DNS provided |

## 4. Verification evidence

### CI run `40209730702` and release run `40209148181`

- `backend`: Ruff clean; **120 passed**, 4 migration tests deselected by the marker filter; migration smoke **4 passed**.
- `frontend`: Biome clean, TypeScript pass, production build pass.
- `docker-e2e`:
  - image built from `backend/Dockerfile`;
  - stack ready; migrations at `f0a1b2c3d4e5`;
  - insecure config rejected;
  - restart persistence OK;
  - runtime rate limit `400 400 429`, `retry-after: 900`;
  - concurrent startup OK `(1|1)`;
  - critical Playwright **25 passed**;
  - PWA **2 passed**;
  - isolated restore `{"user":10,"gym":3,"athlete_profile":4,"body_analysis_file":1,"workout_program_version":4}`, `ok:true`;
  - live restore `ok:true`, gym row reverted, readiness `200`;
  - `drill: PASS`.

### Local release verification

| Check | Result |
|---|---|
| `uv run ruff check app tests` | All checks passed |
| `uv run mypy app` | Success, 40 source files |
| `uv run pytest -q` | **124 passed** |
| `uv run pytest -q -m migrations` | **4 passed** |
| `alembic check` | No new upgrade operations |
| `bun run lint:check` | 129 files, clean |
| `bunx tsc -p tsconfig.build.json --noEmit` | Pass |
| `bun run build` | Pass |
| service-worker unit tests | **6 passed** |
| Full Playwright | **69 passed, 1 skipped** |
| Compose config (staging/production/CI) | Valid |
| Preflight positive/negative cases | Pass / rejected as expected |
| Fresh bootstrap (advisory lock path) | Migrated + seeded, revision `f0a1b2c3d4e5` |
| Backup freshness check | Fresh OK; stale rejected |

## 5. Remaining external dependencies

1. Staging and production hosts with Docker Engine + Compose v2.
2. Two DNS names with `A`/`AAAA` records and ports 80/443 reachable.
3. Real ACME issuance on each host (staging CA for staging, production CA for production).
4. SMTP provider/credentials and a controlled recipient for delivery verification.
5. Sentry DSN (recommended) and a durable log store for audit retention.
6. Encrypted off-host backup destination (object storage or another host); `rclone` optional.
7. A restore drill against the target backup storage and real volumes.
8. External readiness, certificate-expiry, disk, backup-freshness and error alerts.
9. GHCR access if the release workflow's image is used for promotion.
10. Authoritative MVP1 v1.6 specification (documentation gap, not deployment).

## 6. Known limitations

- Rate limiting is in-process; `WEB_CONCURRENCY` must remain `1` until a shared limiter exists.
- Client-IP handling assumes a single trusted proxy (Traefik); adding a CDN requires revisiting the rightmost-XFF logic.
- CI verifies the app image with PostgreSQL and Mailpit but does not start Traefik/ACME; proxy/TLS remains operator-verified.
- No HA, read replica, point-in-time recovery or blue/green deployment. Backup restore is the recovery mechanism.
- Proposed RPO ≤24h and RTO ≤4h are targets, not guarantees.
- Audit events are durable only if stdout logs are shipped to a durable store.
- Large uploads/imports still perform blocking work; acceptable at single-worker MVP scale.
- The application body cap uses `Content-Length`; Traefik's 12 MiB buffer enforces the effective network limit.
- CI uses the Let's Encrypt staging CA value only for config rendering; it does not issue certificates.
- Mailpit proves invitation/recovery code paths, not real SMTP deliverability.
- Docker was unavailable on the development host; runtime evidence is CI-only.

## 7. Verdicts

| Target | Verdict |
|---|---|
| **Staging configuration** | **READY** |
| **Staging deployment** | **NOT VERIFIED** — no target host/DNS |
| **Production configuration** | **READY** |
| **Production deployment** | **NOT VERIFIED** — no target host/DNS/certificate/SMTP/restore drill |
| **Docker runtime (app + DB)** | **VERIFIED IN CI** |
| **Traefik/TLS/ACME runtime** | **NOT VERIFIED** |
| **Private pilot** | **CONDITIONAL GO** after the operator gates above |
| **Public production** | **NO-GO** until staging and production gates are actually verified |
