# Production Deployment Runbook

**Applies to:** Gym Management MVP1
**Deployment model:** single Docker Compose host behind Traefik with Let's Encrypt TLS
**Status of this runbook:** procedures were exercised locally except public TLS/ACME and Docker image execution. See `production-hardening-results.md` for what was and was not verified.

> Do not treat this document as proof of a working public deployment. Complete §4 and §7 on the real host before serving real user data.

## 1. Architecture

```
Internet :80/:443
        │
   Traefik (TLS, HTTP→HTTPS redirect, ACME)
        │  edge network
   backend (FastAPI, built frontend, /api, migrations on start)
        │  internal network
   db (PostgreSQL, no published ports)
```

- Uploaded body-analysis files live in the `uploads` volume mounted at `/app/backend/uploads`.
- PostgreSQL data lives in the `app-db-data` volume.
- Let's Encrypt state lives in the `letsencrypt` volume.
- Only Traefik publishes ports. The database and app are not directly reachable from the host network.
- The app runs with `WEB_CONCURRENCY=1` by default because the rate limiter is in-process. See §12 before raising it.

Files involved: `compose.production.yml`, `backend/Dockerfile`, `backend/scripts/start.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/verify_restore.py`.

## 2. Prerequisites

| Requirement | Detail |
|---|---|
| Host | Linux host with Docker Engine and the Compose v2 plugin |
| DNS | An `A`/`AAAA` record for the chosen domain pointing at the host, propagated before first start |
| Ports | 80 and 443 reachable from the internet (ACME HTTP challenge uses 80) |
| Disk | Enough space for DB, uploads, and at least 2× backup retention |
| Tools (host) | `curl`, `openssl`; `pg_dump`/`pg_restore`/`psql` + `uv`/Python for the host-run backup scripts |
| Email | An SMTP provider if password recovery and invitations are required. Without it, delivery is logged as failed and no mail is sent. |
| Monitoring | External HTTPS check plus access to container logs (see §11) |

## 3. Required configuration

Create a `.env` file next to `compose.production.yml` (never commit it), or export the variables in the shell. Compose fails fast when a required variable is missing.

| Variable | Required | Notes |
|---|---|---|
| `DOMAIN` | yes | Public hostname, e.g. `gym.example.com`. No scheme. |
| `ACME_EMAIL` | yes | Let's Encrypt contact address |
| `POSTGRES_PASSWORD` | yes | Strong random value; used only inside the Compose network |
| `SECRET_KEY` | yes | ≥32 random characters. Rotating it invalidates all sessions, reset links, and invitations. |
| `FIRST_SUPERUSER` | yes | Bootstrap super-admin email |
| `FIRST_SUPERUSER_PASSWORD` | yes | Strong unique password; change it in the UI after first login if it was shared |
| `PROJECT_NAME` | no | Defaults to `Gym Management` |
| `WEB_CONCURRENCY` | no | Keep `1` unless a shared rate limiter is added |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_TLS`, `SMTP_USER`, `SMTP_PASSWORD` | for email | `SMTP_TLS=true` for 587/STARTTLS |
| `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME` | for email | Sender identity |
| `SENTRY_DSN` | no | Error reporting; PII and request bodies are disabled |
| `CSP_CONNECT_SRC` | no | Defaults to `'self'`; must include any extra API origin |
| `LOGIN_IP_RATE_LIMIT`, `RECOVERY_IP_RATE_LIMIT` | no | Per-IP caps across usernames/emails; defaults 50 per 15 min and 30 per hour |

Generate secrets:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'   # SECRET_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'   # POSTGRES_PASSWORD
```

`compose.production.yml` sets `FASTAPI_ENV=production`, `COOKIE_SECURE=true`, `HSTS_ENABLED=true`, `TRUST_PROXY_HEADERS=true`, and an internal `DATABASE_URL` automatically. Do not override those to weaker values.

The application itself refuses to start in `staging`/`production` when `SECRET_KEY` is shorter than 32 characters or `COOKIE_SECURE` is false.

## 4. First deployment

1. **Validate configuration before pulling or building:**

   ```sh
   docker compose -f compose.production.yml config >/dev/null
   ```

   Missing required variables fail here.

2. **Build and start:**

   ```sh
   docker compose -f compose.production.yml up -d --build
   ```

   The backend entrypoint waits for PostgreSQL, runs `alembic upgrade head` (up to 30 attempts), creates/updates the bootstrap superuser, then starts FastAPI. A migration failure exits the container and prevents the app from serving.

3. **Watch startup:**

   ```sh
   docker compose -f compose.production.yml ps
   docker compose -f compose.production.yml logs -f backend
   ```

   Wait for `Application startup complete` and a healthy backend container.

4. **Verify TLS and routing** (see §5). Do not continue until these pass.

5. **Log in** as `FIRST_SUPERUSER`, change the password if it was shared, then create the first gym.

## 5. Post-deployment verification

Run each check against the real domain and keep the output as release evidence.

```sh
# HTTP must redirect permanently to HTTPS
curl -sS -o /dev/null -D - http://$DOMAIN/ | head -n 5

# HTTPS health, security headers, HSTS
curl -sS -o /dev/null -D - https://$DOMAIN/api/v1/utils/health-check/
curl -sS -o /dev/null -w '%{http_code}\n' https://$DOMAIN/api/v1/utils/ready/

# Certificate chain and expiry
openssl s_client -connect $DOMAIN:443 -servername $DOMAIN </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# Authenticated smoke test (expect 200 + Set-Cookie on successful login)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://$DOMAIN/api/v1/login/access-token \
  -d 'username=YOUR_EMAIL&password=YOUR_PASSWORD'
```

Expected: `200` from health and readiness, `301`/`308` redirect from HTTP, a valid publicly trusted certificate, an `Authorization`-free browser session cookie flow, and the headers `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security`.

Also confirm that the database is **not** reachable from the internet:

```sh
nc -zv $DOMAIN 5432    # must fail or time out
```

## 6. Migrations and routine releases

Migrations run automatically on backend start. For an explicit pre-check or manual run:

```sh
docker compose -f compose.production.yml run --rm backend alembic check
docker compose -f compose.production.yml run --rm backend alembic upgrade head
```

Recommended release sequence:

1. Take a backup (§8) and verify it.
2. Review new migrations for destructive/backward-incompatible changes.
3. `docker compose -f compose.production.yml build backend`
4. `docker compose -f compose.production.yml up -d backend`
5. Re-run §5 checks and inspect logs for errors.

The app is expected to be briefly unavailable while the single backend container restarts.

## 7. TLS/ACME notes

- Traefik obtains and renews certificates automatically through the HTTP challenge.
- DNS must be correct **before** first start; repeated failed validations can hit Let's Encrypt rate limits.
- Certificate state is in the `letsencrypt` volume. Back it up with the other volumes if you want to avoid re-issuance.
- Traefik renews around 30 days before expiry. Monitor expiry (§11).
- If issuance fails, inspect `docker compose logs proxy` for ACME errors and confirm port 80 is reachable.
- Local self-signed HTTPS is **not** an acceptable substitute for this verification.

## 8. Backup

### 8.1 Host-run scripts (verified)

Use when PostgreSQL is reachable from the host (local/staging, SSH tunnel, or a published port). Requirements: `pg_dump` 17+, `psql`, `uv` and the repository Python environment.

```sh
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/app'
export BODY_ANALYSIS_DIR='/absolute/path/to/body-analysis'
export BACKUP_DIR='/secure/backups/gym-app'

bash scripts/backup.sh
```

The script writes `<BACKUP_DIR>/<UTC timestamp>/` containing `db.dump`, `uploads.tar.gz`, `counts.txt`, `checksums.txt`, and exits non-zero on any failure. Verify success by checking the exit code and the printed directory.

### 8.2 Compose-native backup

When the DB is only on the internal network:

```sh
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TARGET="backups/$STAMP"
mkdir -p "$TARGET"
chmod 700 "$TARGET"

docker compose -f compose.production.yml exec -T db \
  pg_dump -U postgres -Fc --no-owner --no-privileges app > "$TARGET/db.dump"
docker compose -f compose.production.yml exec -T backend \
  tar -czf - -C /app/backend/uploads . > "$TARGET/uploads.tar.gz"

# Row counts for later integrity comparison
docker compose -f compose.production.yml exec -T db psql -U postgres -d app -Atc \
  'SELECT count(*) FROM "user";' > "$TARGET/counts.txt"
for table in gym athlete_profile body_analysis_file workout_program_version; do
  docker compose -f compose.production.yml exec -T db psql -U postgres -d app -Atc \
    "SELECT count(*) FROM $table;" >> "$TARGET/counts.txt"
done

tar -tzf "$TARGET/uploads.tar.gz" >/dev/null
pg_restore --list "$TARGET/db.dump" >/dev/null
shasum -a 256 "$TARGET"/* > "$TARGET/checksums.txt"
```

`scripts/restore.sh` expects a host-reachable database. For a pure-Compose restore, use `docker compose exec -T db pg_restore ...` and copy the uploads into the volume with a temporary container, or expose the disposable restore DB to the host only for the drill (§9).

### 8.3 Retention and storage

- Keep at least 7 daily, 4 weekly, and 12 monthly backups; tune to the actual recovery objective.
- Store backups outside the Docker host (object storage or another machine).
- Encrypt before off-site transfer, e.g. `age -r <recipient> db.dump` / `gpg --encrypt`.
- Restrict access: directories `0700`, files `0600`, separate credentials from the app host where possible.
- Backups contain athlete personal data and password hashes. Treat them as production data, not logs.
- Run a restore drill (§9) after any schema, server, or storage change and at least quarterly.
- Delete expired backups securely and document deletion.

## 9. Isolated restore drill (required before trusting backups)

Never restore over the live database. Use an explicitly named disposable database and directory.

```sh
# 1. Create a disposable database on a spare PostgreSQL instance
createdb -h localhost -p 55432 gym_restore_drill

# 2. Restore with explicit confirmation
export BACKUP_PATH=/secure/backups/gym-app/20261025T143108Z
export RESTORE_DATABASE_URL='postgresql://USER:PASSWORD@localhost:55432/gym_restore_drill'
export RESTORE_UPLOAD_DIR='/tmp/gym-restore-drill/body-analysis'
export CONFIRM_RESTORE=YES

bash scripts/restore.sh
```

The script verifies checksums, restores the dump, refuses a non-empty upload target unless `ALLOW_NON_EMPTY_UPLOADS=YES`, then runs `scripts/verify_restore.py`. Success output looks like:

```json
{"counts": {"user": 12, "gym": 3, "athlete_profile": 5, "body_analysis_file": 1, "workout_program_version": 5}, "files_checked": 1, "ok": true, "failures": []}
```

Accept the drill only when `ok` is `true`, counts match `counts.txt`, and every referenced upload exists with the recorded size. Then drop the disposable database and delete the restored files.

**Verified example (2026-10-25):** counts above matched, one upload was referenced, and the restored file was byte-identical to the source (SHA-256 `49fda3c9…84d5a`).

## 10. Disaster recovery

When the live database or volume is lost:

1. Stop the backend to prevent writes: `docker compose -f compose.production.yml stop backend`.
2. Take a safety copy of any surviving volumes if possible.
3. Restore the most recent verified backup into the database and uploads location (§9 mechanics, live target).
4. Start the backend; the entrypoint runs any pending migrations.
5. Run §5 verification, then spot-check recent records and a body-analysis file.
6. Record the incident, the backup timestamp used, and any data-loss window.

**RPO/RTO are operator decisions.** The scripts do not provide point-in-time recovery or continuous archiving; the achievable RPO is the age of the last successful backup.

## 11. Monitoring and operations

Minimum viable monitoring:

- External HTTPS probe of `/api/v1/utils/ready/` every 1–5 minutes; alert on non-200. Readiness returns `503` when the DB is unreachable.
- Container health: `docker compose ps`; restart policy is `unless-stopped`.
- Logs: `docker compose logs -f backend proxy`. The app logs request ID, method, path, status, and duration, plus `audit event=...` lines for privileged mutations. Recovery email addresses are redacted from request logs.
- Sentry: set `SENTRY_DSN` for exception visibility; PII and request bodies are disabled.
- Disk: alert on the PostgreSQL volume, uploads volume, and backup destination.
- TLS: alert when the certificate has fewer than 14 days remaining.
- Authentication: watch for repeated `429` responses and `audit` events; there is no metrics backend, so this is log-based.
- Audit retention: logs are stdout-only. Ship them to a durable, access-controlled store if audit evidence is required.

## 12. Scaling and known limits

- **Do not raise `WEB_CONCURRENCY` above 1** without replacing the in-process rate limiter with a shared implementation. Limits are per process; multiple workers multiply the effective allowance.
- Rate limiting assumes **one trusted proxy**. `client_ip` uses the last `X-Forwarded-For` entry. If a CDN or another proxy is added, review `client_ip` and the trusted-proxy configuration before enabling `TRUST_PROXY_HEADERS`.
- Uploads and CSV imports perform blocking work in request handlers. Large files reduce throughput on a single worker.
- JSON request-size enforcement uses `Content-Length`. Traefik should also enforce a maximum body size; add middleware if streamed/chunked uploads are a concern.
- Database and uploads are backed up independently; the backup script runs both in one pass but does not freeze writes. For strict consistency, pause writes during backup or use PostgreSQL's snapshot facilities.
- There is no HA, no read replica, and no blue/green deployment. Recovery is backup-based.

## 13. Rollback

**Application rollback** (schema still compatible):

1. Check out the previous release tag or image.
2. Rebuild/restart only the backend: `docker compose -f compose.production.yml up -d --build backend`.
3. Re-run §5 checks.

Keep release images tagged (and pushed to a registry) if fast rollback matters; `compose.production.yml` currently builds locally.

**Data rollback** (destructive migration or bad data):

1. Stop the backend.
2. Restore the pre-release backup into the database and uploads (§9/§10).
3. Deploy the application version that matches the restored schema.
4. Verify and record the data-loss window.

Alembic downgrades are not part of the release procedure; backups are the rollback mechanism for schema changes.
