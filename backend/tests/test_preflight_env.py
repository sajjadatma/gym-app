from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "preflight_env.py"

BASE = {
    "COMPOSE_PROJECT_NAME": "gym-staging",
    "DOMAIN": "staging.gym.test",
    "ACME_EMAIL": "ops@gym.test",
    "ACME_CA_SERVER": "https://acme-staging-v02.api.letsencrypt.org/directory",
    "POSTGRES_PASSWORD": "staging-db-password-123456",
    "SECRET_KEY": "staging-secret-0123456789-0123456789-abcdef",
    "FIRST_SUPERUSER": "staging-admin@gym.test",
    "FIRST_SUPERUSER_PASSWORD": "staging-admin-password",
    "BACKEND_IMAGE": "gym-app-staging:test",
    "WEB_CONCURRENCY": "1",
    "HSTS_ENABLED": "false",
    "SENTRY_ENVIRONMENT": "staging",
    "EMAIL_REDIRECT_TO": "staging-inbox@gym.test",
}


def write_env(path: Path, **overrides: str) -> Path:
    values = {**BASE, **overrides}
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    return path


def run_preflight(
    path: Path, environment: str = "staging", other: Path | None = None
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(SCRIPT),
        "--env-file",
        str(path),
        "--environment",
        environment,
    ]
    if other:
        args.extend(["--other-env-file", str(other)])
    return subprocess.run(args, capture_output=True, text=True, check=False)


def test_valid_staging_environment_passes(tmp_path: Path) -> None:
    result = run_preflight(write_env(tmp_path / "staging.env"))
    assert result.returncode == 0, result.stderr
    assert "preflight: OK" in result.stdout


def test_production_rejects_staging_acme(tmp_path: Path) -> None:
    path = write_env(
        tmp_path / "production.env",
        COMPOSE_PROJECT_NAME="gym-production",
        HSTS_ENABLED="true",
        SENTRY_ENVIRONMENT="production",
        EMAIL_REDIRECT_TO="",
    )
    result = run_preflight(path, environment="production")
    assert result.returncode == 1
    assert "staging directory" in result.stderr


def test_example_domain_is_rejected(tmp_path: Path) -> None:
    result = run_preflight(
        write_env(tmp_path / "staging.env", DOMAIN="staging.gym.example.com")
    )
    assert result.returncode == 1
    assert "example.com" in result.stderr


def test_reused_credentials_between_environments_are_rejected(
    tmp_path: Path,
) -> None:
    staging = write_env(tmp_path / "staging.env")
    production = write_env(
        tmp_path / "production.env",
        COMPOSE_PROJECT_NAME="gym-production",
        ACME_CA_SERVER="https://acme-v02.api.letsencrypt.org/directory",
        HSTS_ENABLED="true",
        SENTRY_ENVIRONMENT="production",
        EMAIL_REDIRECT_TO="",
    )
    result = run_preflight(staging, other=production)
    assert result.returncode == 1
    assert "must differ" in result.stderr
