from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.finance_models import FinanceAudit
from tests.api.routes.test_finance_foundation import add_staff, make_owner
from tests.utils.helpers import create_athlete, gym_headers, unique_email

pytestmark = pytest.mark.usefixtures("client")


def make_customer(
    client: TestClient, owner: dict[str, str], gym_id: str, prefix: str = "customer"
) -> str:
    coach_email = unique_email(f"{prefix}-coach")
    add_staff(
        client, owner, gym_id, roles=["COACH"], email=coach_email
    )
    coach = gym_headers(
        client, email=coach_email, password="staff-pass-456", gym_id=gym_id
    )
    coach_id = client.get("/api/v1/users/me", headers=coach).json()["id"]
    return create_athlete(
        client,
        coach,
        email=unique_email(f"{prefix}-athlete"),
        coach_user_id=coach_id,
    )["athlete"]["profile"]["user_id"]


def invoice_payload(
    customer_id: str,
    *,
    lines: list[dict[str, Any]] | None = None,
    discount: int = 0,
    installments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "customer_user_id": customer_id,
        "description": "Invoice",
        "due_date": "2026-12-01",
        "discount_irr": discount,
        "lines": lines
        or [
            {
                "kind": "PROGRAM",
                "description": "12-week program",
                "quantity": 1,
                "unit_price_irr": 1_000_000,
            }
        ],
        "installments": installments,
    }


def idem() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


def create_draft(
    client: TestClient, headers: dict[str, str], payload: dict[str, Any]
) -> Any:
    return client.post("/api/v1/finance/invoices", headers=headers, json=payload)


def issue(
    client: TestClient,
    headers: dict[str, str],
    invoice_id: str,
    *,
    posting_date: str = "2026-11-02",
    key: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/finance/invoices/{invoice_id}/issue",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json={"posting_date": posting_date},
    )


def void(
    client: TestClient,
    headers: dict[str, str],
    invoice_id: str,
    *,
    reason: str = "Issued in error",
    key: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/finance/invoices/{invoice_id}/void",
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json={"reason": reason, "posting_date": "2026-11-03"},
    )


def test_catalog_is_gym_scoped_and_permissioned(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Catalog Gym A")
    _gym_b, owner_b = make_owner(client, superuser_headers, name="Catalog Gym B")

    created = client.post(
        "/api/v1/finance/catalog",
        headers=owner_a,
        json={
            "name": "ماهانه بدنسازی",
            "kind": "MEMBERSHIP",
            "default_price_irr": 2_500_000,
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["kind"] == "MEMBERSHIP"

    listed = client.get("/api/v1/finance/catalog", headers=owner_a)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["data"]] == [item["id"]]

    updated = client.patch(
        f"/api/v1/finance/catalog/{item['id']}",
        headers=owner_a,
        json={"default_price_irr": 3_000_000, "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["default_price_irr"] == 3_000_000
    assert updated.json()["is_active"] is False

    cross = client.patch(
        f"/api/v1/finance/catalog/{item['id']}",
        headers=owner_b,
        json={"name": "Hijacked"},
    )
    assert cross.status_code == 404, cross.text
    assert client.get("/api/v1/finance/catalog", headers=owner_b).json()["count"] == 0

    staff = add_staff(client, owner_a, str(gym_a["id"]), roles=["FINANCE_STAFF"])
    denied = client.post(
        "/api/v1/finance/catalog",
        headers=staff,
        json={"name": "بدون مجوز", "kind": "SERVICE", "default_price_irr": 1},
    )
    assert denied.status_code == 403, denied.text

    staff_id = client.get("/api/v1/users/me", headers=staff).json()["id"]
    granted = client.put(
        f"/api/v1/finance/grants/{staff_id}",
        headers=owner_a,
        json={"grants": [{"permission": "finance.catalog.manage"}]},
    )
    assert granted.status_code == 200, granted.text
    allowed = client.post(
        "/api/v1/finance/catalog",
        headers=staff,
        json={"name": "خدمت", "kind": "SERVICE", "default_price_irr": 500_000},
    )
    assert allowed.status_code == 200, allowed.text


def test_issue_assigns_a_per_gym_sequence_and_posts_a_balanced_journal(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Invoice Gym A")
    gym_b, owner_b = make_owner(client, superuser_headers, name="Invoice Gym B")
    customer_a = make_customer(client, owner_a, str(gym_a["id"]))
    customer_b = make_customer(client, owner_b, str(gym_b["id"]))

    first = create_draft(client, owner_a, invoice_payload(customer_a))
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "DRAFT"
    assert first.json()["invoice_number"] is None
    assert first.json()["total_irr"] == 1_000_000
    assert first.json()["balance_irr"] == 1_000_000

    issued = issue(client, owner_a, first.json()["id"])
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "ISSUED"
    assert issued.json()["invoice_number"] == 1
    assert issued.json()["issue_date"] == "2026-11-02"

    second = create_draft(client, owner_a, invoice_payload(customer_a))
    second_issued = issue(client, owner_a, second.json()["id"])
    assert second_issued.json()["invoice_number"] == 2

    other = create_draft(client, owner_b, invoice_payload(customer_b))
    other_issued = issue(client, owner_b, other.json()["id"])
    assert other_issued.json()["invoice_number"] == 1

    # The invoice journal is linked through its source reference.
    entries = client.get("/api/v1/finance/journal", headers=owner_a).json()["data"]
    invoice_entries = [
        entry for entry in entries if entry["event_type"] == "INVOICE_ISSUED"
    ]
    assert len(invoice_entries) == 2
    entry = next(
        item for item in invoice_entries if item["source_id"] == first.json()["id"]
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in entry["lines"]
    } == {("1100", 1_000_000, 0), ("4000", 0, 1_000_000)}

    again = issue(client, owner_a, first.json()["id"])
    assert again.status_code == 409, again.text
    assert again.json()["detail"] == "invoice_not_draft"


def test_drafts_are_editable_and_issued_invoices_are_immutable(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Draft Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    draft = create_draft(client, owner, invoice_payload(customer)).json()

    updated = client.patch(
        f"/api/v1/finance/invoices/{draft['id']}",
        headers=owner,
        json=invoice_payload(
            customer,
            lines=[
                {
                    "kind": "PACK",
                    "description": "10 sessions",
                    "quantity": 10,
                    "unit_price_irr": 200_000,
                }
            ],
        ),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["total_irr"] == 2_000_000

    discarded = client.delete(
        f"/api/v1/finance/invoices/{draft['id']}", headers=owner
    )
    assert discarded.status_code == 200, discarded.text
    assert client.get(
        f"/api/v1/finance/invoices/{draft['id']}", headers=owner
    ).status_code == 404

    issued = issue(
        client, owner, create_draft(client, owner, invoice_payload(customer)).json()["id"]
    ).json()

    patch_issued = client.patch(
        f"/api/v1/finance/invoices/{issued['id']}",
        headers=owner,
        json=invoice_payload(customer),
    )
    assert patch_issued.status_code == 409, patch_issued.text
    assert patch_issued.json()["detail"] == "invoice_not_draft"

    delete_issued = client.delete(
        f"/api/v1/finance/invoices/{issued['id']}", headers=owner
    )
    assert delete_issued.status_code == 409, delete_issued.text


def test_bundle_discount_proration_is_exact_to_the_rial(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Discount Gym")
    customer = make_customer(client, owner, str(gym["id"]))

    # Three one-rial lines with a two-rial discount: every share must fit
    # inside its line and the payables must sum to the invoice total.
    draft = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            discount=2,
            lines=[
                {
                    "kind": "CUSTOM",
                    "description": f"line {index}",
                    "quantity": 1,
                    "unit_price_irr": 1,
                }
                for index in range(3)
            ],
        ),
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["subtotal_irr"] == 3
    assert body["discount_irr"] == 2
    assert body["total_irr"] == 1
    assert sum(line["discount_share_irr"] for line in body["lines"]) == 2
    assert all(line["payable_irr"] >= 0 for line in body["lines"])
    assert sum(line["payable_irr"] for line in body["lines"]) == 1

    line_override = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            lines=[
                {
                    "kind": "PRODUCT",
                    "description": "Product",
                    "quantity": 2,
                    "unit_price_irr": 100_000,
                    "line_discount_irr": 50_000,
                }
            ],
        ),
    )
    assert line_override.status_code == 200, line_override.text
    assert line_override.json()["subtotal_irr"] == 150_000

    too_large = create_draft(
        client,
        owner,
        invoice_payload(customer, discount=1_000_001),
    )
    assert too_large.status_code == 400, too_large.text
    assert too_large.json()["detail"] == "finance_discount_exceeds_total"

    negative_line = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            lines=[
                {
                    "kind": "PRODUCT",
                    "description": "Product",
                    "quantity": 1,
                    "unit_price_irr": 100,
                    "line_discount_irr": 101,
                }
            ],
        ),
    )
    assert negative_line.status_code == 400, negative_line.text


def test_bundle_discount_can_be_allocated_per_line(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Allocation Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    lines = [
        {
            "kind": "CUSTOM",
            "description": "first",
            "quantity": 1,
            "unit_price_irr": 10_000,
            "bundle_discount_irr": 5_000,
        },
        {
            "kind": "CUSTOM",
            "description": "second",
            "quantity": 1,
            "unit_price_irr": 10_000,
            "bundle_discount_irr": 1_000,
        },
    ]

    draft = create_draft(
        client, owner, invoice_payload(customer, discount=6_000, lines=lines)
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert [line["discount_share_irr"] for line in body["lines"]] == [5_000, 1_000]
    assert [line["payable_irr"] for line in body["lines"]] == [5_000, 9_000]
    assert body["total_irr"] == 14_000

    issued = issue(client, owner, body["id"])
    assert issued.status_code == 200, issued.text
    assert [
        line["discount_share_irr"] for line in issued.json()["lines"]
    ] == [5_000, 1_000]

    asymmetric = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            discount=6_000,
            lines=[lines[0], {**lines[1], "bundle_discount_irr": None}],
        ),
    )
    assert asymmetric.status_code == 400, asymmetric.text
    assert asymmetric.json()["detail"] == "finance_discount_allocation_mismatch"

    wrong_total = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            discount=6_000,
            lines=[
                {**lines[0], "bundle_discount_irr": 4_000},
                {**lines[1], "bundle_discount_irr": 1_000},
            ],
        ),
    )
    assert wrong_total.status_code == 400, wrong_total.text
    assert wrong_total.json()["detail"] == "finance_discount_allocation_mismatch"

    over_line = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            discount=20_000,
            lines=[
                {**lines[0], "bundle_discount_irr": 20_000},
                {**lines[1], "bundle_discount_irr": 0},
            ],
        ),
    )
    assert over_line.status_code == 400, over_line.text
    assert over_line.json()["detail"] == "finance_discount_allocation_mismatch"


def test_installments_must_match_the_invoice_total(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Installment Gym")
    customer = make_customer(client, owner, str(gym["id"]))

    mismatch = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            installments=[
                {"due_date": "2026-11-15", "amount_irr": 400_000},
                {"due_date": "2026-12-15", "amount_irr": 400_000},
            ],
        ),
    )
    assert mismatch.status_code == 400, mismatch.text
    assert mismatch.json()["detail"] == "finance_installments_mismatch"

    valid = create_draft(
        client,
        owner,
        invoice_payload(
            customer,
            installments=[
                {"due_date": "2026-11-15", "amount_irr": 400_000},
                {"due_date": "2026-12-15", "amount_irr": 600_000},
            ],
        ),
    )
    assert valid.status_code == 200, valid.text
    assert [row["amount_irr"] for row in valid.json()["installments"]] == [
        400_000,
        600_000,
    ]


def test_customer_must_be_a_member_of_the_invoice_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Customer Gym A")
    gym_b, owner_b = make_owner(client, superuser_headers, name="Customer Gym B")
    customer_b = make_customer(client, owner_b, str(gym_b["id"]))

    response = create_draft(client, owner_a, invoice_payload(customer_b))
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "invalid_invoice_customer"


def test_issue_is_idempotent_and_requires_the_key(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Idempotent Invoice Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    draft = create_draft(client, owner, invoice_payload(customer)).json()

    missing = client.post(
        f"/api/v1/finance/invoices/{draft['id']}/issue",
        headers=owner,
        json={"posting_date": "2026-11-02"},
    )
    assert missing.status_code == 422, missing.text

    key = uuid.uuid4().hex
    first = issue(client, owner, draft["id"], key=key)
    assert first.status_code == 200, first.text
    replay = issue(client, owner, draft["id"], key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["invoice_number"] == first.json()["invoice_number"]

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    assert len(
        [entry for entry in entries if entry["event_type"] == "INVOICE_ISSUED"]
    ) == 1


def test_concurrent_issues_get_unique_numbers(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Concurrent Invoice Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    drafts = [
        create_draft(client, owner, invoice_payload(customer)).json()["id"]
        for _ in range(2)
    ]
    barrier = threading.Barrier(2, timeout=20)

    def attempt(invoice_id: str) -> Any:
        barrier.wait()
        return issue(client, owner, invoice_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, drafts))

    assert [response.status_code for response in responses] == [200, 200], [
        response.text for response in responses
    ]
    numbers = sorted(response.json()["invoice_number"] for response in responses)
    assert numbers == [1, 2]


def test_void_reverses_the_issue_journal_and_records_an_audit_trail(
    client: TestClient,
    superuser_headers: dict[str, str],
    db_session: Session,
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Void Invoice Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    issued = issue(
        client, owner, create_draft(client, owner, invoice_payload(customer)).json()["id"]
    ).json()

    voided = void(client, owner, issued["id"], reason="Wrong customer")
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "VOID"
    assert voided.json()["invoice_number"] == issued["invoice_number"]
    assert voided.json()["void_reason"] == "Wrong customer"

    entries = client.get("/api/v1/finance/journal", headers=owner).json()["data"]
    reversal = next(
        entry
        for entry in entries
        if entry["event_type"] == "INVOICE_VOID"
        and entry["source_id"] == issued["id"]
    )
    assert {
        (line["account_code"], line["debit_irr"], line["credit_irr"])
        for line in reversal["lines"]
    } == {("1100", 0, 1_000_000), ("4000", 1_000_000, 0)}

    twice = void(client, owner, issued["id"])
    assert twice.status_code == 409, twice.text

    actions = [
        row.action
        for row in db_session.exec(
            select(FinanceAudit)
            .where(FinanceAudit.gym_id == uuid.UUID(str(gym["id"])))
            .order_by(FinanceAudit.created_at)
        ).all()
    ]
    assert actions.count("finance.invoice.issued") == 1
    assert actions.count("finance.invoice.voided") == 1


def test_invoice_reads_are_tenant_scoped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym_a, owner_a = make_owner(client, superuser_headers, name="Scope Invoice A")
    _gym_b, owner_b = make_owner(client, superuser_headers, name="Scope Invoice B")
    customer_a = make_customer(client, owner_a, str(gym_a["id"]))
    issued = issue(
        client, owner_a, create_draft(client, owner_a, invoice_payload(customer_a)).json()["id"]
    ).json()

    assert client.get(
        f"/api/v1/finance/invoices/{issued['id']}", headers=owner_b
    ).status_code == 404
    assert client.get("/api/v1/finance/invoices", headers=owner_b).json()["count"] == 0
    assert client.get(
        "/api/v1/finance/invoices",
        headers={**superuser_headers, "X-Gym-ID": str(gym_a["id"])},
    ).json()["count"] == 1


def test_disabled_finance_blocks_issue_but_keeps_drafts(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Disabled Invoice Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    draft = create_draft(client, owner, invoice_payload(customer)).json()

    assert (
        client.patch(
            "/api/v1/finance/settings",
            headers={**superuser_headers, "X-Gym-ID": str(gym["id"])},
            json={"enabled": False},
        ).status_code
        == 200
    )
    blocked = issue(client, owner, draft["id"])
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == "finance_disabled"

    still_draft = client.get(
        f"/api/v1/finance/invoices/{draft['id']}", headers=owner
    )
    assert still_draft.status_code == 200
    assert still_draft.json()["status"] == "DRAFT"
