# ASCORA Finance Phase 4 — Platform Monetization, Dashboards, Exports and Reminders

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Superuser-controlled platform plans, agreements and group contracts; accrue separate ASCORA subscription/commission receivables; record platform collections; expose conservative dues standing; and deliver role dashboards plus CSV exports without merging platform money into any gym ledger.

**Architecture:** Add one bounded `platform` module beside the existing `finance` module. It owns its own catalog, agreements, receivables, invoices, payments, journal, audit, sequence and idempotency records; it never writes to `finance_journal`, a gym's cash account or gym invoice numbering. The existing gym invoice/receipt flow snapshots an applicable platform fee on issue and creates a platform receivable only when money is actually confirmed collected. Superuser-only routes live under `/api/v1/platform`, while gym/coach/athlete reporting extends existing `/api/v1/finance` routes. To avoid circular imports, `platform.py` imports `finance_models`/`platform_models` only; `finance.py` may import platform service functions, and any platform read of a finance aggregate takes the already-computed value as a parameter or uses a lazy/local import.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Alembic, pytest, React 19, TypeScript, TanStack Router/Query, Vite, Playwright, Biome.

**Spec:** `docs/finance/ASCORA-FINANCE-PRD.md` — especially §2 (monetization addendum), §3 (`FR-PLAN`, `FR-FEE`, `FR-REPORT`), §4 (invariants), §12–§17, and §18 Phase 4. Decisions #5, #6, #7, #8, #9, #10, #11, #12, #23, #34, #37, #41, #44, #47, #55, #57, #58, #60, #61, #78, #84, #91, #92 and `ADD-01` are binding; #18, #30 and #46 remain deferred.

## Global Constraints

- Money is persisted as integer IRR (`BigInteger`), never binary floating point; every division uses deterministic integer math and an explicit residual policy.
- Platform money is separate from gym money. A platform receivable is not platform cash; a gym's sales are not ASCORA revenue. Never write platform fees into `finance_journal` or into a gym's `1000` cash account.
- Platform billing writes are atomic: business row + journal + audit + idempotency record commit together. Use `pg_advisory_xact_lock` with the key `platform` for platform writes, and the existing `lock_finance_gym` for gym-side fee snapshots/accruals.
- Every platform write route requires `CurrentSuperuser`; no gym admin or finance staff may read or mutate another tenant's platform billing. Gym-side report routes continue to use existing `FinanceScope` checks.
- Plans are optional: zero active plans, zero prices and commission-only must work. Never fabricate a subscription invoice or fee.
- Commission is calculated only from **confirmed collected** amounts against a snapshot taken at invoice issue. No fee on draft, unissued or voided invoices; no retroactive recalculation after an agreement changes.
- All migrations are additive and reversible. Never rewrite existing finance/invoice rows; the new snapshot columns are nullable for historical rows.
- No automatic coach clawback (#30), no attendance/usage finance input (#18), no AI/smart analytics (#46), no payment gateway, no inventory or payroll engine, no deployment.
- Preserve the current clean branch discipline: implement only after explicit Phase 4 approval, commit on `feat/ascora-finance`, do not merge or deploy.

## Review Focus

These are the failure modes the spec implies but ordinary task tests may miss. Each has an owning test below.

1. **Zero plans + commission-only** — a gym with no active subscription plan must still accrue commission only on eligible confirmed collections and must never receive a fabricated subscription invoice (`AC-35`, `AC-36`).
2. **Group invoice isolation** — one ASCORA invoice for three gyms must keep three traceable per-branch allocations and must not create merged gym journals or cash (`AC-37`).
3. **Snapshot immutability** — replacing an agreement after an invoice is issued must not change that invoice's fee, and a later receipt must use the issue-time snapshot (`AC-24`, `AC-25`, `AC-39`).
4. **Unconfirmed money** — a recorded receipt is already confirmed in this codebase, but a draft/voided invoice, an unallocated receipt or a failed/voided platform payment must never create or confirm a platform fee (`FR-FEE`, `AC-16`, `AC-29`).
5. **Overdue restrictions preserve history** — a restricted gym must still read/export its finance history, and restriction must not delete or hide posted records (`AC-38`, `AC-44`).
6. **Retry/concurrency** — duplicate subscription accrual, invoice issuance, payment recording and commission accrual must produce one row and one balanced journal (`FR-PAY`, §12.1).

---

## File Structure

**Backend**

- Create: `backend/app/platform_models.py` — all platform SQLModel tables plus public/input DTOs. Keep platform identity separate from gym finance models.
- Create: `backend/app/services/platform.py` — Superuser scope guard, locks, sequence, journal, audit, plan/agreement/fee/invoice/payment logic and report read models.
- Create: `backend/app/api/routes/platform.py` — `/api/v1/platform` Superuser API.
- Modify: `backend/app/api/main.py` — include the platform router.
- Modify: `backend/app/finance_models.py` — add the nullable platform-snapshot fields to `FinanceInvoiceLine`.
- Modify: `backend/app/services/finance.py` — snapshot at issue; accrue commission on confirmed receipt/credit; reverse commission on refund.
- Modify: `backend/app/api/routes/finance.py` — add gym report/export routes and a cross-gym coach summary route.
- Create: `backend/app/alembic/versions/f1a2b3c4d5e6_add_platform_billing.py` — additive platform schema and snapshot columns.
- Test: `backend/tests/api/routes/test_platform_plans.py`
- Test: `backend/tests/api/routes/test_platform_agreements.py`
- Test: `backend/tests/api/routes/test_platform_fees.py`
- Test: `backend/tests/api/routes/test_platform_invoices.py`
- Test: `backend/tests/api/routes/test_platform_reports.py`
- Test: `backend/tests/test_platform_migrations.py`

**Frontend**

- Create: `frontend/src/pages/PlatformFinancePage.tsx` — Superuser tabs: overview, plans, agreements, invoices, dues.
- Create: `frontend/src/pages/platform/PlatformOverviewSection.tsx`
- Create: `frontend/src/pages/platform/PlatformPlansSection.tsx`
- Create: `frontend/src/pages/platform/PlatformAgreementsSection.tsx`
- Create: `frontend/src/pages/platform/PlatformInvoicesSection.tsx`
- Create: `frontend/src/pages/platform/PlatformDuesSection.tsx`
- Create: `frontend/src/routes/_app.platform.finance.tsx`
- Modify: `frontend/src/components/AppShell.tsx` — global Superuser nav item.
- Modify: `frontend/src/pages/finance/FinanceOverviewSection.tsx` — gym dashboard cards + export.
- Modify: `frontend/src/pages/CoachEarningsPage.tsx` — cross-gym aggregate.
- Modify: `frontend/src/pages/AthleteFinancePage.tsx` — due/overdue card.
- Modify: `frontend/src/i18n.tsx` — Persian/English keys.
- Test: `frontend/tests/platform-finance.spec.ts`
- Test: `frontend/tests/finance-dashboard.spec.ts`

---

### Task 1: Platform schema, snapshot columns and migration

**Files:**
- Create: `backend/app/platform_models.py`
- Modify: `backend/app/finance_models.py:586-645`
- Create: `backend/app/alembic/versions/f1a2b3c4d5e6_add_platform_billing.py`
- Test: `backend/tests/test_platform_migrations.py`

**Interfaces:**
- Produces: `PlatformPlan`, `PlatformPlanVersion`, `PlatformGroup`, `PlatformGroupMember`, `PlatformAgreement`, `PlatformCommissionTerm`, `PlatformReceivable`, `PlatformCredit`, `PlatformInvoice`, `PlatformInvoiceLine`, `PlatformPayment`, `PlatformPaymentAllocation`, `PlatformJournal`, `PlatformJournalLine`, `PlatformAudit`, `PlatformCost`, `PlatformSequence`, `PlatformOperation`.
- Produces: `FinanceInvoiceLine.platform_agreement_id`, `.platform_agreement_version`, `.platform_allocation_status`, `.platform_snapshot`, `.platform_fee_irr`.
- Consumes: existing `Gym`, `User`, `FinanceInvoiceLine`, `FinanceInvoice`, `FinanceReceipt`, `FinanceRefund` IDs.

- [ ] **Step 1: Write the failing schema test**

```python
def test_platform_migration_creates_separate_schema_and_rolls_back(
    migrated_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_alembic_database(monkeypatch, migrated_database)
    config = _alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    tables = set(inspect(create_engine(migrated_database)).get_table_names())
    assert {
        "platform_plan",
        "platform_plan_version",
        "platform_group",
        "platform_group_member",
        "platform_agreement",
        "platform_commission_term",
        "platform_receivable",
        "platform_credit",
        "platform_invoice",
        "platform_invoice_line",
        "platform_payment",
        "platform_payment_allocation",
        "platform_journal",
        "platform_journal_line",
        "platform_audit",
        "platform_cost",
        "platform_sequence",
        "platform_operation",
    }.issubset(tables)
    with create_engine(migrated_database).connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'finance_invoice_line'"
                )
            )
        }
    assert {
        "platform_agreement_id",
        "platform_agreement_version",
        "platform_allocation_status",
        "platform_snapshot",
        "platform_fee_irr",
    }.issubset(columns)
    command.downgrade(config, "e8f0a2b4c6d8")
    command.check(config)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_platform_migrations.py`
Expected: FAIL because the platform tables do not exist.

- [ ] **Step 3: Add the models and migration**

Create `backend/app/platform_models.py` with these mandatory fields and constraints:

```python
class PlatformPlan(SQLModel, table=True):
    __tablename__ = "platform_plan"
    id: uuid.UUID
    code: str                 # unique, stable
    name: str
    is_active: bool = True
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformPlanVersion(SQLModel, table=True):
    __tablename__ = "platform_plan_version"
    __table_args__ = (
        UniqueConstraint("plan_id", "version_number", name="uq_platform_plan_version"),
        UniqueConstraint("plan_id", "effective_from", name="uq_platform_plan_effective"),
        CheckConstraint("version_number > 0", name="ck_platform_plan_version_number"),
        CheckConstraint("monthly_price_irr >= 0", name="ck_platform_plan_price"),
    )
    id: uuid.UUID
    plan_id: uuid.UUID
    version_number: int
    effective_from: date
    effective_to: date | None
    monthly_price_irr: int       # BigInteger, 0 allowed
    limits: dict[str, Any]       # active_athletes, staff_seats, advanced_finance, sms, storage_mb
    status: str                  # DRAFT, ACTIVE, RETIRED
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformGroup(SQLModel, table=True):
    __tablename__ = "platform_group"
    id: uuid.UUID
    name: str                    # unique
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformGroupMember(SQLModel, table=True):
    __tablename__ = "platform_group_member"
    __table_args__ = (UniqueConstraint("group_id", "gym_id", name="uq_platform_group_gym"),)
    id: uuid.UUID
    group_id: uuid.UUID
    gym_id: uuid.UUID
    allocation_bp: int = 10000   # 0..10000, group invoice attribution
    created_at: datetime

class PlatformAgreement(SQLModel, table=True):
    __tablename__ = "platform_agreement"
    __table_args__ = (
        CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_agreement_scope",
        ),
        CheckConstraint(
            "mode IN ('FREE', 'SUBSCRIPTION', 'COMMISSION', 'HYBRID', 'CUSTOM')",
            name="ck_platform_agreement_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'EFFECTIVE', 'REPLACED', 'DISABLED')",
            name="ck_platform_agreement_status",
        ),
        UniqueConstraint("gym_id", "effective_from", "version", name="uq_platform_agreement_gym_version"),
    )
    id: uuid.UUID
    gym_id: uuid.UUID | None
    group_id: uuid.UUID | None
    version: int
    supersedes_id: uuid.UUID | None
    mode: str
    status: str
    effective_from: date
    effective_to: date | None
    plan_version_id: uuid.UUID | None
    subscription_amount_irr: int = 0
    billing_interval: str = "MONTHLY"
    volume_discount_bp: int = 0
    grace_days: int = 7
    restrict_after_days: int = 21
    created_by_id: uuid.UUID | None
    created_at: datetime
    activated_at: datetime | None

class PlatformCommissionTerm(SQLModel, table=True):
    __tablename__ = "platform_commission_term"
    __table_args__ = (
        CheckConstraint("kind IN ('ANY', 'MEMBERSHIP', 'PROGRAM', 'SESSION', 'PACK', 'PRODUCT', 'SERVICE', 'CUSTOM')", name="ck_platform_term_kind"),
        CheckConstraint("acquisition_source IN ('ANY', 'GYM', 'ASCORA')", name="ck_platform_term_source"),
        CheckConstraint("basis IN ('PERCENT', 'FIXED', 'PERCENT_PLUS_FIXED')", name="ck_platform_term_basis"),
        CheckConstraint("percent_bp >= 0 AND percent_bp <= 10000", name="ck_platform_term_percent"),
        CheckConstraint("fixed_irr >= 0 AND max_fee_irr >= 0", name="ck_platform_term_fixed"),
    )
    id: uuid.UUID
    agreement_id: uuid.UUID
    kind: str
    acquisition_source: str = "ANY"
    basis: str
    percent_bp: int = 0
    fixed_irr: int = 0
    max_fee_irr: int = 0        # 0 = no explicit cap
    created_at: datetime

class PlatformReceivable(SQLModel, table=True):
    __tablename__ = "platform_receivable"
    __table_args__ = (
        CheckConstraint("amount_irr >= 0", name="ck_platform_receivable_amount"),
        CheckConstraint("status IN ('OPEN', 'INVOICED', 'PARTIAL', 'PAID', 'VOID')", name="ck_platform_receivable_status"),
        UniqueConstraint("source_key", name="uq_platform_receivable_source"),
    )
    id: uuid.UUID
    gym_id: uuid.UUID
    agreement_id: uuid.UUID | None
    source_type: str            # COMMISSION, SUBSCRIPTION, ADJUSTMENT
    source_id: uuid.UUID | None # invoice line / receipt / agreement period
    source_key: str
    amount_irr: int
    paid_irr: int = 0
    due_on: date
    status: str = "OPEN"
    snapshot: dict[str, Any]
    created_at: datetime

class PlatformCredit(SQLModel, table=True):
    __tablename__ = "platform_credit"
    __table_args__ = (
        CheckConstraint("amount_irr >= 0 AND remaining_irr >= 0", name="ck_platform_credit_amount"),
        CheckConstraint("remaining_irr <= amount_irr", name="ck_platform_credit_remaining"),
        CheckConstraint("status IN ('OPEN', 'PARTIAL', 'APPLIED', 'VOID')", name="ck_platform_credit_status"),
    )
    id: uuid.UUID
    gym_id: uuid.UUID
    source_type: str            # REFUND, MANUAL
    source_id: uuid.UUID | None
    amount_irr: int
    remaining_irr: int
    status: str = "OPEN"
    reason: str | None
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformInvoice(SQLModel, table=True):
    __tablename__ = "platform_invoice"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_platform_invoice_number"),
        CheckConstraint("status IN ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'VOID')", name="ck_platform_invoice_status"),
        CheckConstraint("total_irr >= 0 AND discount_irr >= 0", name="ck_platform_invoice_total"),
        CheckConstraint(
            "(gym_id IS NOT NULL AND group_id IS NULL) OR "
            "(gym_id IS NULL AND group_id IS NOT NULL)",
            name="ck_platform_invoice_scope",
        ),
    )
    id: uuid.UUID
    gym_id: uuid.UUID | None
    group_id: uuid.UUID | None
    invoice_number: int
    period_start: date
    period_end: date
    issued_on: date
    due_on: date
    status: str
    discount_irr: int = 0
    total_irr: int
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformInvoiceLine(SQLModel, table=True):
    __tablename__ = "platform_invoice_line"
    __table_args__ = (
        UniqueConstraint("invoice_id", "gym_id", "source_key", name="uq_platform_invoice_line_source"),
        CheckConstraint("gross_irr >= 0 AND discount_irr >= 0 AND amount_irr >= 0", name="ck_platform_invoice_line_amount"),
    )
    id: uuid.UUID
    invoice_id: uuid.UUID
    gym_id: uuid.UUID
    receivable_id: uuid.UUID
    source_key: str
    description: str
    gross_irr: int
    discount_irr: int = 0
    amount_irr: int
    paid_irr: int = 0

class PlatformPayment(SQLModel, table=True):
    __tablename__ = "platform_payment"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="ck_platform_payment_amount"),
        CheckConstraint("method IN ('CASH', 'POS', 'TRANSFER')", name="ck_platform_payment_method"),
        UniqueConstraint("operation_key", name="uq_platform_payment_operation"),
    )
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount_irr: int
    method: str
    reference: str | None
    received_on: date
    operation_key: str
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformPaymentAllocation(SQLModel, table=True):
    __tablename__ = "platform_payment_allocation"
    __table_args__ = (UniqueConstraint("payment_id", "invoice_line_id", name="uq_platform_payment_line"),)
    id: uuid.UUID
    payment_id: uuid.UUID
    invoice_line_id: uuid.UUID
    amount_irr: int

class PlatformJournal(SQLModel, table=True):
    __tablename__ = "platform_journal"
    __table_args__ = (UniqueConstraint("entry_number", name="uq_platform_journal_entry"),)
    id: uuid.UUID
    entry_number: int
    posting_date: date
    event_type: str             # PLATFORM_FEE, PLATFORM_FEE_REVERSAL, PLATFORM_PAYMENT
    description: str
    source_type: str
    source_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformJournalLine(SQLModel, table=True):
    __tablename__ = "platform_journal_line"
    __table_args__ = (
        CheckConstraint("debit_irr >= 0 AND credit_irr >= 0", name="ck_platform_journal_line_amounts"),
        CheckConstraint("(debit_irr = 0) <> (credit_irr = 0)", name="ck_platform_journal_line_side"),
    )
    id: uuid.UUID
    journal_id: uuid.UUID
    account_code: str           # 1000 cash, 1100 receivable, 4000 subscription, 4100 commission, 4200 custom
    debit_irr: int
    credit_irr: int
    memo: str | None

class PlatformAudit(SQLModel, table=True):
    __tablename__ = "platform_audit"
    id: uuid.UUID
    gym_id: uuid.UUID | None
    group_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    reason: str | None
    detail: dict[str, Any]
    created_at: datetime

class PlatformCost(SQLModel, table=True):
    __tablename__ = "platform_cost"
    __table_args__ = (CheckConstraint("amount_irr >= 0", name="ck_platform_cost_amount"),)
    id: uuid.UUID
    gym_id: uuid.UUID | None
    category: str
    description: str | None
    amount_irr: int
    incurred_on: date
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformSequence(SQLModel, table=True):
    __tablename__ = "platform_sequence"
    __table_args__ = (UniqueConstraint("doc_type", name="uq_platform_sequence_doc"),)
    id: uuid.UUID
    doc_type: str
    last_value: int = 0

class PlatformOperation(SQLModel, table=True):
    __tablename__ = "platform_operation"
    __table_args__ = (UniqueConstraint("operation_key", name="uq_platform_operation_key"),)
    id: uuid.UUID
    operation_key: str
    request_hash: str
    result_type: str
    result_id: uuid.UUID
    created_at: datetime
```

Add the five nullable snapshot fields to `FinanceInvoiceLine` in `backend/app/finance_models.py` exactly:

```python
platform_agreement_id: uuid.UUID | None = Field(
    default=None,
    foreign_key="platform_agreement.id",
    ondelete="RESTRICT",
    index=True,
)
platform_agreement_version: int | None = Field(default=None)
platform_allocation_status: str = Field(default="NOT_APPLICABLE", max_length=20)
platform_snapshot: dict[str, Any] | None = Field(
    default=None, sa_column=Column(JSON, nullable=True)
)
platform_fee_irr: int = Field(
    default=0, sa_column=Column(BigInteger, nullable=False)
)
```

Create the Alembic migration `f1a2b3c4d5e6_add_platform_billing.py` with:
- `down_revision = "e8f0a2b4c6d8"`;
- all tables above (use `sa.Uuid()`, `BigInteger`, `JSON`, `UTCDateTime`);
- `op.add_column("finance_invoice_line", ...)` for the five snapshot fields;
- an `op.create_foreign_key` for `platform_agreement_id` with `ondelete="RESTRICT"`;
- a `downgrade()` that drops the FK/columns first, then the platform tables in reverse dependency order.

- [ ] **Step 4: Run migration tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_platform_migrations.py tests/test_finance_migrations.py`
Expected: PASS, including upgrade→downgrade→upgrade and `alembic check` with no new upgrade operations.

- [ ] **Step 5: Commit**

```bash
git add backend/app/platform_models.py backend/app/finance_models.py backend/app/alembic/versions/f1a2b3c4d5e6_add_platform_billing.py backend/tests/test_platform_migrations.py
git commit -m "feat(platform): add separate platform billing schema"
```

---

### Task 2: Superuser plan catalog

**Files:**
- Create: `backend/app/services/platform.py`
- Create: `backend/app/api/routes/platform.py`
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/api/routes/test_platform_plans.py`

**Interfaces:**
- Produces: `PlatformScope` dataclass with `require_superuser()` and `ensure_platform_enabled()` (platform billing always exists; this only centralizes audit/actor data).
- Produces: `create_plan(session, *, actor, body) -> PlatformPlanPublic`, `create_plan_version(...)`, `activate_plan_version(...)`, `retire_plan_version(...)`, `list_plans(...) -> PlatformPlansPublic`.
- Produces: routes `GET/POST /api/v1/platform/plans`, `POST /api/v1/platform/plans/{plan_id}/versions`, `POST /api/v1/platform/plans/{plan_id}/versions/{version_id}/activate`, `POST /api/v1/platform/plans/{plan_id}/versions/{version_id}/retire`, `GET /api/v1/platform/plans/{plan_id}/versions/{version_id}/usage`.
- Produces: `PlatformPlanUsagePublic` with `active_athletes`, `staff_seats`, `limit_status` (`OK`/`EXCEEDED`) and the configured limits. Usage is read-only counting; enforcement of core gym operations is intentionally deferred (numeric limits are pilot configuration, and no limit may hide or delete posted finance history).
- Consumes: `CurrentSuperuser`, `SessionDep`; `PlatformAudit`; `PlatformPlan`/`PlatformPlanVersion`.

- [ ] **Step 1: Write the failing tests**

```python
def test_superuser_can_create_zero_price_plan_and_no_active_plan_is_valid(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    empty = client.get("/api/v1/platform/plans", headers=superuser_headers)
    assert empty.status_code == 200
    assert empty.json()["data"] == []

    gym, owner = make_owner(client, superuser_headers, name="Plan Gym")
    denied = client.get("/api/v1/platform/plans", headers=owner)
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/platform/plans",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "code": "FREE",
            "name": "Free",
            "version": {
                "effective_from": "2026-11-01",
                "monthly_price_irr": 0,
                "limits": {"active_athletes": 20, "staff_seats": 2,
                           "advanced_finance": False, "sms": 0, "storage_mb": 100},
            },
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["versions"][0]["status"] == "ACTIVE"
    assert created.json()["versions"][0]["monthly_price_irr"] == 0
    usage = client.get(
        f"/api/v1/platform/plans/{created.json()['id']}/versions/"
        f"{created.json()['versions'][0]['id']}/usage",
        headers=superuser_headers,
    )
    assert usage.status_code == 200
    assert usage.json()["limit_status"] in {"OK", "EXCEEDED"}
    assert usage.json()["limits"]["active_athletes"] == 20

def test_plan_versions_are_effective_dated_immutable_and_retire_without_history_loss(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # create plan with 2026-01-01 version, then a 2026-06-01 replacement
    # assert old version still readable, active version changes at the date
    # assert editing an ACTIVE version returns 409 plan_version_immutable
    # assert retiring leaves historical versions and returns zero active plans
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_plans.py`
Expected: FAIL because `/api/v1/platform/plans` is not registered.

- [ ] **Step 3: Implement service and routes**

`backend/app/services/platform.py`:

```python
@dataclass(frozen=True)
class PlatformScope:
    actor: User

    def require_superuser(self) -> None:
        if not self.actor.is_superuser:
            raise HTTPException(status_code=403, detail="superuser_required")

def _lock_platform(session: Session) -> None:
    session.connection().execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('platform', 0))")
    )

def _record_platform_audit(session: Session, *, actor: User, action: str,
                           target_type: str, target_id: uuid.UUID | None,
                           gym_id: uuid.UUID | None = None,
                           group_id: uuid.UUID | None = None,
                           reason: str | None = None,
                           detail: dict[str, Any] | None = None) -> PlatformAudit: ...
```

Plan creation creates the plan plus its first `PlatformPlanVersion` in one transaction. Validation:
- `code` normalized uppercase, unique (409 `platform_plan_code_exists`);
- `monthly_price_irr >= 0` and `<= MAX_FINANCE_IRR`;
- `limits` keys restricted to `active_athletes`, `staff_seats`, `advanced_finance`, `sms`, `storage_mb`; integer/boolean values non-negative;
- `effective_to` must be `>= effective_from` when present;
- new version effective date must not overlap an existing version for the same plan (409 `platform_plan_period_overlap`);
- an `ACTIVE` version is immutable; changing it requires a new version;
- retire marks `status="RETIRED"` and never deletes rows; zero active versions is valid.

All create/version/activate/retire writes require an `Idempotency-Key` header and use `PlatformOperation` (`operation_key`, `request_hash`, `result_type`, `result_id`) so a retry returns the original result and a reused key with a different payload returns 409 `idempotency_key_reused`. Routes use `CurrentSuperuser` and return the public DTOs. Add `platform.router` to `backend/app/api/main.py`.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_plans.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/app/api/main.py backend/tests/api/routes/test_platform_plans.py
git commit -m "feat(platform): add superuser plan catalog"
```

---

### Task 3: Agreements, groups and commission terms

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/api/routes/platform.py`
- Test: `backend/tests/api/routes/test_platform_agreements.py`

**Interfaces:**
- Produces: `create_group(...)`, `add_group_member(...)`, `create_agreement(...)`, `activate_agreement(...)`, `disable_agreement(...)`, `list_agreements(...) -> PlatformAgreementsPublic`.
- Produces: routes `GET/POST /api/v1/platform/groups`, `POST /api/v1/platform/groups/{group_id}/members`, `GET/POST /api/v1/platform/agreements`, `POST /api/v1/platform/agreements/{agreement_id}/activate`, `POST /api/v1/platform/agreements/{agreement_id}/disable`.
- Consumes: Task 2 plan versions; `PlatformAgreement`, `PlatformCommissionTerm`, `PlatformGroup`, `PlatformGroupMember`.

- [ ] **Step 1: Write the failing tests**

```python
def test_commission_only_agreement_works_with_zero_subscription_plans(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Commission Gym")
    # no plans exist
    created = client.post(
        "/api/v1/platform/agreements",
        headers={**superuser_headers, "Idempotency-Key": uuid.uuid4().hex},
        json={
            "gym_id": str(gym["id"]),
            "mode": "COMMISSION",
            "effective_from": "2026-11-01",
            "subscription_amount_irr": 0,
            "terms": [
                {"kind": "MEMBERSHIP", "acquisition_source": "GYM",
                 "basis": "PERCENT", "percent_bp": 1000},
                {"kind": "ANY", "acquisition_source": "ASCORA",
                 "basis": "PERCENT", "percent_bp": 500},
            ],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["mode"] == "COMMISSION"
    assert created.json()["plan_version_id"] is None
    assert created.json()["status"] == "DRAFT"
    activated = client.post(
        f"/api/v1/platform/agreements/{created.json()['id']}/activate",
        headers=superuser_headers,
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "EFFECTIVE"

def test_group_agreement_keeps_per_branch_members_and_volume_discount(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # create 3 gyms, group with 3 members and allocation_bp summing to 10000,
    # create group agreement mode HYBRID with volume_discount_bp=500
    # assert each member is traceable and no gym ledger row is created
    ...

def test_agreement_rejects_bad_modes_terms_overlap_and_non_superuser(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # gym admin gets 403; SUBSCRIPTION without a plan version -> 400
    # percent_bp > 10000 -> 422; both gym_id and group_id -> 400
    # effective_to < effective_from -> 400
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_agreements.py`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement agreement lifecycle**

Validation:
- exactly one of `gym_id`/`group_id` is present;
- `mode` in the five approved modes; `SUBSCRIPTION` and `HYBRID` require a non-retired plan version; `FREE` and `COMMISSION` must have no subscription amount (force 0); `CUSTOM` may have either;
- if `subscription_amount_irr` is 0 and mode requires subscription, use the plan version price; allow an explicit zero/custom override with audit;
- commission terms only for `COMMISSION`, `HYBRID` and `CUSTOM`; at least one term for `COMMISSION`; `PERCENT` uses `percent_bp`; `FIXED` uses `fixed_irr`; `PERCENT_PLUS_FIXED` uses both; `max_fee_irr` caps the per-line fee when > 0;
- group membership allocation_bp values are 0..10000 and sum to 10000 for a group agreement; volume discount 0..10000;
- all create/activate/disable writes require `Idempotency-Key` and use `PlatformOperation`;
- activation serializes on `_lock_platform`, marks prior effective agreement for the same scope as `REPLACED`, and sets the new row `EFFECTIVE`; no historical term is edited;
- disable sets `DISABLED` but preserves all rows and receivables.

Store a JSON snapshot builder `_agreement_snapshot(agreement)` used by Task 4; it must include `mode`, `plan_version_id`, `subscription_amount_irr`, `volume_discount_bp`, and the ordered terms.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_agreements.py tests/api/routes/test_platform_plans.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_agreements.py
git commit -m "feat(platform): add agreements, groups and commission terms"
```

---

### Task 4: Snapshot commission at issue and accrue on confirmed collections

**Files:**
- Modify: `backend/app/finance_models.py` (`FinanceInvoiceLinePublic`)
- Modify: `backend/app/services/finance.py` (`issue_invoice`, `create_receipt`, `apply_customer_credit`, `invoice_public`)
- Modify: `backend/app/services/platform.py` (fee formatting/accrual helpers)
- Test: `backend/tests/api/routes/test_platform_fees.py`

**Interfaces:**
- Produces: `_snapshot_invoice_platform(session, *, invoice, issue_date)` in `finance.py`.
- Produces: `_platform_fee_for_portion(snapshot: dict[str, Any], portion_irr: int, line_payable_irr: int) -> int` in `platform.py`.
- Produces: `_create_platform_commission(session, *, scope, actor, invoice, amount_irr, received_on, receipt_id=None, credit_movement_id=None, source_prefix) -> int`.
- Produces: `FinanceInvoiceLinePublic.platform_allocation_status: str` and `.platform_fee_irr: int` (the raw snapshot JSON stays server-side).
- Consumes: Task 3 `_agreement_snapshot`; Task 1 `FinanceInvoiceLine` platform fields and `PlatformReceivable`.

- [ ] **Step 1: Write the failing fee tests**

```python
def test_commission_only_accrues_on_confirmed_collection_from_issue_snapshot(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym, owner = make_owner(client, superuser_headers, name="Fee Gym")
    customer = make_customer(client, owner, str(gym["id"]))
    agreement = create_commission_agreement(client, superuser_headers, gym["id"], percent_bp=1000)
    invoice = issued_invoice(client, owner, customer, amount=1_000_000)
    line = client.get(f"/api/v1/finance/invoices/{invoice['id']}", headers=owner).json()["lines"][0]
    assert line["platform_allocation_status"] == "SNAPSHOTTED"
    assert line["platform_fee_irr"] == 100_000
    receipt = record_receipt(client, owner, receipt_payload(customer, amount=400_000,
                                                           allocations=[(invoice["id"], 400_000)]))
    assert receipt.status_code == 200
    receivables = client.get("/api/v1/platform/receivables?gym_id=" + str(gym["id"]),
                             headers=superuser_headers).json()["data"]
    assert sum(row["amount_irr"] for row in receivables) == 40_000

def test_commission_uses_exact_issue_snapshot_after_agreement_replacement(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # issue at 10%; replace with 20%; collect; fee remains 10%
    ...

def test_fixed_fee_is_proportional_across_installments_and_capped(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # fixed 100_000 on a 1_000_000 line; 400k and 600k receipts produce
    # 40_000 then 60_000, never more than 100_000
    ...

def test_no_fee_for_free_subscription_or_unmatched_source_and_no_duplicate_on_retry(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # FREE agreement -> NOT_APPLICABLE; subscription-only -> no commission
    # ASCORA-source term does not match GYM invoice; same receipt key replays
    # draft invoice has no platform snapshot; voiding cannot create a fee
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py`
Expected: FAIL because no platform snapshot/accrual exists.

- [ ] **Step 3: Implement snapshot and accrual**

Expose `platform_allocation_status` and `platform_fee_irr` in `FinanceInvoiceLinePublic` and populate them in `invoice_public` so tests/UI can verify the snapshot without exposing the raw JSON.

In `issue_invoice`, call `_snapshot_invoice_platform` immediately after `_snapshot_invoice_coaches`. Selection:
- effective `PlatformAgreement` for the gym (`gym_id`) or an effective group agreement whose `PlatformGroupMember` contains the gym, with `effective_from <= issue_date` and `effective_to` null or `>= issue_date`, ordered by `version` descending;
- mode `FREE` or `SUBSCRIPTION`: `platform_allocation_status="NOT_APPLICABLE"`, fee 0;
- mode `COMMISSION`, `HYBRID`, `CUSTOM`: choose the most specific term: exact `kind` before `ANY`, exact `acquisition_source` before `ANY`; no term => `NO_TERM` and fee 0;
- snapshot JSON: `agreement_id`, `version`, `mode`, `term` (kind/source/basis/percent/fixed/cap), `volume_discount_bp`;
- `platform_fee_irr` = fee computed against the line's full `payable_irr` for display/cap; never mutate invoice totals.

Fee helper:
```python
def _platform_fee_for_portion(snapshot: dict[str, Any], portion_irr: int,
                              line_payable_irr: int) -> int:
    term = snapshot["term"]
    fee = 0
    if term["basis"] in ("PERCENT", "PERCENT_PLUS_FIXED"):
        fee += portion_irr * int(term["percent_bp"]) // 10_000
    if term["basis"] in ("FIXED", "PERCENT_PLUS_FIXED"):
        fee += (int(term["fixed_irr"]) * portion_irr // line_payable_irr
                if line_payable_irr > 0 else 0)
    cap = int(term.get("max_fee_irr") or 0)
    return min(fee, cap) if cap > 0 else fee
```

In `create_receipt` and `apply_customer_credit`, after `_create_coach_earnings`, call `_create_platform_commission` for each invoice allocation/line portion. It:
- skips lines with no snapshot or `platform_allocation_status != "SNAPSHOTTED"`;
- computes `fee = _platform_fee_for_portion(snapshot, portion, line.payable_irr)`;
- caps cumulative fee for the line at the snapshot's fixed/percent scheduled total (query prior `PlatformReceivable` rows by `source_key` prefix and line ID) so installments cannot exceed 100%;
- creates `PlatformReceivable(gym_id=scope.gym_id, agreement_id=..., source_type="COMMISSION", source_id=line.id, source_key=f"{source_prefix}:{line.id}", amount_irr=fee, due_on=received_on + 30 days, status="OPEN", snapshot=snapshot)`;
- when `fee > 0`, posts a balanced `PlatformJournal` `1100 receivable debit / 4100 commission revenue credit` (or `4200` for `CUSTOM` mode) with `source_type="finance_receipt"`/`"finance_credit"` and source ID;
- writes `PlatformAudit` action `platform.commission.accrued`;
- never touches gym cash or gym journal;
- uses the platform lock and a unique `source_key` so a retry cannot double-accrue.

For `apply_customer_credit`, same helper with `credit_movement_id` and `source_prefix=f"credit:{movement.id}"`.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py tests/api/routes/test_finance_receipts.py tests/api/routes/test_finance_invoices.py`
Expected: PASS; existing finance receipt/invoice behavior unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance.py backend/app/services/platform.py backend/tests/api/routes/test_platform_fees.py
git commit -m "feat(platform): snapshot and accrue commission on confirmed collections"
```

---

### Task 5: Subscription accrual, platform invoices and payments

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/api/routes/platform.py`
- Test: `backend/tests/api/routes/test_platform_invoices.py`

**Interfaces:**
- Produces: `accrue_subscription_period(session, *, actor, agreement_id, period, operation_key) -> PlatformReceivablePublic`.
- Produces: `issue_platform_invoice(session, *, actor, gym_id=None, group_id=None, period_start, period_end, due_on, operation_key) -> PlatformInvoicePublic`.
- Produces: `record_platform_payment(session, *, actor, invoice_id, amount_irr, method, reference, received_on, allocations, operation_key) -> PlatformPaymentPublic`.
- Produces: `void_platform_invoice(...)`.
- Produces routes: `POST /api/v1/platform/agreements/{id}/accrue-period`, `GET/POST /api/v1/platform/invoices`, `GET /api/v1/platform/invoices/{id}`, `POST /api/v1/platform/invoices/{id}/payments`, `POST /api/v1/platform/invoices/{id}/void`, `GET /api/v1/platform/receivables`, `GET /api/v1/platform/payments`.
- Consumes: Task 1 models; Task 3 agreements; Task 4 `PlatformReceivable` rows.

- [ ] **Step 1: Write the failing tests**

```python
def test_subscription_accrual_is_month_bounded_idempotent_and_not_fabricated_without_a_plan(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # COMMISSION agreement -> accrue-period returns 400 platform_not_configured
    # SUBSCRIPTION agreement effective 2026-11-01 with 500_000/month
    # accrue 2026-11 -> one receivable 500_000; replay same key -> same id
    # accrue 2026-10 -> 400 platform_period_outside_agreement
    # zero plans + COMMISSION -> no subscription invoice created

def test_platform_invoice_groups_open_receivables_and_group_invoice_keeps_branch_lines(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # 3 gyms in one group with 3 commission receivables and volume_discount_bp=500
    # issue one group invoice -> one invoice, 3 lines, sum net lines == total
    # assert invoice.discount_irr > 0, sum gross - discount == total,
    # each line.gym_id is traceable and gym journals unchanged

def test_platform_payment_is_partial_safe_idempotent_and_posts_only_platform_cash(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # pay 200_000 of a 500_000 invoice: PARTIALLY_PAID, 300_000 open
    # replay same key -> one payment row; over-allocation -> 400
    # assert platform journal debits 1000 / credits 1100, and gym journal count unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_invoices.py`
Expected: FAIL because the routes/services do not exist.

- [ ] **Step 3: Implement subscription, invoice and payment flows**

Subscription accrual:
- `_lock_platform`, reload agreement, require `EFFECTIVE` and mode in `SUBSCRIPTION`, `HYBRID`, `CUSTOM`;
- resolve amount from `subscription_amount_irr` or the effective plan version price; 0 => 400 `platform_subscription_not_configured`;
- validate the month (`YYYY-MM`) start and end inside `effective_from`/`effective_to`; otherwise 400 `platform_period_outside_agreement`;
- idempotency via `PlatformOperation`; duplicate protection via `source_key=f"subscription:{agreement.id}:{period}"`;
- create `PlatformReceivable(source_type="SUBSCRIPTION", source_id=agreement.id, due_on=period_start, snapshot=...)`;
- post `PlatformJournal` `1100 debit / 4000 subscription revenue credit`; audit `platform.subscription.accrued`; one commit.
- if the active plan version has price 0 and mode is FREE, return 400 `platform_subscription_not_configured`; never create a zero-value invoice line.

Invoice issuance:
- gather `PlatformReceivable` for the chosen gym or group with `status in ("OPEN","PARTIAL")` and `due_on <= period_end`, ordered by `created_at`;
- apply `PlatformCredit` rows for the same gym, oldest first, against the selected receivable amounts; consume `remaining_irr`, update credit status, and reduce the invoice line amount; a credit may not make a line negative;
- require at least one nonzero line; if none return 400 `platform_invoice_empty`;
- allocate `PlatformSequence("PLATFORM_INVOICE")` under `_lock_platform`; each line stores `gross_irr` (receivable net), `discount_irr` (group allocation) and `amount_irr = gross_irr - discount_irr`; mark receivable `INVOICED` (or `PAID` if fully covered by credit);
- for a group invoice, apply the effective group agreement's `volume_discount_bp` to the gross total, split the discount proportionally with largest-remainder integer math, and set `PlatformInvoice.discount_irr`; per-branch `gym_id` and `PlatformGroupMember.allocation_bp` stay traceable;
- no journal for ordinary invoice issuance (the receivable already exists); for a group volume discount, post a balanced `PlatformJournal` `4000/4100 revenue debit / 1100 receivable credit` for the discount from each revenue source, so the invoice total and receivable balance still reconcile; audit `platform.invoice.issued` with `discount_irr`.

Payment:
- validate `amount_irr > 0` and allocations sum to `amount_irr`; default allocations are FIFO over unpaid lines; reject over-allocation with 400 `platform_payment_over_allocated`;
- create `PlatformPayment`, `PlatformPaymentAllocation`s, increment line `paid_irr` and receivable `paid_irr`, set receivable `PARTIAL`/`PAID`, invoice `PARTIALLY_PAID`/`PAID`;
- post `PlatformJournal` `1000 debit / 1100 receivable credit`; audit `platform.payment.recorded`;
- unique `operation_key` + replay returns the same payment.

Void:
- allowed only when `total_irr == paid_irr == 0`; set invoice `VOID`, return lines' receivables to `OPEN`; audit; no journal.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_invoices.py tests/api/routes/test_finance_receipts.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_invoices.py
git commit -m "feat(platform): add subscription accrual, invoices and payments"
```

---

### Task 6: Refund adjustment and platform credit

**Files:**
- Modify: `backend/app/services/finance.py` (`record_refund`)
- Modify: `backend/app/services/platform.py`
- Test: `backend/tests/api/routes/test_platform_fees.py`

**Interfaces:**
- Produces: `_apply_platform_refund(session, *, scope, actor, refund, posting_date) -> int` in `platform.py`.
- Consumes: `FinanceRefund`, `FinanceInvoiceLine` platform snapshots, `PlatformReceivable`.

- [ ] **Step 1: Write the failing test**

```python
def test_invoice_refund_reverses_uncollected_platform_commission_without_gym_cash_clawback(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # commission 10% on a confirmed 1_000_000 receipt => 100_000 receivable
    # refund 300_000 -> open receivable reduced by 30_000
    # if that receivable was already invoiced/paid -> PlatformCredit 30_000
    # gym cash journal contains only the customer refund; no platform cash
    # a fully paid platform invoice remains PAID and receives a platform credit
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py::test_invoice_refund_reverses_uncollected_platform_commission_without_gym_cash_clawback`
Expected: FAIL because no platform adjustment runs on refund.

- [ ] **Step 3: Implement refund adjustment**

In `record_refund`, after `_apply_coach_refund`, call `_apply_platform_refund` for `source == "INVOICE"`.

Rules:
- find `PlatformReceivable` commission rows for the refunded invoice's lines, ordered oldest first;
- proportional reversal = `sum(commission receivables for invoice) * refund.amount_irr // _invoice_paid_irr(...)`;
- for `status == "OPEN"` rows, reduce the open receivable amount directly, never below zero;
- for `INVOICED`/`PARTIAL`/`PAID` rows, create a `PlatformCredit(gym_id=..., source_type="REFUND", source_id=refund.id, amount_irr=credit, remaining_irr=credit, status="OPEN", reason=refund.reason)` consumed by the next platform invoice; never edit an issued invoice or a paid row;
- post `PlatformJournal` `4100 commission revenue debit / 1100 receivable credit` for the reversed uncollected amount (or `4200` for custom); source `finance_refund`;
- audit `platform.commission.reversed` with refund ID and amount;
- no mutation of gym cash, coach settlement or gym journal.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py tests/api/routes/test_finance_refunds_expenses.py tests/api/routes/test_finance_coach_refunds.py`
Expected: PASS; no automatic coach clawback regression.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance.py backend/app/services/platform.py backend/tests/api/routes/test_platform_fees.py
git commit -m "feat(platform): reverse commission on customer refunds"
```

---

### Task 7: Dues standing, reminders and conservative restrictions

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/api/routes/platform.py`
- Test: `backend/tests/api/routes/test_platform_reports.py`

**Interfaces:**
- Produces: `platform_standing(session, *, gym_id, as_of) -> PlatformStandingPublic`.
- Produces: `list_platform_reminders(session, *, as_of, within_days=7) -> PlatformRemindersPublic`.
- Produces routes: `GET /api/v1/platform/dues`, `GET /api/v1/platform/dues/{gym_id}`, `GET /api/v1/platform/reminders`.
- Produces: `PlatformStandingPublic` fields `gym_id`, `open_irr`, `overdue_irr`, `oldest_due_on`, `overdue_days`, `stage` (`CURRENT`, `DUE`, `GRACE`, `RESTRICTED`), `restricted_capabilities`.

- [ ] **Step 1: Write the failing tests**

```python
def test_overdue_stage_progresses_from_due_to_grace_to_restricted_without_hiding_history(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # invoice due 2026-11-01, as_of 2026-11-03 -> DUE
    # as_of 2026-11-10 -> GRACE (grace_days=7)
    # as_of 2026-11-25 -> RESTRICTED (restrict_after_days=21)
    # GET /platform/dues/{gym} still returns old invoices and export still returns rows

def test_platform_reminders_list_due_soon_and_overdue_without_scheduler(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # within_days=7 returns due and overdue; no email/scheduler side effects
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py -k overdue`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement standing and reminders**

Standing is derived on read from open platform invoices/receivables:
- `open_irr` = invoice total − paid;
- `oldest_due_on` = earliest unpaid invoice due date;
- `overdue_days` = max(as_of − due_on, 0);
- stage: current before due; `DUE` from due date; `GRACE` after `grace_days`; `RESTRICTED` after `restrict_after_days` (values from the effective agreement; conservative defaults 7/21);
- `restricted_capabilities=["NEW_PLATFORM_AGREEMENT","NEW_PLATFORM_GROUP"]`; restriction **never** blocks finance reads, exports, gym sales or athlete history.
- enforce this only in `create_agreement`/`create_group` (403 `platform_account_restricted`) so a restricted gym cannot add a new paid platform arrangement; all existing obligations remain.

Reminders: in-app computed list:
- `due_soon`: unpaid invoices with `due_on` between `as_of` and `as_of + within_days`;
- `overdue`: unpaid invoices with `due_on < as_of`;
- no email/SMS/background job; reuse the Phase 3 in-app reminder limitation.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py -k "overdue or reminders"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_reports.py
git commit -m "feat(platform): add dues standing and reminders"
```

---

### Task 8: Gym and platform reports, platform costs and CSV exports

**Files:**
- Modify: `backend/app/finance_models.py` (`FinanceGymSummaryPublic`, `FinanceInvoiceLinePublic` export fields)
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/services/finance.py`
- Modify: `backend/app/api/routes/finance.py`
- Modify: `backend/app/api/routes/platform.py`
- Test: `backend/tests/api/routes/test_platform_reports.py`

**Interfaces:**
- Produces: `gym_summary(session, *, gym_id, from_date, to_date) -> FinanceGymSummaryPublic` in `finance.py`.
- Produces: `platform_overview(session, *, from_date, to_date) -> PlatformOverviewPublic` and `platform_gym_detail(...)` in `platform.py`.
- Produces: `record_platform_cost(...)`, `list_platform_costs(...)`.
- Produces routes: `GET /api/v1/finance/reports/summary`, `GET /api/v1/finance/reports/export`, `GET /api/v1/finance/reports/offboarding-export`, `GET /api/v1/platform/reports/overview`, `GET /api/v1/platform/reports/gyms/{gym_id}`, `GET /api/v1/platform/gyms/{gym_id}/export`, `GET /api/v1/platform/reports/export`, `GET/POST /api/v1/platform/costs`.
- Produces: offboarding CSV rows for invoices, receipts, refunds, expenses, coach agreements/earnings/settlements, platform agreements/receivables/invoices/payments and balances. The gym owner route exports only its gym; the Superuser route may export any gym and all gyms. Export never requires the gym's finance module to be enabled (read/export remains allowed when disabled).

- [ ] **Step 1: Write the failing tests**

```python
def test_gym_summary_separates_collected_sales_overdue_payables_and_estimated_profit(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # issue 1_000_000, collect 400_000, record expense 50_000,
    # create coach payable 120_000 and platform commission 40_000
    # assert keys: confirmed_collections_irr=400_000, sales_irr=1_000_000,
    # overdue_irr>0 only after due, coach_payable_irr=120_000,
    # expenses_irr=50_000, estimated_operating_profit_irr=190_000
    # and the label is "estimated"

def test_platform_overview_shows_zero_mrr_for_commission_only_and_collected_not_invoiced(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # no plans -> mrr_irr == 0
    # invoice 1_000_000 platform receivable, no payment -> collected_fees_irr == 0
    # record 300_000 payment -> collected_fees_irr == 300_000
    # receivable_irr still separate; by_gym contribution subtracts recorded PlatformCost

def test_csv_exports_are_tenant_safe_and_keep_history_for_restricted_gym(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # GET gym export as owner -> 200 text/csv, only own gym
    # GET platform export as owner -> 403
    # GET offboarding-export as owner -> 200 and contains invoice/receipt/coach rows
    # GET /platform/gyms/{other_gym}/export as owner -> 403; Superuser -> 200
    # restricted gym export still contains its old invoice/settlement rows
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py -k "summary or overview or export"`
Expected: FAIL because the report routes do not exist.

- [ ] **Step 3: Implement report read models and exports**

Gym summary fields:
- `confirmed_collections_irr` = sum confirmed `FinanceReceipt.amount_irr` with `received_on` in range;
- `sales_irr` = sum issued `FinanceInvoice.total_irr` with `issue_date` in range;
- `overdue_irr` = sum open invoice balances whose `due_date < today` (or use installment due rows if `due_date` is null; follow existing `_invoice_reminder` logic);
- `renewals_due` = count of active `FinanceMembership` ending in the next 30 days (reuse `list_reminders` shape);
- `coach_payable_irr` = sum over `FinanceCoachEarning` of `max(coach_share - confirmed settlements - reserved - adjustments, 0)`;
- `expenses_irr` = sum `FinanceExpense.amount_irr` with `spent_on` in range (registered, paid status separately exposed as `paid_expenses_irr`);
- `estimated_operating_profit_irr` = `confirmed_collections_irr - paid_expenses_irr - coach_payable_earned_irr - platform_fees_irr`; label it `estimated` in DTO/docs; never call it net income.
  - `coach_payable_earned_irr` uses the same coach-share expense already recognized in `5100` (do not also add `coach_payable_irr`).
  - `platform_fees_irr` uses open/paid commission and subscription receivables attributed to the gym in range.
- Add `FinanceGymSummaryPublic` and `FinanceGymReportRowsPublic` DTOs to `finance_models.py`.
- `POST /platform/costs` requires `Idempotency-Key`, uses `PlatformOperation`, validates `amount_irr >= 0`, and records `PlatformAudit`; a cost is optional and a missing cost must never be guessed.

Platform overview fields:
- `mrr_irr` = sum active monthly subscription amounts for effective agreements (0 if no plans);
- `collected_fees_irr` = sum `PlatformPayment.amount_irr` in range;
- `invoiced_fees_irr` = sum `PlatformInvoice.total_irr` issued in range;
- `receivable_irr` = sum open/partial invoice balances (not cash);
- `overdue_irr` = sum balances where due date passed;
- `by_gym` = per-gym collected fees, open receivables, recorded `PlatformCost` and `contribution_irr = collected_fees − recorded_costs` (null/zero if no costs, never infer a cost);
- `active_plans`, `active_agreements`, `zero_plan_mode` boolean.

Exports:
- use `fastapi.Response` with `media_type="text/csv; charset=utf-8"` and a UTF-8 BOM for Excel;
- gym export is gym-scoped through `resolve_finance_scope` + `FINANCE_VIEW`;
- platform export requires `CurrentSuperuser`;
- filenames include the date range; never include another tenant's rows.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/services/finance.py backend/app/finance_models.py backend/app/api/routes/finance.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_reports.py
git commit -m "feat(platform): add role dashboards and CSV exports"
```

---

### Task 9: Regenerate the typed client and build the Superuser platform UI

**Files:**
- Regenerate: `frontend/src/client/*`, `frontend/openapi.json`
- Create: `frontend/src/pages/PlatformFinancePage.tsx`
- Create: `frontend/src/pages/platform/PlatformOverviewSection.tsx`
- Create: `frontend/src/pages/platform/PlatformPlansSection.tsx`
- Create: `frontend/src/pages/platform/PlatformAgreementsSection.tsx`
- Create: `frontend/src/pages/platform/PlatformInvoicesSection.tsx`
- Create: `frontend/src/pages/platform/PlatformDuesSection.tsx`
- Create: `frontend/src/routes/_app.platform.finance.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/i18n.tsx`
- Test: `frontend/tests/platform-finance.spec.ts`

**Interfaces:**
- Consumes: generated `PlatformService` methods for plans, groups, agreements, receivables, invoices, payments, dues, reports, costs.
- Produces: global route `/_app/platform/finance`; Superuser-only nav item `nav.platformFinance`.

- [ ] **Step 1: Write the failing Playwright test**

```ts
test("superuser configures a commission-only agreement and sees zero MRR", async ({ page }) => {
  await page.goto("/platform/finance")
  await expect(page.getByRole("heading", { name: "مالی پلتفرم" })).toBeVisible()
  await expect(page.getByText("حالت بدون اشتراک")).toBeVisible()
  await page.getByRole("tab", { name: "قراردادها" }).click()
  await page.getByRole("button", { name: "قرارداد جدید" }).click()
  await page.getByRole("button", { name: "باشگاه" }).click()
  await page.getByRole("option").first().click()
  await page.getByRole("button", { name: "مدل" }).click()
  await page.getByRole("option", { name: "کمیسیون" }).click()
  await page.getByRole("button", { name: "افزودن شرط" }).click()
  await page.getByLabel("درصد").fill("10")
  await page.getByRole("button", { name: "فعال‌سازی" }).click()
  await expect(page.getByText("قرارداد فعال شد.")).toBeVisible()
  await expect(page.getByText("MRR")).toContainText("۰")
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && bunx playwright test tests/platform-finance.spec.ts --reporter=line`
Expected: FAIL because the route and UI do not exist.

- [ ] **Step 3: Build the screens**

- Add a global nav item for Superusers when no gym is active:
  `{ to: "/platform/finance", label: "nav.platformFinance", icon: Landmark }`.
- Add route file `frontend/src/routes/_app.platform.finance.tsx` with `createFileRoute("/_app/platform/finance")`.
- `PlatformFinancePage` uses `Tabs`:
  - **overview**: report cards for MRR, collected fees, receivables, overdue, active plans/agreements, zero-plan banner, per-gym table, cost form, CSV export button;
  - **plans**: create plan/version, activate/retire, limits editor, "no active plans" empty state;
  - **agreements**: create gym/group agreement, mode selector, plan selector optional, commission term rows, effective dates, activate/disable, group member editor;
  - **invoices**: issue gym/group invoice for a period, inspect lines with gym allocation, record partial payment, void unpaid invoice;
  - **dues**: standing stages, overdue/grace/restricted badges, in-app reminder list, export.
- Reuse `M3` components (`PageHeader`, `SectionCard`, `Card`, `Dialog`, `Select`, `TextField`, `Button`, `StatusBadge`, `EmptyState`, `Spinner`, `ErrorState`).
- Persian-first copy, RTL, integer money formatting via `useMoney`/`formatIrr`; all amounts display Rial/Toman correctly.
- Add Persian and English i18n keys for every new label and error.
- Regenerate the client with:

```bash
cd backend && FASTAPI_ENV=development ENV_FILE=.env.dev ../.venv/bin/python -c "import app.main, json; print(json.dumps(app.main.app.openapi()))" > ../frontend/openapi.json
cd ../frontend && bun run generate-client && bun run lint
```

- [ ] **Step 4: Run frontend checks and the new test**

Run:
```bash
cd frontend && bun run lint:check && bunx tsc -p tsconfig.build.json --noEmit && bun run test:unit && bun run build
cd frontend && bunx playwright test tests/platform-finance.spec.ts --reporter=line
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/client frontend/openapi.json frontend/src/pages/PlatformFinancePage.tsx frontend/src/pages/platform frontend/src/routes/_app.platform.finance.tsx frontend/src/components/AppShell.tsx frontend/src/i18n.tsx frontend/tests/platform-finance.spec.ts
git commit -m "feat(platform): add superuser platform finance UI"
```

---

### Task 10: Gym dashboard, coach aggregate, athlete dues and Playwright coverage

**Files:**
- Modify: `frontend/src/pages/finance/FinanceOverviewSection.tsx`
- Modify: `frontend/src/pages/CoachEarningsPage.tsx`
- Modify: `frontend/src/pages/AthleteFinancePage.tsx`
- Modify: `backend/app/api/routes/finance.py`
- Modify: `backend/app/services/finance.py`
- Modify: `backend/app/finance_models.py`
- Test: `frontend/tests/finance-dashboard.spec.ts`

**Interfaces:**
- Produces: `GET /api/v1/finance/my/coach-summary` (no `GymContextDep`; resolves all `GymMembership` roles for `CurrentUser`, requires at least one active coach role) returning cross-gym totals `calculated_irr`, `vested_irr`, `eligible_irr`, `settled_irr`, `reserved_irr`, `per_gym`. It queries only `FinanceCoachEarning`/`FinanceCoachSettlement` rows whose `gym_id` belongs to that user's active coach memberships.
- Produces: gym summary cards and export button in the existing finance overview tab.
- Produces: athlete due/overdue card using existing `readMyFinanceAccount`.

- [ ] **Step 1: Write the failing tests**

```ts
test("gym admin sees separate collections, sales, payables and estimated profit", async ({ page }) => {
  await page.goto("/gyms/" + gymId + "/finance")
  await expect(page.getByText("وجه دریافت‌شده")).toBeVisible()
  await expect(page.getByText("فروش صادرشده")).toBeVisible()
  await expect(page.getByText("سود عملیاتی تقریبی")).toBeVisible()
  await page.getByRole("button", { name: "خروجی CSV" }).click()
  // assert download filename
})

test("coach sees cross-gym totals on the earnings page", async ({ page }) => {
  await page.goto("/gyms/" + gymId + "/my/earnings")
  await expect(page.getByText("مجموع همه باشگاه‌ها")).toBeVisible()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && bunx playwright test tests/finance-dashboard.spec.ts --reporter=line`
Expected: FAIL because the cards/aggregate are absent.

- [ ] **Step 3: Implement the role views**

- Gym overview: fetch `FinanceService.readFinanceGymSummary({ query: { from_date, to_date } })`; render cards with distinct labels: confirmed collections, issued sales, overdue, coach payable, expenses, **estimated** operating profit. Add date range and CSV download (`/api/v1/finance/reports/export?from_date=...&to_date=...` via authenticated fetch).
- Coach: add a query to `readMyCoachSummary()` and a totals card `finance.my.allGyms`; keep per-gym breakdown; if only one gym hide the aggregate if it equals the per-gym total.
- Athlete: add a card showing next due installment/overdue from existing `readMyFinanceAccount`; no new endpoint needed.
- Keep all labels distinct; never label receivables as cash or collected fees as gym sales.

- [ ] **Step 4: Run checks**

Run:
```bash
cd frontend && bun run lint:check && bunx tsc -p tsconfig.build.json --noEmit && bun run build
cd frontend && bunx playwright test tests/finance-dashboard.spec.ts tests/finance-coach.spec.ts tests/coach-finance.spec.ts tests/athlete-finance.spec.ts --reporter=line
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/finance/FinanceOverviewSection.tsx frontend/src/pages/CoachEarningsPage.tsx frontend/src/pages/AthleteFinancePage.tsx backend/app/api/routes/finance.py backend/app/services/finance.py backend/app/finance_models.py frontend/tests/finance-dashboard.spec.ts
git commit -m "feat(finance): add role dashboards and coach cross-gym totals"
```

---

### Task 11: Full acceptance evidence, docs and branch finish

**Files:**
- Modify: `docs/finance/00-gap-audit.md`
- Modify: `docs/finance/ASCORA-FINANCE-PRD.md` only if a status note is needed; never change approved decisions.
- Create: `docs/finance/phase4-evidence.md`

**Interfaces:**
- Consumes: all tasks above.
- Produces: decision-by-decision evidence table, command output summary, manual QA notes, remaining risks and rollback notes.

- [ ] **Step 1: Add the Phase 4 evidence document**

Include:
- `what existed` vs `what changed` mapped to `FR-PLAN`, `FR-FEE`, `FR-REPORT`, decisions #5/#6/#7/#8/#9/#10/#11/#12/#23/#34/#37/#41/#44/#47/#55/#57/#58/#60/#61/#78/#84/#91/#92 and `ADD-01`;
- migration name/revision `f1a2b3c4d5e6`, additive columns, downgrade behavior and no existing finance rows rewritten;
- explicit note that #18, #30 and #46 remain deferred;
- manual QA for Superuser, Gym Admin, finance staff, coach and athlete;
- exact commands/results, distinguishing new failures from pre-existing ones;
- one-paragraph independent self-review and concrete remaining risks;
- explicit "not merged, not deployed" status.

- [ ] **Step 2: Update the gap audit**

Add a Phase 4 status section stating:
- plans can be zero/optional and commission-only works;
- platform receivables/collections are separate from gym ledger;
- group invoices keep per-branch lines;
- dashboards/exports and in-app reminders exist;
- plan limits are modeled/surfaced, not yet enforced against core gym operations (if that remains the chosen scope);
- deferred #18/#30/#46 unchanged.

- [ ] **Step 3: Run full backend regression**

Run:
```bash
cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider
cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider -m migrations
cd backend && ../.venv/bin/ruff check --no-cache app tests scripts
cd backend && ../.venv/bin/mypy --cache-dir=/dev/null app
```
Expected: all pass (Phase 3 baseline was 264 backend tests; Phase 4 adds focused tests).

- [ ] **Step 4: Run full frontend regression**

Run:
```bash
cd frontend && bun run lint:check
cd frontend && bunx tsc -p tsconfig.build.json --noEmit
cd frontend && bun run test:unit
cd frontend && bun run build
cd frontend && bunx playwright test --reporter=line
```
Expected: all pass; prior baseline 121 passed / 19 skipped plus the new Phase 4 specs.

- [ ] **Step 5: Run the Docker backup/restore drill at the new head**

Run:
```bash
bash scripts/ci/start-stack.sh
bash scripts/ci/backup-restore-drill.sh
COMPOSE_PROJECT_NAME=gym-ci BACKEND_IMAGE=gym-app-ci:local POSTGRES_PASSWORD=ci-postgres-password \
  SECRET_KEY=ci-only-secret-key-not-for-production-0123456789 \
  FIRST_SUPERUSER=ci-superuser@example.com FIRST_SUPERUSER_PASSWORD=ci-only-superuser-password \
  DOMAIN=localhost ACME_EMAIL=ci@example.com \
  docker compose -f compose.deploy.yml -f compose.ci.yml down -v
```
Expected: `drill: PASS`, platform tables/rows restored, counts and files match, live restore reverts the corrupted gym name.

- [ ] **Step 6: Commit and push (Phase 4 branch only; no merge/deploy)**

```bash
git add -A
git commit -m "docs(finance): record phase 4 evidence and status"
git push origin feat/ascora-finance
git status --short
```

- [ ] **Step 7: Stop and report**

Report: files changed, decision/FR mapping, actual test results, restore evidence, remaining risks, and the explicit next action (human review/approval before any Phase 5 pilot or production work). Do not merge, deploy or start Phase 5.
