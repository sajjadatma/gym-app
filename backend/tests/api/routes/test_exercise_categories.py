from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.routes.test_exercises import _gym_with_coach
from tests.utils.helpers import (
    add_member,
    auth_headers,
    change_password,
    gym_headers,
    program_payload,
    unique_email,
)


def _category(client: TestClient, headers: dict[str, str], name: str) -> dict:
    response = client.post(
        "/api/v1/exercise-categories", headers=headers, json={"name": name}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _exercise(client: TestClient, headers: dict[str, str], category: dict) -> dict:
    response = client.post(
        "/api/v1/exercises",
        headers=headers,
        json={"name_fa": "حرکت " + category["name"], "category_id": category["id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_only_owners_and_admins_manage_the_catalog(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner, coach, athlete = _gym_with_coach(
        client, superuser_headers, "catalog-permissions"
    )
    category = _category(client, owner, "تعادل")
    exercise = _exercise(client, owner, category)
    assert exercise["muscle_group"] == category["name"]
    assert exercise["category_id"] == category["id"]
    assert client.get("/api/v1/exercise-categories", headers=coach).status_code == 200
    assert (
        client.post(
            "/api/v1/exercise-categories", headers=coach, json={"name": "دسته مربی"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/exercises",
            headers=coach,
            json={"name_fa": "حرکت مربی", "category_id": category["id"]},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/exercises/{exercise['id']}",
            headers=coach,
            json={"name_fa": "تغییر مربی"},
        ).status_code
        == 403
    )

    email = unique_email("catalog-admin")
    add_member(
        client,
        owner,
        gym["id"],
        email=email,
        roles=["GYM_ADMIN"],
        password="admin-pass-123",
    )
    raw = auth_headers(client, email, "admin-pass-123")
    change_password(
        client, raw, current_password="admin-pass-123", new_password="admin-pass-456"
    )
    admin = gym_headers(
        client, email=email, password="admin-pass-456", gym_id=gym["id"]
    )
    admin_category = _category(client, admin, "هماهنگی")
    _exercise(client, admin, admin_category)
    assert (
        client.patch(
            f"/api/v1/exercises/{exercise['id']}",
            headers=admin,
            json={"name_fa": "ویرایش توسط مدیر"},
        ).status_code
        == 200
    )

    raw = auth_headers(client, athlete["email"], "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client, email=athlete["email"], password="athlete-pass-456", gym_id=gym["id"]
    )
    assert (
        client.get("/api/v1/exercise-categories", headers=athlete_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/exercise-categories",
            headers=athlete_headers,
            json={"name": "دسته ورزشکار"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/exercises",
            headers=athlete_headers,
            json={"name_fa": "حرکت ورزشکار", "category_id": category["id"]},
        ).status_code
        == 403
    )


def test_categories_validate_names_and_gym_isolation(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _, owner_a, coach_a, _ = _gym_with_coach(client, superuser_headers, "category-a")
    _, owner_b, coach_b, athlete_b = _gym_with_coach(
        client, superuser_headers, "category-b"
    )
    category = _category(client, owner_a, "  حرکت   اصلاحی  ")
    assert category["name"] == "حرکت اصلاحی"
    assert (
        client.post(
            "/api/v1/exercise-categories", headers=owner_a, json={"name": "حرکت اصلاحی"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/exercise-categories", headers=owner_a, json={"name": "بازو"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/exercise-categories", headers=owner_a, json={"name": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/exercise-categories", headers=owner_a, json={"name": "a" * 101}
        ).status_code
        == 422
    )
    visible = client.get("/api/v1/exercise-categories", headers=coach_b).json()["data"]
    assert category["id"] not in {item["id"] for item in visible}
    _category(client, owner_b, category["name"])
    exercise = _exercise(client, owner_a, category)
    assert (
        client.post(
            "/api/v1/exercises",
            headers=owner_b,
            json={"name_fa": "تزریق دسته", "category_id": category["id"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/exercises",
            headers=owner_a,
            json={"name_fa": "دسته نامعتبر", "category_id": str(uuid.uuid4())},
        ).status_code
        == 400
    )
    filtered = client.get(
        "/api/v1/exercises", headers=coach_a, params={"category_id": category["id"]}
    ).json()["data"]
    assert [item["id"] for item in filtered] == [exercise["id"]]
    assert (
        client.get(
            "/api/v1/exercises", headers=coach_b, params={"category_id": category["id"]}
        ).status_code
        == 400
    )

    version = client.post(
        f"/api/v1/athletes/{athlete_b['user_id']}/programs",
        headers=coach_b,
        json={"title": "Isolation"},
    ).json()
    global_exercise = client.get("/api/v1/exercises", headers=coach_b).json()["data"][0]
    payload = program_payload(global_exercise["id"])
    payload["days"][0]["category_id"] = category["id"]
    response = client.put(
        f"/api/v1/program-versions/{version['id']}", headers=coach_b, json=payload
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_exercise_category"


def test_day_categories_survive_publish_copy_templates_and_catalog_edits(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _, owner, coach, athlete = _gym_with_coach(
        client, superuser_headers, "category-history"
    )
    category = _category(client, owner, "تمرین بازو")
    other = _category(client, owner, "تمرین پا")
    exercise = _exercise(client, owner, category)
    version = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "برنامه دسته‌بندی"},
    ).json()
    payload = program_payload(exercise["id"])
    payload["days"][0]["category_id"] = other["id"]
    invalid = client.put(
        f"/api/v1/program-versions/{version['id']}", headers=coach, json=payload
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "exercise_category_mismatch"
    payload["days"][0]["category_id"] = category["id"]
    payload["days"][0]["category_name"] = "نام جعلی"
    saved = client.put(
        f"/api/v1/program-versions/{version['id']}", headers=coach, json=payload
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["days"][0]["category_name"] == category["name"]

    template = client.post(
        "/api/v1/templates",
        headers=coach,
        json={"name": "قالب دسته‌دار", "days": payload["days"]},
    )
    assert template.status_code == 200, template.text
    assert template.json()["days"][0]["category_id"] == category["id"]
    applied = client.post(
        f"/api/v1/templates/{template.json()['id']}/apply",
        headers=coach,
        json={"athlete_user_id": athlete["user_id"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["days"][0]["category_name"] == category["name"]

    published = client.post(
        f"/api/v1/program-versions/{version['id']}/publish", headers=coach
    )
    assert published.status_code == 200, published.text
    edited = client.patch(
        f"/api/v1/exercises/{exercise['id']}",
        headers=owner,
        json={"category_id": other["id"], "name_fa": "نام جدید حرکت"},
    )
    assert edited.status_code == 200
    history = client.get(
        f"/api/v1/program-versions/{version['id']}", headers=coach
    ).json()["days"][0]
    assert history["category_id"] == category["id"]
    assert history["category_name"] == category["name"]
    assert history["exercises"][0]["muscle_group"] == category["name"]
    assert history["exercises"][0]["exercise_name"] == exercise["name_fa"]
    copied = client.post(
        f"/api/v1/program-versions/{version['id']}/new-draft", headers=coach
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["days"][0]["category_name"] == category["name"]

    raw = auth_headers(client, athlete["email"], "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete["email"],
        password="athlete-pass-456",
        gym_id=owner["X-Gym-ID"],
    )
    visible = client.get(
        f"/api/v1/program-versions/{version['id']}", headers=athlete_headers
    )
    assert visible.status_code == 200
    assert visible.json()["days"][0]["category_name"] == category["name"]


def test_explicit_mixed_days_remain_mixed_when_saved(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _, owner, coach, athlete = _gym_with_coach(client, superuser_headers, "mixed-day")
    category = _category(client, owner, "دسته ترکیبی نمونه")
    exercise = _exercise(client, owner, category)
    version = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Mixed"},
    ).json()
    payload = program_payload(exercise["id"])
    payload["days"][0]["category_id"] = None
    saved = client.put(
        f"/api/v1/program-versions/{version['id']}", headers=coach, json=payload
    )
    assert saved.status_code == 200, saved.text
    day = saved.json()["days"][0]
    assert day["category_id"] is None and day["category_name"] is None
    assert day["exercises"][0]["muscle_group"] == category["name"]


def test_multiple_categories_persist_through_active_edits_templates_and_copies(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner, coach, athlete = _gym_with_coach(client, superuser_headers, "multi-day")
    first = _category(client, owner, "سرشانه نمونه")
    second = _category(client, owner, "پا نمونه")
    entries = [_exercise(client, owner, category) for category in (first, second)]
    created = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Multi"},
    ).json()
    payload = program_payload(entries[0]["id"])
    day = payload["days"][0]
    day["category_ids"] = [first["id"], second["id"], first["id"]]
    day["category_names"] = ["Forged"]
    day["exercises"].append({**day["exercises"][0], "exercise_id": entries[1]["id"]})
    url = f"/api/v1/program-versions/{created['id']}"
    saved = client.put(url, headers=coach, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["days"][0]["category_ids"] == [first["id"], second["id"]]
    assert saved.json()["days"][0]["category_names"] == ["سرشانه نمونه", "پا نمونه"]
    assert client.post(url + "/publish", headers=coach).status_code == 200
    payload["title"] = "Edited active"
    assert client.put(url, headers=coach, json=payload).status_code == 200
    persisted = client.get(url, headers=coach).json()
    assert persisted["status"] == "ACTIVE" and persisted["title"] == "Edited active"
    raw = auth_headers(client, athlete["email"], "athlete-pass-123")
    change_password(
        client,
        raw,
        current_password="athlete-pass-123",
        new_password="athlete-pass-456",
    )
    athlete_headers = gym_headers(
        client,
        email=athlete["email"],
        password="athlete-pass-456",
        gym_id=gym["id"],
    )
    assert client.get(url, headers=athlete_headers).json()["title"] == "Edited active"
    assert client.put(url, headers=athlete_headers, json=payload).status_code == 403
    fresh = client.post(
        f"/api/v1/athletes/{athlete['user_id']}/programs",
        headers=coach,
        json={"title": "Fresh"},
    ).json()
    assert fresh["days"] == [] and fresh["goal"] is None and fresh["start_date"] is None
    day["category_ids"] = [first["id"]]
    rejected = client.put(url, headers=coach, json=payload)
    assert rejected.status_code == 400
    assert len(client.get(url, headers=coach).json()["days"][0]["exercises"]) == 2
    copied = client.post(url + "/new-draft", headers=coach).json()
    assert copied["days"][0]["category_names"] == ["سرشانه نمونه", "پا نمونه"]
    template = client.post(
        url + "/save-as-template", headers=coach, json={"name": "Multi template"}
    )
    assert template.status_code == 200, template.text
    assert template.json()["days"][0]["category_names"] == ["سرشانه نمونه", "پا نمونه"]
    assert client.post(url + "/archive", headers=coach).status_code == 200
    assert client.put(url, headers=coach, json=payload).status_code == 400
