"""Verify the local Super Admin bootstrap without printing any secret.

Requires the local API server to be running. Reads credentials from the ignored
local .env through app settings and prints only pass/fail metadata.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402


def main() -> None:
    base_url = "http://localhost:8000"
    with httpx.Client(base_url=base_url, timeout=15) as client:
        response = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={
                "username": settings.FIRST_SUPERUSER,
                "password": settings.FIRST_SUPERUSER_PASSWORD,
            },
        )
        if response.status_code != 200:
            raise SystemExit(
                f"Super Admin login failed with HTTP {response.status_code}"
            )
        token = response.json()["access_token"]
        me = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        me.raise_for_status()
        payload = me.json()
        if not payload.get("is_superuser"):
            raise SystemExit("Bootstrap account is not a global Super Admin")
        print("Super Admin login: OK")
        print("Global superuser: OK")
        print("Email:", payload["email"])
        print("Display name:", payload.get("full_name"))


if __name__ == "__main__":
    main()
