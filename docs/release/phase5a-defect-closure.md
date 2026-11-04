# Phase 5A.6 — Critical/High Defect Closure

**Date:** 2026-11-05
**Branch:** `feat/ascora-finance`
**Scope:** Local-only closure of Phase 5A.5 High findings and the carried 5A.4 integrity evidence gaps
**Status:** **PASS — LOCAL GO for 5A.6** (see independent verification and unresolved limitations)

## 1. Constraints

- Local PostgreSQL, FastAPI backend, Vite frontend, Playwright and Docker Compose.
- Synthetic, disposable data only; no real financial data.
- No deployment, Vercel/Neon change, provider integration or merge to `main`.
- One authorized narrow exception to the no-new-features rule: F-5A5-H6,
  the already-approved multi-gym platform billing UI.
- No 5A.7 work started.
- All 92 decisions and ADD-01 remain in force; deferred items #18/#30/#46
  remain deferred and #42/#61/#90 remain Partial where previously recorded.

## 2. Defect-closure matrix

| ID | Phase | Severity | Finding | Disposition | Evidence |
|---|---|---|---|---|---|
| F-5A5-H1 | 5A.5 | High | Finance Staff customer picker called an admin-only endpoint and was empty. | **Fixed** | `GET /api/v1/finance/customers`, client regeneration, backend boundary test and Playwright customer-option test |
| F-5A5-H2 | 5A.5 | High | Gym dashboard summary cards ignored the Toman display unit and showed raw IRR. | **Fixed** | Summary cards use the configured unit and label; `finance-dashboard.spec.ts` Toman regression |
| F-5A5-H3 | 5A.5 | High | Platform money fields saved `0` for Persian-digit input. | **Fixed** | `normalizeDigits` on plan/version/agreement/percent/cost/payment; Playwright Persian-digit assertions |
| F-5A5-H4 | 5A.5 | High | Platform date fields were Gregorian text inputs and accepted Jalali years as Gregorian. | **Fixed** | Agreement/version/cost dates use the shared Jalali `DateField`; version default is the next day; Playwright Jalali selection |
| F-5A5-H5 | 5A.5 | High | Accounting-period close was irreversible with no confirmation. | **Fixed** | Confirmation dialog with irreversible-action warning; Playwright opens and cancels it |
| F-5A5-H6 | 5A.5 | High | Superuser could not manage multi-gym groups, allocations, volume discounts, consolidated group invoices or subscription accrual from the UI. | **Fixed (authorized exception)** | New group member editor, group list/edit, allocation and discount validation, accrual dialog, gym/group invoice scope and consolidated invoice inspection; two-gym Playwright acceptance with exact accounting assertions |

### H6 implementation details

- **Groups.** Create and edit groups with two or more gyms, per-gym
  allocation percentages, duplicate-gym detection and a 100% allocation
  validation. The group list shows member gyms and allocations and exposes
  an edit action. Edits use the existing replace-members API.
- **Volume discount.** Agreement creation exposes an approved percentage
  field and validates 0–100%; it sends `volume_discount_bp` to the existing
  API. No new business rule was introduced.
- **Accrual.** Effective subscription/hybrid/custom agreements expose the
  existing accrual action with a Gregorian period (`YYYY-MM`) and, for group
  agreements, a branch selector including “all branches”. The UI loops the
  existing per-branch accrual API. The default period is the earliest valid
  period for the agreement: its `effective_from` month when the start date is
  the 1st, otherwise the following month. This prevents the default-dated
  agreement from failing with `platform_period_outside_agreement`.
- **Consolidated invoice.** Invoice creation supports gym or group scope,
  period start/end and due date, uses the existing group invoice API, and
  displays group scope, period, due date, discount and per-gym gross,
  discount, amount, paid and balance.
- **No redesign.** The existing platform finance tabs, dialogs, cards and
  shared components were reused.

### H6 acceptance evidence

`frontend/tests/platform-group-billing.spec.ts` uses two fresh synthetic gyms
and proves:

1. A two-gym group is created with 70/30 allocations; a 70/20 sum is rejected
   with a visible validation error.
2. The group is edited to 60/40.
3. A group subscription agreement of `1,000,000` IRR is created with a 5%
   volume discount; 120% is rejected with a visible validation error.
4. Both branches are accrued for the current month through the UI.
5. A consolidated group invoice is issued and inspected.
6. Exact invoice facts:
   - total discount `50,000`; total `950,000`;
   - gym A: gross `600,000`, discount `30,000`, amount `570,000`;
   - gym B: gross `400,000`, discount `20,000`, amount `380,000`.
7. Exact API accounting facts:
   - the same invoice/line amounts and discount;
   - per-gym platform report recognized revenue and receivable of `570,000`
     and `380,000`.

### Independent-review findings closed during the fix pass

| ID | Finding | Fix and regression |
|---|---|---|
| IR-H1 | The default accrual flow was invalid: a new agreement defaults to today, while the accrual dialog defaulted to the current Gregorian month, whose first day is before today. The API returned `platform_period_outside_agreement` and the UI showed a generic error. | The accrual dialog now defaults to the earliest valid period for the agreement (`effective_from` month, or the next month when `effective_from` is after the 1st). Added a dedicated Playwright test that creates a default-dated agreement, activates it, asserts the default period, accrues successfully and verifies the exact `500,000` receivable. |
| IR-H2 | The H6 acceptance test selected the current Persian month start but accrued the current Gregorian month, so it could fail on dates when the Persian month starts after the Gregorian 1st. The carried 5A.5 superuser test had the same pattern. | Both tests now select the **previous** Persian month start, which is always before the current Gregorian month start, and the H6 test explicitly sets the accrual period to the current Gregorian month. The separate default-accrual test covers the non-backdated path. |

Also added translations for `platform_period_outside_agreement`,
`platform_group_effective`, `platform_group_allocation_invalid`,
`platform_volume_discount_invalid`, `platform_group_name_exists` and
`platform_invoice_empty`, and clarified the accrual period as Gregorian.

## 3. Carried 5A.4 integrity evidence

| Gap | Status | Evidence |
|---|---|---|
| Complete backup-count verification for all finance tables | **Closed** | `scripts/backup_compose.sh` writes a per-backup `finance-counts.txt` with all **28** finance tables; `verify_restore.py` compares the full list; the live restore passes the same file. The Docker drill also compares all **21** platform tables. |
| Concurrent cancellation/payment race | **Closed** | `test_concurrent_platform_cancellation_and_payment_are_serialized` — one request succeeds, the other returns `409`; exactly one of cancellation/payment rows and journals exists; invoice status is consistent. Stable across 5 consecutive runs. |
| Concurrent credit application/invoice issue race | **Closed** | `test_concurrent_credit_application_and_invoice_issue_are_serialized` — invoice issue always succeeds; credit application either applies after issue (`200`) or fails closed with `invoice_not_issued`; credit balance, invoice paid/balance and `ADVANCE_APPLIED` journal counts are consistent in both outcomes. Stable across 5 consecutive runs. |
| Post-migration immutability trigger | **Closed** | `test_platform_credit_immutability_trigger_survives_migration` inserts a platform credit, proves `platform_credit_immutable` is enabled (`tgenabled` `O`/`A`), proves `UPDATE` is rejected with `platform posted records are immutable`, and repeats after downgrade to `f1a2b3c4d5e6` and upgrade to head. |
| Historical reporting limitations | **Preserved — not resolved** | Legacy reporting-date backfill can differ from the ledger business date for pre-5A.3 rows; some historical coach payable/membership renewal metrics are not fully as-of. See `phase5a-reconciliation.md` and `phase5a-migration-recovery.md`. |

### Docker backup/restore drill

- Fresh local CI stack at migration head `a7b8c9d0e1f2`.
- **PASS**: verifier `ok:true`, no failures.
- Exact counts verified for all 28 finance tables and all 21 platform tables,
  including zero-count tables.
- Nonempty seeded finance/platform data restored with balanced journals,
  receipt/allocation consistency, credit balances, payment allocations and
  sequence checks.
- Live restore through `restore_compose.sh` passed and re-ran the verifier with
  the finance counts file.
- Measured duration: **305.05 seconds (~5 min 5 s)**, well under the 60-minute
  local threshold.

## 4. Finance customer endpoint isolation and least privilege

The `GET /api/v1/finance/customers` read model is reviewed and regression-tested:

- requires a resolved finance scope with `finance.view`;
- is gym-scoped through `X-Gym-ID`;
- a finance staff member in gym B receives `403 not_a_gym_member` when
  presenting gym A's context;
- coaches are denied (`403`);
- response rows contain exactly `user_id`, `email`, `full_name`, `roles` —
  no phone, membership ID, owner flag, operational fields or financial data;
- only active members of the requested gym are returned.

No production code change was needed beyond the 5A.5 endpoint; the new test
locks the boundary.

## 5. Verification evidence

| Check | Result |
|---|---|
| Migration tests (`-m migrations`) | **15 passed**; also 15 passed under `TZ=UTC` |
| Concurrency suite | **9 passed**; 5 consecutive runs passed; 9 passed under `TZ=UTC` |
| Finance staff boundary tests | **2 passed** |
| Full backend regression | **335 passed** |
| Playwright `ui-acceptance` project | **7 passed** |
| Full Playwright suite (fresh DB) | **148 passed, 3 skipped** |
| Frontend Biome | Clean |
| Frontend production build | Pass |
| Docker backup/restore drill | **PASS**, `ok:true`, 305.05 s |
| Ruff / Mypy | Clean / clean |

## 6. Medium/Low triage (recorded, not fixed)

These are not Critical/High blockers and are not general UI-polish work for 5A.6.

| ID | Severity | Finding | Rationale / disposition |
|---|---|---|---|
| F-5A5-M1 | Medium | Gym-admin platform billing labels payment history as `یادآوری‌ها`. | Read-only labeling defect; record for Phase 5B. |
| F-5A5-M2 | Low | Raw status/mode enums in the Persian UI. | Cosmetic; no financial or authorization impact. |
| F-5A5-M3 | Medium | Platform cost list, payment history, cancellation-reason display and `due_soon` reminders are not exposed. | Read-only visibility; H6 only authorized group billing. Record for Phase 5B. |
| F-5A5-M4 | Medium | Amount limits are supported only for opening balance; other permissions fail closed with `finance_amount_limit_not_supported`. | Deliberate security behavior; decisions #42/#90 remain Partial. |
| F-5A5-M5 | Medium | Coach/athlete finance pages hardcode Rial and ignore the gym display unit. | Not a required 5A.6 journey; record for Phase 5B. |
| F-5A5-M6 | Medium | Release workflow runs the backup drill after the full Playwright suite on a non-fresh stack. | Release-gate wiring, not local data safety; carried from 5A.4 for Phase 5B. |
| F-5A5-L1 | Low | Platform amounts use grouped Persian digits without an explicit unit. | Record for Phase 5B. |
| F-5A5-L2 | Low | Platform forms retain values after cancel; some failures use a generic snackbar. | Record for Phase 5B. |
| F-5A5-L3 | Low | Customer picker returns all active members without search/pagination and performs per-row role lookups. | Acceptable for local synthetic gyms; scale follow-up. |
| F-5A5-L4 | Low | Mutable reporting-date columns (`recognized_on`, `cancelled_on`, `applied_on`, period boundaries) are not covered by immutability triggers. | Documented residual risk from 5A.4; not a 5A.6 blocker. |

### Additional independent-review Medium/Low

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| IR-M1 | Medium | Group edit is offered for a group with an effective agreement; the API returns `409 platform_group_effective` with a generic error. | Record for Phase 5B; no data corruption. |
| IR-M2 | Medium | Some platform backend error codes beyond the H6 set still fall back to a generic message. | H6-relevant codes now have translations; record the remainder for Phase 5B. |
| IR-M3 | Medium | “All branches” accrual loops branch-by-branch and is not atomic; an error can leave earlier branches committed. Retry is idempotent. | Record; no transaction boundary introduced in 5A.6. |
| IR-M4 | Medium | A 0% group member is allowed, but accrual for that branch is rejected as unconfigured. | Record; the UI allows 0% because the existing API does. |
| IR-M5 | Medium | A consolidated group invoice includes every open/partial receivable for the group within the period, not only subscription receivables. | Existing 5A.2 behavior; record for Phase 5B preview/scope work. |
| IR-M6 | Medium | Backup counts are generated after `pg_dump`; on a writing stack the count file can drift from the dump. The drill uses an idle stack. | Record; no silent-pass risk in the drill. |
| IR-M7 | Medium | Groups/invoices query error states use fallback empty/loading behavior. | Record for Phase 5B. |
| IR-M8 | Low | H6 spec does not add a dedicated mobile viewport check; 5A.5 covers mobile for the role journeys. | Record; no responsive regression observed. |
| IR-M9 | Low | H6 spec does not assert the selected Gregorian effective date or the invoice period/due fields directly; exact amounts and API accounting are asserted. | Record; coverage is sufficient for the High findings. |

## 7. Unresolved LOCAL GO blockers

**None known after the fixes and evidence above**, with these explicit
qualifications:

- Historical reporting limitations remain documented limitations, not silently
  resolved.
- The release-workflow drill isolation issue remains a Phase 5B release-gate
  concern, outside the local-only scope.
- Medium/Low findings above remain recorded for Phase 5B; none is a confirmed
  Critical/High blocker for the 5A.6 local journeys.
- The independent review verdict is recorded below before the final commit.

## 8. Independent verification

A fresh-context independent reviewer ran the 5A.6 change set, the
`ui-acceptance` project, the concurrency/boundary suites, the migration tests,
frontend lint/build and inspected the backup/restore evidence.

- **Critical findings:** none.
- **High findings:** two, both fixed in the 5A.6 fix pass and recorded above
  (IR-H1 default accrual, IR-H2 calendar-dependent date selection).
- **Confirmed safe:** group allocation math and editing, volume-discount
  calculation, consolidated invoice math, per-gym report accounting,
  concurrency invariants, immutability trigger, all-finance/all-platform
  backup counts, customer endpoint boundaries and historical-limitation
  preservation.
- **Residual Medium/Low items:** recorded in section 6; none is a confirmed
  Critical/High blocker for the 5A.6 local scope.

**Final verdict: PASS — LOCAL GO for 5A.6.** No Critical/High blocker remains
open. Historical reporting limitations, mutable reporting-date columns, the
release-workflow drill-isolation concern and the recorded Medium/Low findings
remain open for Phase 5B and are not silently marked resolved.
