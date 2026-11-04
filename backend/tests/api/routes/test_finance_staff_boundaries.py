from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.utils.helpers import create_athlete, unique_email

pytestmark = pytest.mark.usefixtures("client")


def test_finance_staff_has_no_operational_or_administrative_access(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Boundary Gym")
    gym_id = str(gym["id"])
    coach = add_staff(client, owner, gym_id, roles=["COACH"])
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    athlete_email = unique_email("boundary-athlete")
    athlete = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_id,
    )["athlete"]["profile"]
    athlete_id = athlete["user_id"]
    staff = add_staff(client, owner, gym_id, roles=["FINANCE_STAFF"])
    membership_id = next(
        row["membership_id"]
        for row in client.get(
            f"/api/v1/gyms/{gym_id}/members?staff_only=true", headers=owner
        ).json()["data"]
        if row["user_id"] == client.get("/api/v1/users/me", headers=staff).json()["id"]
    )

    staff_gated = [
        ("GET", "/api/v1/athletes", None),
        ("GET", "/api/v1/exercises", None),
        ("GET", "/api/v1/exercise-categories", None),
        ("GET", "/api/v1/templates", None),
        ("GET", f"/api/v1/gyms/{gym_id}/coaches", None),
    ]
    for method, url, body in staff_gated:
        response = client.request(method, url, headers=staff, json=body)
        assert response.status_code == 403, (url, response.status_code, response.text)
        assert response.json()["detail"] == "gym_staff_required", url

    admin_gated = [
        ("GET", f"/api/v1/gyms/{gym_id}/members", None),
        (
            "POST",
            f"/api/v1/gyms/{gym_id}/members",
            {
                "email": unique_email("blocked-member"),
                "roles": ["COACH"],
                "activation_method": "password",
                "initial_password": "blocked-pass-123",
                "phone": "09120000000",
            },
        ),
        (
            "PATCH",
            f"/api/v1/gyms/{gym_id}/members/{membership_id}",
            {"is_active": False},
        ),
        ("PATCH", f"/api/v1/gyms/{gym_id}", {"name": "Hijacked"}),
        ("POST", f"/api/v1/gyms/{gym_id}/transfer-ownership", {
            "new_owner_email": unique_email("hijack"),
            "activation_method": "password",
            "initial_password": "hijack-pass-123",
        }),
    ]
    for method, url, body in admin_gated:
        response = client.request(method, url, headers=staff, json=body)
        assert response.status_code == 403, (url, response.status_code, response.text)
        assert response.json()["detail"] in {
            "gym_admin_required",
            "ownership_transfer_forbidden",
        }, url

    # Resource-level routes must not disclose or mutate another person.
    # Reads and edits resolve the athlete context first and answer "not found"
    # so a finance role cannot probe for existing athletes; admin-only actions
    # answer with an explicit admin requirement.
    athlete_scoped = [
        ("GET", f"/api/v1/athletes/{athlete_id}", None, 404),
        ("PATCH", f"/api/v1/athletes/{athlete_id}", {"training_goal": "x"}, 404),
        ("DELETE", f"/api/v1/athletes/{athlete_id}", None, 403),
        ("POST", f"/api/v1/athletes/{athlete_id}/archive", None, 403),
        ("GET", f"/api/v1/athletes/{athlete_id}/programs", None, 404),
    ]
    for method, url, body, expected in athlete_scoped:
        response = client.request(method, url, headers=staff, json=body)
        assert response.status_code == expected, (
            method,
            url,
            response.status_code,
            response.text,
        )

    people = client.get(
        f"/api/v1/people/{athlete_id}/overview",
        headers=staff,
        params={"gym_id": gym_id, "kind": "ATHLETE"},
    )
    assert people.status_code == 403, people.text
    assert people.json()["detail"] == "gym_admin_required"

    for url in (
        "/api/v1/superuser/coaches",
        "/api/v1/superuser/athletes",
    ):
        response = client.get(url, headers=staff)
        assert response.status_code == 403, (url, response.text)
        assert response.json()["detail"] == "insufficient_privileges"

    # The role still reaches exactly its own finance workspace and gym identity.
    assert client.get("/api/v1/finance/settings", headers=staff).status_code == 200
    assert client.get("/api/v1/finance/accounts", headers=staff).status_code == 200
    assert client.get("/api/v1/finance/journal", headers=staff).status_code == 200
    customers = client.get("/api/v1/finance/customers", headers=staff)
    assert customers.status_code == 200, customers.text
    customer_rows = {row["email"]: row for row in customers.json()["data"]}
    assert athlete_email in customer_rows
    assert "ATHLETE" in customer_rows[athlete_email]["roles"]
    staff_email = client.get("/api/v1/users/me", headers=staff).json()["email"]
    assert staff_email in customer_rows
    # Coaches are not finance operators and must not gain the customer read model.
    assert client.get("/api/v1/finance/customers", headers=coach).status_code == 403
    assert client.get(f"/api/v1/gyms/{gym_id}", headers=staff).status_code == 200
    assert client.get("/api/v1/users/me", headers=staff).status_code == 200

    # Nothing above changed the gym or the athlete.
    assert client.get(f"/api/v1/gyms/{gym_id}", headers=owner).json()["name"] == (
        "Boundary Gym"
    )
    still_there = client.get(f"/api/v1/athletes/{athlete_id}", headers=owner)
    assert still_there.status_code == 200
