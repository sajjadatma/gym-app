# Deployment quick reference

The deployment stack is shared between environments:

- `compose.deploy.yml` — services, volumes, networks, Traefik, healthchecks.
- `compose.staging.yml` / `compose.production.yml` — small environment overrides.
- `compose.ci.yml` — disposable CI stack (no proxy).

Environment files are **not** committed:

```sh
cp .env.staging.example .env.staging
cp .env.production.example .env.production
# replace every placeholder, then:
python3 scripts/preflight_env.py --env-file .env.staging --environment staging
python3 scripts/preflight_env.py --env-file .env.production --environment production
```

Deploy (requires explicit confirmation):

```sh
CONFIRM_DEPLOY=staging bash scripts/deploy_stack.sh staging
CONFIRM_DEPLOY=production bash scripts/deploy_stack.sh production
```

Backups (on the deployment host, Docker running):

```sh
DEPLOY_ENV=production ENV_FILE=.env.production \
  BACKUP_DIR=/var/backups/gym-app bash scripts/backup_compose.sh
```

See `docs/release/staging-deployment-runbook.md` and
`docs/release/production-deployment-runbook.md` for prerequisites, verification,
restore and rollback.
