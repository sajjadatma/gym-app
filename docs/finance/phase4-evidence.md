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

- Backend full suite: **299 passed**.
- Migration tests: **12 passed**.
- Ruff: clean. Mypy: clean.
- Frontend lint/typecheck/unit/build: clean.
- Full Playwright: **140 passed, 3 skipped** with Mailpit available and superuser credentials configured; the 3 skips are the environment-gated superuser suite when credentials are absent.
- Docker backup/restore drill at migration head `f1a2b3c4d5e6`: **PASS**. The restore verifier now also checks the platform ledger: nonempty platform agreement/receivable/credit/credit-application/invoice/line/payment/allocation/journal/sequence counts, balanced journals, journals with at least two lines, payment-to-allocation totals, payment/allocation invoice identity, invoice-line paid-to-allocation totals, gym-scoped credit applications, over-applied credits, overpaid receivables/lines and document sequences. Restored platform counts were `{"platform_agreement": 1, "platform_receivable": 1, "platform_credit": 1, "platform_credit_application": 1, "platform_invoice": 1, "platform_invoice_line": 1, "platform_invoice_cancellation": 0, "platform_invoice_line_reversal": 0, "platform_payment": 1, "platform_payment_allocation": 1, "platform_journal": 1, "platform_journal_line": 2, "platform_sequence": 2}`, `ok:true`, and live restore reverted the corrupted gym name and returned readiness 200.

## Deviations / decisions

- Overdue `RESTRICTED` is a visible informational stage only. No automatic core-feature lockout was invented; Superuser actions, finance history, exports and athlete workout history stay available. Any future enforcement requires explicit approval.
- Proactive reminder delivery (#15/#71) is **NOT implemented**. In-app reminders are labeled `IN_APP_ONLY`; the proactive delivery requirement remains outstanding.
- Plan limits are stored and usage is surfaced, but no core feature enforcement was added because numeric limits are pilot configuration.
- The TanStack route tree was patched manually because the local build did not regenerate it automatically for the new route.
- The platform UI is compact and functional rather than a full bespoke dashboard redesign. The pilot-minimum controls now present are: group creation/selection, plan-version create/activate/retire, platform cost entry, invoice line inspection and a required cancellation-reason dialog. Multi-term agreement editing and bulk group member management remain API-first.

## Deferred decisions

#18 usage/attendance finance input, #30 automatic post-payout coach clawback, and #46 advanced AI/smart analytics remain deferred.

## Remaining gaps / risks

- Proactive email/SMS/scheduled reminders remain outstanding.
- Core plan-limit enforcement remains unimplemented by design.
- Overdue restrictions are informational only.
- Provider/legal/tax validation and the 3–5 gym pilot remain Phase 5.
- Final independent review found a migration-trigger invoice-creation defect, which was fixed by computing the invoice total before insert; focused and full suites pass. Remaining non-blocking gaps are the advanced UI items above and the explicitly outstanding proactive reminder delivery.
- No merge, deployment or Phase 5 implementation has occurred.

## Closeout verification (5 gaps)

1. **Per-gym recognized revenue vs platform journal.** Per-gym recognized revenue is gross platform receivables in range minus non-cancellation refund credits minus discounts on non-cancelled invoices. `test_group_volume_discount_reconciles_gym_and_platform_reports` asserts a 10% group volume discount yields 95,000 (100,000 gross − 5,000 discount), that the per-gym and platform totals agree, that cancelling the invoice restores 100,000 in both, and that cancelled invoices are excluded from `invoiced_fees_irr`. `test_platform_receivables_and_by_gym_reconcile_after_credit_and_cancel` asserts recognized revenue stays 70,000 after a cancellation creates a replacement credit, so cancellation credits are not subtracted twice.
2. **Receivables/overdue after credit.** `available_credit_irr` nets total credits against applications; applied credit is not double-counted because it already appears in receivable paid amounts. The platform overview now sums per-gym net receivables instead of netting one gym's credit against another gym's debt. `test_platform_overview_does_not_cross_net_credit_between_gyms` covers excess credit in one gym plus an overdue receivable in a second gym. `test_platform_standing_is_current_when_credit_covers_overdue_invoice` covers credit fully covering an overdue invoice (open 0, overdue 0, `CURRENT`, no restrictions). The existing credit/cancel test checks before/after application, partial payment, final payment and the gym-summary payable at every step.
3. **Backup/restore.** The verifier checks platform counts against a per-backup `platform-counts.txt`, balanced journals, minimum line integrity, payment/allocation consistency, allocation invoice identity, line-paid totals, gym-scoped credit applications, over-applied credits, overpaid receivables/lines and document sequences. The drill seeds and asserts nonempty platform agreement, receivable, credit, credit application, invoice/line, payment/allocation, balanced journal and sequences.
4. **Decision matrix.** Each decision 1–92 plus ADD-01 is listed individually with status and evidence. #15, #71, #34, #54, #91 and #92 remain **Partial**; #53 and #56 remain **Outstanding**; #18, #30 and #46 remain **Deferred**; the rest are **Implemented**.
5. **Minimum Superuser UI.** Group create/select, plan-version create/activate/retire, platform cost entry, invoice line inspection and required cancellation reason are available in `/platform/finance` using the existing API client and components.

Known limitations kept out of this closeout: owner standing/reminders and the Superuser overview can use different due-date sources (invoice due date vs receivable due date); reporting uses accrual dates per gym while the headline recognized-revenue figure is journal-posting-date based, so a range that cuts between a journal posting date and its source date can differ at the boundary. These are pre-existing reporting boundaries, not credit-reconciliation defects, and are noted for Phase 5 follow-up alongside proactive reminder delivery and plan-limit enforcement.

## Decision coverage (all 92 + ADD-01)

| Decision | Status | Evidence / gap |
|---|---|---|
| 1 | **Implemented** | finance foundation; Phase 1 tests |
| 2 | **Implemented** | non-custody model; payment/receipt tests |
| 3 | **Implemented** | gym recipient; receipt/allocation tests |
| 4 | **Implemented** | target market documented; pilot itself is #53 |
| 5 | **Implemented** | finance enabled default; test_finance_foundation |
| 6 | **Implemented** | platform agreements bill gym |
| 7 | **Implemented** | optional plans; test_platform_plans |
| 8 | **Implemented** | free/zero plans; plan tests |
| 9 | **Implemented** | commission by service; test_platform_agreements |
| 10 | **Implemented** | acquisition source terms; agreements/fees tests |
| 11 | **Implemented** | offline fee receivable; platform fees tests |
| 12 | **Implemented** | effective-dated versions; plan/agreement tests |
| 13 | **Implemented** | catalog/sales from Phase 2 |
| 14 | **Implemented** | line kinds/policies from Phase 2 |
| 15 | **Partial** | manual renewal + in-app reminders only; proactive delivery outstanding |
| 16 | **Implemented** | membership freeze/cancel/transfer/refund tests |
| 17 | **Implemented** | bundles from Phase 2 |
| 18 | **Deferred** | usage/attendance tracking excluded |
| 19 | **Implemented** | coach pay modes from Phase 3 |
| 20 | **Implemented** | direct/waterfall allocation tests |
| 21 | **Implemented** | discount/tax ordering tests |
| 22 | **Implemented** | vesting/collected separation tests |
| 23 | **Implemented** | immutable snapshots; snapshot tests |
| 24 | **Implemented** | discount funding tests |
| 25 | **Implemented** | manual cash/POS/transfer; gateway deliberately disabled |
| 26 | **Implemented** | manual receipt attestation tests |
| 27 | **Implemented** | installments/partial receipts tests |
| 28 | **Implemented** | pending/confirmed/failed/reversed tests |
| 29 | **Implemented** | refund approval/audit tests |
| 30 | **Deferred** | no automatic coach clawback |
| 31 | **Implemented** | balanced journal tests |
| 32 | **Implemented** | invoice/collected/payable separation tests |
| 33 | **Implemented** | settlement cycle/partial tests |
| 34 | **Partial** | overdue stages/reminders visible; no automatic restrictions |
| 35 | **Implemented** | negative balance visibility tests |
| 36 | **Implemented** | manual reconciliation tests |
| 37 | **Implemented** | gym reports/export tests, platform payable netting, 5A.3 date-semantics conformance |
| 38 | **Implemented** | finance grants/staff tests |
| 39 | **Implemented** | coach own earnings tests |
| 40 | **Implemented** | athlete self-service tests |
| 41 | **Implemented** | Superuser full access tests |
| 42 | **Partial** | approval flow implemented; amount limits enforced only for opening balances, other amount-bearing permissions reject unsupported limits (5A.1) |
| 43 | **Implemented** | gym dashboard tests |
| 44 | **Implemented** | platform overview, per-gym netting, credit/cancellation tests and 5A.3 revenue-basis reconciliation |
| 45 | **Implemented** | coach/athlete mobile views |
| 46 | **Deferred** | advanced AI/smart analytics excluded |
| 47 | **Implemented** | tenant isolation tests |
| 48 | **Implemented** | neutral primitives; no future app built |
| 49 | **Implemented** | atomic/idempotency/concurrency tests |
| 50 | **Implemented** | backup/restore drill PASS with balanced platform ledger, counts, allocation and sequence checks |
| 51 | **Implemented** | additive migrations/tests |
| 52 | **Implemented** | staged Phase 1–4 delivery |
| 53 | **Outstanding** | 3–5 real-gym pilot not run (Phase 5) |
| 54 | **Partial** | local integrity/refund/tenant/restore/date-semantics evidence passes; real-gym pilot criteria pending |
| 55 | **Implemented** | offboarding export |
| 56 | **Outstanding** | Iran legal/tax/provider checks before real money |
| 57 | **Implemented** | branch ledger/consolidated reporting |
| 58 | **Implemented** | group contracts/discounts |
| 59 | **Implemented** | disabled finance read-only tests |
| 60 | **Implemented** | integer IRR tests |
| 61 | **Partial** | Jalali display and gym-local report boundaries implemented (5A.3); some current-only vesting/expiry reads still use UTC and the timezone setting is not editable through the API |
| 62 | **Implemented** | standalone income/expense |
| 63 | **Implemented** | membership effective dates |
| 64 | **Implemented** | access/downpayment policy |
| 65 | **Implemented** | membership refund preview/rules |
| 66 | **Implemented** | bundle discount proration |
| 67 | **Implemented** | goods/returns without inventory |
| 68 | **Implemented** | per-gym advance tests |
| 69 | **Implemented** | manual receipt vs reconciliation separation |
| 70 | **Implemented** | one receipt many invoices tests |
| 71 | **Partial** | in-app installment reminders; proactive delivery/restriction policy outstanding |
| 72 | **Implemented** | refund method preference/override |
| 73 | **Implemented** | gym refund obligation/manual coach discrepancy |
| 74 | **Implemented** | issued invoice immutability/correction tests |
| 75 | **Implemented** | missing agreement unresolved tests |
| 76 | **Implemented** | multi-payee allocation tests |
| 77 | **Implemented** | confirmed tranche allocation tests |
| 78 | **Implemented** | Superuser-only platform fee control tests |
| 79 | **Implemented** | acquisition source snapshot tests |
| 80 | **Implemented** | deterministic integer math tests |
| 81 | **Implemented** | settlement parties/proof fields |
| 82 | **Implemented** | weekly/default settlement config |
| 83 | **Implemented** | periodic coach pay tests |
| 84 | **Implemented** | estimated operating profit tests; journal-posting revenue/expense basis reconciled in 5A.3 |
| 85 | **Implemented** | expense fields/recurrence tests |
| 86 | **Implemented** | period close/correction tests |
| 87 | **Implemented** | unique invoice numbering tests |
| 88 | **Implemented** | opening balance/Superuser correction tests |
| 89 | **Implemented** | Superuser acts alone with audit |
| 90 | **Partial** | granular grants implemented; opening-balance amount limit enforced, other permissions reject unsupported limits (5A.1); per-action limits outstanding |
| 91 | **Partial** | limits modeled/surfaced; core enforcement not implemented |
| 92 | **Partial** | local gates/tests/restore pass; public release/pilot/legal not done |
| ADD-01 | **Implemented** | zero-plan/free/commission/hybrid/custom controls and tests |

Remaining PRD gaps: #18, #30, #46 deferred; proactive reminder delivery #15/#71 outstanding; plan-limit enforcement and automatic overdue restrictions not implemented; group-contract UI and some advanced UI configuration remain incomplete.
