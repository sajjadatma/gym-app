# Vercel + Neon Pilot Deployment

Pilot deployment of the Gym application as a single Vercel project, using the
existing Neon Postgres database and Neon Object Storage bucket.

## Architecture

- **Vercel project:** static React/Vite build served by FastAPI via
  `app.frontend()`; all API routes run in one Python 3.14 Vercel Function.
- **Entrypoint:** `server.py` adds `backend/` to `sys.path` and exports the
  FastAPI `app`.
- **Database:** Neon pooled `DATABASE_URL` at runtime. Migrations use the
  direct `DATABASE_URL_UNPOOLED` outside request handling.
- **Storage:** Neon S3-compatible bucket `gym`, accessed server-side with
  `boto3` path-style addressing.
- **Auth:** same-origin cookies with `Secure`, `SameSite=Lax`, and the existing
  CSRF verification.
- **Rate limiting:** database-backed fixed-window counters
  (`RATE_LIMIT_BACKEND=database`) shared across function instances.
- **Region:** `cle1` (Cleveland), nearest configured Vercel region to Neon's
  `aws-us-east-2`.

## Vercel configuration

`vercel.json` sets the frontend build command, function duration, region, and
files excluded from the function bundle. `.python-version` pins Python 3.14.
`requirements.txt` and the root workspace dependency on `app` provide runtime
dependencies.

## Required environment variables

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT/cookie signing; 32+ characters in production |
| `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD` | Initial administrator |
| `DATABASE_URL` | Neon pooled connection string |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `AWS_REGION` | Neon Object Storage |
| `BODY_ANALYSIS_BUCKET=gym` | Existing storage bucket |
| `BODY_ANALYSIS_MAX_BYTES=3500000` | Safe upload limit under Vercel's 4.5 MB payload cap |
| `VITE_MAX_UPLOAD_BYTES=3500000` | Client-side upload limit |
| `FASTAPI_ENV=production` | Enables production validation and HSTS/cookie settings |
| `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`, `HSTS_ENABLED=true` | Cookie/transport security |
| `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_BACKEND=database` | Shared login/recovery limits |
| `TRUST_PROXY_HEADERS=true` | Use Vercel's `x-real-ip` / `x-forwarded-for` |
| `PROJECT_NAME=Gym Management` | Branding |

`FRONTEND_HOST` is derived from `VERCEL_PROJECT_PRODUCTION_URL` when running on
Vercel, keeping invitation links and origin checks on the stable production
domain.

## Limits for this pilot

- Uploads up to **3.5 MB** are supported. Vercel Functions reject payloads over
  4.5 MB before the app sees them, so the previous 10 MB local limit is not
  available on this deployment.
- Large PDF/response bodies are also capped by the same 4.5 MB limit; pilot
  programs are expected to stay well below it.
- The database limiter is fixed-window; a successful login resets that email's
  counter.

## Bootstrap and migrations

Migrations are not run on individual requests. Run them once from a trusted
environment with the direct URL:

```bash
set -a; . ./.env; set +a
cd backend
DATABASE_URL="$DATABASE_URL_UNPOOLED" uv run alembic upgrade head
DATABASE_URL="$DATABASE_URL_UNPOOLED" uv run python scripts/bootstrap.py
```

## Local verification

```bash
# backend
cd backend
uv run pytest -q

# frontend
cd frontend
bun run lint:check
bunx tsc -p tsconfig.build.json --noEmit
npm run build
```

Serverless-shaped local run:

```bash
FASTAPI_ENV=production COOKIE_SECURE=true VERCEL=1 \
VERCEL_PROJECT_PRODUCTION_URL=<domain>.vercel.app \
RATE_LIMIT_BACKEND=database TRUST_PROXY_HEADERS=true \
uv run uvicorn server:app --host 127.0.0.1 --port 8003
```

## Deployment

Project: `sajjadnaserizadehs-projects/gym-v1` (Hobby)  
Production URL: **https://gym-v1-flame.vercel.app**

`vercel.json` installs Bun, installs the frontend workspace from `bun.lock`,
and installs Python dependencies into Vercel's generated virtualenv
(`.vercel/python/.venv`). The Python function bundle excludes `pyproject.toml`
and `uv.lock`, so `requirements.txt` is the single runtime dependency source.

```bash
vercel link --project gym-v1
vercel env add <NAME> production
vercel deploy --prod
```

## Live verification (2026-10-26)

Verified against the production URL with fictional pilot data:

| Check | Result |
| --- | --- |
| HTTPS app, Persian UI, RTL | pass |
| Superuser login and global dashboard | pass |
| Coach login, gym context, assigned athletes | pass |
| Coach program creation, structure save, publish | pass |
| Athlete login and active program view | pass |
| Data persists in Neon after a new request | pass |
| Route refresh (`/athletes`) | pass |
| PWA manifest + service worker on mobile viewport | pass |
| Upload 3.4 MB PDF, download identical bytes | pass |
| Upload 3.6 MB PDF | rejected with 413 |
| Private bucket read without credentials | 403 |
| Deleting an athlete removes the stored object | pass |
| Shared login limiter (5 allowed, 6th 429) | pass |
| Cross-gym and unassigned-coach access | 404 |

Pilot accounts created for testing (fictional):

- `coach1@example.com`, `coach2@example.com`
- `athlete1@example.com` … `athlete3@example.com`
- Shared pilot password is intentionally not stored in this repository.

## Known pilot limitations

- SMTP is not configured; accounts are provisioned by the superuser with
  password activation and their first-login password change is disabled for the
  pilot accounts.
- CSV/XLSX import is capped at 3.5 MB on Vercel (platform request limit).
- PDF/response bodies above 4.5 MB are not supported by Vercel Functions.
- Deployment protection must remain disabled for tester access; only the
  production domain is intended to be public.

