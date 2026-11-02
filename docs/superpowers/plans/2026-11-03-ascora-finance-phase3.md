# ASCORA Phase 3 — coach contracts, allocation and settlement

> **For agentic workers:** Execute this plan inline with `superpowers:executing-plans`. Steps use TDD; write the failing test, watch it fail, then implement.

**Goal:** Version coach agreements, allocate confirmed revenue deterministically (including MIXED discount funding), expose vesting/fixed compensation, record partial settlements, and surface post-refund discrepancies without automatic clawback.

**Architecture:** Extend the existing gym-scoped finance domain and service. Agreements are immutable versions with effective dates and ordered terms. Issued invoice lines snapshot the effective agreement. Confirmed receipt allocations create coach-earning rows and balanced journals. Settlement and discrepancy rows append; issued financial records are never rewritten.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL/Alembic, pytest, React/TypeScript/TanStack, Material 3, Playwright.

**Spec:** `docs/finance/ASCORA-FINANCE-PRD.md` (§13.2, §14.1–14.2, Phase 3 gate).

## Global Constraints

- Preserve all 92 decisions and ADD-01; keep #18, #30, #46 deferred.
- No automatic coach clawback. Do not infer delivery from publication or payment.
- Monetary calculations are integer-only, server-authoritative and deterministic.
- Issued invoices and posted journals are immutable; corrections append linked rows.
- Every write is gym-scoped, idempotent where money moves, and audited.
- No generic rule engine, microservice or unrelated refactor.
- Reuse existing Material 3 components, Jalali dates, generated client and i18n.

## Review Focus

- Partial receipts: split collection across invoice lines without losing or duplicating a rial.
- Discount funding: GYM/COACH/ASCORA/MIXED must leave coach and gym shares summing to the collected net; shortfall falls back deterministically.
- Missing agreement: intake still succeeds, coach share is unresolved, settlement refuses it.
- Vesting: no payout from unpaid or unvested sales; manual attestation is audited.
- Post-payout refund: no negative transfer; discrepancy is visible and manually resolvable.

## Task 1 — Decision #66 explicit bundle-discount allocation

**Files:** `backend/app/finance_models.py`, `backend/app/services/finance.py`,
`backend/tests/api/routes/test_finance_invoices.py`,
`frontend/src/pages/finance/FinanceInvoicesSection.tsx`, `frontend/src/i18n.tsx`

**Interfaces:** `FinanceInvoiceLineInput.bundle_discount_irr: int | None`.
When any line provides it, every line must provide it, each share ≤ that line's
net, and the shares must sum to `FinanceInvoiceCreate.discount_irr`; otherwise
`400 finance_discount_allocation_mismatch`. When all are `None`, keep the
existing proportional default. `FinanceInvoiceLinePublic` exposes the resulting
`discount_share_irr` (already present). The admin draft form offers an optional
per-line bundle-discount field and sends `bundle_discount_irr` only when the
user enters at least one value.

## Task 2 — Versioned coach agreements

Create `finance_coach_agreement` and `finance_coach_agreement_term` tables plus
migration. API: list/create/activate agreements. Terms are ordered and either
`PERCENT` (basis points) or `FIXED` (IRR) for recipients `COACH`/`ASCORA`/`GYM`.
Modes `DIRECT`/`WATERFALL`; vesting `ON_DATE`/`MANUAL` with `vesting_days`.
Activation validates at least one COACH term, percentages ≤ 100%, fixed values
≥ 0 and no duplicate sequence. Drafts are editable; activation is audited and
cannot be re-done.

## Task 3 — Snapshot the effective agreement on issue

Add nullable `coach_user_id`, `coach_agreement_id`, `coach_agreement_version`,
`coach_allocation_status` and `agreement_snapshot` to invoice lines. On issue,
for each line with a coach, select the highest active version effective on the
issue date and store the snapshot; if none, store `UNRESOLVED` without blocking
issue. Lines without a coach are `NOT_APPLICABLE`. Drafts may change the coach;
issued rows are frozen.

## Task 4 — Deterministic allocation on confirmed receipts

Add `finance_coach_earning` rows keyed by `(receipt_id, invoice_line_id)`.
Split each receipt allocation across invoice lines by payable using largest-
remainder. For each line snapshot, run the ordered formula on the collected
base and discount share: DIRECT percentages use the full base, WATERFALL uses
the remaining amount; fixed terms are capped by the remaining base. Discount
funding subtracts the discount from GYM, COACH, ASCORA or proportionally for
MIXED, with the gym as residual and a deterministic fallback. Coach, platform
and gym shares must sum to the collected portion. Post one balanced journal per
receipt (`5100` coach expense / `2100` coach payable). Missing snapshots create
an `UNRESOLVED` earning with zero payable.

## Task 5 — Vesting, fixed compensation and coach read API

Earnings expose calculated/vested/eligible/settled. `ON_DATE` vests when
`receipt_date + vesting_days` is reached; `MANUAL` requires an audited
attestation endpoint with reason. Fixed compensation uses the same term engine
and is capped by the collected line portion. Add `GET /finance/coach-earnings`
for finance users and `GET /finance/my/earnings` for the signed-in coach, both
gym-scoped.

## Task 6 — Manual and partial settlements

Add `finance_coach_settlement` and `finance_coach_settlement_item`. Create a
settlement for an amount up to the coach's eligible balance, allocating items
FIFO; post debit `2100` / credit `1000`; status `RECORDED`, then an audited
`CONFIRMED` step. Partial settlements leave the remainder eligible. No
settlement may include unresolved or unvested earnings.

## Task 7 — Post-refund discrepancies and reconciliation

On invoice refund recording, reverse the coach share proportionally to the
refund across that invoice's earnings. Apply the reversal to unsettled share
first (`5100`/`2100` reversal). Any portion already settled becomes an OPEN
`finance_coach_discrepancy`; never create a negative payout. Add list/resolve
endpoints; resolution requires a note and is audited.

## Task 8 — Coach financial UI and acceptance tests

Admin finance gets a Coaches tab (agreements, earnings, settlements,
discrepancies). Coaches get `/gyms/$gymId/my/earnings` with calculated/vested/
eligible/settled items and settlement history. Add i18n, regenerate the client,
and add Playwright coverage for agreement → invoice with coach → receipt →
vest → partial settlement and for a post-payout refund discrepancy. Update
`docs/finance/00-gap-audit.md` with #15/#71 in-app-only reminders.
