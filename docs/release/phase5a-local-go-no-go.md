# Phase 5A.7 — Final LOCAL GO/NO-GO Assessment

**Date:** 2026-11-08
**Branch:** `feat/ascora-finance`
**Assessed code commit:** `336f147` (Phase 5A.7-R1 code and evidence); the report itself is committed at the branch tip
**Scope:** Final local acceptance gate for ASCORA Finance Phase 5A
**Environment:** Local PostgreSQL, FastAPI backend, Vite frontend, Playwright and Docker Compose
**Data:** Synthetic and disposable only

## 1. Final decision

# LOCAL GO

**The local release candidate is eligible for LOCAL GO under the unchanged 5A.0 baseline.**

Phase 5A.7-R1 resolved the three mandatory date-semantics blockers without a
waiver or a weakened threshold:

1. **DS-M1 resolved.** `GET /finance/reports/summary` now reconstructs
   `renewals_due` and `coach_payable_irr` at the requested `to_date` from
   membership lifecycle audit events, receipt/credit business dates,
   settlement `paid_on` dates and refund-adjustment journal dates. Later
   freezes, resumes, settlements, cancellations and adjustments do not rewrite
   earlier values.
2. **DS-M2 resolved.** Financial CSV exports calculate platform
   receivable/invoice-line balances as of `to_date`, include a `date_basis`
   column on every row, preserve earlier periods when a cancellation happens
   later, and label offboarding balances `as_of_export`.
3. **DS-M3 resolved.** `GET /platform/reports/gyms/{gym_id}` and
   `GET /platform/gyms/{gym_id}/export` have direct multi-period historical
   tests that reconcile to `/platform/reports/overview` and prove no
   cross-tenant netting.
4. **Legacy dates repaired where authoritative.** Migration
   `b9c0d1e2f3a4` repairs pre-5A.3 reporting dates from source events. Rows
   without an authoritative source or with an ambiguous advance match remain
   explicitly documented limitations, not silent guesses.

The approved **100% date-semantics conformance** criterion is met for the
reporting contract in Section 5. There are **zero known Critical/High**
security, tenant-isolation or money-integrity defects, and all other assessed
5A.0 gates pass or are explicitly partial with no mandatory blocker.

A LOCAL GO is **not** authorization for production, real-money operations,
real-gym onboarding or public release.

## 2. Evidence index

- [5A.0 local baselines](phase5a-local-baselines.md)
- [5A.1 security and tenant-isolation audit](phase5a-security-audit.md)
- [5A.2 local financial acceptance](phase5a-local-financial-acceptance.md)
- [5A.3 date-semantics decision record](../finance/date-semantics.md)
- [5A.3 reconciliation](phase5a-reconciliation.md)
- [5A.4 migration, concurrency and recovery](phase5a-migration-recovery.md)
- [5A.5 local UI/UX acceptance](phase5a-local-ui-acceptance.md)
- [5A.6 defect closure](phase5a-defect-closure.md)
- [5A.7-R1 date-semantics remediation](phase5a-r1-date-semantics-remediation.md)
- [Legacy reporting-date reconstruction](../finance/legacy-date-reconstruction.md)
- [Phase 4 decision matrix](../finance/phase4-evidence.md)
- [Approved Phase 5 plan](../superpowers/plans/2026-11-03-ascora-finance-phase5.md)

## 3. Acceptance-baseline checklist

| 5A.0 threshold | Result | Evidence |
|---|---|---|
| Zero open Critical/High security or tenant-isolation findings | **PASS** | `phase5a-security-audit.md`: SEC-5A-01/02 fixed; zero open Critical/High; Medium/Low accepted for local 5A |
| 100% cross-tenant attempts denied | **PASS** | 5A.1 tenant matrix; 5A.6 finance-customer cross-gym/coach tests |
| Authentication/token review | **PASS** | 5A.1: HttpOnly/SameSite cookies, CSRF, revocation, single-use tokens, throttling |
| Zero secrets/real PII in Git, fixtures, logs, screenshots, exports | **PASS for local synthetic scope**; Medium SEC-5A-04 accepted | 5A.1 review; no real data used |
| Local backup access restricted and checksummed | **PASS locally** | 5A.1/5A.4; backup modes/checksums; Medium SEC-5A-04 Phase 5B follow-up |
| Closed-period unexplained delta = 0 IRR | **PASS for the tested synthetic month** | `test_closed_synthetic_month_reconciles_with_zero_delta`; platform overview and gym summary selected fields reconcile to 0 |
| Zero unbalanced journals | **PASS** | 5A.3/5A.4 tests; drill verifier `ok:true` |
| Zero duplicate facts after retries | **PASS** | 5A.2/5A.4 idempotency and concurrency suites |
| Zero allocation, credit, sequence or payment-consistency mismatches | **PASS** | Drill verifier; finance/platform integrity checks; 5A.6 exact counts |
| **100% financial report endpoints covered by date-semantics conformance tests** | **PASS** | Sections 1, 5 and 6: all reporting-contract endpoints have as-of/range tests; summary, CSV, platform per-gym report/export and legacy repair evidence |
| Owner-facing unbilled amounts never labeled overdue | **PASS** | 5A.3 billed/unbilled tests and UI |
| Docker backup/restore with nonempty platform data | **PASS** | 5A.7-R1 drill with `b9c0d1e2f3a4` applied: `ok:true`, `failures:[]`, **305.05 s** |
| Exact restored counts | **PASS** | All 28 finance and 21 platform tables, including zero-count tables |
| All journals balanced; allocations/credits/sequences reconcile | **PASS** | Verifier checks and drill output |
| Local restore ≤ 60 minutes | **PASS** | 305.05 s |
| Upgrade → downgrade → upgrade | **PASS** | 16 migration tests; trigger survival test; `TZ=UTC` pass |
| No athlete/role/program/finance history silently rewritten | **PASS for tested immutable families; Partial coverage** | Journals, lines, payments, allocations, invoice lines, credits/applications, finance invoice/receipt/credit/movement and sequences are checksummed; audit rows, cancellations/reversals and platform operations are not in the preservation snapshot, and athlete/role/program history is not included in the migration checksum snapshot (the drill only counts `athlete_profile` and program-version rows) |
| Full local regression green | **PASS** | Backend **347 passed**; Playwright **148 passed/3 skipped** clean; lint/build/Ruff/Mypy clean |
| Required role journeys pass; no cross-role data | **PASS** | 5A.5/5A.6 role matrix and Playwright; H6 closure |
| Zero Critical/High usability defects blocking a required journey | **PASS** | 5A.5/5A.6 defect log; H1–H6 and IR-H1/H2 closed |
| Key finance screens load without errors; load time recorded | **PASS** | 5A.7-R1 observational local measurement: gym finance 177 ms, platform finance 166 ms, athlete finance 167 ms wall time; navigation DCL/load 42–45 ms. Not a production SLA |
| No redesign/new feature/unrelated refactor | **PASS** | 5A.7-R1 is the authorized date-semantics remediation only; no unrelated feature work |
| All evidence synthetic/local; no deployment/Vercel/Neon/provider/merge | **PASS** | No remote resource used; `.env.dev` SMTP reverted to empty |
| 92 decisions + ADD-01 preserved; #18/#30/#46 Deferred; Partial statuses preserved | **PASS** | Section 7; no decision reclassified |

## 4. Security, accounting, tenancy and recovery

### Security

- 5A.1 fixed the Critical cross-tenant account-takeover finding (SEC-5A-01) and the High false-control amount-limit finding (SEC-5A-02, fail-closed).
- Zero open Critical/High security findings.
- Medium/Low findings remain accepted for local synthetic 5A with Phase 5B follow-ups: backup/Docker context hygiene, secret file modes, upload modes, invitation race, email-change re-auth, deactivation session revocation, tokens in query strings, missing `Cache-Control: no-store`, database password in backup command lines, login timing.
- 5A.6 added a finance-customer boundary test: finance view required, gym-scoped, coach denied, cross-gym staff denied, minimal fields only.

### Accounting

- 5A.2 covered membership sale → invoice → issue → partial receipt → final receipt; refunds; platform credit/invoice/payment; subscription accrual and commission; coach agreement → earning → vesting → settlement → discrepancy; group contract → volume discount → consolidated invoice → cancellation/reissue.
- 5A.3 closed the tested boundary cases: effective due date from first unpaid installment; billed/unbilled split; platform as-of payments/credits/reminders; revenue vs journal posting; void/cancellation period stability; refund period; closed-period backdating; timezone boundary; closed synthetic month zero delta.
- 5A.4/5A.6 concurrency and idempotency evidence: one fact/one journal per retried operation, no double pay, no over-allocation, no duplicate invoice lines, stable cancellation/payment and credit/invoice races.
- 5A.7-R1 closed the date-semantics coverage gap: historical gym summary
  renewals/coach payable, as-of CSV balance rows with explicit `date_basis`,
  and historical platform per-gym report/export reconciliation across two
  gyms and two periods. Closed-period zero-delta and reconciliation boundary
  tests remain green.

### Tenant isolation

- 100% of tested cross-tenant attempts denied across API, exports, forged `X-Gym-ID`, forged path IDs and client filters.
- Finance customer endpoint: gym-scoped, coach denied, cross-gym staff `403 not_a_gym_member`, minimal fields.
- No role sees another role's or gym's financial data in the role matrix.

### Recovery

- 5A.7-R1 fresh Docker drill: **PASS**, `ok:true`, `failures:[]`, **305.05 s**.
- The new migration `b9c0d1e2f3a4` was copied into the running CI backend and applied with `alembic upgrade head` before the drill; the drill log records the backup/restore, not the migration command itself.
- Exact counts for **28 finance tables** and **21 platform tables**, including zero-count tables.
- Live restore through `restore_compose.sh` passed and re-ran the verifier with `finance-counts.txt` and `platform-counts.txt`.
- Balanced journals, allocation/credit/sequence consistency, upload checksum/size checks passed.
- A fresh image build was not available because Docker image pulls failed in this local environment with a credential/proxy error (`error getting credentials - err: signal: terminated`). The drill used the cached 5A.6 application image with the new forward-only migration applied. Schema/table counts are unchanged by 5A.7-R1.

## 5. Date-semantics endpoint coverage matrix

The matrix was re-derived from the actual `@router.get` decorators in `backend/app/api/routes/finance.py` and `backend/app/api/routes/platform.py` and covers every endpoint with a financial reporting, aggregate, export, reminder, dues or historical/as-of read surface. Configuration-only and identity-directory endpoints (`/accounts`, `/settings`, `/grants`, `/catalog`, `/plans`, `/groups`, `/customers`) are inventoried as non-reporting and excluded from the historical-conformance count. Evidence references are to the current test suite and 5A.7-R1 verification.

### 5.1 Gym finance

| Endpoint | Range / as-of | Canonical date basis | Evidence | Status |
|---|---|---|---|---|
| `GET /finance/reports/summary` | inclusive `from_date..to_date`; balances as of `to_date` | journal `posting_date` for cash/revenue/expense; invoice `issue_date` for sales; effective due date for overdue; as-of paid for invoices; membership/coaching lifecycle as of `to_date` | `test_closed_synthetic_month_reconciles_with_zero_delta`, `test_revenue_recognition_aligns_with_journal_for_boundary_range`, `test_gym_summary_renewals_are_reconstructed_at_the_requested_date`, `test_gym_summary_coach_payable_uses_receipt_and_settlement_dates`, `test_gym_summary_coach_payable_excludes_later_refund_adjustment`, `test_gym_summary_coach_payable_restores_cancelled_settlement_after_cancel_date` | **Fully verified** |
| `GET /finance/reports/export` | range for event rows; balances as of `to_date` | journal/business dates per row family; explicit `date_basis` on every row | `test_csv_exports_are_tenant_safe_and_keep_history`, `test_refund_posts_in_recorded_period_not_request_period`, `test_paid_expense_export_uses_paid_journal_date`, `test_gym_export_has_explicit_date_basis_and_matches_summary_as_of`, `test_platform_balance_rows_use_as_of_payments_credits_and_cancellation`, `test_export_uses_business_dates_for_refunds_and_expenses` | **Fully verified** |
| `GET /finance/reports/offboarding-export` | all history to gym-local today; balances as-of export time | same as export; balance rows labelled `as_of_export` | `test_offboarding_export_labels_balances_as_of_export` | **Fully verified for its as-of-export contract** |
| `GET /finance/reminders` | `gym_today` + horizon | first unpaid installment due date / invoice due date | `test_effective_due_date_uses_first_unpaid_installment`, `test_reminders_report_due_installments_and_renewals` | **Fully verified for current behavior** |
| `GET /finance/invoices`, `/invoices/{id}` | current | effective due date, `gym_today` | 5A.2 invoice/installment tests; 5A.5 UI | **Current-only verified** |
| `GET /finance/platform/invoices` | current | invoice `issued_on` / `due_on` | 5A.2/5A.5 | **Current-only verified** |
| `GET /finance/platform/dues` | current (no `as_of` parameter) | billed `due_on`, unbilled `recognized_on` | `test_platform_billed_unbilled_split_and_owner_consistency` | **Current-only verified** — the date-semantics doc is corrected in this change set to state there is no `as_of` parameter |
| `GET /finance/platform/payments` | current | `received_on` | 5A.2/5A.5 | **Current-only verified / safe** |
| `GET /finance/my/account` | current | current document dates/balances | `athlete-finance.spec.ts`, 5A.5 | **Current-only verified** |
| `GET /finance/my/earnings`, `/my/settlements`, `/my/coach-summary` | current | `created_at`, vesting date, `paid_on` | `coach-finance.spec.ts`, `test_coach_summary_aggregates_own_gyms_only` | **Current-only verified** |
| `GET /finance/journal`, `/journal/{id}` | no range | journal `posting_date` | 5A.2/5A.3 journal tests; drill | **Safe / fully verified for posted-date integrity** |
| `GET /finance/periods` | current lifecycle | `opened_at`, `period_start`, `period_end`, `closed_at` | 5A.3 closed-period tests | **Fully verified** |
| `GET /finance/receipts`, `/receipts/{id}`, `/expenses`, `/expenses/{id}`, `/refunds`, `/credits`, `/memberships`, `/memberships/{id}`, `/memberships/{id}/refund-preview`, `/coach-*`, `/reconciliation` | current | document business dates | 5A.2/5A.3 tests | **Current-only verified** |
| `/finance/customers` | current | identity/roles directory only | 5A.6 boundary tests | **Non-reporting; excluded** |
| `/finance/accounts`, `/settings`, `/grants`, `/catalog` | — | configuration | 5A.1/5A.2 | **Non-reporting; excluded** |

### 5.2 ASCORA platform

| Endpoint | Range / as-of | Canonical date basis | Evidence | Status |
|---|---|---|---|---|
| `GET /platform/reports/overview` | inclusive; balances/MRR as of `to_date` | headline journal `posting_date`; by-gym `recognized_on`; costs `incurred_on`; invoiced `issued_on` + cancellation `cancelled_on` | `test_closed_synthetic_month_reconciles_with_zero_delta`, `test_platform_cancellation_does_not_rewrite_original_period`, `test_platform_discount_cancellation_is_period_stable`, `test_platform_overview_does_not_cross_net_credit_between_gyms` | **Fully verified** |
| `GET /platform/reports/export` | same | same; explicit `date_basis` | `test_csv_exports_are_tenant_safe_and_keep_history`, `test_platform_per_gym_report_and_export_reconcile_across_periods` | **Fully verified** |
| `GET /platform/reports/gyms/{gym_id}` | inclusive; as of `to_date` | same by-gym basis | `test_platform_per_gym_report_and_export_reconcile_across_periods`, `test_platform_per_gym_cancellation_and_credit_as_of` | **Fully verified** |
| `GET /platform/gyms/{gym_id}/export` | same | same; explicit `date_basis` | `test_platform_per_gym_report_and_export_reconcile_across_periods`, `test_platform_per_gym_cancellation_and_credit_as_of` | **Fully verified** |
| `GET /platform/dues`, `/dues/{gym_id}` | optional `as_of` | billed `due_on`; unbilled `recognized_on`; as-of payments/credits | `test_platform_historical_standing_and_reminders_use_as_of_events`, `test_platform_historical_unbilled_ignores_future_payment` | **Fully verified** |
| `GET /platform/reminders` | optional `as_of` | invoice `issued_on`/`due_on`; as-of balance | `test_platform_historical_standing_and_reminders_use_as_of_events`, `test_platform_reminders_are_in_app_only_and_list_due_and_overdue` | **Fully verified** |
| `GET /platform/receivables` | current | `recognized_on`/`due_on` | 5A.2/5A.3 | **Current-only verified** |
| `GET /platform/invoices`, `/invoices/{id}` | current | `issued_on`/`due_on`; current paid/balance | 5A.2/5A.3/5A.6 | **Current-only verified** |
| `GET /platform/payments` | current | `received_on` | 5A.2/5A.3 | **Current-only verified / safe** |
| `GET /platform/costs` | current | `incurred_on` | 5A.2 | **Current-only verified / safe** |
| `GET /platform/agreements` | current | effective dates/terms | 5A.2/5A.6 | **Current-only verified / safe** |
| `GET /platform/plans`, `/groups` | — | non-financial | 5A.2/5A.6 | **Non-reporting; excluded** |

### 5.3 Special date-semantics assessment

| Item | Finding |
|---|---|
| Historical coach payable | Reconstructed at `to_date` from earning receipt/credit/journal dates, as-of settlement items and as-of refund adjustments. **Fully verified.** |
| Membership renewal metrics | Reconstructed at `to_date` from membership start/cancel dates and audit-backed freeze/resume extensions; incomplete history fails closed and is tested. **Fully verified.** |
| CSV balance rows | Platform receivable/invoice-line balances reconstructed from as-of payment allocations, credits and cancellation dates; every row carries `date_basis`. **Fully verified.** |
| Legacy date backfill | Unambiguous source-linked rows repaired by `b9c0d1e2f3a4`; ambiguous or source-less rows remain documented limitations. **Partially repaired as explicitly documented; no invented dates.** |
| Closed-period zero delta | Proven for the tested closed synthetic month and selected platform/gym reports. **PASS for the tested acceptance period.** |
| Current-only reads | Gym/athlete/coach document lists and `my/*` reads are current by design; they are not historical reports. **Current-only, not as-of.** |

**Date-semantics verdict: the 100% conformance baseline is met for the approved reporting contract.** No mandatory date-semantics blocker remains.

## 6. Final automated evidence

| Check | Result | Notes |
|---|---|---|
| Full backend regression | **347 passed** in 232.32 s | 5A.7-R1 final run |
| Migration tests | **16 passed** in 9.24 s | Also **16 passed under `TZ=UTC`** in 8.57 s |
| Concurrency suite | **9 passed** | 5A.6 evidence: 5 consecutive runs and `TZ=UTC` |
| Finance staff boundary tests | **2 passed** | 5A.6 |
| Full Playwright (5A.7-R1) | **148 passed, 3 skipped** | Clean run, no retry needed |
| `ui-acceptance` project | **7 passed** | Includes H6 two-gym billing and default accrual |
| Frontend lint | **Clean** | 175 files |
| Frontend build | **Pass** | Vite production build |
| Ruff / Mypy | **Clean / clean** | 48 source files |
| Docker backup/restore drill | **PASS**, `ok:true`, `failures:[]`, **305.05 s** | New migration applied before drill; 28 finance + 21 platform tables exact |
| Local load measurement | Gym finance **177 ms**, platform finance **166 ms**, athlete finance **167 ms** wall; DCL/load 42–45 ms | Observational measurement on the local reference machine; no retained raw log. Not a production SLA |

The 5A.7-R1 full Playwright run was clean at 148 passed and 3 skipped, with no retry needed. The 12 additional backend tests are 11 API-level date-semantics tests (historical renewals and fail-closed history, coach payable, CSV date basis/as-of balances, platform per-gym reconciliation, cancellation/credit) plus one new legacy-repair migration test, bringing the migration suite to 16.

## 7. PRD decision status matrix (all 92 + ADD-01)

| Decision | Status | 5A.7-R1 reconciliation |
|---|---|---|
| 1 | **Implemented** | Confirmed; no status change in 5A.7. |
| 2 | **Implemented** | Confirmed; no status change in 5A.7. |
| 3 | **Implemented** | Confirmed; no status change in 5A.7. |
| 4 | **Implemented** | Confirmed; no status change in 5A.7. |
| 5 | **Implemented** | Confirmed; no status change in 5A.7. |
| 6 | **Implemented** | Confirmed; no status change in 5A.7. |
| 7 | **Implemented** | Confirmed; no status change in 5A.7. |
| 8 | **Implemented** | Confirmed; no status change in 5A.7. |
| 9 | **Implemented** | Confirmed; no status change in 5A.7. |
| 10 | **Implemented** | Confirmed; no status change in 5A.7. |
| 11 | **Implemented** | Confirmed; no status change in 5A.7. |
| 12 | **Implemented** | Confirmed; no status change in 5A.7. |
| 13 | **Implemented** | Confirmed; no status change in 5A.7. |
| 14 | **Implemented** | Confirmed; no status change in 5A.7. |
| 15 | **Partial** | Confirmed Partial: in-app reminders only; proactive delivery not implemented. |
| 16 | **Implemented** | Confirmed; no status change in 5A.7. |
| 17 | **Implemented** | Confirmed; no status change in 5A.7. |
| 18 | **Deferred** | Deferred — unchanged. |
| 19 | **Implemented** | Confirmed; no status change in 5A.7. |
| 20 | **Implemented** | Confirmed; no status change in 5A.7. |
| 21 | **Implemented** | Confirmed; no status change in 5A.7. |
| 22 | **Implemented** | Confirmed; no status change in 5A.7. |
| 23 | **Implemented** | Confirmed; no status change in 5A.7. |
| 24 | **Implemented** | Confirmed; no status change in 5A.7. |
| 25 | **Implemented** | Confirmed; no status change in 5A.7. |
| 26 | **Implemented** | Confirmed; no status change in 5A.7. |
| 27 | **Implemented** | Confirmed; no status change in 5A.7. |
| 28 | **Implemented** | Confirmed; no status change in 5A.7. |
| 29 | **Implemented** | Confirmed; no status change in 5A.7. |
| 30 | **Deferred** | Deferred — unchanged. |
| 31 | **Implemented** | Confirmed; no status change in 5A.7. |
| 32 | **Implemented** | Confirmed; no status change in 5A.7. |
| 33 | **Implemented** | Confirmed; no status change in 5A.7. |
| 34 | **Partial** | Confirmed Partial: stages/reminders visible; no automatic restrictions. |
| 35 | **Implemented** | Confirmed; no status change in 5A.7. |
| 36 | **Implemented** | Confirmed; no status change in 5A.7. |
| 37 | **Implemented** | Functionality confirmed; as-of summary and CSV balance conformance now verified (DS-M1/M2 resolved). Status unchanged. |
| 38 | **Implemented** | Confirmed; no status change in 5A.7. |
| 39 | **Implemented** | Confirmed; no status change in 5A.7. |
| 40 | **Implemented** | Confirmed; no status change in 5A.7. |
| 41 | **Implemented** | Confirmed; no status change in 5A.7. |
| 42 | **Partial** | Confirmed Partial: only opening-balance limit enforced; other permission limits fail closed. |
| 43 | **Implemented** | Gym dashboard functionality confirmed; historical renewals/coach payable now reconstructed and tested. |
| 44 | **Implemented** | Platform overview/per-gym netting confirmed; per-gym report/export historical conformance now tested (DS-M3 resolved). |
| 45 | **Implemented** | Confirmed; no status change in 5A.7. |
| 46 | **Deferred** | Deferred — unchanged. |
| 47 | **Implemented** | Tenant-isolation matrix and 5A.6 customer boundary tests pass. |
| 48 | **Implemented** | Confirmed; no status change in 5A.7. |
| 49 | **Implemented** | 5A.4/5A.6 idempotency and concurrency suites pass, including cancellation/payment and credit/invoice races. |
| 50 | **Implemented** | 5A.7-R1 Docker drill PASS with the new migration applied, exact 28 finance + 21 platform counts, 305.05 s. |
| 51 | **Implemented** | Migration and trigger tests pass; preservation snapshot is Partial for audit/cancellation/platform-operation rows (MIG-M1). |
| 52 | **Implemented** | Confirmed; no status change in 5A.7. |
| 53 | **Outstanding** | Outstanding: no real-gym pilot; Phase 5B only. |
| 54 | **Partial** | Partial: local integrity/tenant/restore/date/migration/concurrency evidence passes, including 100% reporting-contract date conformance; pilot criteria pending. |
| 55 | **Implemented** | Offboarding export exists; balances are as-of export time and labelled `as_of_export` (DS-M2 resolved). |
| 56 | **Outstanding** | Outstanding: Iran legal/tax/privacy/provider work not done. |
| 57 | **Implemented** | Confirmed; no status change in 5A.7. |
| 58 | **Implemented** | Group contracts/discounts and 5A.6 multi-gym UI/consolidated invoice confirmed. |
| 59 | **Implemented** | Confirmed; no status change in 5A.7. |
| 60 | **Implemented** | Confirmed; no status change in 5A.7. |
| 61 | **Partial** | Partial: Jalali/gym-local boundaries implemented; some current-only reads use UTC and timezone setting is not editable/audited. |
| 62 | **Implemented** | Confirmed; no status change in 5A.7. |
| 63 | **Implemented** | Confirmed; no status change in 5A.7. |
| 64 | **Implemented** | Confirmed; no status change in 5A.7. |
| 65 | **Implemented** | Confirmed; no status change in 5A.7. |
| 66 | **Implemented** | Confirmed; no status change in 5A.7. |
| 67 | **Implemented** | Confirmed; no status change in 5A.7. |
| 68 | **Implemented** | Confirmed; no status change in 5A.7. |
| 69 | **Implemented** | Confirmed; no status change in 5A.7. |
| 70 | **Implemented** | Confirmed; no status change in 5A.7. |
| 71 | **Partial** | Confirmed Partial: in-app reminders only; proactive delivery/restriction policy outstanding. |
| 72 | **Implemented** | Confirmed; no status change in 5A.7. |
| 73 | **Implemented** | Confirmed; no status change in 5A.7. |
| 74 | **Implemented** | Confirmed; no status change in 5A.7. |
| 75 | **Implemented** | Confirmed; no status change in 5A.7. |
| 76 | **Implemented** | Confirmed; no status change in 5A.7. |
| 77 | **Implemented** | Confirmed; no status change in 5A.7. |
| 78 | **Implemented** | Confirmed; no status change in 5A.7. |
| 79 | **Implemented** | Confirmed; no status change in 5A.7. |
| 80 | **Implemented** | Confirmed; no status change in 5A.7. |
| 81 | **Implemented** | Confirmed; no status change in 5A.7. |
| 82 | **Implemented** | Confirmed; no status change in 5A.7. |
| 83 | **Implemented** | Confirmed; no status change in 5A.7. |
| 84 | **Implemented** | Estimated operating profit tests pass; date-semantics coverage now verified. |
| 85 | **Implemented** | Confirmed; no status change in 5A.7. |
| 86 | **Implemented** | Confirmed; no status change in 5A.7. |
| 87 | **Implemented** | Confirmed; no status change in 5A.7. |
| 88 | **Implemented** | Confirmed; no status change in 5A.7. |
| 89 | **Implemented** | Confirmed; no status change in 5A.7. |
| 90 | **Partial** | Confirmed Partial: grants implemented; only opening-balance amount limit enforced. |
| 91 | **Partial** | Confirmed Partial: limits modeled/surfaced; core enforcement not implemented. |
| 92 | **Partial** | Partial: local gates pass; public release/pilot/legal not authorized. |
| ADD-01 | **Implemented** | Implemented; zero/free/commission/hybrid/custom controls confirmed. |

**Status reconciliation:** #18, #30 and #46 remain **Deferred**. #15, #34, #42, #54, #61, #71, #90, #91 and #92 remain **Partial**. #53 and #56 remain **Outstanding**. All other decisions remain **Implemented**. `ADD-01` remains **Implemented**. No decision was reclassified by 5A.7 or 5A.7-R1. #15/#71 proactive delivery, #34 automatic restrictions, #42/#90 per-action amount enforcement, #61 complete date/timezone conformance, #91 plan-limit enforcement and #92 release requirements remain unresolved.

## 8. Open risks by severity

### Critical

None known.

### High

None known in security, tenant isolation, money integrity or required journeys. The former date-semantics blocker category is resolved and verified in Section 5.

### Medium

| ID | Finding | Disposition |
|---|---|---|
| DS-M1 | `GET /finance/reports/summary` mixed current-only `renewals_due`/`coach_payable_irr` with historical range fields. | **Resolved**; reconstructed as-of and tested |
| DS-M2 | `GET /finance/reports/export`/offboarding balance rows were current-state and had no `date_basis`. | **Resolved**; as-of balances, explicit `date_basis`, offboarding `as_of_export` |
| DS-M3 | Per-gym platform report/export lacked historical conformance tests. | **Resolved**; multi-period reconciliation and export tests added |
| DS-M4 | Legacy reporting-date backfill can differ from the original ledger business date. | **Partially repaired** for unambiguous sources; remaining cases documented in `legacy-date-reconstruction.md` |
| DS-M5 | Date-semantics doc described `/finance/platform/dues` as accepting `as_of`; the route is current-only. | **Resolved**; documentation corrected |
| SEC-5A-04 | Backup/Docker context excludes not tightened; backup directory not Git-ignored. | Accepted for local 5A; Phase 5B |
| F-5A5-M1/M3/M4/M5/M6 | Platform payment-history labeling, missing cost/payment/cancellation/due-soon views, amount-limit Partial, coach/athlete Rial hardcoding, release-workflow drill isolation. | Phase 5B / accepted local risk |
| IR-M1..M7 | Group edit after effective agreement, untranslated backend errors, non-atomic all-branch accrual, 0% allocation accrual, broader consolidated scope, backup-count timing, query error states. | Recorded for Phase 5B |
| MIG-M1 | Migration preservation snapshot does not cover audit rows, invoice cancellations/reversals or platform operations. No rewrite observed; key immutable finance/platform families are checksummed. | Open evidence gap; Phase 5B |
| DATE-M1 | `recognized_on`, `cancelled_on`, `applied_on` and period boundaries remain mutable by direct SQL (no immutability trigger). | Accepted Medium residual risk; Phase 5B |
| TZ-L1 | Custom gym timezone path is handled in SQL but only the `Asia/Tehran` fallback is tested; the timezone setting is not editable/audited through the API. | Low; Phase 5B |

### Low

- Secret file modes, upload modes, invitation race, email-change re-auth, deactivation session revocation, tokens in query strings, missing `Cache-Control: no-store`, database password in backup command lines, login timing.
- Raw enums, missing currency labels, platform form state retention, customer list pagination/role N+1, hardcoded verifier table lists, immutability test trigger-name-only query.
- H6 mobile-specific coverage is from the 5A.5 role suite rather than a new H6 mobile test.

## 9. Remaining incomplete features

These are not hidden by LOCAL GO and are not implemented in Phase 5A:

- Proactive reminder delivery (#15/#71) — in-app only.
- Configurable overdue restrictions (#34).
- Per-action finance-staff amount limits beyond opening balance (#42/#90).
- Plan-limit enforcement (#91).
- Platform period lock/closed-period model.
- Editable/audited finance timezone setting.
- Automatic coach clawback (#30), usage/attendance finance input (#18), advanced AI/analytics (#46).
- Real-gym pilot (#53), Iran legal/tax/privacy/provider work (#56), public-release requirements (#92).
- Platform UI visibility for costs/payment history/cancellation reason/due-soon reminders, and non-atomic all-branch accrual.

## 10. Explicit limitations of this local release candidate

- Local synthetic data only; no real financial data.
- No production, Vercel/Neon, remote infrastructure, provider or legal signoff.
- No merge to `main`.
- Backup/restore proves local recoverability, not production RPO/RTO.
- Legacy reporting rows without an authoritative source event, or with an ambiguous applied-advance match, remain on the `created_at` backfill; this is documented in `docs/finance/legacy-date-reconstruction.md`.
- Historical renewal reconstruction depends on append-only membership audit events; incomplete legacy freeze history fails closed rather than guessing.
- Migration preservation evidence covers the tested immutable finance/platform families but not audit, cancellation/reversal or platform-operation rows. No data rewrite was observed.
- Reporting-date columns remain mutable by direct SQL; this is a documented Medium residual risk, not a confirmed money error.
- A fresh Docker application image could not be built because Docker image pulls failed in this local environment with a credential/proxy error. The backup/restore drill used the cached 5A.6 image with the new forward-only migration applied; the retained drill log does not include the `alembic upgrade head` step. Schema and table counts are unchanged by 5A.7-R1.
- The 5A.7-R1 decision is based on the evidence in this repository and the fresh runs listed above. No external approval is claimed.

## 11. Recommended next actions (not initiated)

1. Stop local Phase 5A work; the LOCAL GO gate is met.
2. Do not start Phase 5B, deployment, provider integration, a real-gym pilot or release until separately authorized.
3. In a separately authorized Phase 5B, address the residual Medium/Low findings and any remaining legacy rows without an authoritative source.
4. A LOCAL GO does not authorize production, real-money operations, real-gym onboarding or public release.

---

**Final decision: LOCAL GO.** The local release candidate meets the unchanged 5A.0 acceptance baseline. The former date-semantics blockers are resolved and verified, with no confirmed Critical/High security, tenant-isolation or money-integrity defect.
