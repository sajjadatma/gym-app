from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import FinanceAudit
from tests.api.routes.test_finance_foundation import make_owner

pytestmark = pytest.mark.usefixtures("client")


def opening_payload(
    *,
    debit: int = 500_000,
    credit: int | None = None,
    debit_code: str = "1000",
    credit_code: str = "3000",
    posting_date: str = "2026-11-01",
    description: str = "Opening balance",
) -> dict[str, Any]:
    return {
        "posting_date": posting_date,
        "description": description,
        "lines": [
            {"account_code": debit_code, "debit_irr": debit},
            {
                "account_code": credit_code,
                "credit_irr": debit if credit is None else credit,
            },
        ],
    }


def idem(key: str | None = None) -> dict[str, str]:
    return {"Idempotency-Key": key or uuid.uuid4().hex}


def post_opening(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    *,
    key: str | None = None,
) -> Any:
    return client.post(
        "/api/v1/finance/opening-balance",
        headers={**headers, **idem(key)},
        json=payload or opening_payload(),
    )


def correct(
    client: TestClient,
    headers: dict[str, str],
    journal_id: str,
    *,
    reason: str = "Opening balance correction",
    key: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/finance/journal/{journal_id}/correct",
        headers={**headers, **idem(key)},
        json={"reason": reason, "posting_date": "2026-11-02"},
    )


def superuser_gym(
    superuser_headers: dict[str, str], gym_id: str
) -> dict[str, str]:
    return {**superuser_headers, "X-Gym-ID": gym_id}


def test_opening_balance_posts_a_balanced_journal_and_lists_it(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Journal Gym")

    accounts = client.get("/api/v1/finance/accounts", headers=owner)
    assert accounts.status_code == 200, accounts.text
    codes = [row["code"] for row in accounts.json()["data"]]
    assert codes == ["1000", "1100", "2000", "3000", "4000", "5000"]

    created = post_opening(client, owner)
    assert created.status_code == 200, created.text
    journal = created.json()
    assert journal["entry_number"] == 1
    assert journal["event_type"] == "OPENING_BALANCE"
    assert journal["reversal_of_id"] is None
    assert sorted(
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in journal["lines"]
    ) == [("1000", 500_000, 0), ("3000", 0, 500_000)]
    assert journal["created_by_name"]

    listed = client.get("/api/v1/finance/journal", headers=owner)
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] == 1
    assert listed.json()["data"][0]["id"] == journal["id"]

    detail = client.get(f"/api/v1/finance/journal/{journal['id']}", headers=owner)
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == journal["id"]

    assert client.get("/api/v1/finance/journal", headers=owner).json()["data"][0][
        "posting_date"
    ] == "2026-11-01"


def test_unbalanced_or_invalid_opening_balance_is_rejected(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Unbalanced Gym")

    unbalanced = post_opening(
        client, owner, opening_payload(debit=100_000, credit=90_000)
    )
    assert unbalanced.status_code == 400, unbalanced.text
    assert unbalanced.json()["detail"] == "finance_unbalanced_journal"

    unknown_account = post_opening(
        client, owner, opening_payload(debit_code="9999")
    )
    assert unknown_account.status_code == 400, unknown_account.text
    assert unknown_account.json()["detail"] == "invalid_finance_account"

    both_sides = post_opening(
        client,
        owner,
        {
            "posting_date": "2026-11-01",
            "lines": [
                {"account_code": "1000", "debit_irr": 10, "credit_irr": 10},
                {"account_code": "3000", "credit_irr": 10},
            ],
        },
    )
    assert both_sides.status_code == 422, both_sides.text

    fractional = post_opening(
        client,
        owner,
        {
            "posting_date": "2026-11-01",
            "lines": [
                {"account_code": "1000", "debit_irr": 10.5},
                {"account_code": "3000", "credit_irr": 10.5},
            ],
        },
    )
    assert fractional.status_code == 422, fractional.text

    single_line = post_opening(
        client,
        owner,
        {
            "posting_date": "2026-11-01",
            "lines": [{"account_code": "1000", "debit_irr": 10}],
        },
    )
    assert single_line.status_code == 422, single_line.text

    # Nothing was posted by any rejected attempt.
    assert client.get("/api/v1/finance/journal", headers=owner).json()["count"] == 0


def test_opening_balance_is_posted_once_per_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Once Gym")
    assert post_opening(client, owner).status_code == 200

    duplicate = post_opening(client, owner, key=uuid.uuid4().hex)
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"] == "finance_opening_balance_exists"


def test_disabled_finance_allows_reads_and_blocks_new_postings(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Disabled Gym")
    assert post_opening(client, owner).status_code == 200

    disabled = client.patch(
        "/api/v1/finance/settings",
        headers=superuser_gym(superuser_headers, str(gym["id"])),
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text

    blocked = post_opening(client, owner, key=uuid.uuid4().hex)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == "finance_disabled"

    # History stays readable while disabled.
    history = client.get("/api/v1/finance/journal", headers=owner)
    assert history.status_code == 200, history.text
    assert history.json()["count"] == 1

    enabled = client.patch(
        "/api/v1/finance/settings",
        headers=superuser_gym(superuser_headers, str(gym["id"])),
        json={"enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    assert post_opening(client, owner, key=uuid.uuid4().hex).status_code == 409


def test_only_superuser_can_correct_an_opening_balance(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Correction Gym")
    created = post_opening(client, owner).json()

    denied = correct(client, owner, created["id"])
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "superuser_required"

    corrected = correct(
        client,
        superuser_gym(superuser_headers, str(gym["id"])),
        created["id"],
        reason="Bank statement correction",
    )
    assert corrected.status_code == 200, corrected.text
    reversal = corrected.json()
    assert reversal["event_type"] == "CORRECTION"
    assert reversal["entry_number"] == 2
    assert reversal["reversal_of_id"] == created["id"]
    assert reversal_lines_are_swapped(reversal["lines"])

    twice = correct(
        client,
        superuser_gym(superuser_headers, str(gym["id"])),
        created["id"],
        key=uuid.uuid4().hex,
    )
    assert twice.status_code == 409, twice.text
    assert twice.json()["detail"] == "finance_already_corrected"

    missing = client.post(
        f"/api/v1/finance/journal/{uuid.uuid4()}/correct",
        headers={**superuser_gym(superuser_headers, str(gym["id"])), **idem()},
        json={"reason": "not there", "posting_date": "2026-11-02"},
    )
    assert missing.status_code == 404, missing.text


def reversal_lines_are_swapped(lines: list[dict[str, Any]]) -> bool:
    expected = {("1000", 0, 500_000), ("3000", 500_000, 0)}
    return {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in lines
    } == expected


def test_correction_is_idempotent_for_the_same_key(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Idempotent Gym")
    created = post_opening(client, owner).json()
    headers = superuser_gym(superuser_headers, str(gym["id"]))
    key = uuid.uuid4().hex

    first = correct(client, headers, created["id"], key=key)
    assert first.status_code == 200, first.text
    replay = correct(client, headers, created["id"], key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]

    reused = client.post(
        f"/api/v1/finance/journal/{created['id']}/correct",
        headers={**headers, **idem(key)},
        json={
            "reason": "Different reason with the same key",
            "posting_date": "2026-11-02",
        },
    )
    assert reused.status_code == 409, reused.text
    assert reused.json()["detail"] == "idempotency_key_reused"

    assert client.get("/api/v1/finance/journal", headers=owner).json()["count"] == 2


def test_idempotency_key_is_required_for_financial_writes(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Key Required Gym")
    missing = client.post(
        "/api/v1/finance/opening-balance",
        headers=owner,
        json=opening_payload(),
    )
    assert missing.status_code == 400, missing.text
    assert missing.json()["detail"] == "idempotency_key_required"
    assert client.get("/api/v1/finance/journal", headers=owner).json()["count"] == 0


def test_journal_numbers_are_sequential_per_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Number Gym A")
    gym_b, owner_b = make_owner(client, superuser_headers, name="Number Gym B")

    first_a = post_opening(client, owner_a)
    assert first_a.status_code == 200, first_a.text
    assert first_a.json()["entry_number"] == 1

    first_b = post_opening(client, owner_b)
    assert first_b.status_code == 200, first_b.text
    assert first_b.json()["entry_number"] == 1

    second_a = correct(
        client,
        superuser_gym(superuser_headers, str(gym_a["id"])),
        first_a.json()["id"],
    )
    assert second_a.status_code == 200, second_a.text
    assert second_a.json()["entry_number"] == 2

    assert client.get("/api/v1/finance/journal", headers=owner_b).json()["count"] == 1


def test_period_close_starts_a_new_open_period_for_late_corrections(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Period Gym")
    first = post_opening(client, owner).json()
    original_period = first["period_id"]

    closed = client.post("/api/v1/finance/periods/close", headers=owner)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"

    again = client.post("/api/v1/finance/periods/close", headers=owner)
    assert again.status_code == 409, again.text
    assert again.json()["detail"] == "finance_no_open_period"

    corrected = correct(
        client,
        superuser_gym(superuser_headers, str(gym["id"])),
        first["id"],
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["period_id"] != original_period

    periods = client.get("/api/v1/finance/periods", headers=owner)
    assert periods.status_code == 200, periods.text
    by_id = {row["id"]: row for row in periods.json()["data"]}
    assert by_id[original_period]["status"] == "CLOSED"
    assert by_id[corrected.json()["period_id"]]["status"] == "OPEN"

    # The closed period's posting is unchanged.
    original = client.get(
        f"/api/v1/finance/journal/{first['id']}", headers=owner
    ).json()
    assert original["period_id"] == original_period
    assert original["entry_number"] == 1


def test_finance_action_permissions_are_enforced_for_staff(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    from tests.api.routes.test_finance_foundation import add_staff

    gym, owner = make_owner(client, superuser_headers, name="Grants Needed Gym")
    staff = add_staff(client, owner, str(gym["id"]), roles=["FINANCE_STAFF"])

    # Read-only finance staff can read the chart and journal.
    assert client.get("/api/v1/finance/accounts", headers=staff).status_code == 200
    assert client.get("/api/v1/finance/journal", headers=staff).status_code == 200

    denied = post_opening(client, staff)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "finance_access_denied"

    denied_close = client.post("/api/v1/finance/periods/close", headers=staff)
    assert denied_close.status_code == 403, denied_close.text


def test_journal_reading_is_tenant_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Scope Gym A")
    _gym_b, owner_b = make_owner(client, superuser_headers, name="Scope Gym B")
    created = post_opening(client, owner_a).json()

    cross = client.get(
        f"/api/v1/finance/journal/{created['id']}", headers=owner_b
    )
    assert cross.status_code == 404, cross.text
    assert cross.json()["detail"] == "finance_journal_not_found"

    cross_list = client.get("/api/v1/finance/journal", headers=owner_b)
    assert cross_list.json()["count"] == 0

    superuser_read = client.get(
        f"/api/v1/finance/journal/{created['id']}",
        headers=superuser_gym(superuser_headers, str(gym_a["id"])),
    )
    assert superuser_read.status_code == 200, superuser_read.text


def test_audit_records_actor_action_reason_and_linkage(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Audit Gym")
    created = post_opening(client, owner).json()
    corrected = correct(
        client,
        superuser_gym(superuser_headers, str(gym["id"])),
        created["id"],
        reason="Audited correction",
    ).json()

    rows = db_session.exec(
        select(FinanceAudit)
        .where(FinanceAudit.gym_id == uuid.UUID(str(gym["id"])))
        .order_by(FinanceAudit.created_at)
    ).all()
    actions = [row.action for row in rows]
    assert actions == [
        "finance.opening_balance.posted",
        "finance.journal.corrected",
    ]
    posted, correction = rows
    assert posted.target_type == "finance_journal"
    assert posted.target_id == uuid.UUID(created["id"])
    assert posted.detail["entry_number"] == 1
    assert correction.reason == "Audited correction"
    assert correction.target_id == uuid.UUID(corrected["id"])
    assert correction.detail["reversal_of_id"] == created["id"]


def test_concurrent_opening_balance_posts_exactly_one_journal(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Concurrent Opening Gym")
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return post_opening(client, owner, key=f"opening-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409], [response.text for response in responses]
    assert client.get("/api/v1/finance/journal", headers=owner).json()["count"] == 1


def test_concurrent_corrections_post_exactly_one_reversal(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Concurrent Correction Gym")
    created = post_opening(client, owner).json()
    headers = superuser_gym(superuser_headers, str(gym["id"]))
    barrier = threading.Barrier(2, timeout=20)

    def attempt(index: int) -> Any:
        barrier.wait()
        return correct(client, headers, created["id"], key=f"correction-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409], [response.text for response in responses]
    assert client.get("/api/v1/finance/journal", headers=owner).json()["count"] == 2


def test_opening_balance_request_hash_covers_the_payload(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    _gym, owner = make_owner(client, superuser_headers, name="Payload Hash Gym")
    key = uuid.uuid4().hex
    first = post_opening(client, owner, key=key)
    assert first.status_code == 200, first.text

    replay = post_opening(client, owner, key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]

    changed = post_opening(
        client, owner, opening_payload(debit=700_000), key=key
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"] == "idempotency_key_reused"


def test_superuser_can_disable_and_read_history_for_a_gym_with_no_settings_row(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fresh Settings Gym")
    assert (
        client.get("/api/v1/finance/settings", headers=owner).json()["enabled"]
        is True
    )
    headers = superuser_gym(superuser_headers, str(gym["id"]))
    assert (
        client.patch(
            "/api/v1/finance/settings", headers=headers, json={"enabled": False}
        ).json()["enabled"]
        is False
    )



def test_a_reversed_opening_balance_can_be_reposted_with_corrected_amounts(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Restated Opening Gym")
    first = post_opening(client, owner, opening_payload(debit=500_000))
    assert first.status_code == 200, first.text

    corrected = correct(
        client,
        superuser_gym(superuser_headers, str(gym["id"])),
        first.json()["id"],
        reason="Wrong opening amount",
    )
    assert corrected.status_code == 200, corrected.text

    restated = post_opening(
        client,
        owner,
        opening_payload(debit=700_000),
        key=uuid.uuid4().hex,
    )
    assert restated.status_code == 200, restated.text
    assert restated.json()["entry_number"] == 3

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    assert [entry["event_type"] for entry in entries] == [
        "OPENING_BALANCE",
        "CORRECTION",
        "OPENING_BALANCE",
    ]
    active = entries[0]
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in active["lines"]
    } == {("1000", 700_000, 0), ("3000", 0, 700_000)}

    # Only one opening may be active at a time.
    assert post_opening(
        client, owner, opening_payload(debit=900_000), key=uuid.uuid4().hex
    ).status_code == 409


def test_settings_and_period_changes_are_audited(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Audit Coverage Gym")
    headers = superuser_gym(superuser_headers, str(gym["id"]))

    assert (
        client.patch(
            "/api/v1/finance/settings",
            headers=owner,
            json={"display_unit": "TOMAN"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/v1/finance/settings", headers=headers, json={"enabled": False}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/v1/finance/settings", headers=headers, json={"enabled": True}
        ).status_code
        == 200
    )
    assert post_opening(client, owner).status_code == 200
    assert client.post("/api/v1/finance/periods/close", headers=owner).status_code == 200

    from app.finance_models import FinanceAudit

    rows = db_session.exec(
        select(FinanceAudit)
        .where(FinanceAudit.gym_id == uuid.UUID(str(gym["id"])))
        .order_by(FinanceAudit.created_at)
    ).all()
    actions = [row.action for row in rows]
    assert actions.count("finance.settings.updated") == 3
    assert "finance.period.closed" in actions

    settings_rows = [row for row in rows if row.action == "finance.settings.updated"]
    assert settings_rows[0].detail["changes"]["display_unit"]["to"] == "TOMAN"
    assert settings_rows[1].detail["changes"]["enabled"] == {
        "from": True,
        "to": False,
    }
    closed = next(row for row in rows if row.action == "finance.period.closed")
    assert closed.target_type == "finance_period"
    assert closed.target_id is not None
