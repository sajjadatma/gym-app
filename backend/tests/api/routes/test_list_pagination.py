from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event

from tests.conftest import test_engine
from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    create_athlete,
    create_gym,
    unique_email,
)


def _owner(
    client: TestClient, superuser_headers: dict[str, str], name: str
) -> tuple[dict, dict[str, str]]:
    email = unique_email("page-owner")
    gym = create_gym(
        client,
        superuser_headers,
        name=name,
        owner_email=email,
        password="owner-pass-123",
    )["gym"]
    raw = auth_headers(client, email, "owner-pass-123")
    change_password(
        client,
        raw,
        current_password="owner-pass-123",
        new_password="owner-pass-456",
    )
    headers = auth_headers(client, email, "owner-pass-456")
    headers["X-Gym-ID"] = gym["id"]
    return gym, headers


def _coach(
    client: TestClient,
    owner: dict[str, str],
    gym: dict,
    *,
    email: str | None = None,
) -> dict:
    return add_member(
        client,
        owner,
        gym["id"],
        email=email or unique_email("page-coach"),
        roles=["COACH"],
        phone="09120000000",
    )["member"]


def _athlete(
    client: TestClient,
    owner: dict[str, str],
    coach_user_id: str,
    *,
    name: str,
) -> dict:
    return create_athlete(
        client,
        owner,
        email=unique_email("page-athlete"),
        coach_user_id=coach_user_id,
        full_name=name,
        phone="09120000000",
    )["athlete"]["profile"]


def test_gym_athlete_list_pages_counts_and_archives(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Athletes")
    coach = _coach(client, owner, gym)
    created = [
        _athlete(client, owner, coach["user_id"], name=f"Athlete {index:02d}")
        for index in range(12)
    ]

    first = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"limit": 5, "offset": 0},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["count"] == 12
    assert len(body["data"]) == 5

    second = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"limit": 5, "offset": 5},
    ).json()
    last = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"limit": 5, "offset": 10},
    ).json()
    assert len(second["data"]) == 5
    assert len(last["data"]) == 2
    assert last["count"] == 12

    ids = [
        row["user_id"]
        for page in (body, second, last)
        for row in page["data"]
    ]
    assert len(ids) == 12
    assert len(set(ids)) == 12

    search = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"q": "Athlete 03", "limit": 10},
    ).json()
    assert search["count"] == 1
    assert search["data"][0]["full_name"] == "Athlete 03"

    archived = client.post(
        f"/api/v1/athletes/{created[0]['user_id']}/archive",
        headers=owner,
    )
    assert archived.status_code == 200, archived.text

    active = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"is_archived": False, "limit": 10},
    ).json()
    only_archived = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"is_archived": True, "limit": 10},
    ).json()
    assert active["count"] == 11
    assert only_archived["count"] == 1
    assert only_archived["data"][0]["user_id"] == created[0]["user_id"]


def test_gym_athlete_assignment_scope_and_page_bounds(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Scope")
    first_coach = _coach(client, owner, gym)
    second_coach = _coach(client, owner, gym)
    for index in range(3):
        _athlete(
            client,
            owner,
            first_coach["user_id"],
            name=f"Assigned {index}",
        )

    second_headers = auth_headers(
        client, second_coach["email"], "member-pass-123"
    )
    change_password(
        client,
        second_headers,
        current_password="member-pass-123",
        new_password="member-pass-456",
    )
    second_headers = auth_headers(
        client, second_coach["email"], "member-pass-456"
    )
    second_headers["X-Gym-ID"] = gym["id"]
    scoped = client.get(
        "/api/v1/athletes", headers=second_headers, params={"limit": 10}
    )
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["count"] == 0
    assert scoped.json()["data"] == []

    assigned = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"assigned_to_me": True, "limit": 10},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["count"] == 0

    beyond = client.get(
        "/api/v1/athletes",
        headers=owner,
        params={"limit": 10, "offset": 100},
    )
    assert beyond.status_code == 200, beyond.text
    assert beyond.json()["data"] == []
    assert beyond.json()["count"] == 3


def test_members_staff_only_pagination(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Members")
    coach = _coach(client, owner, gym)
    _coach(client, owner, gym)
    _coach(client, owner, gym)
    for index in range(2):
        _athlete(client, owner, coach["user_id"], name=f"Member Athlete {index}")

    all_members = client.get(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        params={"limit": 50},
    ).json()
    assert all_members["count"] == 6

    first = client.get(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        params={"staff_only": True, "limit": 2, "offset": 0},
    ).json()
    second = client.get(
        f"/api/v1/gyms/{gym['id']}/members",
        headers=owner,
        params={"staff_only": True, "limit": 2, "offset": 2},
    ).json()
    assert first["count"] == 4
    assert second["count"] == 4
    assert len(first["data"]) == 2
    assert len(second["data"]) == 2
    emails = [member["email"] for member in first["data"] + second["data"]]
    assert len(set(emails)) == 4
    assert all(
        "COACH" in member["roles"] or member["is_owner"]
        for member in first["data"] + second["data"]
    )


def test_superuser_lists_paginate_and_filter_status(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Superuser Lists")
    coach = _coach(client, owner, gym)
    _coach(client, owner, gym)
    _coach(client, owner, gym)
    athletes = [
        _athlete(client, owner, coach["user_id"], name=f"SU Athlete {index:02d}")
        for index in range(11)
    ]
    client.post(
        f"/api/v1/athletes/{athletes[-1]['user_id']}/archive",
        headers=owner,
    )

    active_page = client.get(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        params={"is_archived": False, "limit": 5, "offset": 5},
    ).json()
    archived_page = client.get(
        "/api/v1/superuser/athletes",
        headers=superuser_headers,
        params={"is_archived": True, "limit": 5},
    ).json()
    assert active_page["count"] == 10
    assert len(active_page["data"]) == 5
    assert archived_page["count"] == 1
    assert archived_page["data"][0]["user_id"] == athletes[-1]["user_id"]

    coaches_first = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"is_active": True, "limit": 2, "offset": 0},
    ).json()
    coaches_second = client.get(
        "/api/v1/superuser/coaches",
        headers=superuser_headers,
        params={"is_active": True, "limit": 2, "offset": 2},
    ).json()
    assert coaches_first["count"] == 3
    assert len(coaches_first["data"]) == 2
    assert len(coaches_second["data"]) == 1
    assert all(
        row["roles"] == ["COACH"] for row in coaches_first["data"]
    )


def test_gym_coach_picker_paginates_and_searches(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Coach Picker")
    coaches = [
        _coach(client, owner, gym) for _index in range(3)
    ]

    first = client.get(
        f"/api/v1/gyms/{gym['id']}/coaches",
        headers=owner,
        params={"limit": 2, "offset": 0},
    )
    second = client.get(
        f"/api/v1/gyms/{gym['id']}/coaches",
        headers=owner,
        params={"limit": 2, "offset": 2},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["count"] == 3
    assert len(first.json()["data"]) == 2
    assert len(second.json()["data"]) == 1

    searched = client.get(
        f"/api/v1/gyms/{gym['id']}/coaches",
        headers=owner,
        params={"q": coaches[0]["email"], "limit": 20},
    )
    assert searched.json()["count"] == 1
    assert searched.json()["data"][0]["user_id"] == coaches[0]["user_id"]


def test_invalid_pagination_parameters_are_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Invalid")
    for params in (
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
    ):
        response = client.get(
            "/api/v1/athletes", headers=owner, params=params
        )
        assert response.status_code == 422, params


def _select_count(
    client: TestClient,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any],
) -> int:
    statements: list[str] = []

    def listener(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: Any,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", listener)
    try:
        response = client.get(url, headers=headers, params=params)
    finally:
        event.remove(test_engine, "before_cursor_execute", listener)
    assert response.status_code == 200, response.text
    return len(statements)


def test_list_query_count_is_independent_of_page_size(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = _owner(client, superuser_headers, "Page Query Count")
    coach = _coach(client, owner, gym)
    for _index in range(4):
        _coach(client, owner, gym)
    for index in range(4):
        _athlete(client, owner, coach["user_id"], name=f"Count {index}")

    small = _select_count(
        client,
        "/api/v1/superuser/coaches",
        superuser_headers,
        {"limit": 1},
    )
    large = _select_count(
        client,
        "/api/v1/superuser/coaches",
        superuser_headers,
        {"limit": 5},
    )
    assert small == large

    small_athletes = _select_count(
        client,
        "/api/v1/athletes",
        owner,
        {"limit": 1},
    )
    large_athletes = _select_count(
        client,
        "/api/v1/athletes",
        owner,
        {"limit": 4},
    )
    assert small_athletes == large_athletes
