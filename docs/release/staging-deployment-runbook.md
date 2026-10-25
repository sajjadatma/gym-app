# Staging Deployment Runbook

**Purpose:** deploy and verify an isolated staging copy of MVP1.
**Deployment unit:** Docker Compose on one Linux host behind Traefik.
**Status:** configuration and CI runtime are verified; an actual staging host/DNS has not been deployed from this environment.

## 1. Isolation model

Staging and production may share a host only if they use separate Compose projects. Each project gets its own containers, networks and named volumes.

| Item | Staging |
|---|---|
| Compose project | `gym-staging` (enforced by preflight) |
| Environment file | `.env.staging` (never committed) |
| Domain | e.g. `staging.gym.example.com` |
| Database | private `gym-staging_app-db-data` volume |
| Uploads | private `gym-staging_uploads` volume |
| Sessions | separate `SECRET_KEY`; cookies are domain-scoped |
| ACME | Let's Encrypt **staging** directory; untrusted certs are expected |
| Email | redirected to `EMAIL_REDIRECT_TO`; `HSTS_ENABLED=false` with the untrusted CA |
| Data | fake/test accounts only; never copy production data |

Staging cannot reach production because the Compose networks and volumes are project-scoped and the database is never published.

## 2. Prerequisites

- Linux host with Docker Engine and Compose v2.
- DNS `A`/`AAAA` for the staging domain points at the host.
- Ports 80/443 reachable (port 80 is used for the ACME HTTP challenge).
- At least 2× the expected DB + upload size free for backups.
- SMTP sandbox credentials **or** SMTP left empty. If SMTP is configured, `EMAIL_REDIRECT_TO` is mandatory and is enforced at startup.
- A staging super-admin password that is not reused anywhere.

## 3. Required environment variables

Copy and edit:

```sh
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

Required keys are documented in the template. The deployment fails fast when any of these are missing or weak: `COMPOSE_PROJECT_NAME`, `DOMAIN`, `ACME_EMAIL`, `ACME_CA_SERVER`, `POSTGRES_PASSWORD`, `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `BACKEND_IMAGE`, `WEB_CONCURRENCY`, `HSTS_ENABLED`, `SENTRY_ENVIRONMENT`.

Generate secrets:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'   # SECRET_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'   # POSTGRES_PASSWORD
```

## 4. Validate

```sh
python3 scripts/preflight_env.py --env-file .env.staging --environment staging

COMPOSE_PROJECT_NAME=gym-staging docker compose --env-file .env.staging \
  -f compose.deploy.yml -f compose.staging.yml config >/dev/null
```

Preflight rejects: production secrets, the production ACME directory, HSTS with the untrusted staging CA, more than one worker, colliding project names, and placeholders.

To compare both environment files for accidental reuse:

```sh
python3 scripts/preflight_env.py --env-file .env.staging --environment staging \
  --other-env-file .env.production
```

## 5. Deploy

```sh
CONFIRM_DEPLOY=staging bash scripts/deploy_stack.sh staging
```

The script validates the environment, renders Compose, builds `BACKEND_IMAGE`, starts the stack, and runs the smoke checks. The backend entrypoint validates configuration, waits for PostgreSQL, runs migrations and bootstrap under a PostgreSQL advisory lock, then starts the API.

Watch startup:

```sh
docker compose --env-file .env.staging \
  -f compose.deploy.yml -f compose.staging.yml ps
docker compose --env-file .env.staging \
  -f compose.deploy.yml -f compose.staging.yml logs -f backend
```

Do not continue until the backend is healthy.

## 6. Verify

Automated:

```sh
REQUIRE_HSTS=false CHECK_HTTP_REDIRECT=1 \
  bash scripts/smoke_stack.sh https://staging.gym.example.com
```

Manual checks:

- HTTP redirects to HTTPS; the staging certificate is untrusted, so browsers will warn. That is expected.
- `/api/v1/utils/health-check/` returns `200`.
- `/api/v1/utils/ready/` returns `200`; stop the DB and confirm it returns `503`.
- Login as the staging superuser; create a gym; invite a fake athlete; confirm the invitation email arrives only at `EMAIL_REDIRECT_TO`.
- Reload the page and confirm the session survives.
- Make a cookie-authenticated mutation with the CSRF header removed; expect `403 csrf_failed`.
- Repeat failed logins; expect `429` and `Retry-After`.
- Upload a body-analysis file, restart the backend, and confirm the file and record persist.
- Run a backup and restore drill (§8).

## 7. Migrations

Migrations run automatically on backend start. Concurrent starts are serialized by an advisory lock; only one instance migrates.

For an explicit check:

```sh
docker compose --env-file .env.staging \
  -f compose.deploy.yml -f compose.staging.yml run --rm backend \
  alembic check
```

A failed migration exits the container and prevents the new version from serving. Do not run downgrades with possible data loss; restore the pre-release backup instead.

## 8. Backup and restore

On the deployment host, with the stack running:

```sh
DEPLOY_ENV=staging ENV_FILE=.env.staging \
  BACKUP_DIR=/var/backups/gym-app-staging \
  BACKUP_RETENTION_DAYS=7 \
  bash scripts/backup_compose.sh
```

This produces `db.dump`, `uploads.tar.gz`, row counts and checksums, and writes `last_success`.

Check freshness (for an external monitor or timer):

```sh
BACKUP_DIR=/var/backups/gym-app-staging MAX_AGE_HOURS=26 \
  bash scripts/check_backup_freshness.sh
```

Restore is destructive and requires explicit confirmation:

```sh
BACKUP_PATH=/var/backups/gym-app-staging/<timestamp> \
DEPLOY_ENV=staging ENV_FILE=.env.staging CONFIRM_RESTORE=YES \
  bash scripts/restore_compose.sh
```

The restore stops the backend, restores PostgreSQL and uploads, starts the backend, then verifies row counts and every referenced upload. Run this first in staging.

Store an encrypted copy off the host (`age`/`gpg`) and test a restore at least quarterly. Backups contain athlete data and password hashes.

## 9. Scheduled backups

Copy the examples in `deploy/systemd/` to `/etc/systemd/system/`, adjust `deploy/systemd/backup.env.example`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now gym-backup.timer
systemctl list-timers gym-backup.timer
```

Alert on `systemctl --failed` and on `scripts/check_backup_freshness.sh` returning non-zero.

## 10. Rollback

Application:

```sh
BACKEND_IMAGE=gym-app-staging:<previous-tag> \
  CONFIRM_DEPLOY=staging bash scripts/deploy_stack.sh staging
```

If the schema changed incompatibly, stop the backend and restore the pre-release backup. Migrations are forward-only; backups are the schema rollback mechanism.

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| Traefik serves no certificate | DNS propagation, port 80, `docker compose logs proxy`, ACME rate limits |
| Backend restarts | `docker compose logs backend`; configuration validation now fails fast |
| `503` readiness | PostgreSQL health, credentials, disk space |
| Login returns `403 origin_not_allowed` | `FRONTEND_HOST` must exactly match the browser origin |
| Emails not delivered | SMTP settings and `EMAIL_REDIRECT_TO`; delivery failures are logged without recipients |
| Uploads disappear | Confirm the `uploads` volume is mounted and not replaced on deploy |
| Backup fails | `docker compose ps`, DB health, free space, and the backup script's non-zero exit |

Never expose the PostgreSQL port publicly. Never deploy staging with production secrets or data.
