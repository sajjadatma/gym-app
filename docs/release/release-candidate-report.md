# Release Candidate Report

**Date:** 2026-10-25
**Candidate source commit:** `12ef88fc805263966f32557b528d6b8ecfbf7a8c`
**Release workflow:** [run 40209148181](https://github.com/sajjadatma/gym-app/actions/runs/40209148181) — success
**Image:** built and tested in CI as `ghcr.io/sajjadatma/gym-app:12ef88fc…`; **not pushed** (`push_image=false`). No production deployment was performed.
**Documentation commit:** follows the candidate as a docs-only change; the tested code is unchanged.

## 1. Candidate contents

- Shared deployment stack + isolated staging/production/CI overrides.
- Environment templates and preflight validation.
- Advisory-lock migration/bootstrap.
- Trusted-proxy client-IP hardening and Traefik body cap.
- JSON logging, Sentry environment, staging email redirection.
- Compose backup/restore/freshness tooling and systemd examples.
- Expanded CI and a release workflow that tests one image before optional publication.

## 2. Test results

| Gate | Result |
|---|---|
| Backend unit/API suite (local) | **124 passed** |
| Backend CI (excluding migration marker) | **120 passed**, 4 deselected |
| Migration smoke tests | **4 passed** |
| Ruff | Clean |
| Mypy | Clean, 40 source files |
| `alembic check` | No new upgrade operations |
| Frontend Biome | Clean, 129 files |
| TypeScript | Pass |
| Production frontend build | Pass |
| Service-worker unit tests | **6 passed** |
| Full Playwright (release workflow) | **69 passed, 1 skipped** |
| Critical Playwright (CI) | **25 passed** |
| Production PWA smoke | **2 passed** |
| Staging/production/CI Compose config | Valid |
| Preflight positive/negative | Pass / rejected |
| Fresh bootstrap | Migrated + seeded at `f0a1b2c3d4e5` |
| Backup freshness | Fresh OK; stale rejected |

## 3. Security verification

- Cookie session: `gym_access_token` HttpOnly/SameSite/Secure in deployment; readable CSRF cookie; unsafe cookie requests require `X-CSRF-Token`.
- Logout revokes the token generation; prior bearer and cookie tokens return `401`.
- Rate limiting: runtime CI probe returned `400, 400, 429` with `Retry-After: 900`; per-IP and per-identity limits.
- Proxy IP: rightmost `X-Forwarded-For` only, IP-validated; spoofed prefixes and malformed values fall back to the peer.
- Origin validation on login/recovery/reset/invitation.
- Security headers/CSP/HSTS verified locally and in CI application responses; Traefik TLS runtime remains operator-verified.
- Request body: 12 MiB Traefik buffer cap plus app-level JSON `Content-Length` cap.
- Email templates autoescape; staging redirects all delivery; production rejects redirection.
- Invalid production configuration is rejected before startup.
- Secrets are not committed; deployment env files are git-ignored.

## 4. Docker verification

- Image built from `backend/Dockerfile` in CI.
- Container started with PostgreSQL and Mailpit; readiness `200`.
- Migrations applied at `f0a1b2c3d4e5`.
- Restart preserved database rows and uploaded files.
- Short/insecure secret prevented startup.
- Two concurrent containers against a fresh DB converged to one `alembic_version` row; both became ready.
- Traefik container and ACME were **not** started; proxy/TLS runtime is **NOT VERIFIED**.

## 5. Staging verification

| Item | Status |
|---|---|
| Configuration, isolation, preflight | **VERIFIED** |
| Docker runtime used by staging (app + DB) | **VERIFIED IN CI** |
| Actual staging host/DNS/ACME/Traefik | **NOT VERIFIED** |
| Staging SMTP sandbox | **NOT VERIFIED** (Mailpit only) |
| Target-storage restore | **NOT VERIFIED** |

## 6. Production verification

| Item | Status |
|---|---|
| Production config validation | **VERIFIED** |
| Production image/test suite | **VERIFIED IN CI** |
| Public TLS/ACME/HSTS under Traefik | **NOT VERIFIED** |
| Real SMTP delivery | **NOT VERIFIED** |
| Production host deployment | **NOT VERIFIED** |
| Production backup destination/restore | **NOT VERIFIED** |
| Monitoring/alerting/durable audit | **NOT VERIFIED** |

## 7. Remaining blockers

No code-level release blocker remains for a controlled pilot. The following are **operator/external gates**, not repository defects:

1. Staging and production hosts, DNS, firewall 80/443.
2. Real ACME/TLS/HTTP redirect verification on both domains.
3. SMTP provider credentials and delivery test.
4. Encrypted off-host backup storage and a target restore drill.
5. External readiness, Sentry, log shipping, backup-freshness, disk and certificate alerts.
6. Confirmation that staging and production projects/volumes/secrets are distinct on the target host.
7. Public-production decision on durable audit retention and monitoring.

## 8. Exact operator actions

1. Copy `.env.staging.example` → `.env.staging`, replace placeholders, run `preflight_env.py`.
2. Point staging DNS at the host, then `CONFIRM_DEPLOY=staging bash scripts/deploy_stack.sh staging`.
3. Verify staging HTTPS, ACME staging cert, readiness, login, email redirection, and backup/restore.
4. Copy `.env.production.example` → `.env.production`; set the tested image digest in `BACKEND_IMAGE`.
5. Run the release workflow with `push_image=true` (or tag `v*`) to publish the tested image.
6. On production, log in to GHCR, run `CONFIRM_DEPLOY=production NO_BUILD=1 bash scripts/deploy_stack.sh production`.
7. Run the post-deploy smoke script, a target backup, and an isolated restore drill.
8. Enable external monitoring, log shipping and backup/certificate alerts.
9. Record the image digest, deployment time, restore evidence and alert checks.

## 9. Verdict

**Release candidate: PASS for staging configuration and Docker runtime; production deployment NOT VERIFIED.**

- Local: **GO**
- Staging configuration: **GO**
- Staging deployment: **NOT VERIFIED**
- Production configuration: **GO**
- Production deployment: **NOT VERIFIED**
- Private pilot: **CONDITIONAL GO**
- Public production: **NO-GO**
