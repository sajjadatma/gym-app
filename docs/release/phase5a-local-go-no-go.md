# Phase 5A.7 — Final LOCAL GO/NO-GO Assessment

**Date:** 2026-11-08
**Branch:** `feat/ascora-finance`
**Assessed commit:** `0152971`
**Scope:** Final local acceptance gate for ASCORA Finance Phase 5A
**Environment:** Local PostgreSQL, FastAPI backend, Vite frontend, Playwright and Docker Compose
**Data:** Synthetic and disposable only

## 1. Final decision

# LOCAL NO-GO

**The local release candidate is not eligible for LOCAL GO under the approved 5A.0 baseline.**

All security, tenant-isolation, financial-workflow, concurrency, recovery, UI/UX and defect-closure gates that were tested pass or are explicitly partial, and there are **zero known Critical/High security, tenant-isolation or money-integrity defects**. The blocking category is the mandatory **date-semantics coverage** gate:

> 5A.0 requires **100% of financial report endpoints covered by date-semantics conformance tests**. The approved LOCAL NO-GO rule also states that **any financial report endpoint with unverified or mixed date semantics** is a NO-GO trigger.

The evidence does not prove 100% coverage. Specifically:

1. **`GET /finance/reports/summary` is a mixed-basis report.** `renewals_due` and `coach_payable_irr` are computed from the current membership/coaching state, not reconstructed as of the requested `to_date`. No conformance test proves historical as-of behavior for these fields. The date-semantics decision record itself records this limitation.
2. **`GET /finance/reports/export` and `GET /finance/reports/offboarding-export` contain current-state balance rows.** The CSV `BALANCE` rows use current `paid_irr`/status values and the current summary fields; they are not as-of reconstructed. The CSV also has no explicit `date_basis` column. Tests cover selected row families (recorded refunds, paid expenses, tenant safety) but not every row family or historical balance behavior.
3. **`GET /platform/gyms/{gym_id}/export` has no date-semantics test evidence.** The endpoint is listed as canonical in the date-semantics matrix, but no backend or Playwright test exercises it against a historical range.
4. **`GET /platform/reports/gyms/{gym_id}` is only current-period tested.** The 5A.6 Playwright test asserts current-month amounts; it does not cover a historical/as-of boundary or the same range-splitting cases as the platform overview.
5. **Documentation and route behavior disagree for `GET /finance/platform/dues`.** The date-semantics matrix describes an optional `as_of`; the route has no `as_of` parameter and returns current standing. This is corrected in the current documentation change set, but it reinforces that the endpoint inventory was not independently exact.
6. **Legacy backfill limitation remains.** Pre-5A.3 rows may carry `recognized_on`/`applied_on` derived from creation time rather than the original business/journal date. The migration evidence covers the new columns but not historical equivalence for legacy rows.

These are not new code regressions introduced by 5A.6. They are unresolved gaps in the approved 5A.0 baseline. Reclassifying them as acceptable would silently weaken the baseline, which this report does not do.

### What would change the decision

A LOCAL GO could be reconsidered only if the owner explicitly authorizes a recorded 5A.0 baseline change or waiver for the documented current-only fields and the missing endpoint coverage, **or** the implementation/tests are extended to prove the required as-of behavior. No such authorization is present in this assessment.

A LOCAL NO-GO is not authorization for production, real-money operations, real-gym onboarding or public release.

## 2. Evidence index

- [5A.0 local baselines](phase5a-local-baselines.md)
- [5A.1 security and tenant-isolation audit](phase5a-security-audit.md)
- [5A.2 local financial acceptance](phase5a-local-financial-acceptance.md)
- [5A.3 date-semantics decision record](../finance/date-semantics.md)
- [5A.3 reconciliation](phase5a-reconciliation.md)
- [5A.4 migration, concurrency and recovery](phase5a-migration-recovery.md)
- [5A.5 local UI/UX acceptance](phase5a-local-ui-acceptance.md)
- [5A.6 defect closure](phase5a-defect-closure.md)
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
| **100% financial report endpoints covered by date-semantics conformance tests** | **FAIL** | Sections 1 and 5: mixed/current-only fields, missing endpoint tests, legacy backfill |
| Owner-facing unbilled amounts never labeled overdue | **PASS** | 5A.3 billed/unbilled tests and UI |
| Docker backup/restore with nonempty platform data | **PASS** | 5A.7 drill: `ok:true`, no failures, **306.43 s** |
| Exact restored counts | **PASS** | All 28 finance and 21 platform tables, including zero-count tables |
| All journals balanced; allocations/credits/sequences reconcile | **PASS** | Verifier checks and drill output |
| Local restore ≤ 60 minutes | **PASS** | 306.43 s |
| Upgrade → downgrade → upgrade | **PASS** | 15 migration tests; trigger survival test; `TZ=UTC` pass |
| No athlete/role/program/finance history silently rewritten | **PASS for tested immutable families; Partial coverage** | Journals, lines, payments, allocations, invoice lines, credits/applications, finance invoice/receipt/credit/movement and sequences are checksummed; audit rows, cancellations/reversals and platform operations are not in the preservation snapshot, and athlete/role/program history is not included in the migration checksum snapshot (the drill only counts `athlete_profile` and program-version rows) |
| Full local regression green | **PASS** | Backend 335; Playwright 148 passed/3 skipped at 0152971; 5A.7 rerun 147 + one known flaky mobile archive test passed on retry; lint/build clean |
| Required role journeys pass; no cross-role data | **PASS** | 5A.5/5A.6 role matrix and Playwright; H6 closure |
| Zero Critical/High usability defects blocking a required journey | **PASS** | 5A.5/5A.6 defect log; H1–H6 and IR-H1/H2 closed |
| Key finance screens load without errors; load time recorded | **PASS** | 5A.7 observational local measurement (no retained raw log): gym finance 159 ms, platform finance 153 ms, athlete finance 170 ms wall time; navigation DCL/load ≈ 40–43 ms. Not a production SLA |
| No redesign/new feature/unrelated refactor | **PASS** | Only authorized H6 exception in 5A.6; 5A.7 documentation-only |
| All evidence synthetic/local; no deployment/Vercel/Neon/provider/merge | **PASS** | No remote resource used; `.env.dev` SMTP reverted to empty |
| 92 decisions + ADD-01 preserved; #18/#30/#46 Deferred; Partial statuses preserved | **PASS** | Section 7 |

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
- The date-semantics coverage gap remains the only accounting-baseline failure.

### Tenant isolation

- 100% of tested cross-tenant attempts denied across API, exports, forged `X-Gym-ID`, forged path IDs and client filters.
- Finance customer endpoint: gym-scoped, coach denied, cross-gym staff `403 not_a_gym_member`, minimal fields.
- No role sees another role's or gym's financial data in the role matrix.

### Recovery

- 5A.7 fresh Docker drill: **PASS**, `ok:true`, `failures:[]`, **306.43 s**.
- Exact counts for **28 finance tables** and **21 platform tables**, including zero-count tables.
- Live restore through `restore_compose.sh` passed and re-ran the verifier with `finance-counts.txt` and `platform-counts.txt`.
- Balanced journals, allocation/credit/sequence consistency, upload checksum/size checks passed.

## 5. Date-semantics endpoint coverage matrix

The matrix covers every endpoint with a financial reporting, aggregate, export, reminder, dues or historical/as-of read surface. Configuration-only endpoints (`/accounts`, `/settings`, `/grants`, `/catalog`, `/plans`, `/groups`) are inventoried as non-reporting and excluded from the historical-conformance count. Evidence references are to the current test suite and 5A.7 verification.

### 5.1 Gym finance

| Endpoint | Range / as-of | Canonical date basis | Evidence | Status |
|---|---|---|---|---|
| `GET /finance/reports/summary` | inclusive `from_date..to_date`; balances as of `to_date` | journal `posting_date` for cash/revenue/expense; invoice `issue_date` for sales; effective due date for overdue; as-of paid for invoices | `test_closed_synthetic_month_reconciles_with_zero_delta`, `test_revenue_recognition_aligns_with_journal_for_boundary_range`, `test_void_preserves_original_period_and_reverses_in_void_period`, `test_void_receivable_uses_void_posting_date` | **Partially verified / mixed basis — blocker**: `renewals_due` and `coach_payable_irr` are current-state, not as-of `to_date`; no historical test |
| `GET /finance/reports/export` | inclusive range | mixed row families: cash events, accrual dates, invoice issue dates, balance rows | `test_csv_exports_are_tenant_safe_and_keep_history`, `test_refund_posts_in_recorded_period_not_request_period`, `test_paid_expense_export_uses_paid_journal_date` | **Partially verified — blocker**: `BALANCE` rows use current `paid_irr`/status; no `date_basis` column; not every row family has a range test |
| `GET /finance/reports/offboarding-export` | all history to gym-local today | current balances at export time | `test_csv_exports_are_tenant_safe_and_keep_history` (header/tenant only) | **Current-only / partially verified — blocker under a literal 100% requirement**: no as-of historical semantics or row-family conformance test |
| `GET /finance/reminders` | `gym_today` + horizon | first unpaid installment due date / invoice due date | `test_effective_due_date_uses_first_unpaid_installment`, `test_reminders_report_due_installments_and_renewals` | **Fully verified for current behavior** |
| `GET /finance/invoices`, `/invoices/{id}` | current | effective due date, `gym_today` | 5A.2 invoice/installment tests; 5A.5 UI | **Current-only verified** |
| `GET /finance/platform/invoices` | current | invoice `issued_on` / `due_on` | 5A.2/5A.5 | **Current-only verified** |
| `GET /finance/platform/dues` | current (no `as_of` parameter) | billed `due_on`, unbilled `recognized_on` | `test_platform_billed_unbilled_split_and_owner_consistency` | **Current-only verified** — the date-semantics doc is corrected in this change set to state there is no `as_of` parameter |
| `GET /finance/platform/payments` | current | `received_on` | 5A.2/5A.5 | **Current-only verified / safe** |
| `GET /finance/my/account` | current | current document dates/balances | `athlete-finance.spec.ts`, 5A.5 | **Current-only verified** |
| `GET /finance/my/earnings`, `/my/settlements`, `/my/coach-summary` | current | `created_at`, vesting date, `paid_on` | `coach-finance.spec.ts`, `test_coach_summary_aggregates_own_gyms_only` | **Current-only verified** |
| `GET /finance/journal`, `/journal/{id}` | no range | journal `posting_date` | 5A.2/5A.3 journal tests; drill | **Safe / fully verified for posted-date integrity** |
| `GET /finance/periods` | current lifecycle | `opened_at`, `period_start`, `period_end`, `closed_at` | 5A.3 closed-period tests | **Fully verified** |
| `GET /finance/receipts`, `/receipts/{id}`, `/expenses`, `/expenses/{id}`, `/refunds`, `/credits`, `/memberships`, `/coach-*`, `/reconciliation` | current | document business dates | 5A.2/5A.3 tests | **Current-only verified** |
| `/finance/customers` | current | identity/roles directory only | 5A.6 boundary tests | **Non-reporting; excluded** |
| `/finance/accounts`, `/settings`, `/grants`, `/catalog` | — | configuration | 5A.1/5A.2 | **Non-reporting; excluded** |

### 5.2 ASCORA platform

| Endpoint | Range / as-of | Canonical date basis | Evidence | Status |
|---|---|---|---|---|
| `GET /platform/reports/overview` | inclusive; balances/MRR as of `to_date` | headline journal `posting_date`; by-gym `recognized_on`; costs `incurred_on`; invoiced `issued_on` + cancellation `cancelled_on` | `test_closed_synthetic_month_reconciles_with_zero_delta`, `test_platform_cancellation_does_not_rewrite_original_period`, `test_platform_discount_cancellation_is_period_stable`, `test_platform_overview_does_not_cross_net_credit_between_gyms` | **Fully verified** |
| `GET /platform/reports/export` | same | same | `test_csv_exports_are_tenant_safe_and_keep_history`, 5A.2 export metric parsing | **Fully verified** |
| `GET /platform/reports/gyms/{gym_id}` | inclusive; as of `to_date` | same by-gym basis | 5A.6 Playwright current-month exact amounts; 5A.3 overview by-gym tests | **Partially verified — blocker**: no historical/as-of boundary test for this endpoint |
| `GET /platform/gyms/{gym_id}/export` | same | same | No backend or Playwright test | **Unverified — blocker** |
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
| Historical coach payable | `coach_payable_irr` in `GET /finance/reports/summary` and the CSV summary is current outstanding coaching payable, not reconstructed as of `to_date`. **Partially verified / baseline gap.** |
| Membership renewal metrics | `renewals_due` in `GET /finance/reports/summary` counts current ACTIVE/FROZEN memberships with `end_date` in the next 30 days; it is not a historical as-of count. **Partially verified / baseline gap.** |
| CSV balance rows | `platform_receivable` and `platform_invoice_line` `BALANCE` rows use current `paid_irr`/status, not as-of historical paid amounts. **Partially verified / baseline gap.** |
| Legacy date backfill | Pre-5A.3 platform receivables/credits and finance credit movements can use creation date rather than original business date. New rows use canonical dates. **Documented limitation; not proven equivalent.** |
| Closed-period zero delta | Proven for the tested synthetic month and selected platform/gym reports, not for every report endpoint. **Partial.** |
| Current-only reads | Gym/athlete/coach document lists and `my/*` reads are current by design; they are not historical reports. **Current-only, not as-of.** |

**Date-semantics verdict: the 100% conformance baseline is NOT met.** This is the sole mandatory LOCAL GO blocker category.

## 6. Final automated evidence

| Check | Result | Notes |
|---|---|---|
| Full backend regression | **335 passed** in 240.84 s | 5A.7 fresh run |
| Migration tests | **15 passed** | Also **15 passed under `TZ=UTC`** |
| Concurrency suite | **9 passed** | 5A.6 evidence: 5 consecutive runs and `TZ=UTC` |
| Finance staff boundary tests | **2 passed** | 5A.6 |
| Full Playwright (committed code) | **148 passed, 3 skipped** | 5A.6 final clean run at 0152971 |
| Full Playwright (5A.7 rerun) | **147 passed, 3 skipped, 1 flaky archive test** | The mobile-admin archive test passed on immediate retry; no product regression found |
| `ui-acceptance` project | **7 passed** | Includes H6 two-gym billing and default accrual |
| Frontend lint | **Clean** | 175 files |
| Frontend build | **Pass** | Vite production build |
| Ruff / Mypy | **Clean / clean** | 48 source files |
| Docker backup/restore drill | **PASS**, `ok:true`, **306.43 s** | 28 finance + 21 platform tables exact |
| Local load measurement | Gym finance **159 ms**, platform finance **153 ms**, athlete finance **170 ms** wall; DCL/load ≈ 40–43 ms | Observational measurement on the local reference machine; no retained raw log. Not a production SLA |

The 5A.7 Playwright rerun had one known mobile-admin archive-menu flake; it passed on retry. The clean 148-pass run at the same commit is the primary Playwright evidence.

## 7. PRD decision status matrix (all 92 + ADD-01)

| Decision | Status | 5A.7 reconciliation |
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
| 37 | **Implemented** | Functionality confirmed (gym reports/export, platform payable netting). **Evidence caveat:** full date-semantics conformance is not proven for summary current-only fields and CSV balance rows (DS-M1/M2). Status not changed in 5A.7. |
| 38 | **Implemented** | Confirmed; no status change in 5A.7. |
| 39 | **Implemented** | Confirmed; no status change in 5A.7. |
| 40 | **Implemented** | Confirmed; no status change in 5A.7. |
| 41 | **Implemented** | Confirmed; no status change in 5A.7. |
| 42 | **Partial** | Confirmed Partial: only opening-balance limit enforced; other permission limits fail closed. |
| 43 | **Implemented** | Gym dashboard functionality confirmed; historical current-only fields in summary are recorded as DS-M1. |
| 44 | **Implemented** | Platform overview/per-gym netting confirmed; per-gym report/export historical coverage is Partial (DS-M3). |
| 45 | **Implemented** | Confirmed; no status change in 5A.7. |
| 46 | **Deferred** | Deferred — unchanged. |
| 47 | **Implemented** | Tenant-isolation matrix and 5A.6 customer boundary tests pass. |
| 48 | **Implemented** | Confirmed; no status change in 5A.7. |
| 49 | **Implemented** | 5A.4/5A.6 idempotency and concurrency suites pass, including cancellation/payment and credit/invoice races. |
| 50 | **Implemented** | 5A.7 Docker drill PASS, exact 28 finance + 21 platform counts, 306.43 s. |
| 51 | **Implemented** | Migration and trigger tests pass; preservation snapshot is Partial for audit/cancellation/platform-operation rows (MIG-M1). |
| 52 | **Implemented** | Confirmed; no status change in 5A.7. |
| 53 | **Outstanding** | Outstanding: no real-gym pilot; Phase 5B only. |
| 54 | **Partial** | Partial: local integrity/tenant/restore/date/migration/concurrency evidence passes; pilot criteria pending. |
| 55 | **Implemented** | Offboarding export exists; its balance semantics are current-only (DS-M2). |
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
| 84 | **Implemented** | Estimated operating profit tests pass; date-semantics coverage caveat remains under DS-M1/M2. |
| 85 | **Implemented** | Confirmed; no status change in 5A.7. |
| 86 | **Implemented** | Confirmed; no status change in 5A.7. |
| 87 | **Implemented** | Confirmed; no status change in 5A.7. |
| 88 | **Implemented** | Confirmed; no status change in 5A.7. |
| 89 | **Implemented** | Confirmed; no status change in 5A.7. |
| 90 | **Partial** | Confirmed Partial: grants implemented; only opening-balance amount limit enforced. |
| 91 | **Partial** | Confirmed Partial: limits modeled/surfaced; core enforcement not implemented. |
| 92 | **Partial** | Partial: local gates pass; public release/pilot/legal not authorized. |
| ADD-01 | **Implemented** | Implemented; zero/free/commission/hybrid/custom controls confirmed. |

**Status reconciliation:** #18, #30 and #46 remain **Deferred**. #15, #34, #42, #54, #61, #71, #90, #91 and #92 remain **Partial**. #53 and #56 remain **Outstanding**. All other decisions remain **Implemented**. `ADD-01` remains **Implemented**. No decision was reclassified by 5A.7. #15/#71 proactive delivery, #34 automatic restrictions, #42/#90 per-action amount enforcement, #61 complete date/timezone conformance, #91 plan-limit enforcement and #92 release requirements remain unresolved.

## 8. Open risks by severity

### Critical

None known.

### High

None known in security, tenant isolation, money integrity or required journeys.

The date-semantics baseline failure is a **mandatory acceptance-gate blocker**, reported separately from defect severity because it is a coverage/evidence failure, not a confirmed production defect.

### Medium

| ID | Finding | Disposition |
|---|---|---|
| DS-M1 | `GET /finance/reports/summary` mixes current-only `renewals_due`/`coach_payable_irr` with historical range fields. | **Blocks LOCAL GO under the 5A.0 baseline**; fix or obtain an explicit recorded baseline waiver |
| DS-M2 | `GET /finance/reports/export`/offboarding balance rows are current-state; no `date_basis`; not every row family is range-tested. | **Blocks LOCAL GO under the 5A.0 baseline** |
| DS-M3 | `GET /platform/reports/gyms/{gym_id}` lacks a historical/as-of boundary test; `GET /platform/gyms/{gym_id}/export` is unverified. | **Blocks LOCAL GO under the 5A.0 baseline** |
| DS-M4 | Legacy reporting-date backfill can differ from the original ledger business date. | Preserve as open historical limitation; not silently resolved |
| DS-M5 | Date-semantics doc described `/finance/platform/dues` as accepting `as_of`; the route is current-only. | Documentation corrected in this change set |
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

These are not hidden by LOCAL NO-GO and are not implemented in Phase 5A:

- Proactive reminder delivery (#15/#71) — in-app only.
- Configurable overdue restrictions (#34).
- Per-action finance-staff amount limits beyond opening balance (#42/#90).
- Plan-limit enforcement (#91).
- Full historical/as-of reconstruction of coach payable, membership renewal metrics and CSV balance rows.
- `date_basis` column in CSV exports.
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
- Date-semantics coverage is not 100%; historical coach payable, renewal metrics, CSV balance rows and legacy backfills remain current/legacy.
- The full Playwright suite has one known mobile-admin archive-menu flake that passed on retry; this is a test-stability issue, not a product regression.
- Migration preservation evidence is complete for the tested immutable finance/platform families but not for audit, cancellation/reversal or platform-operation rows. No data rewrite was observed.
- Reporting-date columns remain mutable by direct SQL; this is a documented Medium residual risk, not a confirmed money error.
- The 5A.7 decision is based on the evidence in this repository at `0152971` and the fresh runs listed above. No external approval is claimed.

## 11. Recommended next actions (not initiated)

1. Decide whether to fix the date-semantics gaps in a separate authorized task, or explicitly record a 5A.0 baseline waiver for the documented current-only fields.
2. If fixing: add as-of reconstruction/tests for `renewals_due` and `coach_payable_irr`; add `BALANCE` as-of/date-basis behavior and row-family tests for CSV; add historical tests for platform per-gym report/export. The `/finance/platform/dues` documentation is corrected in this change set.
3. Re-run the date-semantics suite and the full backend/Playwright evidence after any fix.
4. Do not start Phase 5B, deployment, provider integration, real-gym pilot or release until separately authorized.
5. A LOCAL GO, if later achieved, still would not authorize production, real-money operations, real-gym onboarding or public release.

---

**Final decision: LOCAL NO-GO.** The local release candidate is not authorized for LOCAL GO because the approved 100% financial-report date-semantics criterion is not met. All other assessed gates pass or are explicitly partial with no confirmed Critical/High defect.
