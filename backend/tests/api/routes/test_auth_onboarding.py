from __future__ import annotations

import re

from fastapi.testclient import TestClient

from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    extract_invitation_token,
    gym_headers,
    unique_email,
)


def test_invitation_activation_and_initial_password_flow(
    client: TestClient,
    superuser_headers: dict[str, str],
    email_outbox: list[dict],
) -> None:
    owner_email = unique_email("invited-owner")
    created = create_gym(
        client,
        superuser_headers,
        name="Invite Gym",
        owner_email=owner_email,
        method="invite",
    )
    assert created["invitation_sent"] is True
    assert created["initial_password"] is None
    assert len(email_outbox) == 1
    token = extract_invitation_token(email_outbox[0]["html_content"])

    accepted = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "new_password": "invited-owner-pass-123"},
    )
    assert accepted.status_code == 200, accepted.text
    reused = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "new_password": "another-pass-123"},
    )
    assert reused.status_code == 400
    headers = auth_headers(client, owner_email, "invited-owner-pass-123")
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False

    coach_email = unique_email("invited-coach")
    member = add_member(
        client,
        {**headers, "X-Gym-ID": created["gym"]["id"]},
        created["gym"]["id"],
        email=coach_email,
        roles=["COACH"],
        method="invite",
    )
    assert member["invitation_sent"] is True
    token = extract_invitation_token(email_outbox[-1]["html_content"])
    assert (
        client.post(
            "/api/v1/auth/accept-invitation",
            json={"token": token, "new_password": "invited-coach-pass-123"},
        ).status_code
        == 200
    )
    assert auth_headers(client, coach_email, "invited-coach-pass-123")


def test_athlete_invitation_activation(
    client: TestClient,
    superuser_headers: dict[str, str],
    email_outbox: list[dict],
) -> None:
    owner_email = unique_email("invite-athlete-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Athlete Invite Gym",
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
    coach_email = unique_email("invite-athlete-coach")
    coach_member = add_member(
        client,
        owner,
        gym["id"],
        email=coach_email,
        roles=["COACH"],
        password="coach-pass-123",
    )["member"]
    raw_coach = auth_headers(client, coach_email, "coach-pass-123")
    change_password(
        client,
        raw_coach,
        current_password="coach-pass-123",
        new_password="coach-pass-456",
    )
    coach = gym_headers(
        client, email=coach_email, password="coach-pass-456", gym_id=gym["id"]
    )
    athlete_email = unique_email("invite-athlete")
    created = create_athlete(
        client,
        coach,
        email=athlete_email,
        coach_user_id=coach_member["user_id"],
        method="invite",
    )
    assert created["invitation_sent"] is True
    assert created["initial_password"] is None
    token = extract_invitation_token(email_outbox[-1]["html_content"])
    accepted = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "new_password": "athlete-invite-pass-123"},
    )
    assert accepted.status_code == 200, accepted.text
    athlete_headers = auth_headers(client, athlete_email, "athlete-invite-pass-123")
    athlete_headers["X-Gym-ID"] = gym["id"]
    me = client.get("/api/v1/athletes/me", headers=athlete_headers)
    assert me.status_code == 200
    assert me.json()["profile"]["user_id"] == created["athlete"]["profile"]["user_id"]


def test_first_login_password_change_is_enforced(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("owner")
    gym = create_gym(
        client,
        superuser_headers,
        name="Password Gym",
        owner_email=owner_email,
        password="initial-pass-123",
    )["gym"]
    headers = auth_headers(client, owner_email, "initial-pass-123")
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    blocked = client.get(
        f"/api/v1/gyms/{gym['id']}/members", headers={**headers, "X-Gym-ID": gym["id"]}
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "password_change_required"

    change_password(
        client,
        headers,
        current_password="initial-pass-123",
        new_password="changed-pass-123",
    )
    new_headers = gym_headers(
        client, email=owner_email, password="changed-pass-123", gym_id=gym["id"]
    )
    assert (
        client.get(f"/api/v1/gyms/{gym['id']}/members", headers=new_headers).status_code
        == 200
    )


def test_password_recovery_token_and_validation(
    client: TestClient,
    superuser_headers: dict[str, str],
    monkeypatch,
) -> None:
    owner_email = unique_email("recover")
    create_gym(
        client,
        superuser_headers,
        name="Recovery Gym",
        owner_email=owner_email,
        password="recover-pass-123",
    )
    outbox: list[str] = []

    def fake_send_email(
        *, email_to: str = "", subject: str = "", html_content: str = ""
    ) -> None:
        _ = (email_to, subject)
        outbox.append(html_content)

    monkeypatch.setattr("app.api.routes.login.send_email", fake_send_email)
    response = client.post(f"/api/v1/password-recovery/{owner_email}")
    assert response.status_code == 200
    assert len(outbox) == 1
    match = re.search(r"reset-password\?token=([^\"&<]+)", outbox[0])
    assert match
    reset = client.post(
        "/api/v1/reset-password/",
        json={"token": match.group(1), "new_password": "recovered-pass-123"},
    )
    assert reset.status_code == 200, reset.text
    assert auth_headers(client, owner_email, "recovered-pass-123")

    invalid = client.post(
        "/api/v1/reset-password/",
        json={"token": "not-a-token", "new_password": "whatever-pass-123"},
    )
    assert invalid.status_code == 400

    unknown = client.post("/api/v1/password-recovery/unknown@example.com")
    assert unknown.status_code == 200


def test_public_registration_routes_are_not_available(
    client: TestClient,
) -> None:
    for path in ("/api/v1/users/signup", "/api/v1/users/register", "/api/v1/users/"):
        response = client.post(
            path,
            json={
                "email": unique_email("free"),
                "password": "free-pass-123",
                "full_name": "Free",
            },
        )
        assert response.status_code in {404, 405}


def test_missing_and_invalid_gym_context(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    owner_email = unique_email("context")
    gym = create_gym(
        client,
        superuser_headers,
        name="Context Gym",
        owner_email=owner_email,
        password="context-pass-123",
    )["gym"]
    raw = auth_headers(client, owner_email, "context-pass-123")
    change_password(
        client,
        raw,
        current_password="context-pass-123",
        new_password="context-pass-456",
    )
    headers = auth_headers(client, owner_email, "context-pass-456")
    missing = client.get("/api/v1/athletes", headers=headers)
    assert missing.status_code == 400
    invalid = client.get(
        "/api/v1/athletes",
        headers={"Authorization": "Bearer invalid", "X-Gym-ID": gym["id"]},
    )
    assert invalid.status_code == 403

    other = create_gym(
        client,
        superuser_headers,
        name="Other Gym",
        owner_email=unique_email("other-owner"),
        password="other-pass-123",
    )["gym"]
    not_member = client.get(
        "/api/v1/athletes",
        headers={**headers, "X-Gym-ID": other["id"]},
    )
    assert not_member.status_code == 403


def test_athlete_can_belong_to_two_gyms_with_independent_profiles(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    athlete_email = unique_email("multi-athlete")
    gyms = []
    for suffix in ("A", "B"):
        owner_email = unique_email(f"owner-{suffix}")
        created = create_gym(
            client,
            superuser_headers,
            name=f"Multi Gym {suffix}",
            owner_email=owner_email,
            password="multi-owner-pass-123",
        )
        raw = auth_headers(client, owner_email, "multi-owner-pass-123")
        change_password(
            client,
            raw,
            current_password="multi-owner-pass-123",
            new_password="multi-owner-pass-456",
        )
        headers = gym_headers(
            client,
            email=owner_email,
            password="multi-owner-pass-456",
            gym_id=created["gym"]["id"],
        )
        coach_email = unique_email("multi-coach")
        add_member(
            client,
            headers,
            created["gym"]["id"],
            email=coach_email,
            roles=["COACH"],
            password="multi-coach-pass-123",
        )
        raw_coach = auth_headers(client, coach_email, "multi-coach-pass-123")
        change_password(
            client,
            raw_coach,
            current_password="multi-coach-pass-123",
            new_password="multi-coach-pass-456",
        )
        coach = gym_headers(
            client,
            email=coach_email,
            password="multi-coach-pass-456",
            gym_id=created["gym"]["id"],
        )
        coaches = client.get(
            f"/api/v1/gyms/{created['gym']['id']}/coaches", headers=coach
        ).json()["data"]
        coach_id = next(
            row["user_id"] for row in coaches if row["email"] == coach_email
        )
        athlete = create_athlete(
            client,
            coach,
            email=athlete_email,
            coach_user_id=coach_id,
            password="multi-athlete-pass-123" if suffix == "A" else "ignored-pass-123",
            full_name="Multi Athlete",
        )["athlete"]["profile"]
        assert athlete["gym_id"] == created["gym"]["id"]
        assert athlete["training_goal"] == "قدرت"
        gyms.append({"gym": created["gym"], "coach": coach, "athlete": athlete})

    raw_athlete = auth_headers(client, athlete_email, "multi-athlete-pass-123")
    change_password(
        client,
        raw_athlete,
        current_password="multi-athlete-pass-123",
        new_password="multi-athlete-pass-456",
    )
    for entry in gyms:
        headers = gym_headers(
            client,
            email=athlete_email,
            password="multi-athlete-pass-456",
            gym_id=entry["gym"]["id"],
        )
        me = client.get("/api/v1/athletes/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["profile"]["gym_id"] == entry["gym"]["id"]
        update = client.patch(
            "/api/v1/athletes/me",
            headers=headers,
            json={"training_goal": f"goal-{entry['gym']['id']}"},
        )
        assert update.status_code == 200
        assert update.json()["profile"]["training_goal"] == f"goal-{entry['gym']['id']}"

    for entry in gyms:
        headers = gym_headers(
            client,
            email=athlete_email,
            password="multi-athlete-pass-456",
            gym_id=entry["gym"]["id"],
        )
        me = client.get("/api/v1/athletes/me", headers=headers).json()
        assert me["profile"]["training_goal"] == f"goal-{entry['gym']['id']}"
