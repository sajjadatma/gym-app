#!/usr/bin/env python3
"""Validate a staging or production environment file before deployment.

Parses KEY=VALUE without executing the file. Prints key names only, never
values, so it is safe to run in CI logs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PLACEHOLDER_MARKERS = ("replace-with", "changethis", "your-", "example.com")
REQUIRED = (
    "COMPOSE_PROJECT_NAME",
    "DOMAIN",
    "ACME_EMAIL",
    "ACME_CA_SERVER",
    "POSTGRES_PASSWORD",
    "SECRET_KEY",
    "FIRST_SUPERUSER",
    "FIRST_SUPERUSER_PASSWORD",
    "BACKEND_IMAGE",
    "WEB_CONCURRENCY",
    "HSTS_ENABLED",
    "SENTRY_ENVIRONMENT",
)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def fail(message: str) -> None:
    print(f"preflight: FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_environment(
    environment: str, values: dict[str, str], errors: list[str]
) -> None:
    for key in REQUIRED:
        if not values.get(key):
            errors.append(f"{key} is required")
            continue
        value = values[key]
        if key not in {"DOMAIN", "ACME_EMAIL", "ACME_CA_SERVER", "SENTRY_ENVIRONMENT"}:
            lowered = value.lower()
            if any(marker in lowered for marker in PLACEHOLDER_MARKERS if marker != "example.com"):
                errors.append(f"{key} still contains a placeholder")

    expected_project = f"gym-{environment}"
    if values.get("COMPOSE_PROJECT_NAME") != expected_project:
        errors.append(f"COMPOSE_PROJECT_NAME must be {expected_project}")

    domain = values.get("DOMAIN", "")
    if not domain or domain.startswith(("http://", "https://", "localhost")):
        errors.append("DOMAIN must be a bare public hostname")
    if "." not in domain:
        errors.append("DOMAIN must contain a dot")

    if "@" not in values.get("ACME_EMAIL", ""):
        errors.append("ACME_EMAIL must be an email address")

    if len(values.get("SECRET_KEY", "")) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    if len(values.get("POSTGRES_PASSWORD", "")) < 16:
        errors.append("POSTGRES_PASSWORD must be at least 16 characters")
    if len(values.get("FIRST_SUPERUSER_PASSWORD", "")) < 12:
        errors.append("FIRST_SUPERUSER_PASSWORD must be at least 12 characters")
    if values.get("POSTGRES_PASSWORD") == values.get("SECRET_KEY"):
        errors.append("POSTGRES_PASSWORD and SECRET_KEY must differ")

    if values.get("WEB_CONCURRENCY", "1") != "1":
        errors.append(
            "WEB_CONCURRENCY must stay 1 until a shared rate limiter is deployed"
        )

    if values.get("HSTS_ENABLED", "").lower() not in {"true", "false"}:
        errors.append("HSTS_ENABLED must be true or false")
    if environment == "production" and values.get("HSTS_ENABLED") != "true":
        errors.append("HSTS_ENABLED must be true in production")
    if environment == "staging" and values.get("HSTS_ENABLED") != "false":
        errors.append(
            "HSTS_ENABLED must be false in staging while using the untrusted staging CA"
        )

    ca_server = values.get("ACME_CA_SERVER", "")
    if environment == "staging" and "acme-staging-v02" not in ca_server:
        errors.append("ACME_CA_SERVER must use the Let's Encrypt staging directory")
    if environment == "production" and "acme-staging" in ca_server:
        errors.append("ACME_CA_SERVER must not use the staging directory in production")

    if values.get("SENTRY_ENVIRONMENT") != environment:
        errors.append(f"SENTRY_ENVIRONMENT must be {environment}")

    redirect = values.get("EMAIL_REDIRECT_TO", "")
    if environment == "staging" and not redirect:
        errors.append("EMAIL_REDIRECT_TO is required in staging")
    if environment == "production" and redirect:
        errors.append("EMAIL_REDIRECT_TO must be empty in production")


def compare_environments(
    first: dict[str, str], second: dict[str, str], errors: list[str]
) -> None:
    for key in (
        "COMPOSE_PROJECT_NAME",
        "DOMAIN",
        "POSTGRES_PASSWORD",
        "SECRET_KEY",
        "FIRST_SUPERUSER",
        "FIRST_SUPERUSER_PASSWORD",
        "BACKEND_IMAGE",
    ):
        if first.get(key) and first.get(key) == second.get(key):
            errors.append(f"{key} must differ between staging and production")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--environment", required=True, choices=("staging", "production"))
    parser.add_argument("--other-env-file", type=Path)
    args = parser.parse_args()

    if not args.env_file.is_file():
        fail(f"environment file not found: {args.env_file}")

    values = parse_env(args.env_file)
    errors: list[str] = []
    check_environment(args.environment, values, errors)

    if args.other_env_file:
        if not args.other_env_file.is_file():
            fail(f"comparison environment file not found: {args.other_env_file}")
        compare_environments(values, parse_env(args.other_env_file), errors)

    if errors:
        for error in errors:
            print(f"preflight: FAIL: {error}", file=sys.stderr)
        return 1

    print(f"preflight: OK ({args.environment}, {len(values)} keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
