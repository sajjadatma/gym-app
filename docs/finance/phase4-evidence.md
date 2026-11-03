# ASCORA Finance Phase 4 — evidence and status

**Branch:** `feat/ascora-finance`
**Plan:** `docs/superpowers/plans/2026-11-03-ascora-finance-phase4.md`
**Migration head:** `f1a2b3c4d5e6`
**Status:** implemented locally, verified, pushed to the feature branch; **not merged and not deployed**.

## What existed

Phase 3 provided versioned coach agreements, deterministic sale allocation, confirmed-only coach settlements, cancellation of recorded payouts, refund adjustments, periodic fixed coach expenses, reconciliation and in-app reminders. There was no platform plan catalog, platform agreement/group contract, separate ASCORA receivable/payment ledger, platform invoice cancellation, owner platform-billing view or platform dashboard/export.

## What changed

### Platform billing module

- New `platform_*` tables for plans/versions, groups/members, agreements/commission terms, receivables, credits/applications, invoices/lines, invoice cancellations/line reversals, payments/allocations, journal/lines, audit, costs, sequence and idempotency.
- Platform journal is separate from `finance_journal`; it uses its own accounts (`1000`, `1100`, `4000`, `4100`, `4200`) and never touches gym cash or gym document sequences.
- Database guards: balanced platform journal trigger, append-only triggers on posted records, unique partial indexes for gym/group agreement versions, credit source uniqueness, cross-link tenant/group/invoice guards, cancellation status/payment guard.

### Monetization controls

- Superuser plan catalog with effective-dated versions, limits, activation/retirement and usage counts.
- Zero plans are valid. `FREE`, `SUBSCRIPTION`, `COMMISSION`, `HYBRID` and `CUSTOM` agreements work with `plan_version_id=None` and an explicit subscription amount.
- Gym and group agreements, effective-dated versions, activation/replacement/disable, commission terms by service kind and acquisition source, volume discounts.
- Superuser authority is unconditional; overdue standing is informational and never a route gate.

### Fees, invoices, payments and refunds

- Invoice issue snapshots the single ASCORA source: a coach ASCORA term suppresses the separate platform commission; otherwise the most specific platform commission term applies.
- Commission/ASCORA share is recognized only on confirmed receipts or applied advances.
- Fixed and percentage fees are capped by the snapshot; duplicate recognition is guarded.
- Subscription accrual validates the whole month against agreement dates; group subscription accrual requires a branch.
- Platform invoices aggregate open receivables, preserve per-branch group lines, support partial payments and append-only unpaid cancellation with reversal rows and replacement credits.
- Refunds append `PlatformCredit` and a balanced platform revenue reversal; original receivable/invoice amounts are never rewritten.

### Dashboards, exports and owner access

- Gym summary separates cashflow (`1000` movements) from accrual revenue/expense and reports balances/payables separately.
- Platform overview separates collected cash, recognized platform revenue, billed amounts, receivables and estimated operating profit; MRR only counts currently effective agreements.
- Gym owners have read-only access to their own platform invoices, dues and payments, including their group-invoice branch lines; access survives finance being disabled.
- CSV exports label rows by `CASHFLOW`, `ACCRUAL`, `BILLING` or `BALANCE`; offboarding export includes finance and platform history.

### UI

- Superuser `/platform/finance` page: overview, plans, agreements, invoices, dues/reminders, CSV export, plan/agreement/invoice creation, payment recording and unpaid cancellation.
- Gym finance overview dashboard with separate cashflow/accrual cards and export.
- Gym finance “Platform billing” read-only tab for owners.
- Coach earnings shows an all-gyms summary; athlete finance shows amount due/overdue count.

## Verification

- Backend full suite: **295 passed**.
- Migration tests: **12 passed**.
- Ruff: clean. Mypy: clean.
- Frontend lint/typecheck/unit/build: clean.
- Full Playwright: **140 passed, 3 skipped** with Mailpit available and superuser credentials configured; the 3 skips are the environment-gated superuser suite when credentials are absent.
- Docker backup/restore drill at migration head `f1a2b3c4d5e6`: **PASS**. Counts `{"user": 9, "gym": 3, "athlete_profile": 4, "body_analysis_file": 1, "workout_program_version": 4}`, `ok:true`, live restore reverted the corrupted gym name and readiness returned 200.

## Deviations / decisions

- Overdue `RESTRICTED` is a visible informational stage only. No automatic core-feature lockout was invented; Superuser actions, finance history, exports and athlete workout history stay available. Any future enforcement requires explicit approval.
- Proactive reminder delivery (#15/#71) is **NOT implemented**. In-app reminders are labeled `IN_APP_ONLY`; the proactive delivery requirement remains outstanding.
- Plan limits are stored and usage is surfaced, but no core feature enforcement was added because numeric limits are pilot configuration.
- The TanStack route tree was patched manually because the local build did not regenerate it automatically for the new route.
- The platform UI is compact and functional rather than a full bespoke dashboard redesign. Advanced configuration remains narrower than the ideal: group-contract creation, full multiple-term editing, plan-version lifecycle/usage actions, platform-cost entry, invoice line inspection, payment-history label and cancellation-reason input are API-first or read-only in the UI.

## Deferred decisions

#18 usage/attendance finance input, #30 automatic post-payout coach clawback, and #46 advanced AI/smart analytics remain deferred.

## Remaining gaps / risks

- Proactive email/SMS/scheduled reminders remain outstanding.
- Core plan-limit enforcement remains unimplemented by design.
- Overdue restrictions are informational only.
- Provider/legal/tax validation and the 3–5 gym pilot remain Phase 5.
- Final independent review found a migration-trigger invoice-creation defect, which was fixed by computing the invoice total before insert; focused and full suites pass. Remaining non-blocking gaps are the advanced UI items above and the explicitly outstanding proactive reminder delivery.
- No merge, deployment or Phase 5 implementation has occurred.

## Decision coverage (all 92 + ADD-01)

| Decisions | Status | Evidence |
|---|---|---|
| 01–05 | PASS | embedded finance, Superuser toggle, gym recipient, pilot target |
| 06–12 | PASS | optional plans, free/commission modes, configurable sources/services, effective-dated contracts |
| 13–17 | PASS | existing Phase 2/3 sales, bundles, paid membership |
| 18 | DEFERRED | no attendance/usage finance input |
| 19–29 | PASS | existing Phase 3 coach/refund/payment behavior plus platform contracts |
| 30 | DEFERRED | no automatic post-payout coach clawback |
| 31–40 | PASS | journal, payables, reconciliation, permissions, coach/athlete views |
| 41–45 | PASS | Superuser full access, limits, role dashboards, mobile views |
| 46 | DEFERRED | no advanced AI/smart analytics |
| 47–58 | PASS | tenant isolation, additive migration, group contracts/discounts, exports |
| 59–71 | PASS | disabled read-only, integer IRR, Jalali, manual receipts/refunds/reminders |
| 72–82 | PASS | refund method, linked corrections, agreements, splits, settlement evidence |
| 83–92 | PASS | periodic coach pay, estimated profit, expenses, period close, numbering, audit, release gates |
| ADD-01 | PASS | zero-plan/free/commission/hybrid/custom controls, configurable rates/categories/sources |

Remaining PRD gaps: #18, #30, #46 deferred; proactive reminder delivery #15/#71 outstanding; plan-limit enforcement and automatic overdue restrictions not implemented; group-contract UI and some advanced UI configuration remain incomplete.
