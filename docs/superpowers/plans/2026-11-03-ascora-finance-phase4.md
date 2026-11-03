# ASCORA Finance Phase 4 — Platform Monetization, Dashboards, Exports and Reminders

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use **native execution with independent fresh-context reviews** for each financially sensitive slice, as specified below.

**Goal:** Add Superuser-controlled platform plans, agreements and group contracts; accrue separate ASCORA subscription/commission receivables; record platform collections; expose conservative dues standing; and deliver role dashboards plus CSV exports without merging platform money into any gym ledger.

**Architecture:** Add one bounded `platform` module beside the existing `finance` module. It owns its own catalog, agreements, receivables, invoices, payments, journal, audit, sequence and idempotency records; it never writes to `finance_journal`, a gym's cash account or gym invoice numbering. The existing gym invoice/receipt flow snapshots an applicable platform fee on issue and creates a platform receivable only when money is actually confirmed collected. Superuser-only routes live under `/api/v1/platform`; read-only owner routes and role reporting extend existing `/api/v1/finance` routes. To avoid circular imports, `platform.py` imports `finance_models`/`platform_models` only; `finance.py` may import platform service functions, and any platform read of a finance aggregate takes the already-computed value as a parameter or uses a lazy/local import.

## Execution Model

- Execute natively in this session, one numbered task at a time, in order. Do not run tasks in parallel.
- After each task’s focused tests pass, before the next task starts, dispatch an independent fresh-context reviewer (a `subagent` with no prior context) using the task’s files, diff, acceptance tests and PRD references. The reviewer must check financial correctness, tenant isolation, append-only history, idempotency and scope creep.
- Fix review findings before starting the next task. Each task ends with its own commit; do not squash slices.
- Financially sensitive slices are Tasks 1, 3, 4, 5, 6, 7 and 8. They require the independent review gate before proceeding.
- Never merge, deploy or start Phase 5 without explicit authorization. A passing test suite is not deployment evidence.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Alembic, pytest, React 19, TypeScript, TanStack Router/Query, Vite, Playwright, Biome.

**Spec:** `docs/finance/ASCORA-FINANCE-PRD.md` — especially §2 (monetization addendum), §3 (`FR-PLAN`, `FR-FEE`, `FR-REPORT`), §4 (invariants), §12–§17, and §18 Phase 4. Decisions #5, #6, #7, #8, #9, #10, #11, #12, #23, #34, #37, #41, #44, #47, #55, #57, #58, #60, #61, #78, #84, #91, #92 and `ADD-01` are binding; #18, #30 and #46 remain deferred.

## Revision Notes from Conditional Approval

1. **No mandatory plan records** — all five modes work with zero plans; subscription-only/hybrid/custom may carry an explicit amount and no `plan_version_id`. Plans are optional templates.
2. **Append-only history** — refunds, credits, corrections and unpaid-invoice cancellations append linked records/reversals; posted receivable and invoice amounts are never rewritten.
3. **Cancellation defined** — only an `ISSUED` invoice with zero payments can be cancelled; a cancellation plus line-reversal rows and any required discount-journal reversal are appended. Paid invoices require a credit-note/refund path. Cancellation does not waive the fee.
4. **Single ASCORA recognition** — an issue-time coach ASCORA share suppresses the separate platform commission for that line; recognition uses the actual coach-earning share. A double-recognition condition fails closed.
5. **Authority and owner access** — overdue standing is informational only and never gates Superuser actions. Gym owners receive read-only access to only their own platform invoices, dues and payment history.
6. **Cashflow vs accrual** — cashflow is derived from posted cash-account movements; estimated operating profit is derived from recognized revenue minus recognized expenses. They are reported, exported and labeled separately.
7. **Reminders** — in-app reminders only; proactive delivery (#15/#71) remains an explicitly outstanding approved requirement.
8. **Scope control** — only the tables named in Task 1 are added; no scheduler, gateway, rule engine, core plan-enforcement layer or speculative feature.

## Global Constraints

- Money is persisted as integer IRR (`BigInteger`), never binary floating point; every division uses deterministic integer math and an explicit residual policy.
- Platform money is separate from gym money. A platform receivable is not platform cash; a gym's sales are not ASCORA revenue. Never write platform fees into `finance_journal` or into a gym's `1000` cash account.
- Platform billing writes are atomic: business row + journal + audit + idempotency record commit together. Use `pg_advisory_xact_lock` with the key `platform` for platform writes, and the existing `lock_finance_gym` for gym-side fee snapshots/accruals.
- Superuser-only platform writes require `CurrentSuperuser`. Gym owners and finance staff get **read-only** access to their own gym’s platform invoices, dues and payments. No role may read or mutate another tenant’s platform billing.
- Commercial plans are optional for every mode. `FREE`, `SUBSCRIPTION`, `COMMISSION`, `HYBRID` and `CUSTOM` may all operate with **zero plan records**; a plan version is an optional reusable price/limit template, never a prerequisite for an agreement. Zero prices and zero active plans are valid.
- Posted financial facts are append-only. Never change a posted receivable, invoice line, payment allocation or journal amount in place. Corrections, refunds, credits and unpaid-invoice cancellations create linked reversal/adjustment records and, where revenue was recognized, a balanced reversal journal. Status/lifecycle fields may change only through an audited transition; amount fields are immutable.
- Commission is calculated only from **confirmed collected** amounts against a snapshot taken at invoice issue. No fee on draft or unissued invoices; no retroactive recalculation after an agreement changes. An invoice that must be cancelled uses the explicit append-only cancellation path, never a rewrite of its lines.
- One sale must not recognize the same ASCORA amount twice. If the issue-time coach snapshot already allocates an ASCORA share for a line, that share is the platform amount recognized for the line and a separate platform commission is suppressed; otherwise the platform commercial fee applies. This is a single-recognition rule, not an additional fee.
- All migrations are additive and reversible. Never rewrite existing finance/invoice rows; the new snapshot and cancellation fields are nullable/additive for historical rows.
- Cashflow and accrual profit are separate metrics with separate formulas. Cashflow uses confirmed receipts/payments/paid expenses/recorded refunds. Accrual profit uses recognized revenue and recognized expenses from posted ledger facts. Never subtract a payable a second time, and never label cashflow as profit.
- Create only the tables and abstractions named in this plan. Do not add a scheduler, rule engine, gateway, inventory, payroll, speculative integrations or a plan-enforcement layer over core gym operations.
- Proactive reminder delivery (#15/#71) is an **outstanding approved requirement**, not completed by in-app reminder reads. This plan may implement in-app reminders only; the evidence and gap audit must keep proactive email/SMS/scheduled delivery explicitly open.
- No automatic coach clawback (#30), no attendance/usage finance input (#18), no AI/smart analytics (#46), no payment gateway, no inventory or payroll engine, no deployment.
- Preserve the current clean branch discipline: implement only after explicit Phase 4 approval, commit on `feat/ascora-finance`, do not merge or deploy.

## Review Focus

These are the failure modes the spec implies but ordinary task tests may miss. Each has an owning test below.

1. **Zero plans + every mode without plan records** — `SUBSCRIPTION`, `HYBRID` and `CUSTOM` must work with direct contract amounts and no plan row; commission-only and free must work with zero active plans; no fabricated subscription invoice (`AC-35`, `AC-36`, `ADD-01`).
2. **Group invoice isolation** — one ASCORA invoice for three gyms must keep three traceable per-branch allocations and must not create merged gym journals or cash (`AC-37`).
3. **Snapshot immutability and append-only history** — replacing an agreement after issue must not change that invoice’s fee; refunds, credits and unpaid-invoice cancellations must append linked reversals, never rewrite posted receivable/invoice amounts (`AC-24`, `AC-25`, `AC-39`, §4.4).
4. **Unconfirmed money and cancellation** — a draft/unissued invoice, an unpaid platform invoice cancellation or a failed payment must never create or confirm a platform fee; cancellation rules and reversal journals must be explicit (`FR-FEE`, `AC-16`, `AC-29`).
5. **Single ASCORA recognition** — a coach agreement ASCORA share and a platform commercial commission cannot both be recognized for the same collected portion; the issue-time snapshot determines one amount (`#78`, `FR-FEE`, `FR-SHARE`).
6. **Superuser authority and owner read-only access** — overdue standing must never block a Superuser action; a gym owner must see only its own platform invoices, dues and payment history, read-only (`AC-05`, `AC-38`, `AC-44`).
7. **Cashflow vs accrual** — an unpaid invoice increases recognized revenue but not cash; a paid expense reduces cash and accrual expense; estimated operating profit must not be derived from collected cash (`FR-REPORT`, `AC-40`).
8. **Retry/concurrency** — duplicate subscription accrual, invoice issuance, cancellation, payment recording, commission accrual and ASCORA-share recognition must produce one row and one balanced journal (`FR-PAY`, §12.1).

---

## File Structure

**Backend**

- Create: `backend/app/platform_models.py` — all platform SQLModel tables plus public/input DTOs. Keep platform identity separate from gym finance models.
- Create: `backend/app/services/platform.py` — Superuser scope guard, locks, sequence, journal, audit, plan/agreement/fee/invoice/payment logic and report read models.
- Create: `backend/app/api/routes/platform.py` — `/api/v1/platform` Superuser API.
- Modify: `backend/app/api/main.py` — include the platform router.
- Modify: `backend/app/finance_models.py` — add the nullable platform-snapshot fields to `FinanceInvoiceLine`, plus gym summary DTOs.
- Modify: `backend/app/services/finance.py` — snapshot at issue; accrue ASCORA share/commission on confirmed receipt/credit; reverse on refund; gym summary and owner platform read models.
- Modify: `backend/app/api/routes/finance.py` — gym report/export routes, cross-gym coach summary, and read-only owner platform billing routes.
- Create: `backend/app/alembic/versions/f1a2b3c4d5e6_add_platform_billing.py` — additive platform schema, cancellation tables and snapshot columns.
- Test: `backend/tests/api/routes/test_platform_plans.py`
- Test: `backend/tests/api/routes/test_platform_agreements.py`
- Test: `backend/tests/api/routes/test_platform_fees.py`
- Test: `backend/tests/api/routes/test_platform_invoices.py`
- Test: `backend/tests/api/routes/test_platform_owner_access.py`
- Test: `backend/tests/api/routes/test_platform_reports.py`
- Test: `backend/tests/test_platform_migrations.py`

**Frontend**

- Create: `frontend/src/pages/PlatformFinancePage.tsx` — Superuser tabs: overview, plans, agreements, invoices, dues.
- Create: `frontend/src/pages/platform/PlatformOverviewSection.tsx`
- Create: `frontend/src/pages/platform/PlatformPlansSection.tsx`
- Create: `frontend/src/pages/platform/PlatformAgreementsSection.tsx`
- Create: `frontend/src/pages/platform/PlatformInvoicesSection.tsx`
- Create: `frontend/src/pages/platform/PlatformDuesSection.tsx`
- Create: `frontend/src/pages/finance/FinancePlatformSection.tsx` — read-only owner view of own platform invoices, dues and payments.
- Create: `frontend/src/routes/_app.platform.finance.tsx`
- Modify: `frontend/src/components/AppShell.tsx` — global Superuser nav item.
- Modify: `frontend/src/pages/FinancePage.tsx` — add the platform-billing tab for owners.
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
- Produces: `PlatformPlan`, `PlatformPlanVersion`, `PlatformGroup`, `PlatformGroupMember`, `PlatformAgreement`, `PlatformCommissionTerm`, `PlatformReceivable`, `PlatformCredit`, `PlatformCreditApplication`, `PlatformInvoice`, `PlatformInvoiceLine`, `PlatformInvoiceCancellation`, `PlatformInvoiceLineReversal`, `PlatformPayment`, `PlatformPaymentAllocation`, `PlatformJournal`, `PlatformJournalLine`, `PlatformAudit`, `PlatformCost`, `PlatformSequence`, `PlatformOperation`.
- Produces: `FinanceInvoiceLine.platform_agreement_id`, `.platform_agreement_version`, `.platform_allocation_status`, `.platform_snapshot`, `.platform_fee_irr`, `.platform_ascora_term_share_irr`.
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
        "platform_credit_application",
        "platform_invoice",
        "platform_invoice_line",
        "platform_invoice_cancellation",
        "platform_invoice_line_reversal",
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
        "platform_ascora_term_share_irr",
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
        CheckConstraint("status IN ('OPEN', 'INVOICED', 'PARTIAL', 'PAID', 'CREDITED', 'VOID')", name="ck_platform_receivable_status"),
        UniqueConstraint("source_key", name="uq_platform_receivable_source"),
    )
    id: uuid.UUID
    gym_id: uuid.UUID
    agreement_id: uuid.UUID | None
    source_type: str            # COMMISSION, SUBSCRIPTION, COACH_ASCORA_SHARE
    source_id: uuid.UUID | None # invoice line / receipt / agreement period / earning
    source_key: str
    amount_irr: int             # immutable recognized amount
    paid_irr: int = 0           # derived cache from allocations; never a source amount
    due_on: date
    status: str = "OPEN"        # derived lifecycle cache; amount changes only via PlatformCredit
    snapshot: dict[str, Any]
    created_at: datetime

class PlatformCredit(SQLModel, table=True):
    __tablename__ = "platform_credit"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="ck_platform_credit_amount"),
    )
    id: uuid.UUID
    gym_id: uuid.UUID
    source_type: str            # REFUND, MANUAL, INVOICE_CANCELLATION
    source_id: uuid.UUID | None
    amount_irr: int             # immutable credit amount
    reason: str | None
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformCreditApplication(SQLModel, table=True):
    __tablename__ = "platform_credit_application"
    __table_args__ = (
        UniqueConstraint("credit_id", "invoice_line_id", name="uq_platform_credit_application"),
        CheckConstraint("amount_irr > 0", name="ck_platform_credit_application_amount"),
    )
    id: uuid.UUID
    credit_id: uuid.UUID
    invoice_line_id: uuid.UUID
    amount_irr: int
    created_at: datetime

class PlatformInvoice(SQLModel, table=True):
    __tablename__ = "platform_invoice"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_platform_invoice_number"),
        CheckConstraint("status IN ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'CREDITED', 'CANCELLED')", name="ck_platform_invoice_status"),
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
        CheckConstraint("gross_irr >= 0 AND discount_irr >= 0 AND credit_irr >= 0 AND amount_irr >= 0", name="ck_platform_invoice_line_amount"),
    )
    id: uuid.UUID
    invoice_id: uuid.UUID
    gym_id: uuid.UUID
    receivable_id: uuid.UUID
    source_key: str
    description: str
    gross_irr: int
    discount_irr: int = 0
    credit_irr: int = 0
    amount_irr: int             # immutable net billed amount
    paid_irr: int = 0           # derived from payment allocations

class PlatformInvoiceCancellation(SQLModel, table=True):
    __tablename__ = "platform_invoice_cancellation"
    __table_args__ = (
        UniqueConstraint("invoice_id", name="uq_platform_invoice_cancellation"),
        CheckConstraint("length(reason) >= 3", name="ck_platform_invoice_cancel_reason"),
    )
    id: uuid.UUID
    invoice_id: uuid.UUID
    reason: str
    journal_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    created_at: datetime

class PlatformInvoiceLineReversal(SQLModel, table=True):
    __tablename__ = "platform_invoice_line_reversal"
    __table_args__ = (
        UniqueConstraint("cancellation_id", "invoice_line_id", name="uq_platform_invoice_line_reversal"),
        CheckConstraint("amount_irr > 0", name="ck_platform_invoice_line_reversal_amount"),
    )
    id: uuid.UUID
    cancellation_id: uuid.UUID
    invoice_line_id: uuid.UUID
    amount_irr: int
    created_at: datetime

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

Add the six nullable snapshot fields to `FinanceInvoiceLine` in `backend/app/finance_models.py` exactly:

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
platform_ascora_term_share_irr: int = Field(
    default=0, sa_column=Column(BigInteger, nullable=False)
)
```

These are the only platform tables approved for Phase 4. Do not add a generic workflow/rule engine, inbound payment gateway, inventory, payroll, scheduler, notification-delivery table or plan-enforcement table.

Create the Alembic migration `f1a2b3c4d5e6_add_platform_billing.py` with:
- `down_revision = "e8f0a2b4c6d8"`;
- all tables above (use `sa.Uuid()`, `BigInteger`, `JSON`, `UTCDateTime`);
- `op.add_column("finance_invoice_line", ...)` for the six snapshot fields;
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

Plan catalog entries are optional reusable templates. The absence of a plan, or the absence of any active plan, never blocks an agreement or accrual path. Plan creation creates the plan plus its first `PlatformPlanVersion` in one transaction when the Superuser chooses to create one. Validation:
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
- Consumes: optional Task 2 plan versions as price/limit templates; `PlatformAgreement`, `PlatformCommissionTerm`, `PlatformGroup`, `PlatformGroupMember`.

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

def test_subscription_only_hybrid_and_custom_work_without_plan_records(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    gym1, _ = make_owner(client, superuser_headers, name="No Plan Subscription Gym")
    gym2, _ = make_owner(client, superuser_headers, name="No Plan Hybrid Gym")
    gym3, _ = make_owner(client, superuser_headers, name="No Plan Custom Gym")
    # still no platform_plan rows
    subscription = create_agreement(
        client, superuser_headers, gym_id=gym1["id"], mode="SUBSCRIPTION",
        subscription_amount_irr=500_000, plan_version_id=None, terms=[],
    )
    assert subscription.status_code == 200, subscription.text
    assert subscription.json()["plan_version_id"] is None
    assert subscription.json()["subscription_amount_irr"] == 500_000

    hybrid = create_agreement(
        client, superuser_headers, gym_id=gym2["id"], mode="HYBRID",
        subscription_amount_irr=200_000, plan_version_id=None,
        terms=[{"kind": "ANY", "basis": "PERCENT", "percent_bp": 500}],
    )
    assert hybrid.status_code == 200, hybrid.text

    custom = create_agreement(
        client, superuser_headers, gym_id=gym3["id"], mode="CUSTOM",
        subscription_amount_irr=0, plan_version_id=None,
        terms=[{"kind": "ANY", "basis": "FIXED", "fixed_irr": 10_000}],
    )
    assert custom.status_code == 200, custom.text

def test_group_agreement_keeps_per_branch_members_and_volume_discount(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # create 3 gyms, group with 3 members and allocation_bp summing to 10000,
    # create group agreement mode HYBRID with volume_discount_bp=500 and no plan
    # assert each member is traceable and no gym ledger row is created
    ...

def test_agreement_rejects_bad_modes_terms_overlap_and_non_superuser(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # gym admin gets 403; percent_bp > 10000 -> 422; both gym_id and group_id -> 400
    # effective_to < effective_from -> 400; unknown limits/terms -> 422
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_agreements.py`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement agreement lifecycle**

Validation:
- exactly one of `gym_id`/`group_id` is present;
- `mode` in the five approved modes;
- **no mode requires a plan record.** A plan version is optional for every mode. `FREE` and `COMMISSION` force `subscription_amount_irr=0`; `SUBSCRIPTION`, `HYBRID` and `CUSTOM` may use an explicit `subscription_amount_irr` with `plan_version_id=None` (including a valid zero amount). If a plan version is supplied, its `monthly_price_irr` is the default only when `subscription_amount_irr` is omitted; an explicit amount always wins and is audited;
- commission terms are allowed only for `COMMISSION`, `HYBRID` and `CUSTOM`; `COMMISSION` requires at least one term; `SUBSCRIPTION` and `FREE` require none; `PERCENT` uses `percent_bp`, `FIXED` uses `fixed_irr`, `PERCENT_PLUS_FIXED` uses both; `max_fee_irr` caps the per-line fee when > 0;
- group membership allocation_bp values are 0..10000 and sum to 10000 for a group agreement; volume discount 0..10000;
- all create/activate/disable writes require `Idempotency-Key` and use `PlatformOperation`;
- activation serializes on `_lock_platform`, marks prior effective agreement for the same scope as `REPLACED`, and sets the new row `EFFECTIVE`; no historical term is edited;
- disable sets `DISABLED` but preserves all rows and receivables;
- **Superuser authority is unconditional.** No standing/overdue check may block create, activate, replace or disable for a Superuser. Overdue standing is displayed and may drive reminders, never a Superuser permission gate.

Store a JSON snapshot builder `_agreement_snapshot(agreement)` used by Task 4; it must include `mode`, `plan_version_id` (nullable), `subscription_amount_irr`, `volume_discount_bp`, `grace_days`, `restrict_after_days` and the ordered terms.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_agreements.py tests/api/routes/test_platform_plans.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_agreements.py
git commit -m "feat(platform): add agreements, groups and commission terms"
```

---

### Task 4: Snapshot the single ASCORA source at issue and accrue exactly once on confirmed collections

**Files:**
- Modify: `backend/app/finance_models.py` (`FinanceInvoiceLinePublic`)
- Modify: `backend/app/services/finance.py` (`issue_invoice`, `create_receipt`, `apply_customer_credit`, `invoice_public`)
- Modify: `backend/app/services/platform.py` (fee formatting/accrual helpers)
- Test: `backend/tests/api/routes/test_platform_fees.py`

**Interfaces:**
- Produces: `_snapshot_invoice_platform(session, *, invoice, issue_date)` in `finance.py`.
- Produces: `_platform_fee_for_portion(snapshot: dict[str, Any], portion_irr: int, line_payable_irr: int) -> int` in `platform.py`.
- Produces: `_create_platform_ascora_receivable(session, *, scope, actor, invoice, amount_irr, received_on, receipt_id=None, credit_movement_id=None, source_prefix) -> int`.
- Produces: `FinanceInvoiceLinePublic.platform_allocation_status: str`, `.platform_fee_irr: int`, `.platform_ascora_term_share_irr: int` (the raw snapshot JSON stays server-side).
- Consumes: Task 3 `_agreement_snapshot`; Task 1 `FinanceInvoiceLine` platform fields and `PlatformReceivable`; existing `FinanceCoachEarning.platform_share_irr`.

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

def test_ascora_coach_share_and_platform_commission_are_recognized_exactly_once(
    client: TestClient, superuser_headers: dict[str, str], db_session: Session
) -> None:
    # coach snapshot: COACH 20% + ASCORA 10% + GYM 70%; platform agreement 5%
    # issue line -> status COACH_ASCORA_TERM, platform_ascora_term_share_irr=100_000
    # collect 1_000_000 -> exactly one platform revenue recognition of 100_000
    # (not 150_000); platform journal 4100 credit total == 100_000
    # a second sale without an ASCORA coach term uses the 5% commission instead
    ...

def test_no_fee_for_free_subscription_or_unmatched_source_and_no_duplicate_on_retry(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # FREE agreement -> NOT_APPLICABLE; subscription-only -> no commission
    # ASCORA-source term does not match GYM invoice; same receipt key replays
    # draft invoice has no platform snapshot; cancellation cannot create a fee
    # a line whose coach earning unexpectedly has platform_share_irr while
    # status is SNAPSHOTTED fails closed with platform_double_recognition_guard
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py`
Expected: FAIL because no platform snapshot/accrual exists.

- [ ] **Step 3: Implement snapshot and accrual**

Expose `platform_allocation_status`, `platform_fee_irr` and `platform_ascora_term_share_irr` in `FinanceInvoiceLinePublic` and populate them in `invoice_public` so tests/UI can verify the snapshot without exposing the raw JSON.

In `issue_invoice`, call `_snapshot_invoice_platform` immediately after `_snapshot_invoice_coaches`. Selection:
- **single-recognition rule first:** if the coach snapshot for the line allocates a positive ASCORA share (computed with the existing `_allocate_coach_shares` against the line’s full payable), set `platform_allocation_status="COACH_ASCORA_TERM"`, `platform_ascora_term_share_irr` to that scheduled share, set `platform_fee_irr` to the same scheduled amount for display, and persist a `platform_snapshot` with `source="COACH_ASCORA_TERM"`, coach agreement id/version and the scheduled share. **Do not** select or snapshot a platform commercial commission for that line; a separate commission would double-recognize the same ASCORA money;
- otherwise, find an effective `PlatformAgreement` for the gym (`gym_id`) or an effective group agreement whose `PlatformGroupMember` contains the gym, with `effective_from <= issue_date` and `effective_to` null or `>= issue_date`, ordered by `version` descending;
- mode `FREE` or `SUBSCRIPTION`: `platform_allocation_status="NOT_APPLICABLE"`, fee 0;
- mode `COMMISSION`, `HYBRID`, `CUSTOM`: choose the most specific term: exact `kind` before `ANY`, exact `acquisition_source` before `ANY`; no term => `NO_TERM` and fee 0;
- snapshot JSON: `agreement_id`, `version`, `mode`, `term` (kind/source/basis/percent/fixed/cap), `volume_discount_bp`;
- `platform_fee_irr` = fee computed against the line's full `payable_irr` for display/cap; never mutate invoice totals.

This makes the coach snapshot, when present with an ASCORA recipient, the single source of the ASCORA amount. The platform agreement remains the source only for lines without an ASCORA coach term. Audit both decisions as `platform.ascora_source.snapshotted` with `source=COACH_ASCORA_TERM|PLATFORM_COMMISSION|NONE`.

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

In `create_receipt` and `apply_customer_credit`, after `_create_coach_earnings`, call `_create_platform_ascora_receivable` for each invoice allocation/line portion. It recognizes exactly one platform amount per line:

- **`COACH_ASCORA_TERM` line:** query the `FinanceCoachEarning` rows created for this receipt/credit and line. Create `PlatformReceivable(source_type="COACH_ASCORA_SHARE", source_id=earning.id, source_key=f"ascora:{earning.id}", amount_irr=earning.platform_share_irr, ...)` for the actual earned ASCORA share. If `earning.platform_share_irr == 0`, create no receivable. Post `1100 receivable debit / 4100 commission revenue credit` (or `4200` for `CUSTOM` mode) for that amount. This recognizes the coach agreement’s ASCORA share once and **never** also creates a platform commission receivable for the same line.
- **`SNAPSHOTTED` line:** compute `fee = _platform_fee_for_portion(snapshot, portion, line.payable_irr)`. If the corresponding earning unexpectedly has `platform_share_irr > 0`, fail closed with 409 `platform_double_recognition_guard` instead of recognizing both; this is a data/snapshot inconsistency, not an auto-correction.
- caps cumulative fee for the line at the snapshot’s fixed/percent scheduled total (query prior `PlatformReceivable` rows by source prefix and line ID) so installments cannot exceed 100%;
- creates `PlatformReceivable(gym_id=scope.gym_id, agreement_id=..., source_type="COMMISSION", source_id=line.id, source_key=f"{source_prefix}:{line.id}", amount_irr=fee, due_on=received_on + 30 days, status="OPEN", snapshot=snapshot)`;
- when `fee > 0`, posts a balanced `PlatformJournal` `1100 receivable debit / 4100 commission revenue credit` (or `4200` for `CUSTOM` mode) with `source_type="finance_receipt"`/`"finance_credit"` and source ID;
- otherwise `NOT_APPLICABLE`/`NO_TERM` lines create nothing;
- writes `PlatformAudit` action `platform.ascora.recognized` with `source=COACH_ASCORA_TERM|PLATFORM_COMMISSION`, amount and source key;
- never touches gym cash or gym journal;
- uses the platform lock and a unique `source_key` so a retry cannot double-accrue.

For `apply_customer_credit`, same helper with `credit_movement_id` and `source_prefix=f"credit:{movement.id}"`.

This single-recognition rule is the only permitted interaction between `FinanceCoachEarning.platform_share_irr` and Phase 4 platform fees. Do not add a second platform revenue row for the same earning or line.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_fees.py tests/api/routes/test_finance_receipts.py tests/api/routes/test_finance_invoices.py`
Expected: PASS; existing finance receipt/invoice behavior unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance.py backend/app/services/platform.py backend/tests/api/routes/test_platform_fees.py
git commit -m "feat(platform): snapshot and recognize the single ASCORA amount once"
```

---

### Task 5: Subscription accrual, platform invoices, payments and cancellation

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/api/routes/platform.py`
- Test: `backend/tests/api/routes/test_platform_invoices.py`

**Interfaces:**
- Produces: `accrue_subscription_period(session, *, actor, agreement_id, period, operation_key) -> PlatformReceivablePublic`.
- Produces: `issue_platform_invoice(session, *, actor, gym_id=None, group_id=None, period_start, period_end, due_on, operation_key) -> PlatformInvoicePublic`.
- Produces: `record_platform_payment(session, *, actor, invoice_id, amount_irr, method, reference, received_on, allocations, operation_key) -> PlatformPaymentPublic`.
- Produces: `cancel_platform_invoice(session, *, actor, invoice_id, reason, operation_key) -> PlatformInvoicePublic`.
- Produces routes: `POST /api/v1/platform/agreements/{id}/accrue-period`, `GET/POST /api/v1/platform/invoices`, `GET /api/v1/platform/invoices/{id}`, `POST /api/v1/platform/invoices/{id}/payments`, `POST /api/v1/platform/invoices/{id}/cancel`, `GET /api/v1/platform/receivables`, `GET /api/v1/platform/payments`.
- Consumes: Task 1 models; Task 3 agreements; Task 4 `PlatformReceivable` rows.

- [ ] **Step 1: Write the failing tests**

```python
def test_subscription_accrual_is_month_bounded_idempotent_and_not_fabricated_without_a_plan(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # COMMISSION agreement -> accrue-period returns 400 platform_not_configured
    # SUBSCRIPTION agreement effective 2026-11-01, plan_version_id=None and
    # explicit subscription_amount_irr=500_000
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

def test_unpaid_platform_invoice_cancellation_is_append_only_and_reversible(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # cancel only an ISSUED invoice with paid_irr == 0 and a reason >= 3 chars
    # original invoice total/lines remain byte-identical; cancellation + line
    # reversal rows are appended; linked receivables become available again
    # repeat cancel -> same cancellation row, no duplicate journal
    # group volume-discount journal is reversed with 1100 debit / revenue credit
    # cancel a PARTIALLY_PAID/PAID invoice -> 409 platform_invoice_paid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_invoices.py`
Expected: FAIL because the routes/services do not exist.

- [ ] **Step 3: Implement subscription, invoice and payment flows**

Subscription accrual:
- `_lock_platform`, reload agreement, require `EFFECTIVE` and mode in `SUBSCRIPTION`, `HYBRID`, `CUSTOM`;
- resolve amount in this order: explicit `subscription_amount_irr` when supplied, otherwise the optional plan version’s `monthly_price_irr`, otherwise 0. **A plan record is not required.** A positive explicit amount with `plan_version_id=None` is valid for subscription-only, hybrid and custom;
- if resolved amount is 0 (free or no subscription component), return 400 `platform_subscription_not_configured` and create **no** receivable, invoice line or journal; never fabricate a zero-value subscription;
- validate the month (`YYYY-MM`) start and end inside `effective_from`/`effective_to`; otherwise 400 `platform_period_outside_agreement`;
- idempotency via `PlatformOperation`; duplicate protection via `source_key=f"subscription:{agreement.id}:{period}"`;
- create `PlatformReceivable(source_type="SUBSCRIPTION", source_id=agreement.id, due_on=period_start, snapshot=...)`;
- post `PlatformJournal` `1100 debit / 4000 subscription revenue credit`; audit `platform.subscription.accrued`; one commit.

Invoice issuance:
- gather `PlatformReceivable` for the chosen gym or group with `status in ("OPEN","PARTIAL")` and `due_on <= period_end`, ordered by `created_at`;
- apply available `PlatformCredit` rows for the same gym, oldest first, by appending `PlatformCreditApplication` rows; available credit = `credit.amount_irr - sum(existing applications)`; a credit may not make a line negative; do not mutate the credit amount;
- require at least one nonzero line; if none return 400 `platform_invoice_empty`;
- allocate `PlatformSequence("PLATFORM_INVOICE")` under `_lock_platform`; each line stores `gross_irr` (receivable net), `discount_irr` (group allocation) and `amount_irr = gross_irr - discount_irr - credit_irr` (never negative); mark receivable `INVOICED` or `CREDITED` when credit covers it in full (never `PAID`, because no cash moved);
- for a group invoice, apply the effective group agreement's `volume_discount_bp` to the gross total, split the discount proportionally with largest-remainder integer math, and set `PlatformInvoice.discount_irr`; per-branch `gym_id` and `PlatformGroupMember.allocation_bp` stay traceable;
- no journal for ordinary invoice issuance (the receivable already exists); for a group volume discount, post a balanced `PlatformJournal` `4000/4100 revenue debit / 1100 receivable credit` for the discount from each revenue source, so the invoice total and receivable balance still reconcile; audit `platform.invoice.issued` with `discount_irr`.

Payment:
- validate `amount_irr > 0` and allocations sum to `amount_irr`; default allocations are FIFO over unpaid lines; reject over-allocation with 400 `platform_payment_over_allocated`;
- create append-only `PlatformPayment` and `PlatformPaymentAllocation` rows; recompute line/invoice/receivable `paid_irr` as derived caches from allocations (never treat the cache as a posted amount); set lifecycle `PARTIALLY_PAID`/`PAID`;
- post `PlatformJournal` `1000 debit / 1100 receivable credit`; audit `platform.payment.recorded`;
- unique `operation_key` + replay returns the same payment.

Unpaid invoice cancellation:
- valid only when the invoice is `ISSUED` with **zero payment allocations** (`paid_irr == 0`); a `PARTIALLY_PAID` or `PAID` invoice returns 409 `platform_invoice_paid` and must use a credit note/refund path instead;
- require a reason of at least 3 characters and an `Idempotency-Key`; repeat returns the same cancellation;
- append a `PlatformInvoiceCancellation` and one `PlatformInvoiceLineReversal` per invoice line; the original `PlatformInvoice.total_irr` and `PlatformInvoiceLine.amount_irr` rows are **never changed**;
- mark only the lifecycle status `CANCELLED`; compute invoice balance as `total_irr - sum(reversals) - paid_irr`; the linked `PlatformReceivable.amount_irr` never changes and becomes available again because active invoice-line reservations are reduced by the reversal rows;
- if `PlatformCreditApplication` rows were used on the cancelled invoice, append replacement `PlatformCredit` rows for the applied amounts (source `INVOICE_CANCELLATION`, reason links to the cancellation) so the credit remains usable; never mutate or delete the original credit applications;
- if the cancelled invoice posted a group volume-discount journal at issuance, post a balanced reversal `1100 receivable debit / 4000/4100 revenue credit` for that discount; ordinary invoices have no issuance journal and therefore no cancellation journal;
- cancellation does **not** waive the underlying platform fee: the accrued receivable remains. If Superuser intends to waive the fee, a separate `PlatformCredit` (append-only) and balanced revenue reversal must be recorded with its own reason; never conflate cancellation with write-off;
- audit `platform.invoice.cancelled` with reason, invoice id and reversal ids.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_invoices.py tests/api/routes/test_finance_receipts.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/api/routes/platform.py backend/tests/api/routes/test_platform_invoices.py
git commit -m "feat(platform): add subscription accrual, invoices, payments and cancellation"
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
    # refund 300_000 -> append PlatformCredit 30_000; original receivable amount unchanged
    # credit is consumed by the next platform invoice through PlatformCreditApplication
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
- find `PlatformReceivable` commission/ASCORA-share rows for the refunded invoice's lines, ordered oldest first;
- proportional reversal = `sum(platform receivables for invoice) * refund.amount_irr // _invoice_paid_irr(...)`;
- **append** a `PlatformCredit(gym_id=..., source_type="REFUND", source_id=refund.id, amount_irr=credit, reason=refund.reason)` for the reversed amount. Never reduce, edit or delete the original receivable amount, invoice line, invoice total or payment allocation. The credit is consumed by the next platform invoice through `PlatformCreditApplication`;
- post `PlatformJournal` `4100/4200 revenue debit / 1100 receivable credit` for the reversed amount; source `finance_refund`;
- audit `platform.ascora.reversed` with refund ID, source key and amount;
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

### Task 7: Dues standing, in-app reminders and read-only owner access

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/services/finance.py`
- Modify: `backend/app/api/routes/platform.py`
- Modify: `backend/app/api/routes/finance.py`
- Modify: `backend/app/finance_models.py`
- Test: `backend/tests/api/routes/test_platform_reports.py`
- Test: `backend/tests/api/routes/test_platform_owner_access.py`

**Interfaces:**
- Produces: `platform_standing(session, *, gym_id, as_of) -> PlatformStandingPublic`.
- Produces: `list_platform_reminders(session, *, as_of, within_days=7) -> PlatformRemindersPublic`.
- Produces: `owner_platform_billing(session, *, gym_id, as_of) -> FinancePlatformBillingPublic` (own invoices, dues, payments; no mutations).
- Produces Superuser routes: `GET /api/v1/platform/dues`, `GET /api/v1/platform/dues/{gym_id}`, `GET /api/v1/platform/reminders`.
- Produces owner read-only routes: `GET /api/v1/finance/platform/invoices`, `GET /api/v1/finance/platform/dues`, `GET /api/v1/finance/platform/payments`.
- Produces: `PlatformStandingPublic` fields `gym_id`, `open_irr`, `overdue_irr`, `oldest_due_on`, `overdue_days`, `stage` (`CURRENT`, `DUE`, `GRACE`, `RESTRICTED`), `informational_restrictions`.
- Consumes: existing `resolve_finance_scope`, `FINANCE_VIEW`, `GymContextDep`, `CurrentSuperuser`.

- [ ] **Step 1: Write the failing tests**

```python
def test_overdue_stage_progresses_from_due_to_grace_to_restricted_without_hiding_history(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # invoice due 2026-11-01, as_of 2026-11-03 -> DUE
    # as_of 2026-11-10 -> GRACE (grace_days=7)
    # as_of 2026-11-25 -> RESTRICTED (restrict_after_days=21)
    # GET /platform/dues/{gym} still returns old invoices and export still returns rows
    # Superuser can still create/replace agreements and groups while restricted

def test_platform_reminders_list_due_soon_and_overdue_without_scheduler(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # within_days=7 returns due and overdue
    # response is marked delivery_scope="IN_APP_ONLY"
    # no email/SMS/scheduler side effects; proactive delivery remains OUTSTANDING

def test_gym_owner_has_read_only_access_to_own_platform_billing(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # owner A can GET own /finance/platform/invoices, /dues and /payments
    # owner A cannot read owner B's rows; owner A cannot POST/PATCH any platform route
    # Superuser sees both gyms; owner response has no mutation controls
    # access remains readable when the gym finance module is disabled
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py tests/api/routes/test_platform_owner_access.py -k "overdue or reminders or owner"`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement standing, reminders and owner read models**

Standing is derived on read from open platform invoices/receivables:
- `open_irr` = invoice total − paid − invoice-line reversals (cancelled invoices contribute zero);
- `oldest_due_on` = earliest unpaid invoice due date;
- `overdue_days` = max(as_of − due_on, 0);
- stage: current before due; `DUE` from due date; `GRACE` after `grace_days`; `RESTRICTED` after `restrict_after_days` (values from the effective agreement; conservative defaults 7/21);
- `informational_restrictions` names the commercial reminders shown to the gym, but **no route gate is applied**. In particular, Superuser create/activate/replace/disable/group actions are never blocked by overdue standing; they continue with audit (`#41`, `#89`). Phase 4 does not invent an automatic core-feature lockout; the configured grace/restrict days drive visible stages and reminders only. Any future enforcement must be separately approved and must preserve read-only history/export.
- Owner read routes filter by `ctx.gym.id`, require only `FINANCE_VIEW`, do not call `require_enabled()` (read/export remains available when finance is disabled), and expose no mutation methods. Cross-gym IDs return 404/403 with no leakage.

Reminders: in-app computed list:
- `due_soon`: unpaid invoices with `due_on` between `as_of` and `as_of + within_days`;
- `overdue`: unpaid invoices with `due_on < as_of`;
- `delivery_scope="IN_APP_ONLY"`;
- no email/SMS/background job in this task. **Proactive delivery (#15/#71) remains an approved outstanding requirement** and must not be marked complete in the gap audit or evidence; a later explicitly approved delivery slice owns it.

- [ ] **Step 4: Run tests**

Run: `cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/api/routes/test_platform_reports.py tests/api/routes/test_platform_owner_access.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/platform.py backend/app/services/finance.py backend/app/api/routes/platform.py backend/app/api/routes/finance.py backend/app/finance_models.py backend/tests/api/routes/test_platform_reports.py backend/tests/api/routes/test_platform_owner_access.py
git commit -m "feat(platform): add dues standing, in-app reminders and owner read-only access"
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
def test_gym_summary_keeps_cashflow_and_accrual_profit_independent(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # issue 1_000_000 with no receipt:
    #   sales_irr=1_000_000, recognized_revenue_irr=1_000_000,
    #   cash_collected_irr=0, receivable_irr=1_000_000
    # pay a 50_000 expense:
    #   net_cashflow_irr=-50_000, recognized_expenses_irr=50_000,
    #   estimated_operating_profit_irr=950_000
    # collect 400_000 + accrue 120_000 coach share + 40_000 platform fee:
    #   net_cashflow_irr=350_000; recognized_expenses_irr=210_000;
    #   estimated_operating_profit_irr=790_000 (profit does not follow cash)
    # overdue_irr only after due; payables are separate balances

def test_platform_overview_separates_collected_cash_from_recognized_revenue(
    client: TestClient, superuser_headers: dict[str, str]
) -> None:
    # no plans -> mrr_irr == 0
    # accrue 100_000 platform receivable, no payment:
    #   collected_fees_irr=0, recognized_platform_revenue_irr=100_000,
    #   receivable_irr=100_000, estimated_operating_profit_irr=100_000
    # record 30_000 payment:
    #   collected_fees_irr=30_000, recognized revenue still 100_000
    # record 20_000 PlatformCost -> profit 80_000; by_gym contribution uses
    # recognized revenue minus recorded cost, never collected cash

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

Gym summary fields — keep the two families visibly separate in the DTO and UI:

**Cashflow (cash facts from the posted gym journal):**
- `cash_collected_irr` = debits to account `1000` on `RECEIPT_CONFIRMED` journals in range, including customer advances received;
- `cash_refunded_irr` = credits to account `1000` on `REFUND_RECORDED` journals in range;
- `cash_expenses_paid_irr` = credits to account `1000` on `EXPENSE_PAID` journals in range;
- `cash_coach_settlements_irr` = credits to account `1000` on `COACH_SETTLED` journals in range;
- `net_cashflow_irr = cash_collected_irr - cash_refunded_irr - cash_expenses_paid_irr - cash_coach_settlements_irr`;
- exclude `OPENING_BALANCE` and `CORRECTION` journals from operating cashflow; corrections remain visible separately.

**Accrual (posted ledger facts):**
- `recognized_revenue_irr` = credits minus debits on accounts `4000`/`4100` for journals in range, excluding `OPENING_BALANCE` and tenant-balance-only corrections; this is ledger-derived, not receipt cash;
- `recognized_expenses_irr` = debits minus credits on accounts `5000`/`5100` for journals in range, excluding `OPENING_BALANCE`, plus platform commission/subscription/ASCORA-share receivables accrued for this gym in range (the platform ledger is a separate recorded fact);
- `estimated_operating_profit_irr = recognized_revenue_irr - recognized_expenses_irr`; label **estimated** in DTO/docs; never call it net income and never substitute collected cash;
- `sales_irr` = sum issued `FinanceInvoice.total_irr` with `issue_date` in range (billing metric, not cash);
- `receivable_irr` = open customer invoice balance after confirmed allocations, valid credits and linked reversals;
- `overdue_irr` = sum open invoice balances whose `due_date < today` (or installment due rows if `due_date` is null; follow existing `_invoice_reminder` logic);
- `renewals_due` = count of active `FinanceMembership` ending in the next 30 days;
- `coach_payable_irr` = sum over `FinanceCoachEarning` of `max(coach_share - confirmed settlements - reserved - adjustments, 0)`;
- `platform_payable_irr` = open platform receivables for this gym.

Do not subtract `coach_payable_irr` or `platform_payable_irr` from profit a second time: their earned/accrued expense is already in `5100` or in the platform accrual added above.

Add `FinanceGymSummaryPublic` and `FinanceGymReportRowsPublic` DTOs to `finance_models.py`.
`POST /platform/costs` requires `Idempotency-Key`, uses `PlatformOperation`, validates `amount_irr >= 0`, and records `PlatformAudit`; a cost is optional and a missing cost must never be guessed.

Platform overview fields — same separation:
- `mrr_irr` = sum active monthly subscription amounts for effective agreements (0 if no plans);
- `collected_fees_irr` = debits to platform account `1000` on `PLATFORM_PAYMENT` journals in range (**cash**; equal to payment amounts when allocations are consistent);
- `recognized_platform_revenue_irr` = credits minus debits on platform revenue accounts `4000`/`4100`/`4200` in range (**accrual**);
- `invoiced_fees_irr` = sum `PlatformInvoice.total_irr` issued in range (billing metric);
- `receivable_irr` = sum open/partial invoice balances (not cash);
- `overdue_irr` = sum balances where due date passed;
- `by_gym` = per-gym `recognized_platform_revenue_irr`, `collected_fees_irr`, open receivables, recorded `PlatformCost` and `contribution_irr = recognized_platform_revenue_irr − recorded_costs` (null/zero if no costs, never infer a cost);
- `estimated_operating_profit_irr = recognized_platform_revenue_irr - recorded_platform_costs_irr`;
- `active_plans`, `active_agreements`, `zero_plan_mode` boolean.

Exports:
- every exported metric row carries `metric_family` = `CASHFLOW`, `ACCRUAL`, `BILLING` or `BALANCE`; never mix families in one unlabeled total;
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
git commit -m "feat(platform): add cashflow/accrual dashboards and exports"
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
  - **overview**: separate **cashflow** cards (collected fees, refunds, net cash) from **accrual** cards (recognized platform revenue, recorded costs, estimated operating profit); separate billing/balance cards (invoiced, receivables, overdue); MRR; active plans/agreements; zero-plan banner; per-gym table; cost form; CSV export button;
  - **plans**: create plan/version, activate/retire, limits/usage editor, "no active plans" empty state; plans explicitly labeled optional templates;
  - **agreements**: create gym/group agreement, mode selector, optional plan selector, explicit subscription amount field for no-plan subscription/hybrid/custom, commission term rows, effective dates, activate/disable, group member editor;
  - **invoices**: issue gym/group invoice for a period, inspect gross/discount/net lines with gym allocation, record partial payment, cancel an unpaid invoice with a reason and view the append-only reversal; never offer paid-invoice cancellation;
  - **dues**: standing stages, informational grace/restricted badges, in-app reminder list with `IN_APP_ONLY` note, export.
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

### Task 10: Gym dashboard, owner platform view, coach aggregate, athlete dues and Playwright coverage

**Files:**
- Create: `frontend/src/pages/finance/FinancePlatformSection.tsx`
- Modify: `frontend/src/pages/FinancePage.tsx`
- Modify: `frontend/src/pages/finance/FinanceOverviewSection.tsx`
- Modify: `frontend/src/pages/CoachEarningsPage.tsx`
- Modify: `frontend/src/pages/AthleteFinancePage.tsx`
- Modify: `backend/app/api/routes/finance.py`
- Modify: `backend/app/services/finance.py`
- Modify: `backend/app/finance_models.py`
- Test: `frontend/tests/finance-dashboard.spec.ts`

**Interfaces:**
- Produces: `GET /api/v1/finance/my/coach-summary` (no `GymContextDep`; resolves all `GymMembership` roles for `CurrentUser`, requires at least one active coach role) returning cross-gym totals `calculated_irr`, `vested_irr`, `eligible_irr`, `settled_irr`, `reserved_irr`, `per_gym`. It queries only `FinanceCoachEarning`/`FinanceCoachSettlement` rows whose `gym_id` belongs to that user's active coach memberships.
- Produces: gym summary cards with separate **cashflow**, **accrual**, **billing** and **balance** groups, plus export button.
- Produces: read-only `FinancePlatformSection` tab using the owner platform routes from Task 7; no create/cancel/pay controls.
- Produces: athlete due/overdue card using existing `readMyFinanceAccount`.

- [ ] **Step 1: Write the failing tests**

```ts
test("gym admin sees cashflow and accrual metrics separately and can export", async ({ page }) => {
  await page.goto("/gyms/" + gymId + "/finance")
  await expect(page.getByText("جریان نقدی")).toBeVisible()
  await expect(page.getByText("سود عملیاتی تقریبی (تعهدی)")).toBeVisible()
  await expect(page.getByText("وجه دریافت‌شده")).toBeVisible()
  await expect(page.getByText("فروش صادرشده")).toBeVisible()
  await page.getByRole("button", { name: "خروجی CSV" }).click()
  // assert download filename
})

test("gym owner sees own platform invoices, dues and payments read-only", async ({ page }) => {
  await page.goto("/gyms/" + gymId + "/finance")
  await page.getByRole("tab", { name: "مالی پلتفرم" }).click()
  await expect(page.getByText("صورتحساب‌های پلتفرم")).toBeVisible()
  await expect(page.getByText("مانده بدهی")).toBeVisible()
  await expect(page.getByRole("button", { name: "ثبت پرداخت" })).toHaveCount(0)
})

test("coach sees cross-gym totals on the earnings page", async ({ page }) => {
  await page.goto("/gyms/" + gymId + "/my/earnings")
  await expect(page.getByText("مجموع همه باشگاه‌ها")).toBeVisible()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && bunx playwright test tests/finance-dashboard.spec.ts --reporter=line`
Expected: FAIL because the cards/aggregate/owner view are absent.

- [ ] **Step 3: Implement the role views**

- Gym overview: fetch `FinanceService.readFinanceGymSummary({ query: { from_date, to_date } })`; render grouped cards:
  - **Cashflow:** cash collected, refunds, expenses paid, coach settlements paid, net cashflow;
  - **Accrual:** recognized revenue, recognized expenses, **estimated** operating profit;
  - **Billing:** issued sales;
  - **Balances:** receivables, overdue, coach payable, platform payable.
  Add date range and CSV download (`/api/v1/finance/reports/export?from_date=...&to_date=...` via authenticated fetch). Never label a balance as cash or cashflow as profit.
- Owner platform view: add a `finance.tabPlatform` tab rendering `FinancePlatformSection` from the read-only owner endpoints; show invoices, dues/standing and payment history with no mutation buttons; show a clear note that ASCORA billing is separate from the gym’s own ledger.
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
git add frontend/src/pages/finance/FinancePlatformSection.tsx frontend/src/pages/FinancePage.tsx frontend/src/pages/finance/FinanceOverviewSection.tsx frontend/src/pages/CoachEarningsPage.tsx frontend/src/pages/AthleteFinancePage.tsx backend/app/api/routes/finance.py backend/app/services/finance.py backend/app/finance_models.py frontend/tests/finance-dashboard.spec.ts
git commit -m "feat(finance): add cashflow/accrual dashboards and owner platform view"
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
- `what existed` vs `what changed` mapped to `FR-PLAN`, `FR-FEE`, `FR-REPORT`, and a complete decision matrix for **all 92 decisions + `ADD-01`** with `PASS`/`PLANNED`/`DEFERRED` (Phase 4 highlights #5/#6/#7/#8/#9/#10/#11/#12/#23/#34/#37/#41/#44/#47/#55/#57/#58/#60/#61/#78/#84/#91/#92);
- migration name/revision `f1a2b3c4d5e6`, additive columns, downgrade behavior and no existing finance rows rewritten;
- evidence that `SUBSCRIPTION`, `HYBRID` and `CUSTOM` work with zero plan rows and that all five modes work with zero active plans;
- evidence that refunds, credits and unpaid-invoice cancellations append reversals and leave original receivable/invoice amounts unchanged;
- evidence that a coach ASCORA share and a platform commission are recognized exactly once for the same collected portion;
- evidence that Superuser authority is unchanged while restricted and that gym owners have read-only access to only their own platform invoices, dues and payments;
- evidence that overdue stages/reminders are configured and surfaced, with any core-feature lockout explicitly marked as not implemented/deferred rather than silently claimed;
- separate cashflow and accrual profit figures with the formulas and a test showing an unpaid invoice increases accrual revenue but not cash;
- **proactive reminder delivery #15/#71 remains OUTSTANDING**; in-app reminders are explicitly partial and must not be reported as completed;
- manual QA for Superuser, Gym Admin, finance staff, coach and athlete;
- exact commands/results, distinguishing new failures from pre-existing ones;
- independent fresh-context review notes for each financially sensitive slice, including findings and how they were resolved before the next slice;
- one-paragraph independent self-review and concrete remaining risks;
- explicit "not merged, not deployed" status.

- [ ] **Step 2: Update the gap audit**

Add a Phase 4 status section stating:
- plans can be zero/optional and every mode, including subscription-only, hybrid and custom, works without mandatory plan records;
- platform receivables/collections are separate from gym ledger;
- group invoices keep per-branch lines and volume discounts remain traceable;
- posted receivable/invoice amounts are append-only; unpaid invoice cancellation is a linked reversal;
- Superuser authority is unconditional; owners have read-only own-tenant platform billing views;
- dashboards separate cashflow from accrual profit and export labeled metric families;
- in-app reminders exist, but **proactive delivery #15/#71 is an outstanding approved requirement**;
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
