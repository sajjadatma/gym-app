# Phase 5A.7-R1 — Date-Semantics Blocker Remediation

**Date:** 2026-11-08
**Branch:** `feat/ascora-finance`
**Scope:** Targeted remediation of DS-M1, DS-M2, DS-M3 and legacy reporting dates
**Environment:** Local synthetic data only
**Baseline:** Unchanged Phase 5A.0 thresholds; no waiver

## 1. Authorization and boundary

The project owner authorized 5A.7-R1 after the original 5A.7 LOCAL NO-GO. The
authorization covers only the date-semantics blockers, their tests, evidence
updates and the final reassessment. It does not authorize deployment,
Vercel/Neon changes, providers, real financial data, a merge to `main`, or
Phase 5B.

## 2. DS-M1 — Historical gym summary

`gym_summary()` previously used current membership status/end date for
`renewals_due` and current settlement/adjustment totals for
`coach_payable_irr`.

Implemented:

- `renewals_due` is reconstructed at `to_date`:
  - membership `start_date <= to_date`;
  - not cancelled on or before `to_date`;
  - end date as of `to_date` inside the 30-day window;
  - later resume extensions are reversed using append-only
    `finance.membership.resumed` audit rows (`resume_on`, `paused_days`);
  - incomplete legacy freeze history fails closed with
    `membership_history_incomplete` instead of using today's `end_date`.
- `coach_payable_irr` is reconstructed at `to_date`:
  - earning recognized only when its business date (receipt `received_on`,
    credit movement `applied_on`, or journal `posting_date`) is on/before
    `to_date`;
  - settlement items included only when `paid_on <= to_date` and the
    settlement was not cancelled on/before `to_date`;
  - refund adjustments included only when their journal posted on/before
    `to_date`.

Tests:

- `test_gym_summary_renewals_are_reconstructed_at_the_requested_date`
- `test_gym_summary_coach_payable_uses_receipt_and_settlement_dates`
- `test_gym_summary_coach_payable_excludes_later_refund_adjustment`
- `test_gym_summary_coach_payable_restores_cancelled_settlement_after_cancel_date`
- `test_gym_summary_fails_closed_on_incomplete_membership_freeze_history`

## 3. DS-M2 — Financial CSV exports

Implemented:

- Every gym CSV row now has a seventh `date_basis` column.
- Summary balance rows are dated `to_date` and labelled `as_of_to_date`;
  range rows are labelled `range`. `renewals_due` is included as a balance
  summary row.
- Platform `BALANCE` rows use as-of payment allocations, credits and
  cancellation dates:
  - `platform_receivable` uses `platform_receivable_paid_as_of`;
  - `platform_invoice_line` uses `platform_invoice_line_paid_as_of`;
  - a cancellation only removes a line when `cancelled_on <= to_date`;
  - balance rows are included when their originating event is on/before
    `to_date`, even if it predates `from_date`;
  - exported platform receivable balances are checked against the
    `/platform/dues/{gym_id}` standing for the same as-of date.
- Offboarding export uses `balance_basis="as_of_export"` and dates balance
  summary rows at gym-local today.
- Refunds recorded after `to_date` remain `BALANCE` rows at their local
  creation date until the recording date; recorded refunds use the journal
  posting date.
- Platform report and per-gym exports also carry `date_basis`.

Tests:

- `test_gym_export_has_explicit_date_basis_and_matches_summary_as_of`
- `test_platform_balance_rows_use_as_of_payments_credits_and_cancellation`
- `test_offboarding_export_labels_balances_as_of_export`
- `test_export_uses_business_dates_for_refunds_and_expenses`

## 4. DS-M3 — Platform per-gym reports and exports

The service already used period/as-of dates. 5A.7-R1 added direct
endpoint-level conformance tests:

- two gyms, two periods (November and December 2026), subscriptions,
  invoices, partial payments and costs;
- `GET /platform/reports/gyms/{gym_id}` equals the matching
  `by_gym` row in `GET /platform/reports/overview` for November, December and
  the combined range;
- `GET /platform/gyms/{gym_id}/export` metrics equal the detail endpoint and
  carry `date_basis`;
- `GET /platform/reports/export` carries `date_basis` and its per-gym
  contribution row equals the detail endpoint;
- a separate test covers an as-of credit application and a later invoice
  cancellation across period boundaries;
- per-gym figures reconcile to the platform totals without cross-tenant
  netting.

Tests: `test_platform_per_gym_report_and_export_reconcile_across_periods`,
`test_platform_per_gym_cancellation_and_credit_as_of`.

## 5. Legacy reporting dates

Migration `b9c0d1e2f3a4_repair_legacy_reporting_dates.py` repairs only rows
with an unambiguous source event:

- subscription receivables from the period in `source_key`;
- commission receivables from the linked receipt or advance;
- ASCORA coach-share receivables from the linked earning receipt;
- platform refund credits from the refund journal;
- cancellation credits from the invoice `cancelled_on`;
- applied customer-credit movements from a unique `ADVANCE_APPLIED` journal.

Amounts, journals, audit rows and immutable timestamps are preserved.
Ambiguous or source-less rows are left unchanged. Details:
`docs/finance/legacy-date-reconstruction.md`.

Test: `test_reporting_date_repair_uses_authoritative_source_events`, which
also proves that a manual (source-less) receivable keeps its existing date,
an ambiguous two-journal advance is left unchanged, and credit amounts and
journal dates are not rewritten.

## 6. Verification evidence

| Check | Result |
|---|---|
| Full backend regression | **347 passed** in 232.32 s |
| Migration suite | **16 passed** in 9.24 s; **16 passed** under `TZ=UTC` in 8.57 s |
| Full Playwright | **148 passed, 3 skipped**, no retry |
| Frontend lint | Clean, 175 files |
| Frontend build | Passed |
| Ruff | Clean |
| Mypy | Clean, 48 source files |
| Docker backup/restore with new migration applied | **PASS**, `ok:true`, `failures:[]`, **305.05 s**, 28 finance + 21 platform tables |
| Local load (observational) | gym finance 177 ms, platform finance 166 ms, athlete finance 167 ms; DCL/load 42–45 ms |

The CI application image was the cached 5A.6 image because Docker image pulls
failed in this local environment with a credential/proxy error. The new
forward-only migration was copied into the running backend and applied with
`alembic upgrade head` before the drill; the retained drill log records the
backup/restore, not the migration command. 5A.7-R1 adds no schema/table changes, so the backup/restore
table set and verifier are unchanged.

## 7. Residual limitations

- Legacy rows without an authoritative source event, or with an ambiguous
  applied-advance match, remain on the `created_at` backfill.
- Historical renewals require append-only membership audit events; incomplete
  legacy freeze history fails closed.
- Migration preservation evidence still does not cover audit,
  cancellation/reversal or platform-operation rows.
- Reporting-date columns remain mutable by direct SQL (DATE-M1).
- No external legal, provider or production approval is claimed.
