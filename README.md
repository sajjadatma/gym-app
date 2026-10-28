# ASCORA — Gym Management MVP1

A local-first, multi-gym management PWA for managing gyms, staff, coaches, athletes and **manually authored workout programs**, with Persian-first RTL UI, Material Design 3, Jalali dates and A4 print/PDF output.

This repository implements the approved Gym Management MVP1 specification. It started from the approved [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) and keeps its FastAPI + SQLModel + PostgreSQL + React + Vite + TanStack Router + Alembic + Pytest + Playwright foundation.

Development and staging run locally. Production runs on **Vercel with Neon Postgres and Neon Object Storage**. See [`docs/environments.md`](docs/environments.md) for the environment contract, safety guards and promotion process.

## Stack

- **Backend:** FastAPI, SQLModel, PostgreSQL, Alembic, PyJWT, Argon2/bcrypt password hashing, Pytest.
- **Frontend:** React 19, TypeScript, Vite, TanStack Router/Query, Axios, React Aria accessibility primitives, `@internationalized/date`, Material Design 3 tokens/components, Vazirmatn.
- **Local services:** PostgreSQL 17 (Homebrew) and Mailpit for invitations/password recovery.
- **PWA:** web manifest, icons and a minimal service worker. Service worker is registered in production builds; the FastAPI app serves the built SPA with deep-link fallback.
- **Exercise catalog:** owners and gym admins create gym-scoped categories and custom exercises; coaches select existing catalog entries to author programs. Days carry category snapshots through templates, athlete views and print/PDF.
- **UI system:** Material Design 3 only. The template's shadcn/Tailwind presentation layer was replaced; Tailwind is not used.

## Prerequisites

- Node.js 22+, Bun 1.3+
- `uv` and Python 3.14 (uv manages the project Python)
- Local PostgreSQL 17
- Mailpit (`brew install mailpit` or the Docker Compose service)
- Docker is optional; the documented local path uses Homebrew PostgreSQL and Mailpit.

## First-time local setup

1. Create the local environment files:

   ```sh
   cp .env.dev.example .env.dev
   cp .env.stage.example .env.stage
   ```

   Set private local passwords in both files. Both are git-ignored.

2. Bootstrap the isolated local databases and demo data:

   ```sh
   npm run db:bootstrap:dev
   npm run db:bootstrap:stage
   ```

3. Start an environment:

   ```sh
   npm run dev     # development: 5173 + 8000
   npm run stage   # staging:     5174 + 8001
   ```

   - Development: <http://localhost:5173> · API <http://127.0.0.1:8000/docs>
   - Staging: <http://localhost:5174> · API <http://127.0.0.1:8001/docs>

Demo accounts are documented in [`docs/local-testing.md`](docs/local-testing.md).
Local superuser credentials are in `.env.dev` / `.env.stage`.

## PWA / production local build

The PWA installability and service worker are active in production builds, still on localhost only:

```sh
cd frontend
bun run build
# FastAPI now serves the built SPA and PWA at http://localhost:8000
cd ../backend
ENV_FILE=../.env.dev uv run fastapi dev --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000>. Deep links work through the SPA fallback. In Chrome, use the install icon in the address bar to check installability. Service worker registration and manifest/icons are covered by Playwright (`PWA_PROD=1`).

## Tests

Backend (dedicated `gym_app_test` database, never the dev database):

```sh
cd backend
uv run pytest -q
```

The suite includes a migration smoke test (`-m migrations`) that creates, upgrades and drops a disposable `gym_app_migration_test` database derived from `TEST_DATABASE_URL`; it never touches `DATABASE_URL`. Run only that test with:

```sh
cd backend
uv run pytest -q -m migrations
```

Frontend lint is non-mutating by default; `lint:fix` applies the fixes:

```sh
cd frontend
bun run lint:check
bun run lint:fix
```

Frontend Playwright against the dev server (demo data required):

```sh
cd frontend
bunx playwright test
```

Playwright against the local production build/PWA (build first):

```sh
cd frontend
bun run build
PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test
```

The superuser journey (`tests/superuser-context.spec.ts`, project `superuser`) is skipped unless `PLAYWRIGHT_SUPERUSER_EMAIL` and `PLAYWRIGHT_SUPERUSER_PASSWORD` are set, because the demo seed has no superuser. It expects a disposable environment, never the `gym_app` development data:

```sh
# Build a disposable database from TEST_DATABASE_URL; its name must end in _test.
createdb gym_app_superuser_test
cd backend
DATABASE_URL=postgresql://…/gym_app_superuser_test uv run alembic upgrade head
DATABASE_URL=postgresql://…/gym_app_superuser_test uv run python -m app.initial_data
DATABASE_URL=postgresql://…/gym_app_superuser_test uv run python scripts/seed_demo.py
psql postgresql://…/gym_app_superuser_test \
  -c "UPDATE \"user\" SET is_superuser = true WHERE email = 'ali@example.com';"

# Serve it on :8001 and Vite on :5174.
DATABASE_URL=postgresql://…/gym_app_superuser_test FRONTEND_HOST=http://localhost:5174 \
  uv run uvicorn app.main:app --port 8001
cd ../frontend && VITE_API_URL=http://localhost:8001 bun run dev --host localhost --port 5174
```

Then run the superuser project with the demo credentials:

```sh
cd frontend
PLAYWRIGHT_BASE_URL=http://localhost:5174 PLAYWRIGHT_API_URL=http://localhost:8001 \
PLAYWRIGHT_SUPERUSER_EMAIL=ali@example.com PLAYWRIGHT_SUPERUSER_PASSWORD='DemoPass123!' \
bunx playwright test tests/superuser-context.spec.ts --project=superuser
```

Drop `gym_app_superuser_test` when finished. Never reset, seed or migrate `gym_app` for this suite.

The backend test suite refuses to run unless `TEST_DATABASE_URL` ends in `_test`. It uses a fake test Super Admin password, never the real local secret.

## Local reset (destructive, dedicated dev/stage DB only)

Reset the selected local database and reseed demo data:

```sh
npm run db:reset:dev -- --yes
npm run db:reset:stage -- --yes
```

The script refuses non-local hosts and only resets names ending `_dev` or
`_stage`. It never touches the test database or production Neon data.

## Super Admin verification without printing the secret

With the API running:

```sh
cd backend
uv run python scripts/verify_superadmin_login.py
```

It prints only pass/fail metadata and the account identity, never the password.

## Privacy and local-only boundaries

- Body-analysis files are stored under `backend/uploads/body-analysis/` (Git-ignored) and every download is permission-checked for the gym, athlete, assigned coach/admin.
- `internal_coach_note` exists only in staff responses; it is absent from athlete APIs, the athlete UI and print/PDF output.
- Invitations and password recovery use Mailpit locally; no external SMTP is configured.
- No attendance, workout performance logging, analytics, chat, nutrition, payments, AI program generation or native app features are implemented.
- No deployment or public hosting is configured for MVP1. Minimal GitHub Actions CI gates (lint, type checks, tests, migration smoke test, frontend build) are defined in `.github/workflows/ci.yml`; no deploy steps are included.

## Documentation

- [`docs/local-testing.md`](docs/local-testing.md) — demo accounts, acceptance walkthroughs and PWA checks.
- [`docs/implementation-progress.md`](docs/implementation-progress.md) — acceptance-criteria checklist, commands and verified results.
