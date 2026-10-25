# Production Deployment Runbook

**Applies to:** Gym Management MVP1
**Deployment model:** one Linux host, Docker Compose, Traefik + Let's Encrypt
**Status:** configuration and CI runtime verified; the live production host, DNS, certificate issuance, SMTP delivery and target-storage restore are operator-gated. Do not treat this document as proof of a live deployment.

## 1. Topology

```
Internet :80/:443
        │
   Traefik (TLS, HTTP→HTTPS, ACME, 12 MiB body cap)
        │  edge network
   backend (FastAPI + built frontend, migrations, readiness)
        │  internal network (no published ports)
   PostgreSQL
```

- Uploads: `gym-production_uploads` volume at `/app/backend/uploads`.
- Database: `gym-production_app-db-data` volume.
- Certificates: `gym-production_letsencrypt` volume.
- Only Traefik publishes ports. The DB and backend are not reachable from the internet.
- `WEB_CONCURRENCY=1` because the rate limiter is in-process. Do not raise it without a shared limiter.

## 2. Prerequisites

| Requirement | Detail |
|---|---|
| Host | Linux + Docker Engine + Compose v2 |
| DNS | `A`/`AAAA` for `DOMAIN` points at the host before first start |
| Ports | 80 and 443 reachable; 80 is required for ACME |
| Disk | DB + uploads + at least 2× backup retention |
| Registry | GHCR login if pulling the tested release image |
| SMTP | A production provider if invitations/recovery are required |
| Monitoring | External HTTPS probe, log shipping, Sentry DSN, certificate-expiry alert |

## 3. Secrets and environment

```sh
cp .env.production.example .env.production
chmod 600 .env.production
```

Required values:

| Variable | Requirement |
|---|---|
| `COMPOSE_PROJECT_NAME` | Exactly `gym-production` (preflight enforces) |
| `DOMAIN` | Bare public hostname |
| `ACME_EMAIL` | Let's Encrypt contact |
| `ACME_CA_SERVER` | Production directory (staging is rejected) |
| `POSTGRES_PASSWORD` | Unique, 16+ chars, not reused |
| `SECRET_KEY` | Unique, 32+ chars; rotation invalidates all sessions/reset links |
| `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD` | Unique strong bootstrap credentials |
| `BACKEND_IMAGE` | Immutable release tag or digest |
| `HSTS_ENABLED` | `true` |
| `SENTRY_ENVIRONMENT` | `production` |
| `EMAIL_REDIRECT_TO` | Empty (startup rejects redirection) |
| `SMTP_*`, `EMAILS_FROM_*` | Required for real email delivery |
| `SENTRY_DSN` | Recommended |

Generate secrets with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.

Never commit `.env.production`. Keep a root-readable copy for systemd backup jobs. Rotate `SECRET_KEY` only with the knowledge that it logs every user out and invalidates outstanding invitations/resets.

Validate:

```sh
python3 scripts/preflight_env.py --env-file .env.production --environment production \
  --other-env-file .env.staging
```

## 4. Release and image promotion

1. Run the **Release candidate** workflow on the release commit or `v*` tag. It builds one image, runs the full Playwright suite, PWA smoke, migration-race checks, config-failure checks, and backup/restore drill, then publishes the same tested image to GHCR when requested.
2. Record the image digest from the workflow summary.
3. Put that immutable reference in `.env.production`:

```sh
BACKEND_IMAGE=ghcr.io/<owner>/<repo>@sha256:<digest>
```

4. Log in on the host if the package is private:

```sh
echo "$GHCR_TOKEN" | docker login ghcr.io -u <user> --password-stdin
```

Deploy the already-tested image **without rebuilding**:

```sh
CONFIRM_DEPLOY=production NO_BUILD=1 bash scripts/deploy_stack.sh production
```

For staging, use `CONFIRM_DEPLOY=staging`; never reuse the production env file.

## 5. Database and migrations

The backend entrypoint:

1. validates configuration and fails fast on invalid secrets/cookies;
2. waits for PostgreSQL;
3. takes a PostgreSQL advisory lock;
4. runs `alembic upgrade head`;
5. runs the idempotent superuser/bootstrap seed;
6. releases the lock and starts the API.

Concurrent containers serialize on the lock, so only one migrates. A migration failure exits the container and prevents the incompatible version from serving.

Pre-deploy check:

```sh
docker compose --env-file .env.production \
  -f compose.deploy.yml -f compose.production.yml run --rm backend alembic check
```

Migrations are forward-only. If a release is destructive or incompatible, take and verify a backup first; roll back by restoring the backup and deploying the matching previous image. Never run an automatic schema downgrade against real data.

## 6. First deployment

```sh
CONFIRM_DEPLOY=production bash scripts/deploy_stack.sh production
```

`scripts/deploy_stack.sh` runs preflight, renders Compose, starts the stack, and runs smoke checks. Wait for the backend healthcheck before continuing.

## 7. Post-deploy verification

Automated:

```sh
REQUIRE_HSTS=true CHECK_HTTP_REDIRECT=1 \
  SMOKE_EMAIL="$FIRST_SUPERUSER" SMOKE_PASSWORD="$FIRST_SUPERUSER_PASSWORD" \
  bash scripts/smoke_stack.sh https://gym.example.com
```

Manual/operator checks:

```sh
# HTTP must redirect
curl -sS -o /dev/null -D - http://gym.example.com/ | head -n 5

# Certificate chain and expiry
openssl s_client -connect gym.example.com:443 -servername gym.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# Database must not be reachable
nc -zv gym.example.com 5432   # must fail
```

Then verify in the UI:

- Login, logout, reload, and session expiry behavior.
- CSRF: remove `X-CSRF-Token` from a cookie-authenticated mutation → `403`.
- Rate limiting: repeated failed logins → `429` + `Retry-After`.
- Super Admin, gym admin, coach and athlete journeys.
- Cross-gym isolation with two clubs.
- Invitation and password-recovery delivery to a controlled recipient.
- Body-analysis upload and download.
- PWA install/refresh.

## 8. Backups

Run on the host with the stack running:

```sh
DEPLOY_ENV=production ENV_FILE=.env.production \
  BACKUP_DIR=/var/backups/gym-app \
  BACKUP_RETENTION_DAYS=14 \
  BACKUP_RCLONE_REMOTE=remote:gym-app-backups \
  bash scripts/backup_compose.sh
```

Output: `db.dump`, `uploads.tar.gz`, `counts.txt`, `checksums.txt`, `last_success`.

- Backups contain PII and password hashes. Store encrypted off-host (`age`, `gpg`, encrypted object storage) and restrict access (`0700`/`0600`).
- `BACKUP_RCLONE_REMOTE` is optional and fails the backup if `rclone` or the copy fails.
- Retention prunes old directories only inside `BACKUP_DIR`.
- Schedule with `deploy/systemd/gym-backup.timer.example`; alert on `systemctl --failed` and on `scripts/check_backup_freshness.sh` returning non-zero.
- Proposed RPO: ≤24 hours (last nightly backup). Proposed RTO: ≤4 hours for a single-host restore. These are targets for operator approval, not guarantees.

### Restore after data loss

```sh
BACKUP_PATH=/var/backups/gym-app/<timestamp> \
DEPLOY_ENV=production ENV_FILE=.env.production CONFIRM_RESTORE=YES \
  bash scripts/restore_compose.sh
```

The script verifies checksums, stops the backend, restores PostgreSQL and uploads, starts the backend, and verifies row counts plus every referenced upload. Re-run the post-deploy verification afterward and record the data-loss window.

### Isolated drill (required before relying on backups)

Run `scripts/ci/backup-restore-drill.sh` in CI, or repeat its approach manually into a disposable database and upload directory. Never test a destructive restore against production. The CI drill verifies checksums, row counts, and upload sizes in an isolated database.

## 9. Monitoring and alerting

Minimum:

- **Availability:** external HTTPS GET `/api/v1/utils/ready/` every 1–5 min; alert on non-200. A `503` means the DB is unreachable.
- **Errors:** `SENTRY_DSN` with PII and request bodies disabled; alert on new high-severity issues.
- **Logs:** JSON logs (`LOG_JSON=true`) contain request ID, method, redacted path, status, duration and `audit` events. Ship to a durable, access-controlled store. Stdout-only logs are not durable audit evidence.
- **Auth abuse:** alert on sustained `429` volume and unusual audit events (ownership, membership, lifecycle, program publish/delete).
- **Backups:** alert when `check_backup_freshness.sh` fails; verify restore quarterly.
- **Disk:** alert on DB/uploads/backup volume usage.
- **TLS:** alert when the certificate has fewer than 14 days remaining.
- **Containers:** restart policy is `unless-stopped`; alert on unhealthy containers.

## 10. Rollback

Application rollback (schema compatible):

```sh
# set BACKEND_IMAGE in .env.production to the previous immutable digest
CONFIRM_DEPLOY=production NO_BUILD=1 bash scripts/deploy_stack.sh production
```

Data rollback (bad migration/data):

1. Stop the backend: `docker compose ... stop backend`.
2. Restore the pre-release backup with `scripts/restore_compose.sh`.
3. Deploy the application version matching the restored schema.
4. Verify and record the data-loss window.

If the host is lost, rebuild from the runbook, restore the newest verified backup, and re-point DNS. Keep the Compose files, env templates and systemd units in version control; keep secrets in the password manager/secret store.

## 11. Final production gate

A production GO requires all of:

- [ ] Release workflow green for the exact image digest being deployed.
- [ ] Preflight passes with staging/production comparison.
- [ ] Public DNS and ACME certificate verified; HTTP redirects; HSTS present.
- [ ] Smoke script passes, including login and readiness.
- [ ] Backend, DB and uploads healthy after a restart.
- [ ] Backup succeeds on the target storage and an isolated restore matches counts/files.
- [ ] SMTP delivery verified to a controlled recipient.
- [ ] External readiness, log shipping, Sentry, backup-freshness, disk and certificate alerts are live.
- [ ] No unresolved critical security/data-integrity finding.
