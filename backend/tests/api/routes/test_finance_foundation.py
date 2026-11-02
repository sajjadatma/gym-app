from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    gym_headers,
    unique_email,
)

pytestmark = pytest.mark.usefixtures("client")


def make_owner(
    client: TestClient,
    superuser_headers: dict[str, str],
    *,
    name: str,
) -> tuple[dict[str, object], dict[str, str]]:
    email = unique_email("owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=name,
        owner_email=email,
        password="owner-pass-123",
    )["gym"]
    assert isinstance(gym, dict)
    raw = auth_headers(client, email, "owner-pass-123")
    change_password(
        client,
        raw,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    return gym, gym_headers(
        client,
        email=email,
        password="owner-pass-456",
        gym_id=str(gym["id"]),
    )


def add_staff(
    client: TestClient,
    owner: dict[str, str],
    gym_id: str,
    *,
    roles: list[str],
    email: str | None = None,
) -> dict[str, str]:
    email = email or unique_email("staff")
    add_member(
        client,
        owner,
        gym_id,
        email=email,
        roles=roles,
        password="staff-pass-123",
    )
    raw = auth_headers(client, email, "staff-pass-123")
    change_password(
        client,
        raw,
        current_password="staff-pass-123",
        new_password="staff-pass-456",
    )
    return gym_headers(
        client, email=email, password="staff-pass-456", gym_id=gym_id
    )


def test_finance_is_enabled_by_default_and_only_superuser_can_disable(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Default Finance Gym")

    settings = client.get("/api/v1/finance/settings", headers=owner)
    assert settings.status_code == 200, settings.text
    body = settings.json()
    assert body["enabled"] is True
    assert body["display_unit"] == "RIAL"
    assert body["can_manage"] is True
    assert body["can_toggle"] is False
    assert "finance.view" in body["permissions"]

    denied = client.patch(
        "/api/v1/finance/settings", headers=owner, json={"enabled": False}
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "superuser_required"

    assert client.get("/api/v1/finance/settings", headers=owner).json()["enabled"]

    superuser_gym_headers = {
        **superuser_headers,
        "X-Gym-ID": str(gym["id"]),
    }
    disabled = client.patch(
        "/api/v1/finance/settings",
        headers=superuser_gym_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False
    assert disabled.json()["can_toggle"] is True

    still_disabled = client.get("/api/v1/finance/settings", headers=owner)
    assert still_disabled.status_code == 200
    assert still_disabled.json()["enabled"] is False

    reenabled = client.patch(
        "/api/v1/finance/settings",
        headers=superuser_gym_headers,
        json={"enabled": True},
    )
    assert reenabled.status_code == 200, reenabled.text
    assert reenabled.json()["enabled"] is True


def test_gym_admin_can_configure_display_unit_but_not_enable_flag(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Display Gym")

    updated = client.patch(
        "/api/v1/finance/settings", headers=owner, json={"display_unit": "TOMAN"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_unit"] == "TOMAN"

    invalid = client.patch(
        "/api/v1/finance/settings", headers=owner, json={"display_unit": "USD"}
    )
    assert invalid.status_code == 422

    combined = client.patch(
        "/api/v1/finance/settings",
        headers=owner,
        json={"display_unit": "RIAL", "enabled": False},
    )
    assert combined.status_code == 403


def test_finance_staff_role_grants_no_operational_access(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Staff Separation Gym")
    gym_id = str(gym["id"])
    staff = add_staff(client, owner, gym_id, roles=["FINANCE_STAFF"])

    # The finance role is a valid membership that reaches finance only.
    settings = client.get("/api/v1/finance/settings", headers=staff)
    assert settings.status_code == 200, settings.text
    assert settings.json()["can_manage"] is False
    assert settings.json()["can_toggle"] is False
    assert settings.json()["permissions"] == ["finance.view"]

    # Operational staff surfaces stay closed.
    athletes = client.get("/api/v1/athletes", headers=staff)
    assert athletes.status_code == 403, athletes.text
    members = client.get(f"/api/v1/gyms/{gym_id}/members", headers=staff)
    assert members.status_code == 403, members.text
    create_member = client.post(
        f"/api/v1/gyms/{gym_id}/members",
        headers=staff,
        json={
            "email": unique_email("blocked"),
            "roles": ["COACH"],
            "activation_method": "password",
            "initial_password": "blocked-pass-123",
        },
    )
    assert create_member.status_code == 403, create_member.text
    exercises = client.post(
        "/api/v1/exercises",
        headers=staff,
        json={
            "name_fa": "حرکت غیرمجاز",
            "category_id": str(uuid.uuid4()),
        },
    )
    assert exercises.status_code == 403, exercises.text


def test_finance_staff_cannot_open_another_gyms_finance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Finance Gym A")
    gym_b, _owner_b = make_owner(client, superuser_headers, name="Finance Gym B")
    staff = add_staff(client, owner_a, str(gym_a["id"]), roles=["FINANCE_STAFF"])

    own = client.get("/api/v1/finance/settings", headers=staff)
    assert own.status_code == 200, own.text

    cross = client.get(
        "/api/v1/finance/settings",
        headers={**staff, "X-Gym-ID": str(gym_b["id"])},
    )
    assert cross.status_code == 403, cross.text
    assert cross.json()["detail"] == "not_a_gym_member"

    superuser_cross = client.get(
        "/api/v1/finance/settings",
        headers={**superuser_headers, "X-Gym-ID": str(gym_b["id"])},
    )
    assert superuser_cross.status_code == 200, superuser_cross.text


def test_finance_requires_gym_context(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Context Gym")
    response = client.get(
        "/api/v1/finance/settings",
        headers={key: value for key, value in owner.items() if key != "X-Gym-ID"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "gym_context_required"


def test_coaches_and_athletes_have_no_gym_finance_access(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="No Finance Gym")
    gym_id = str(gym["id"])
    coach = add_staff(client, owner, gym_id, roles=["COACH"])

    coach_response = client.get("/api/v1/finance/settings", headers=coach)
    assert coach_response.status_code == 403, coach_response.text
    assert coach_response.json()["detail"] == "finance_access_denied"

    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    athlete_email = unique_email("finance-athlete")
    create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_id,
        password="athlete-pass-123",
    )
    raw = auth_headers(client, athlete_email, "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete = gym_headers(
        client,
        email=athlete_email,
        password="athlete-pass-456",
        gym_id=gym_id,
    )
    athlete_response = client.get("/api/v1/finance/settings", headers=athlete)
    assert athlete_response.status_code == 403, athlete_response.text
    assert athlete_response.json()["detail"] == "finance_access_denied"
    assert client.get("/api/v1/finance/journal", headers=athlete).status_code == 403
