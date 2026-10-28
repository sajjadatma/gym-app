# Environments

ASCORA uses three explicitly separated environments. Development and staging
run locally; production runs on Vercel with Neon Postgres and Neon Object
Storage.

| | Development | Staging | Production |
| --- | --- | --- | --- |
| Purpose | Daily coding | Production-like acceptance | Real users |
| Frontend | `http://localhost:5173` | `http://localhost:5174` | Vercel |
| Backend | `http://127.0.0.1:8000` | `http://127.0.0.1:8001` | Vercel Function |
| Database | local `gym_dev` | local `gym_stage` | Neon production branch |
| Files | local `backend/uploads/development-body-analysis` | local `backend/uploads/staging-body-analysis` | Neon Object Storage |
| Email | disabled / Mailpit | disabled / Mailpit | configured provider |
| Config file | `.env.dev` | `.env.stage` | Vercel environment variables |
| Demo data | seeded | seeded | never seeded |
| Secrets | local only | local only | Vercel secrets |

Each environment has its own database, uploads, signing secret, superuser,
cookies and limits. Secrets are never shared between environments.

## Environment selection

The backend loads **exactly one** file:

- `ENV_FILE=.env.dev` for development
- `ENV_FILE=.env.stage` for staging
- no `ENV_FILE` on Vercel; platform environment variables are used

This prevents a local command from inheriting production values from `.env`.
The local startup commands set `ENV_FILE` for you.

## Local setup

```bash
cp .env.dev.example .env.dev
cp .env.stage.example .env.stage
npm run db:bootstrap:dev
npm run db:bootstrap:stage
```

Fill in private values in `.env.dev` and `.env.stage` before sharing either
environment. Both files are git-ignored.

### Start

```bash
npm run dev     # development: 5173 + 8000
npm run stage   # staging:     5174 + 8001
```

Both commands:

1. verify the selected file and local database host;
2. create the database if needed;
3. apply migrations;
4. bootstrap the superuser;
5. seed deterministic demo data;
6. start backend and frontend with strict ports.

Demo accounts use the shared local password documented in
[`local-testing.md`](local-testing.md). The local superuser credentials are in
the selected `.env` file.

### Reset

```bash
npm run db:reset:dev -- --yes
npm run db:reset:stage -- --yes
```

Resetting is destructive and only works against a local database whose name
ends in `_dev` or `_stage`.

## Safety guards

- `FASTAPI_ENV=development` and `FASTAPI_ENV=staging` reject non-local database
  hosts.
- Demo seeding refuses `FASTAPI_ENV=production` and remote databases.
- Bootstrap and reset scripts refuse remote hosts.
- Production HTML is served with `Cache-Control: no-store`.
- Missing hashed assets return real `404` responses, never the SPA shell.
- PWA assets are preserved with content-type validation.

## CI

Every pull request runs:

- backend tests and migration smoke test;
- frontend lint, typecheck and build;
- environment contract checks;
- isolated dev and stage database bootstrap;
- full Docker end-to-end and PWA smoke tests.

Release candidates are built once, tested as the release image, and only then
published.

## Production

- Project: `sajjadnaserizadehs-projects/gym-v1`
- URL: <https://gym-v1-flame.vercel.app>
- Database: Neon production branch
- Storage: private Neon Object Storage bucket

Production secrets live only in Vercel. Do not create `.env.production` with
real values on a workstation.

### Promotion

Use **Actions → Production deploy → Run workflow**, type `production`, and
approve the protected `production` environment. The workflow:

1. pulls production settings from Vercel;
2. builds a production artifact;
3. deploys it;
4. runs `scripts/smoke-production.sh`.

Required repository secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
`VERCEL_PROJECT_ID`.

### Migrations

Run migrations once from a trusted environment with the direct Neon URL, never
inside a request or a preview deployment:

```bash
set -a; . ./.env; set +a
cd backend
DATABASE_URL="$DATABASE_URL_UNPOOLED" uv run alembic upgrade head
```

### Rollback

- **Application:** promote the previous Vercel deployment.
- **Database:** restore the Neon branch/snapshot; do not reverse-write
  migrations on production.
- **Files:** Neon Object Storage branches with the database branch.

Verify recovery with `scripts/smoke-production.sh <url>` after any rollback.
