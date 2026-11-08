# Phase 5A.3 — Accounting Reconciliation Evidence

**Date:** 2026-11-04
**Branch:** `feat/ascora-finance`
**Scope:** Local-only synthetic reconciliation and date-semantics verification
**Status:** PASS — LOCAL GO for 5A.3

## 1. Closed synthetic month

Scenario:
- One local synthetic gym.
- HYBRID platform agreement: subscription `500,000` IRR + 10% commission.
- Subscription accrued for November 2026.
- Gym sale invoice `1,000,000` IRR issued and fully received on `2026-11-05`.
- Report range: `2026-11-01..2026-11-30`.

Expected:
- Platform recognized revenue = `500,000` subscription + `100,000` commission = `600,000`.
- Sum of per-gym recognized revenue = `600,000`.
- Headline − per-gym delta = `0` IRR.
- Gym recognized revenue = `1,000,000`; cash collected = `1,000,000`.
- Gym platform payable = `600,000` total exposure.
- Every finance and platform journal balanced.

Actual:
- Platform recognized revenue: `600,000`.
- Sum of per-gym recognized revenue: `600,000`.
- Delta: `0` IRR.
- Gym recognized revenue: `1,000,000`.
- Cash collected: `1,000,000`.
- Gym platform payable: `600,000`.
- Unbalanced finance journals: `0`.
- Unbalanced platform journals: `0`.

Test: `backend/tests/api/routes/test_finance_date_semantics_5a3.py::test_closed_synthetic_month_reconciles_with_zero_delta`.

## 2. Date-semantics boundary evidence

| Boundary case | Result |
|---|---|
| Effective due date uses first unpaid installment; partial payment advances it | PASS |
| Platform historical standing ignores a payment dated after `as_of` | PASS |
| Historical reminders exclude invoices issued after `as_of` | PASS |
| Billed vs unbilled split and owner/Superuser total exposure | PASS |
| Revenue recognition boundary: headline and by-gym both `600,000` in the receipt period, `0` later | PASS |
| Gym void preserves original-period sales/revenue and reverses in the void period | PASS |
| Refund appears in the recorded period, not the request period | PASS |
| Platform cancellation preserves the original invoice period and reverses in the cancellation period | PASS |
| Closed period rejects backdated posting | PASS |
| Gym timezone boundary (`21:00 UTC` → next Tehran day) | PASS |
| Historical unbilled balance ignores a future payment | PASS |
| Discount cancellation preserves original-period per-gym revenue | PASS |
| Void receivable uses the void journal posting date | PASS |
| Refund export uses the journal posting date, not UTC request time | PASS |
| Paid expense export uses the paid journal date | PASS |
| Rejected refunds are omitted from cash/balance export | PASS |

Test file: `backend/tests/api/routes/test_finance_date_semantics_5a3.py` — **14 passed**.

## 3. Reconciliation invariants

| Invariant | Result |
|---|---|
| Zero unexplained IRR for the closed synthetic period | PASS (`0` delta) |
| No cross-gym credit/receivable netting | PASS (existing cross-gym test; per-gym total exposure sums) |
| No double ASCORA recognition | PASS (existing single-recognition tests) |
| Consistent owner and Superuser billed balances | PASS (`billed_open_irr` / `billed_receivable_irr` align; unbilled is separate) |
| Refunds/discounts/credits/cancellations consistent across periods | PASS for the covered boundary tests |
| Balanced journals | PASS (`post_journal`/`post_platform_journal` enforce balance; test queries find none) |
| Immutable posted records | PASS (void/cancellation append reversals; no posted amount rewrite) |

## 4. Commands and results

| Check | Result |
|---|---|
| Date-semantics suite | **14 passed** (also 14 passed under `TZ=UTC`) |
| Finance + platform suites | **156 passed** (also 156 passed under `TZ=UTC`) |
| Full backend regression | **323 passed** (also 323 passed under `TZ=UTC`) |
| Migration tests | **13 passed** |
| Ruff | Clean |
| Mypy | Clean |

## 5. Remaining discrepancies / risks

See `docs/finance/date-semantics.md` §6. Summary:
- Legacy pre-5A.3 rows with an unambiguous source event are repaired by migration `b9c0d1e2f3a4`; source-less or ambiguous rows remain on `created_at` and are documented in `docs/finance/legacy-date-reconstruction.md`.
- CSV exports now carry an explicit `date_basis` on every row.
- Platform has no separate closed-period model.
- Gym timezone is used for report boundaries but is not yet editable/audited through the API.
- Reversed `from_date > to_date` is a caller contract, not rejected by every route.
- Cross-gym platform reports use the platform default `Asia/Tehran`; gym-scoped owner views use the gym timezone.
- Historical membership renewals and coach payable are now reconstructed at the requested as-of date from membership audit events, receipt/credit dates, settlement dates and refund-adjustment journal dates.
- Export balance rows reconstruct platform receivable/invoice-line paid amounts from as-of payment allocations, credits and cancellation dates; every CSV row carries `date_basis`.
- `unbilled_overdue_irr` is intentionally `0` under the owner-facing policy; unbilled aging is not implemented.

Posted journal facts are not rewritten. The read model no longer rewrites historical recognized revenue for discount cancellations.

## 6. 5A.7-R1 remediation

The original 5A.7 review found that the approved 5A.0 requirement for **100% of
financial report endpoints covered by date-semantics conformance tests** was
not met. Phase 5A.7-R1 resolved those blockers:

- Gym summary `renewals_due` and `coach_payable_irr` are reconstructed at
  `to_date`; later freezes, resumes, settlements, cancellations and refund
  adjustments do not rewrite earlier values.
- Financial CSV exports calculate platform balance rows as of `to_date`, emit
  an explicit `date_basis` for every row, and preserve earlier periods when a
  cancellation happens later. Offboarding balances are labelled `as_of_export`.
- Platform per-gym reports and exports have direct multi-period tests that
  reconcile to the platform overview and prove no cross-tenant netting.
- Legacy reporting dates with an unambiguous source event are repaired by
  migration `b9c0d1e2f3a4`; remaining irrecoverable cases are documented in
  `docs/finance/legacy-date-reconstruction.md`.

The closed-period zero-delta and reconciliation boundary tests remain green.
The final LOCAL GO / NO-GO decision is recorded in
`docs/release/phase5a-local-go-no-go.md` after the full 5A.7-R1 verification.
