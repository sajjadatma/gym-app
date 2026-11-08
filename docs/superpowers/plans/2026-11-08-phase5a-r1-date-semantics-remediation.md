# Phase 5A.7-R1 — Date-Semantics Blocker Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the three date-semantics LOCAL NO-GO blockers (DS-M1 gym summary, DS-M2 CSV exports, DS-M3 platform per-gym reports/exports), reconstruct or explicitly bound legacy dates, and re-run the full 5A.0 acceptance gate.

**Architecture:** Keep the existing FastAPI/SQLModel/PostgreSQL service model. Add read-only as-of calculations from authoritative event rows; do not rewrite posted journals or mutable business rows. Add explicit CSV `date_basis` metadata. Add a forward-only data-repair migration only for legacy reporting-date columns with an unambiguous source event. Add focused conformance tests at service and route level.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Alembic, pytest, Playwright, React, Docker Compose.

**Spec:** Phase 5A.7-R1 authorization (owner message), `docs/release/phase5a-local-go-no-go.md`, `docs/finance/date-semantics.md`, `docs/release/phase5a-local-baselines.md`, `docs/finance/phase4-evidence.md`.

## Global Constraints

- Local synthetic data only.
- No deployment, Vercel/Neon, provider, real financial data or merge to `main`.
- No new product features, redesign or unrelated refactoring.
- Preserve all 92 decisions + ADD-01; #18/#30/#46 stay Deferred; Partial/Outstanding stay unchanged unless verified evidence supports a change.
- Do not alter posted journals, payments, allocations, invoice lines or audit rows.
- Do not weaken any 5A.0 threshold and do not introduce a waiver.
- Every production behavior change starts from a failing test.
- Commit and push only after full verification.

## Root-Cause Findings

1. `gym_summary()` computes `renewals_due` from current `FinanceMembership.status` + current `end_date`, and `coach_payable_irr` from current settlement/adjustment totals. Both ignore `to_date`.
2. `_gym_report_rows()` uses current `paid_irr`/status for platform `BALANCE` rows, never emits `date_basis`, and skips a platform invoice line even when cancellation happened after the requested range.
3. `platform_gym_detail()` and `/platform/gyms/{gym_id}/export` have no historical endpoint-level conformance tests, although the service already uses as-of standing and period dates.
4. Legacy `recognized_on`/`applied_on` were backfilled from `created_at`. Some rows have authoritative source events in `source_key`, receipts, credit movements, refund journals or invoice cancellations; others do not.

## Review Focus

- Membership freeze/resume after the as-of date must not change the historical renewal count.
- A settlement/refund/cancellation after the as-of date must not change historical coach payable.
- A platform cancellation or payment after the as-of date must not change earlier per-gym balances.
- CSV balance rows must reconcile to the summary/report for the same `to_date`.
- Missing lifecycle audit for a legacy membership must fail closed or be documented, never guessed from today's row.

---

### Task 1: Historical gym summary (DS-M1)

**Files:**
- Modify: `backend/app/services/finance.py` (`gym_summary`, new helpers near coach/membership helpers)
- Test: `backend/tests/api/routes/test_finance_date_semantics_5a3.py` or new `test_finance_history_5a7r1.py`

**Interfaces:**
- Produces: `_earning_business_date(session, earning) -> date`
- Produces: `_settlement_cancellation_date(session, settlement) -> date | None`
- Produces: `_earning_paid_as_of(session, earning_id, as_of) -> int`
- Produces: `_earning_adjustment_as_of(session, earning_id, as_of) -> int`
- Produces: `_coach_payable_as_of(session, gym_id, as_of) -> int`
- Produces: `_membership_end_date_as_of(session, membership, as_of) -> date`
- Produces: `_renewals_due_as_of(session, gym_id, as_of) -> int`

- [ ] **Step 1: Write failing tests** for:
  - Membership ending in 30-day window as of a past date, later freeze/resume extends `end_date`, and a later cancellation.
  - Coach earning created on receipt date; settlement recorded/confirmed later; settlement cancelled later; refund adjustment posted later.
  - Assert summary values at multiple `to_date` values.
- [ ] **Step 2: Run tests, watch fail for mixed current-state values.**
- [ ] **Step 3: Implement helpers from authoritative rows.** Earning date = receipt `received_on`, credit movement `applied_on` (fallback local `created_at`), else journal `posting_date`. Settlement paid-as-of = items whose `paid_on <= as_of` and not cancelled on/before `as_of`. Adjustment = `applied_irr` where refund journal `posting_date <= as_of`. Membership end-date-as-of = current `end_date` minus `paused_days` from `finance.membership.resumed` audit rows whose `resume_on > as_of`; cancellation excluded when `cancelled_at <= as_of`; start date must be `<= as_of`.
- [ ] **Step 4: Run focused tests and existing finance suite.**
- [ ] **Step 5: Commit.**

### Task 2: Historical CSV exports and date-basis metadata (DS-M2)

**Files:**
- Modify: `backend/app/api/routes/finance.py` (`_gym_report_rows`, header and every row)
- Modify: `backend/app/services/platform.py` (as-of paid helpers if needed)
- Test: new `backend/tests/api/routes/test_finance_export_history_5a7r1.py`

**Interfaces:**
- Produces: CSV header `metric_family,row_type,reference,date,amount_irr,status,date_basis`
- Produces: every row has explicit `date_basis`
- Produces: platform receivable/invoice-line `BALANCE` amounts use as-of paid/credit state

- [ ] **Step 1: Write failing tests** for:
  - Header includes `date_basis`.
  - Summary balance rows equal `/finance/reports/summary` for the same `to_date`.
  - Partial receipt before as-of, later receipt after as-of.
  - Platform invoice partial payments, credit application, cancellation before vs after as-of.
  - Refund recorded after as-of and expense paid after as-of.
  - Offboarding export labels balance rows `as_of_export` and uses today's date.
- [ ] **Step 2: Run tests, watch fail.**
- [ ] **Step 3: Implement** as-of paid helpers, `date_basis` on every row, cancellation only hidden when `cancelled_on <= to_date`, and add `renewals_due` summary row.
- [ ] **Step 4: Run focused tests plus existing export tests.**
- [ ] **Step 5: Commit.**

### Task 3: Platform per-gym report and export conformance (DS-M3)

**Files:**
- Modify: `backend/app/services/platform.py` only if a test proves a defect.
- Test: new `backend/tests/api/routes/test_platform_gym_report_history_5a7r1.py`

**Interfaces:**
- Proves `GET /platform/reports/gyms/{gym_id}` equals the matching `by_gym` row in `GET /platform/reports/overview` for identical ranges/as-of.
- Proves `GET /platform/gyms/{gym_id}/export` metrics equal the detail endpoint.

- [ ] **Step 1: Write failing/coverage tests** across two gyms and two periods (Nov, Dec): subscriptions, receipts, partial payment, credits, cancellation, costs; query Nov, Dec and combined ranges; assert per-gym reconciliation and no cross-gym netting; assert export CSV metrics.
- [ ] **Step 2: Run; fix any real defect exposed.**
- [ ] **Step 3: Add route-level test for export content and tenant scope.**
- [ ] **Step 4: Run focused and existing platform suites.**
- [ ] **Step 5: Commit.**

### Task 4: Legacy reporting-date reconstruction

**Files:**
- Create: `backend/app/alembic/versions/<new>_repair_legacy_reporting_dates.py`
- Test: `backend/tests/test_finance_migrations.py`
- Create: `docs/finance/legacy-date-reconstruction.md`

- [ ] **Step 1: Write migration test** seeding legacy rows with authoritative sources (subscription source_key, receipt-linked commission source_key, earning-linked ASCORA share, refund journal, cancellation invoice) and non-authoritative rows that must remain unchanged.
- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Implement forward-only migration**:
  - `platform_receivable.recognized_on` from subscription period, receipt `received_on`, credit movement `applied_on`, or earning source.
  - `platform_credit.recognized_on` from refund journal posting date or invoice `cancelled_on`.
  - `finance_credit_movement.applied_on` from uniquely matched `ADVANCE_APPLIED` journal posting date; leave ambiguous rows untouched.
  - Preserve all amounts, journals, audit rows and timestamps.
- [ ] **Step 4: Run migration suite plus `TZ=UTC`.**
- [ ] **Step 5: Document repaired cases and irrecoverable/ambiguous cases.** Commit.

### Task 5: Evidence and final reassessment

**Files:**
- Modify: `docs/finance/date-semantics.md`
- Modify: `docs/release/phase5a-reconciliation.md`
- Modify: `docs/release/phase5a-local-go-no-go.md`
- Create: `docs/release/phase5a-r1-date-semantics-remediation.md`

- [ ] **Step 1: Produce route-verified endpoint matrix** from actual route decorators, with exact parameters, date basis, as-of behavior, test names and status.
- [ ] **Step 2: Update reconciliation/date-semantics evidence.**
- [ ] **Step 3: Reassess every mandatory 5A.0 criterion** and record LOCAL GO / CONDITIONAL LOCAL GO / LOCAL NO-GO with evidence.
- [ ] **Step 4: Run full backend, migrations, relevant Playwright, lint, type-check, build.**
- [ ] **Step 5: Obtain independent fresh-context verification.**
- [ ] **Step 6: Commit and push. Stop before Phase 5B.**

## Verification Commands

```bash
cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider
cd backend && ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider -m migrations
cd backend && TZ=UTC ENV_FILE=.env.dev ../.venv/bin/python -B -m pytest -q -p no:cacheprovider -m migrations
cd frontend && bun run lint:check && bun run build
cd frontend && PLAYWRIGHT_SUPERUSER_EMAIL=... PLAYWRIGHT_SUPERUSER_PASSWORD=... bunx playwright test <relevant specs>
```
