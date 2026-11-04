# Phase 5A.5 — Local UI/UX Acceptance by Role

**Date:** 2026-11-05
**Branch:** `feat/ascora-finance`
**Scope:** Local-only UI/UX acceptance with synthetic data
**Status:** **CONDITIONAL PASS — implemented role journeys pass; one High platform-group gap deferred to 5A.6**

## 1. Environment and constraints

- Local PostgreSQL, FastAPI backend, Vite frontend and Playwright.
- Synthetic, disposable data only; no real financial data.
- No deployment, Vercel/Neon change, provider integration or merge to `main`.
- Desktop Chrome plus mobile viewports used by the existing suite, including
  `390×844` and the configured Pixel 5 project.
- Persian RTL, Jalali dates and Persian monetary formatting were exercised.
- Fixes were restricted to confirmed Critical/High blockers; no redesign or new
  product feature was added.

## 2. Role-by-role acceptance matrix

| Role | Required journey | Result | Evidence |
|---|---|---|---|
| Superuser | Platform overview, plans/versions, groups, agreements, invoices/lines, partial payment, cancellation reason, costs, dues/reminders, CSV export | **PASS for single-gym plans/agreements/invoices; group consolidation deferred** | `frontend/tests/role-ui-acceptance.spec.ts` — creates a plan and a replacement version, activates it, creates a group and subscription agreement, accrues a receivable, issues two invoices, records a partial payment, validates the cancellation-reason minimum and cancels the second invoice, records a platform cost, checks in-app-only reminders and downloads `platform.csv`. Multi-gym groups, volume discounts and consolidated group invoices are not exposed in the UI (H6) |
| Gym Admin | Finance dashboard, invoices, receipts, refunds, memberships, platform billing read-only view, CSV export | **PASS** | `finance-dashboard.spec.ts`, `finance.spec.ts`, `finance-phase2.spec.ts`; new `role-ui-acceptance.spec.ts` verifies dashboard metrics, invoice validation, platform billing read-only behavior, grant-dialog limits, `finance.csv` and mobile layout |
| Finance Staff | Permitted finance actions, amount-limit behavior, denied operational areas, read/export | **PASS** | New staff fixture and grants through the admin API; staff sees only Dashboard/Finance, cannot open members or admin/grant endpoints, cannot add a coach agreement without a grant, can select customers for granted invoice/payment/refund/membership actions, records an expense, and downloads `finance.csv`. Unsupported non-opening amount limits are rejected with `finance_amount_limit_not_supported` |
| Coach | Own earnings, vesting, settlements, cross-gym isolation | **PASS** | Existing `coach-finance.spec.ts` covers calculated/vested/settled earnings; new spec verifies own-only earnings, denial of gym finance, denial of the admin coach-earnings listing, and `not_a_gym_member` for another gym |
| Athlete | Own bills, receipts, installments, memberships, refund request | **PASS** | Existing `athlete-finance.spec.ts` now creates an invoice with two equal installments and verifies the athlete sees them alongside bills, receipts, membership and a refund request; new spec verifies personal finance only, denial of gym finance and coach endpoints, and mobile layout |

## 3. Cross-cutting checks

| Check | Result | Evidence |
|---|---|---|
| Navigation and end-to-end interactions | **PASS** | Every role reached its permitted workspace; direct navigation to forbidden areas redirected to the club dashboard |
| Authorization and access denial | **PASS** | Staff members list `403 gym_admin_required`; staff grants write `403`; coach finance listing `403 finance_access_denied`; athlete coach earnings `403 coach_access_required`; cross-gym coach context `403 not_a_gym_member` |
| Visibility boundaries | **PASS** | Staff nav excludes members/athletes; coach nav excludes finance; athlete nav excludes staff finance; gym-admin platform billing has no payment button |
| Desktop viewport | **PASS** | `ui-acceptance` Desktop Chrome project |
| Mobile viewport | **PASS** | New specs resize to `390×844` and assert no horizontal overflow; existing Pixel 5 athlete/coach/admin suites pass |
| Persian RTL | **PASS** | `html[dir="rtl"]` asserted for superuser, gym admin, finance staff, coach and athlete journeys |
| Jalali dates | **PASS** | Platform agreement/version/cost dates use the shared Jalali `DateField`; rendered agreement dates and athlete invoice dates show Persian-calendar dates |
| Monetary formatting | **PASS** | Persian-digit input and grouping asserted for plans, agreements, payments and expenses; the gym dashboard summary cards now follow the configured Toman/Rial unit with an explicit label |
| Dialogs and validation | **PASS** | New plan/version/group/agreement/invoice/payment/cancel/cost dialogs complete; empty invoice customer shows `مشتری را انتخاب کنید`; cancellation confirmation stays disabled until the reason is at least 3 characters; period close requires an explicit irreversible-action confirmation |
| Error feedback | **PASS** | API errors are surfaced through the existing snackbar/inline error patterns; permission denials are visible and do not leave the UI in a submitting state |

## 4. Automated evidence

| Check | Result |
|---|---|
| Initial full Playwright baseline | **140 passed, 3 skipped** |
| New `ui-acceptance` project | **5 passed** |
| Full Playwright suite after 5A.5 changes | **146 passed, 3 skipped** |
| Frontend Biome check | Clean |
| Frontend production build | Pass |
| Backend finance staff/grants/receipts/invoices regression | **34 passed** |
| Backend full regression | **331 passed** |

Screenshots are attached to the Playwright report for each role on desktop and
mobile (`superuser-platform-finance`, `gym-admin-finance`,
`finance-staff-boundaries`, `coach-earnings`, `athlete-finance`).

## 5. Findings

### Critical

None confirmed.

### High — fixed

| ID | Finding | Resolution and regression |
|---|---|---|
| F-5A5-H1 | Finance Staff with granted invoice/payment/refund/membership actions received an empty customer picker. The shared hook called the admin-only `GET /gyms/{gym_id}/members`, which returns `403 gym_admin_required` for `FINANCE_STAFF`; the actions were visible but not completable. | Added a narrow `GET /api/v1/finance/customers` read model (finance view required, active gym members only, identity/roles only), regenerated the client, switched the shared finance hook to it, and added a backend boundary assertion plus a Playwright customer-option/expense/export assertion. |
| F-5A5-H2 | Gym dashboard summary cards used `formatNumber` on raw IRR and ignored the configured display unit. With Toman selected, six headline amounts appeared 10× too large without a unit. | Changed the six summary cards to use the configured unit and append the unit label. Added `finance-dashboard.spec.ts` coverage that switches to Toman, asserts the card shows `تومان`, and restores Rial. |
| F-5A5-H3 | Platform money fields used raw `Number(value)`, so Persian-digit input saved `0` with a success message. | Normalized Persian/Arabic digits through `normalizeDigits` before parsing plan price, plan-version price, agreement amount/percent, cost and payment amounts. The superuser journey now enters Persian digits and asserts the saved Persian-grouped amount. |
| F-5A5-H4 | Platform agreement/version/cost date fields were plain Gregorian text inputs and accepted a Jalali year as a Gregorian year. | Replaced the three editable platform dates with the shared Jalali `DateField` picker, defaulted replacement versions to the next day, and updated the superuser journey to select the month start from the Jalali calendar. |
| F-5A5-H5 | Closing an accounting period was a single click with no confirmation and no reopen path. | Added a confirmation dialog that states the close is irreversible and requires an explicit confirmation. The gym-admin journey opens the dialog and cancels it without closing the live period. |

### High — open, deferred to 5A.6

| ID | Finding | Why it is not fixed in 5A.5 |
|---|---|---|
| F-5A5-H6 | Superuser platform billing is not end-to-end for multi-gym groups: the UI can create a one-gym group and group agreement, but cannot add a second gym/allocation, set a volume discount, or issue a consolidated group invoice. Subscription receivables also require the API accrual action before the UI invoice flow. | Closing this requires new UI workflows (group membership/allocation editor, volume-discount input, consolidated invoice form, accrual action). That is a feature addition, which the 5A.5 constraint explicitly forbids. The underlying APIs and 5A.2 acceptance exist; the gap is UI exposure. It is recorded for 5A.6/Phase 5B and is the reason the 5A.5 verdict is conditional rather than a full LOCAL GO for consolidated group billing. |

### Medium / Low (recorded, not fixed in 5A.5)

| ID | Finding | Severity | Decision |
|---|---|---|---|
| F-5A5-M1 | Gym-admin platform billing labels the payment-history list as `یادآوری‌ها` (reminders). The rows are platform payments, not reminders. | Medium | Record for 5A.6 triage; the required gym-admin read-only journey still completes. |
| F-5A5-M2 | Platform plan/agreement/status values are shown as raw enums (`DRAFT`, `ACTIVE`, `SUBSCRIPTION`) rather than localized labels. | Low | Cosmetic; no financial or authorization impact. |
| F-5A5-M3 | The platform page has no visible group list, cancellation-reason display, cost list or payment history; platform invoice cards omit gym/due dates. | Medium | Read-only visibility gaps; record for 5A.6 triage. |
| F-5A5-M4 | Platform reminders render only `overdue`, not API `due_soon` items. | Medium | Record; gym-admin and superuser in-app reminder scope is visible. |
| F-5A5-M5 | Amount limits are intentionally supported only for `finance.opening.manage`; other permissions reject a limit with `finance_amount_limit_not_supported`. | Medium (known Partial) | Deliberate fail-closed behavior recorded in the security audit; decisions #42/#90 remain Partial. |
| F-5A5-M6 | Coach and athlete finance pages hardcode `RIAL` rather than the gym display setting. | Medium | Record; no cross-role data exposure. |
| F-5A5-L1 | Platform amounts use grouped Persian numbers without an explicit currency unit on the platform page. | Low | Record; gym finance shows the configured unit. |
| F-5A5-L2 | Platform forms retain values after cancel; a user may see a generic snackbar rather than an inline field error for some version/cost failures. | Low | Record for 5A.6 polish. |
| F-5A5-L3 | The new customer picker returns all active members without search/pagination and performs per-row role lookups. | Low | Fine for local synthetic gyms; record for scale follow-up. |

## 6. Carried-forward 5A.4 evidence items

These remain **open** and are not resolved or reclassified by 5A.5:

- Full finance backup-count verification (the verifier reports all finance
  counts but does not compare every finance table to a backup count file).
- Concurrent invoice cancellation + payment and concurrent credit application
  + invoice issue race tests.
- Post-migration immutability-trigger verification.
- Historical reporting limitations: legacy reporting-date backfill can differ
  from the ledger business date, and some historical coach/membership metrics
  are not fully as-of.

Also carried: release-workflow drill isolation, mutable reporting-date columns
by direct SQL, and partial concurrency/assertion coverage documented in
`docs/release/phase5a-migration-recovery.md`.

## 7. Remaining limitations

- UI acceptance uses current synthetic data, not a production-sized or
  historical dataset.
- The new Playwright specs create synthetic plans, gyms, agreements, invoices,
  staff users and grants; they are not a data-migration or deployment test.
- The platform invoice journey uses the documented subscription-accrual endpoint
  to create receivables before exercising the UI invoice flow; there is no
  scheduler in the local stack. The UI has no accrual control (part of H6).
- Multi-gym groups, volume discounts and consolidated group invoices are not
  exposed in the UI. They remain an open High product-scope gap (H6) and were
  not implemented because 5A.5 forbids new features.
- The finance-staff customer picker is a flat active-member list without search
  or pagination; this is adequate for local synthetic gyms but not proven at
  scale.
- No claim is made that every endpoint, every amount edge case or every
  historical reporting view is covered by UI automation.
- No 5A.6 or 5A.7 work has started.

## 8. Verdict

**5A.5: conditional PASS for the implemented role journeys; not a full LOCAL GO
for consolidated platform-group billing.**

- All implemented role journeys complete locally: Superuser single-gym plans,
  versions, groups, agreements, invoices, payments, cancellation, costs,
  reminders and export; Gym Admin dashboard, invoices, receipts, refunds,
  memberships, platform billing and export; Finance Staff granted actions,
  boundaries and export; Coach own earnings and isolation; Athlete personal
  finance, installments, receipts, membership and refund request.
- No role sees another role's financial data.
- Desktop/mobile, Persian RTL, Jalali dates and monetary formatting are
  evidenced, including the dashboard display-unit regression.
- Five confirmed High UI defects (H1–H5) are fixed with focused regression
  coverage.
- One confirmed High gap (H6 — multi-gym group consolidation, volume discount
  and consolidated invoices) requires new UI features and is deferred to 5A.6.
  Medium/Low findings and all 5A.4 evidence gaps remain open for triage before
  the final LOCAL GO/NO-GO and Phase 5B.
