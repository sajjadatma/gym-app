# FormYar backend

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

- Local demo data: `uv run python scripts/seed_demo.py`.
- Destructive dedicated-dev reset: `CONFIRM_RESET_GYM_APP=YES bash scripts/reset_dev_db.sh` (optionally `SEED_DEMO_DATA=YES`).
- Super Admin bootstrap login check without printing the secret: `uv run python scripts/verify_superadmin_login.py`.

See the root [`README.md`](../README.md) and [`docs/local-testing.md`](../docs/local-testing.md).
