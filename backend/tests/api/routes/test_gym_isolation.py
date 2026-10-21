from __future__ import annotations

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


def test_gym_and_coach_data_are_isolated(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_a_email = unique_email("owner-a")
    owner_b_email = unique_email("owner-b")
    gym_a = create_gym(
        client,
        superuser_headers,
        name="Gym A",
        owner_email=owner_a_email,
        password="owner-a-pass-123",
    )["gym"]
    gym_b = create_gym(
        client,
        superuser_headers,
        name="Gym B",
        owner_email=owner_b_email,
        password="owner-b-pass-123",
    )["gym"]

    raw_a = auth_headers(client, owner_a_email, "owner-a-pass-123")
    change_password(
        client,
        raw_a,
        current_password="owner-a-pass-123",
        new_password="owner-a-pass-456",
    )
    owner_a = gym_headers(
        client,
        email=owner_a_email,
        password="owner-a-pass-456",
        gym_id=gym_a["id"],
    )
    raw_b = auth_headers(client, owner_b_email, "owner-b-pass-123")
    change_password(
        client,
        raw_b,
        current_password="owner-b-pass-123",
        new_password="owner-b-pass-456",
    )
    owner_b = gym_headers(
        client,
        email=owner_b_email,
        password="owner-b-pass-456",
        gym_id=gym_b["id"],
    )

    coach_email = unique_email("coach")
    add_member(
        client,
        owner_a,
        gym_a["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )
    add_member(
        client,
        owner_b,
        gym_b["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )
    raw_coach = auth_headers(client, coach_email, "coach-pass-123")
    change_password(
        client,
        raw_coach,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    coach_a = gym_headers(
        client,
        email=coach_email,
        password="coach-pass-456",
        gym_id=gym_a["id"],
    )
    coach_b = gym_headers(
        client,
        email=coach_email,
        password="coach-pass-456",
        gym_id=gym_b["id"],
    )
    coaches_a = client.get(
        f"/api/v1/gyms/{gym_a['id']}/coaches", headers=coach_a
    ).json()["data"]
    coaches_b = client.get(
        f"/api/v1/gyms/{gym_b['id']}/coaches", headers=coach_b
    ).json()["data"]
    coach_id_a = next(
        item["user_id"] for item in coaches_a if item["email"] == coach_email
    )
    coach_id_b = next(
        item["user_id"] for item in coaches_b if item["email"] == coach_email
    )

    athlete_a_email = unique_email("athlete-a")
    athlete_b_email = unique_email("athlete-b")
    athlete_a = create_athlete(
        client,
        coach_a,
        email=athlete_a_email,
        coach_user_id=coach_id_a,
        password="athlete-a-pass-123",
    )["athlete"]["profile"]
    athlete_b = create_athlete(
        client,
        coach_b,
        email=athlete_b_email,
        coach_user_id=coach_id_b,
        password="athlete-b-pass-123",
    )["athlete"]["profile"]

    listed_a = client.get("/api/v1/athletes", headers=coach_a)
    assert listed_a.status_code == 200
    assert [row["user_id"] for row in listed_a.json()["data"]] == [athlete_a["user_id"]]

    listed_b = client.get("/api/v1/athletes", headers=coach_b)
    assert listed_b.status_code == 200
    assert [row["user_id"] for row in listed_b.json()["data"]] == [athlete_b["user_id"]]

    cross = client.get(f"/api/v1/athletes/{athlete_b['user_id']}", headers=coach_a)
    assert cross.status_code == 404

    coach_admin_attempt = client.post(
        f"/api/v1/gyms/{gym_a['id']}/members",
        headers=coach_a,
        json={
            "email": unique_email("blocked"),
            "roles": ["COACH"],
            "activation_method": "password",
            "initial_password": "blocked-pass-123",
        },
    )
    assert coach_admin_attempt.status_code == 403

    cross_gym_admin = client.get(f"/api/v1/gyms/{gym_b['id']}/members", headers=owner_a)
    assert cross_gym_admin.status_code == 404
    assert client.get("/api/v1/athletes", headers=owner_a).status_code == 200

    raw_athlete = auth_headers(client, athlete_a_email, "athlete-a-pass-123")
    change_password(
        client,
        raw_athlete,
        current_password="athlete-a-pass-123",
        new_password="athlete-a-pass-456",
    )
    athlete_a_headers = gym_headers(
        client,
        email=athlete_a_email,
        password="athlete-a-pass-456",
        gym_id=gym_a["id"],
    )
    me = client.get("/api/v1/athletes/me", headers=athlete_a_headers)
    assert me.status_code == 200
    assert me.json()["profile"]["user_id"] == athlete_a["user_id"]

    wrong_gym = client.get(
        "/api/v1/athletes/me", headers={**athlete_a_headers, "X-Gym-ID": gym_b["id"]}
    )
    assert wrong_gym.status_code == 403
    assert client.get("/api/v1/athletes", headers=athlete_a_headers).status_code == 403

    programs_b = client.get(
        f"/api/v1/athletes/{athlete_b['user_id']}/programs", headers=coach_a
    )
    assert programs_b.status_code == 404


def test_ownership_transfer_permissions(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("owner")
    admin_email = unique_email("admin")
    gym = create_gym(
        client,
        superuser_headers,
        name="Ownership Gym",
        owner_email=owner_email,
        password="owner-pass-123",
    )["gym"]
    raw_owner = auth_headers(client, owner_email, "owner-pass-123")
    change_password(
        client,
        raw_owner,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    owner = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    admin = add_member(
        client,
        owner,
        gym["id"],
        email=admin_email,
        roles=["GYM_ADMIN"],
        password="admin-pass-123",
    )["member"]
    raw_admin = auth_headers(client, admin_email, "admin-pass-123")
    change_password(
        client,
        raw_admin,
        current_password="admin-pass-123",
        new_password="admin-pass-456",
    )
    admin_headers = gym_headers(
        client, email=admin_email, password="admin-pass-456", gym_id=gym["id"]
    )
    forbidden = client.post(
        f"/api/v1/gyms/{gym['id']}/transfer-ownership",
        headers=admin_headers,
        json={
            "new_owner_email": admin_email,
            "activation_method": "password",
            "initial_password": "new-owner-pass-123",
        },
    )
    assert forbidden.status_code == 403

    transfer = client.post(
        f"/api/v1/gyms/{gym['id']}/transfer-ownership",
        headers=owner,
        json={"new_owner_email": admin_email},
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["gym"]["owner_id"] == admin["user_id"]

    old_owner_members = client.get(f"/api/v1/gyms/{gym['id']}/members", headers=owner)
    assert old_owner_members.status_code == 403
    new_owner_members = client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers=admin_headers
    )
    assert new_owner_members.status_code == 200

    super_transfer = client.post(
        f"/api/v1/gyms/{gym['id']}/transfer-ownership",
        headers={**superuser_headers, "X-Gym-ID": gym["id"]},
        json={"new_owner_email": owner_email},
    )
    assert super_transfer.status_code == 200, super_transfer.text
    assert super_transfer.json()["gym"]["owner_id"] != admin["user_id"]

    same_owner = client.post(
        f"/api/v1/gyms/{gym['id']}/transfer-ownership",
        headers={**superuser_headers, "X-Gym-ID": gym["id"]},
        json={"new_owner_email": owner_email},
    )
    assert same_owner.status_code == 400


def test_owner_without_explicit_role_has_implicit_admin_and_loses_it_after_transfer(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("implicit-owner")
    member_email = unique_email("new-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Implicit Owner Gym",
        owner_email=owner_email,
        password="owner-pass-123",
    )["gym"]
    raw_owner = auth_headers(client, owner_email, "owner-pass-123")
    change_password(
        client,
        raw_owner,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    owner = gym_headers(
        client, email=owner_email, password="owner-pass-456", gym_id=gym["id"]
    )
    gyms = client.get("/api/v1/gyms/", headers=owner)
    assert gyms.status_code == 200
    own_gym = next(item for item in gyms.json()["data"] if item["id"] == gym["id"])
    assert own_gym["is_owner"] is True
    assert "GYM_ADMIN" in own_gym["my_roles"]
    assert (
        client.get(f"/api/v1/gyms/{gym['id']}/members", headers=owner).status_code
        == 200
    )

    add_member(
        client,
        owner,
        gym["id"],
        email=member_email,
        roles=["COACH"],
        password="member-pass-123",
    )
    transfer = client.post(
        f"/api/v1/gyms/{gym['id']}/transfer-ownership",
        headers=owner,
        json={"new_owner_email": member_email},
    )
    assert transfer.status_code == 200, transfer.text

    old_gyms = client.get("/api/v1/gyms/", headers=owner)
    assert old_gyms.status_code == 200
    assert all(item["id"] != gym["id"] for item in old_gyms.json()["data"])
    assert client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers=owner
    ).status_code in {403, 404}
