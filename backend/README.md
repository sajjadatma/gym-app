# ASCORA backend

FastAPI + SQLModel + PostgreSQL backend for the Gym Management MVP1.

```sh
uv sync
uv run alembic upgrade head
uv run python -m app.initial_data
uv run fastapi dev --host 127.0.0.1 --port 8000
```

- Environment values are loaded from the Git-ignored repository-root `.env`.
- The global Super Admin is bootstrapped idempotently from `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`.
- 54 global Persian exercises are seeded idempotently from `app/seed_data.py`.
- Tests use `TEST_DATABASE_URL` and refuse non-`_test` databases:

```sh
uv run pytest -q
```

- The suite includes a migration smoke test that creates, upgrades and drops the disposable `gym_app_migration_test` database derived from `TEST_DATABASE_URL`; it never touches `DATABASE_URL`. Run only that test with `uv run pytest -q -m migrations`.

- Local demo data: `uv run python scripts/seed_demo.py`.
- Destructive dedicated-dev reset: `CONFIRM_RESET_GYM_APP=YES bash scripts/reset_dev_db.sh` (optionally `SEED_DEMO_DATA=YES`).
- Super Admin bootstrap login check without printing the secret: `uv run python scripts/verify_superadmin_login.py`.

See the root [`README.md`](../README.md) and [`docs/local-testing.md`](../docs/local-testing.md).

Exercise catalog updates require a gym owner or admin. Coaches can read `/api/v1/exercise-categories` and `/api/v1/exercises` and use catalog IDs in programs/templates; category and exercise writes return HTTP 403 for coaches. Categories are global read-only entries or gym-scoped custom entries. New exercise payloads require `category_id`; `muscle_group` remains in responses as the category label for compatibility. Workout days store multiple category IDs and saved category names; singular category inputs and legacy mixed days remain compatible. Active programs can be edited by authorized staff, and edits must remain publishable. Archived versions are read-only.

Run `uv run alembic upgrade head` to add categories and backfill existing catalog entries without resetting data.
