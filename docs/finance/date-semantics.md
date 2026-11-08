# Financial Date Semantics — Phase 5A.3 Decision Record

**Date:** 2026-11-04
**Branch:** `feat/ascora-finance`
**Scope:** Local-first financial reporting and read models
**Status:** Approved local decision record for 5A.3; implemented and tested. **5A.7-R1 remediated the date-semantics blockers; see §7.**

## 1. Approval record

The project owner approved the local-first Phase 5A plan and instructed 5A.3 to define canonical date semantics, reconcile reports against journal/allocation facts, and fix confirmed defects. That instruction is the approval for this record.

No external signature, auditor, legal opinion or production approval is claimed.

## 2. Definitions

- **Business date:** an explicit calendar date supplied by the operator or derived from a business event (`received_on`, `spent_on`, `paid_on`, `issued_on`, `due_on`, `cancelled_on`).
- **Journal posting date:** the authoritative accounting date stored on `finance_journal.posting_date` or `platform_journal.posting_date`.
- **Gym-local date:** the calendar date in the gym’s configured timezone (`FinanceSettings.timezone`, default `Asia/Tehran`).
- **Platform-local date:** the platform reporting calendar (`Asia/Tehran` for cross-gym platform reports).
- **Billed:** a platform receivable covered by a non-cancelled platform invoice.
- **Unbilled:** an accrued platform receivable not yet covered by an issued platform invoice.
- **As-of date:** the historical cut-off for a read model. Only events dated on or before it may affect balances.
- **Inclusive range:** `from_date <= date <= to_date`.

## 3. Canonical rules

### 3.1 Timezone and ranges

1. Instants are stored in UTC. Business dates are gym-local calendar dates.
2. `gym_today(session, gym_id)` uses `ZoneInfo(FinanceSettings.timezone)` for gym-scoped due/overdue/reminder/renewal calculations.
3. Cross-gym platform reports use `platform_today()` with `Asia/Tehran`.
4. All report ranges are inclusive. `from_date <= to_date` is the required caller contract.
5. Month-end subscription accrual uses calendar month end; year-end and leap-year behavior follow the same rule.

### 3.2 Gym invoice due dates

1. If installments exist, the effective due date is the due date of the **first unpaid installment**, determined by waterfall allocation of confirmed receipts and applied credits oldest-first.
2. If no installments exist, the effective due date is `FinanceInvoice.due_date`.
3. `overdue` is `balance > 0` and `effective_due_on < gym_today`.
4. The same helper is used by invoice reads, reminders, gym summary and export.
5. The invoice’s stored `due_date` remains the contractual invoice date; it is not rewritten.

### 3.3 Platform billed vs unbilled

1. Owner-facing `open_irr`, `overdue_irr`, stage and reminders use **billed invoices only**.
2. Unbilled receivables are reported separately as `unbilled_open_irr` / `unbilled_receivable_irr`; they are never labeled overdue to the owner.
3. Superuser reports expose:
   - `billed_receivable_irr`
   - `unbilled_receivable_irr`
   - `billed_overdue_irr`
   - `unbilled_overdue_irr`
   - total exposure (`receivable_irr`)
4. Available credit is applied to billed invoices oldest-due-first; remaining credit reduces unbilled exposure.
5. Owner billed balance + owner unbilled balance equals Superuser total exposure for the same gym and as-of date.
6. Receivable-only gyms are included in `/platform/dues`.

### 3.4 Revenue recognition vs journal posting

1. The journal `posting_date` is the ledger truth for headline revenue, expenses and cash.
2. Platform receivable and credit rows carry `recognized_on`, set to the same business date as the corresponding journal posting:
   - subscription: period start;
   - commission/ASCORA: receipt `received_on`;
   - refund credit: refund posting date;
   - cancellation replacement credit: cancellation date (excluded from recognized revenue).
3. Per-gym platform recognized revenue uses `recognized_on`; the headline uses `posting_date`. New data must reconcile to 0 IRR for a closed period.
4. Group volume discount journals post at `invoice.issued_on`, not `period_end`.
5. Pre-5A.3 rows with an unambiguous source event are repaired by migration `b9c0d1e2f3a4`; rows without an authoritative source remain on the `created_at` backfill and are documented as a legacy limitation in `docs/finance/legacy-date-reconstruction.md`.

### 3.5 Historical as-of

1. Platform standing and reminders accept `as_of`; platform overview/detail use `to_date` as the as-of date.
2. Historical invoice paid amounts are reconstructed from `PlatformPaymentAllocation` joined to `PlatformPayment.received_on <= as_of`.
3. Cancellations use `PlatformInvoice.cancelled_on`; an invoice cancelled after `as_of` remains billed at that historical date.
4. Credit availability uses `recognized_on`/`created_at` and application dates `<= as_of`. Applied credits in gym invoice paid-as-of use the explicit `applied_on` business date, falling back to the creation date for legacy rows.
5. Gym summary uses `to_date` as the as-of date; paid amounts use receipt `received_on` and applied-credit dates.
6. Mutable `paid_irr`, `status` and `balance_irr` are not used as historical billed facts. Unbilled historical exposure uses the receivable gross amount and available credit as of the date; it does not subtract a later payment from `paid_irr`.
7. Gym summary `renewals_due` is reconstructed at `to_date`: membership `start_date <= to_date`, not cancelled on/before the date, and the end date as of that date inside the 30-day window. Later freeze/resume extensions are reversed using append-only `finance.membership.resumed` audit events. Incomplete legacy freeze history fails closed with `membership_history_incomplete`.
8. Gym summary `coach_payable_irr` is reconstructed at `to_date` from earning business dates (receipt `received_on`, credit `applied_on`, or journal `posting_date`), settlement items with `paid_on <= to_date` that were not cancelled on/before the date, and refund adjustments whose journal posted on/before the date.

### 3.6 Sales, voids, cancellations and closed periods

1. Gym `sales_irr` is the journal-based gross issuance (`INVOICE_ISSUED` credits to account `4000`) minus `INVOICE_VOID` debits in the same range. A void appears in the void period and does not rewrite the original period.
2. Platform `invoiced_fees_irr` is gross invoice total by `issued_on` minus cancellation total in the cancellation period by `cancelled_on`.
3. Per-gym recognized revenue subtracts a discount in the invoice issue period regardless of current cancellation status, and adds the discount back in the cancellation period. A later cancellation therefore does not rewrite the original period.
4. Platform cancellation journal posts at `cancelled_on`, not the original `issued_on`.
5. Gym periods carry `period_start`/`period_end`. A posting before the open period start is rejected with `finance_posting_outside_open_period` once any period has been closed. The first open period may extend backwards for initial data.
6. Superuser corrections must request a posting date inside the open period; a date before the open-period start is rejected with `finance_posting_outside_open_period`. The correction links the original and does not backdate into a closed period.
7. Platform has no separate closed-period model in 5A.3; platform invoice issuance is dated today and cancellation is dated at cancellation time, so historical invoice periods are not rewritten by later cancellations.

### 3.7 Exports

1. Date-filtered exports apply the requested range to event rows. Balance rows (summary balances, platform receivable and platform invoice-line balances) are as-of `to_date` and are included when their originating event is on or before `to_date`, even if it predates `from_date`.
2. Cash rows use the cash event date: recorded refund journal `posting_date`, paid expense journal `posting_date`, coach earning journal `posting_date`, settlement `paid_on`, platform payment `received_on`. Unrecorded refunds are `BALANCE` rows dated in the gym-local calendar, and rejected refunds are omitted because they are not a liability or cash movement.
3. Accrual rows use the business accrual date: unpaid expense `spent_on`, platform receivable `recognized_on`, agreement `effective_from`.
4. Offboarding export is all-history; its balance metrics are as-of the export time, and it uses gym-local today as the upper bound. Balance rows are labelled `as_of_export`.
5. Every CSV row now carries an explicit `date_basis` column: `range`, `as_of_to_date`, `as_of_export`, `issue_date`, `received_on`, `posting_date`, `spent_on`, `paid_on`, `recognized_on`, `created_at_local`, or a combined balance basis such as `recognized_on;as_of_to_date`.
6. Platform report exports also carry `date_basis`: `range` for accrual/cash metrics and `as_of_to_date` for receivable/overdue balances.

## 4. Endpoint → date/basis matrix

### 4.1 Gym finance

| Endpoint | Range / as-of | Date basis | Amount basis | Status |
|---|---|---|---|---|
| `/finance/reports/summary` | inclusive `from_date..to_date`; balances as of `to_date` | journal posting date for cash/revenue/expense; invoice issue date for sales; effective due date for overdue; membership/coaching lifecycle as of `to_date` | journal net; invoice total; as-of paid; historical renewals; historical coach payable; platform total exposure | **Fully verified** — incl. `test_gym_summary_renewals_are_reconstructed_at_the_requested_date`, `test_gym_summary_coach_payable_uses_receipt_and_settlement_dates`, `test_gym_summary_coach_payable_excludes_later_refund_adjustment`, `test_gym_summary_coach_payable_restores_cancelled_settlement_after_cancel_date` |
| `/finance/reports/export` | range for event rows; balances as of `to_date` | journal/business dates as listed in §3.7; explicit `date_basis` per row | same as summary + as-of row balances | **Fully verified** — incl. `test_gym_export_has_explicit_date_basis_and_matches_summary_as_of`, `test_platform_balance_rows_use_as_of_payments_credits_and_cancellation`, `test_export_uses_business_dates_for_refunds_and_expenses`, `test_paid_expense_export_uses_paid_journal_date` |
| `/finance/reports/offboarding-export` | all history; balances as of export time, labelled `as_of_export` | same as export, with explicit `date_basis` | same as export; as-of export time | **Fully verified for its as-of-export contract** — `test_offboarding_export_labels_balances_as_of_export` |
| `/finance/reminders` | `gym_today` + horizon | first unpaid installment due date / invoice due date | remaining installment amount | **Fully verified** — `test_effective_due_date_uses_first_unpaid_installment`, `test_reminders_report_due_installments_and_renewals` |
| `/finance/invoices`, `/invoices/{id}` | current | effective due date; `gym_today` | current paid/balance | Canonical |
| `/finance/platform/invoices` | current | invoice `issued_on` / `due_on` | current paid/balance | Current-only read |
| `/finance/platform/dues` | current (no `as_of` parameter) | billed invoice `due_on`; unbilled `recognized_on` | billed net, unbilled net, total exposure | **Current-only verified** — documentation corrected in 5A.7 |
| `/finance/platform/payments` | current | `received_on` | gym-scoped allocation | Safe |
| `/finance/my/account` | current | current document dates | current balances/advance | Current-only |
| `/finance/my/earnings`, `/my/settlements`, `/my/coach-summary` | current | `created_at`, `vesting_date`, `paid_on` | current shares/settlements | Current-only |
| `/finance/journal` | no range filter | journal `posting_date` | debit/credit | Safe |
| `/finance/periods` | current | `opened_at`, `period_start`, `period_end`, `closed_at` | lifecycle | Canonical |
| `/finance/receipts`, `/receipts/{id}`, `/expenses`, `/expenses/{id}`, `/refunds`, `/credits`, `/memberships`, `/memberships/{id}`, `/memberships/{id}/refund-preview`, `/coach-*`, `/reconciliation` | current | document business dates | current amounts/status | Current-only |
| `/finance/customers` | current | identity/roles directory | no financial balance | Non-reporting; excluded |
| `/finance/accounts`, `/settings`, `/grants`, `/catalog` | — | — | configuration | Safe |

### 4.2 ASCORA platform

| Endpoint | Range / as-of | Date basis | Amount basis | Status |
|---|---|---|---|---|
| `/platform/reports/overview` | inclusive; balances/MRR as of `to_date` | headline journal `posting_date`; by-gym `recognized_on`; costs `incurred_on`; invoiced `issued_on` + cancellation `cancelled_on` | journal net; per-gym recognized; total exposure; gross minus cancellation | **Fully verified** — `test_closed_synthetic_month_reconciles_with_zero_delta`, `test_platform_cancellation_does_not_rewrite_original_period`, `test_platform_discount_cancellation_is_period_stable`, `test_platform_overview_does_not_cross_net_credit_between_gyms` |
| `/platform/reports/export` | same | same; explicit `date_basis` | same | **Fully verified** — `test_csv_exports_are_tenant_safe_and_keep_history`, `test_platform_per_gym_report_and_export_reconcile_across_periods` |
| `/platform/reports/gyms/{gym_id}` | inclusive; as of `to_date` | same by-gym basis | same | **Fully verified** — `test_platform_per_gym_report_and_export_reconcile_across_periods`, `test_platform_per_gym_cancellation_and_credit_as_of` |
| `/platform/gyms/{gym_id}/export` | same | same; explicit `date_basis` | same | **Fully verified** — `test_platform_per_gym_report_and_export_reconcile_across_periods`, `test_platform_per_gym_cancellation_and_credit_as_of` |
| `/platform/dues`, `/dues/{gym_id}` | optional `as_of` | billed `due_on`; unbilled `recognized_on` | billed/unbilled split; as-of payments/credit | **Fully verified** — `test_platform_historical_standing_and_reminders_use_as_of_events`, `test_platform_historical_unbilled_ignores_future_payment` |
| `/platform/reminders` | optional `as_of` | invoice `issued_on`/`due_on` | as-of invoice balance | **Fully verified** — `test_platform_historical_standing_and_reminders_use_as_of_events`, `test_platform_reminders_are_in_app_only_and_list_due_and_overdue` |
| `/platform/receivables` | current | `recognized_on`/`due_on` | current amount/paid | Current-only |
| `/platform/invoices`, `/invoices/{id}` | current | `issued_on`/`due_on` | current paid/balance | Current-only |
| `/platform/payments` | current | `received_on` | payment/allocation | Safe |
| `/platform/costs` | current | `incurred_on` | cost amount | Safe |
| `/platform/agreements` | current | effective dates | terms | Safe |
| `/platform/plans`, `/groups` | — | plan/group dates | non-financial | Safe |

## 5. Boundary-case coverage

| Case | Test |
|---|---|
| Different invoice and receivable due dates | `test_platform_billed_unbilled_split_and_owner_consistency`, `test_platform_historical_standing_and_reminders_use_as_of_events` |
| Partial installment payment and next unpaid installment | `test_effective_due_date_uses_first_unpaid_installment` |
| Credit created after `as_of` | 5A.1 `test_platform_standing_is_current_when_credit_covers_overdue_invoice`; credit availability uses `as_of` |
| Discount journal at issuance | `test_revenue_recognition_aligns_with_journal_for_boundary_range`, 5A.2 group acceptance |
| Report range splitting recognition/posting | `test_revenue_recognition_aligns_with_journal_for_boundary_range` |
| Void across periods | `test_void_preserves_original_period_and_reverses_in_void_period` |
| Platform cancellation across periods | `test_platform_cancellation_does_not_rewrite_original_period` |
| Refund recorded in a later period | `test_refund_posts_in_recorded_period_not_request_period` |
| Closed period backdating | `test_closed_period_rejects_backdated_posting` |
| Timezone boundary | `test_gym_today_uses_gym_timezone` |
| Closed synthetic month zero delta | `test_closed_synthetic_month_reconciles_with_zero_delta` |
| Historical unbilled balance ignores a future payment | `test_platform_historical_unbilled_ignores_future_payment` |
| Discount cancellation is period-stable for per-gym revenue | `test_platform_discount_cancellation_is_period_stable` |
| Void receivable uses the void posting date | `test_void_receivable_uses_void_posting_date` |
| Paid expense export uses the paid journal date | `test_paid_expense_export_uses_paid_journal_date` |
| Membership freeze/resume after the as-of date | `test_gym_summary_renewals_are_reconstructed_at_the_requested_date` |
| Settlement/refund/cancellation after the as-of date | `test_gym_summary_coach_payable_uses_receipt_and_settlement_dates`, `test_gym_summary_coach_payable_excludes_later_refund_adjustment`, `test_gym_summary_coach_payable_restores_cancelled_settlement_after_cancel_date` |
| CSV balance row equals summary/report for the same as-of | `test_gym_export_has_explicit_date_basis_and_matches_summary_as_of`, `test_platform_balance_rows_use_as_of_payments_credits_and_cancellation` |
| Platform per-gym report reconciles to overview across periods | `test_platform_per_gym_report_and_export_reconcile_across_periods` |
| Platform per-gym cancellation and credit as-of boundaries | `test_platform_per_gym_cancellation_and_credit_as_of` |
| Incomplete legacy membership freeze history fails closed | `test_gym_summary_fails_closed_on_incomplete_membership_freeze_history` |

## 6. Remaining discrepancies / limitations

1. **Historical backfill:** legacy rows with an unambiguous source event are repaired. Rows without a source event, or with an ambiguous applied-advance match, remain on the `created_at` backfill and are documented in `docs/finance/legacy-date-reconstruction.md`.
2. **CSV format:** resolved; every financial CSV row carries `date_basis`.
3. **Platform closed periods:** there is no platform period model; platform invoice issuance/cancellation dates are controlled at creation/cancellation time. A future platform period lock would require a separate approved change.
4. **Timezone editing:** `FinanceSettings.timezone` is used for calculations but remains read-only through the API; changing it requires a direct local settings row. A validated edit/audit workflow is a Phase 5B hardening item.
5. **Range validation:** `from_date <= to_date` is the caller contract; not every route rejects a reversed range yet. This is a low-risk API validation gap.
6. **Platform aggregate timezone:** cross-gym platform reports use the platform default `Asia/Tehran`, not a per-gym timezone; gym-scoped owner views use the gym timezone.
7. **Membership history dependency:** historical renewals use append-only membership audit events. Incomplete legacy freeze history fails closed rather than guessing.
8. **Export balance rows:** platform receivable/invoice-line balance rows are reconstructed as of `to_date` from payment allocations, credits and cancellation dates; legacy rows without those facts remain limited.
9. **Unbilled aging:** `unbilled_overdue_irr` is intentionally `0`; unbilled aging is not implemented.
10. **Receivable public read model:** `PlatformReceivablePublic` does not expose `recognized_on`.
11. **Closed-period guard scope:** the gym guard rejects backdated postings after any closed period; platform has no equivalent period lock.

These limitations do not change posted journal facts and are recorded for Phase 5B.

## 7. 5A.7-R1 remediation

Phase 5A.7-R1 resolved the date-semantics blockers identified by the original
5A.7 assessment:

1. `GET /finance/reports/summary` now reconstructs `renewals_due` and
   `coach_payable_irr` at `to_date` from authoritative lifecycle, receipt,
   credit, settlement and refund-adjustment records. Later freezes, resumes,
   settlements, cancellations and adjustments do not rewrite earlier values.
2. `GET /finance/reports/export` and `offboarding-export` now carry an
   explicit `date_basis` column and calculate platform receivable/invoice-line
   balances as of `to_date`. Later cancellations no longer erase earlier
   periods, and offboarding balances are labelled `as_of_export`.
3. `GET /platform/reports/gyms/{gym_id}` and
   `GET /platform/gyms/{gym_id}/export` now have direct historical
   conformance tests across two gyms and multiple periods, including
   reconciliation to `/platform/reports/overview` and no cross-tenant netting.
4. Legacy reporting dates are repaired from unambiguous source events, with
   irrecoverable/ambiguous cases documented separately.

The matrix above was re-derived from the actual `@router.get` decorators in
`backend/app/api/routes/finance.py` and `backend/app/api/routes/platform.py`;
configuration-only and identity-directory endpoints are explicitly excluded.
The 5A.0 100% conformance criterion is met for the reporting contract as
recorded here. The final LOCAL GO / NO-GO decision is recorded in
`docs/release/phase5a-local-go-no-go.md` after the full 5A.7-R1 verification.
