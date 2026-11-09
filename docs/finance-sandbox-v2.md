# Finance Sandbox V2 — Local Test Implementation

**Date:** 2026-11-09
**Branch:** `codex/finance-sandbox-v2`
**Worktree:** `/Users/sajad/.local/share/opencode/worktree/886215/finance-sandbox-v2`
**Base:** `origin/main` (`f3b37bc`)
**Status:** Local test implementation only; not deployed, merged or pushed.

## 1. Isolation

- Dedicated PostgreSQL databases on `127.0.0.1:5432`:
  - `gym_finance_sandbox_v2`
  - `gym_finance_sandbox_v2_test`
- No existing database (`gym_dev`, `gym_stage`, `gym_test`, `gym_app`, Neon or others) was migrated, seeded or reset.
- Local configuration: `.env.finance-sandbox` (git-ignored).
- Local URLs:
  - UI: <http://localhost:5180>
  - API: <http://127.0.0.1:8010>
- The backend port `8010` and frontend port `5180` are dedicated to this sandbox.
- The pre-existing finance branch was inspected only for context; this implementation is independent and based on `origin/main`.

## 2. Access control

- **Global Administrator** (`is_superuser`): all gyms, platform contracts, taxes, cross-gym reports and all gym-scoped finance routes.
- **Gym Administrator** (gym owner or `GYM_ADMIN`): own-gym coach contracts, sales, payments, settlements, refunds, taxes (read-only) and reports.
- Coaches and athletes have no finance access.
- Every finance route checks either superuser status or own-gym admin membership on the backend. Gym isolation is not enforced only in the UI.
- Gym path IDs and report `gym_id` values are checked server-side.

## 3. Implemented domain

### Platform contracts

- Default rates per category (`MEMBERSHIP`, `NUTRITION`, `TRAINING`).
- Gym-specific overrides, with per-category fallback to the default.
- Effective dates, versions, draft/active/archived status.
- Overlapping active contracts are rejected.
- Effective platform percentage reports its source (`PLATFORM_DEFAULT` or `GYM_OVERRIDE`).

### Coach contracts

- Per gym, coach and sales category.
- Platform percentage is resolved server-side, displayed read-only, and revalidated on creation/activation and sale creation.
- Gym and coach percentages are gym-admin controlled.
- Exact 100% allocation is enforced in the backend database/service and in the form.
- Coach must be an active `COACH` member of the same gym.
- Sales reject a stale contract when the current platform policy no longer matches it; a successor contract is required.

### Sales, taxes and allocation

- Categories: gym membership, nutrition program, training program.
- Named taxes: percentage or fixed amount, active/inactive, explicitly selected per sale.
- Default VAT: `Value-added tax`, 10%, seeded by migration.
- Taxes apply to the base selling amount and never compound on each other.
- All party shares are calculated from the final amount paid by the athlete, including taxes.
- Integer IRR storage; basis points for percentages.
- Deterministic rounding: platform and coach use integer division; gym receives the residual. Shares always sum exactly to the payment.

Approved example:

| Item | Amount |
|---|---:|
| Base selling amount | 1,000,000 IRR |
| VAT 10% | 100,000 IRR |
| Athlete pays | 1,100,000 IRR |
| Platform 10% | 110,000 IRR |
| Gym 40% | 440,000 IRR |
| Coach 50% | 550,000 IRR |

### Simulated payments

- Clearly labelled test gateway; no banking/provider integration.
- Outcomes: success, failure, cancellation and retry.
- Only successful payments create platform/gym/coach allocations.
- Idempotency keys prevent duplicate payments and allocations.
- Row locks and unique constraints handle concurrent submissions.
- Failed/cancelled payments leave the sale awaiting payment and create no payable balances.

### Simulated settlements

- Calculated allocations, pending settlements and completed simulated settlements are separate.
- A settlement request creates a `PENDING` settlement; completion is a separate explicit action.
- Completion never happens merely because a settlement was requested.
- Over-amount requests are rejected.
- Automatic simulated settlement path creates and completes eligible settlements.
- Cancelled pending settlements release their reserved allocations.

### Simulated refunds

- Full and partial refunds.
- Refunds follow the original payment allocation snapshot.
- Refund beyond the remaining amount is rejected.
- Refunds after a completed settlement create linked settlement-adjustment rows; completed settlement records are never rewritten.
- Refund idempotency keys prevent duplicates.
- Sale status becomes partially/fully refunded.

### Reporting and audit

- Period activity: base sales, taxes, athlete payments, platform/gym/coach shares, refunds, completed settlements.
- As-of balances: unsettled platform/gym/coach shares, pending settlements, completed settlements.
- Explicit date range, optional category and gym filter (global admin), CSV export.
- Same aggregation logic for dashboard, reports and CSV.
- `finance_audit` records actor, gym, action, entity and time for significant actions.
- Sales retain contract IDs, percentage snapshot, tax snapshot and payment allocation history.

## 4. API surface

- `GET/POST /api/v1/finance/platform-contracts`, activate/archive
- `GET /api/v1/finance/platform-policy`
- `GET/POST/PATCH /api/v1/finance/taxes`
- `GET/POST /api/v1/finance/gyms/{gym_id}/coach-contracts`, activate/archive
- `GET /api/v1/finance/gyms/{gym_id}/coaches`
- `POST /api/v1/finance/gyms/{gym_id}/sales/preview`
- `GET/POST /api/v1/finance/gyms/{gym_id}/sales`
- `POST /api/v1/finance/gyms/{gym_id}/sales/{sale_id}/payments`
- `GET /api/v1/finance/gyms/{gym_id}/payments`
- `POST /api/v1/finance/gyms/{gym_id}/payments/{payment_id}/refunds`
- `GET/POST /api/v1/finance/gyms/{gym_id}/settlements`, complete/cancel/auto
- `GET /api/v1/finance/overview`
- `GET /api/v1/finance/reports`
- `GET /api/v1/finance/reports/export`
- `GET /api/v1/finance/gyms/{gym_id}/audit`

## 5. UI

- Persian-first RTL UI using the existing M3 design system.
- Role-adaptive navigation: `مالی` for global and gym administrators only.
- Separate screens:
  - نمای کلی
  - قراردادها و درصدها
  - فروش و پرداخت‌ها
  - مالیات‌ها
  - تسویه‌ها
  - گزارش‌ها
- Superuser-only platform contract and tax administration.
- Money fields visibly use `تومان`; stored values remain IRR.
- Validation messages appear next to fields; the contract form shows the remaining percentage live and disables save unless the total is exactly 100%.
- Payment/settlement simulation is explicitly labelled.
- Loading, empty, error, success and permission-redirect states are present.
- Desktop and mobile layouts avoid page-level horizontal overflow.

## 6. Verification actually run

| Check | Result |
|---|---|
| Full backend suite (dedicated `_test` DB) | **170 passed** in 88.93 s |
| Migration suite | **4 passed**; also **4 passed** under `TZ=UTC` |
| Backend lint (Ruff) | Clean |
| Backend types (Mypy) | Clean (45 source files) |
| Finance browser journey | **4 passed** (admin, mobile/RTL, global admin) |
| Full Playwright suite | **113 passed, 18 skipped**, one known mobile-admin archive-menu flake; it passed on immediate retry |
| Frontend lint | Clean |
| Frontend build | Passed |

The mobile-admin archive flake is pre-existing test instability in the archive row menu, not a finance regression. No finance test failed.

## 7. Limitations

- Test/simulation only; no real payment provider, bank API, settlement rail, tax filing or remittance.
- No partial payment; one successful simulated payment covers the full sale.
- A refund is blocked while a settlement is pending; complete or cancel the pending settlement first.
- Platform has no closed-period lock; the implementation does not add one.
- Contract overlap is validated by the service, not a database exclusion constraint.
- The full superuser-context Playwright spec was not used as acceptance evidence because it exercises unrelated invitation email flows; the finance global-admin journey is covered by `finance-sandbox.spec.ts`.
- The work is committed locally and **not pushed**; no deployment, merge or production data is involved.

## 8. Persian guide for trying both journeys

### مدیر باشگاه (`ali@example.com`)

1. وارد <http://localhost:5180> شوید.
2. از منوی کنار صفحه، «مالی» را باز کنید.
3. «قراردادها و درصدها» را باز کنید. یک قرارداد جدید بسازید:
   - مربی را انتخاب کنید.
   - دسته فروش را انتخاب کنید.
   - درصد پلتفرم را ببینید؛ این عدد خواندنی است و از قرارداد پلتفرم می‌آید.
   - درصد باشگاه و مربی را وارد کنید تا «درصد باقی‌مانده» صفر شود.
   - ذخیره کنید و سپس قرارداد را فعال کنید.
4. «فروش و پرداخت‌ها» را باز کنید و «فروش جدید» را بزنید:
   - دسته، توضیح و مبلغ پایه به تومان را وارد کنید.
   - مالیات پیش‌فرض را انتخاب کنید.
   - مربی را انتخاب کنید.
   - «محاسبه پیش‌نمایش» را بزنید و سهم پلتفرم، باشگاه و مربی را ببینید.
   - «ثبت فروش» و سپس «پرداخت موفق» را بزنید. سهم‌ها ایجاد می‌شوند.
5. «تسویه‌ها» را باز کنید:
   - «درخواست تسویه» بسازید؛ وضعیت «در انتظار تسویه» است.
   - «تکمیل تسویه» را بزنید تا تسویه شبیه‌سازی‌شده کامل شود.
6. «گزارش‌ها» را باز کنید؛ فعالیت دوره و مانده تا تاریخ را ببینید و «خروجی CSV» بگیرید.

### مدیر سراسری (`finance-sandbox-admin@example.com`)

1. وارد <http://localhost:5180> شوید.
2. «مالی» را باز کنید و نمای کلی سراسری و مقایسه باشگاه‌ها را ببینید.
3. «قراردادهای پلتفرم» را باز کنید:
   - قرارداد پیش‌فرض یا اختصاصی باشگاه بسازید.
   - درصد هر دسته را وارد کنید، پیش‌نویس را ذخیره و سپس فعال کنید.
4. «مالیات‌ها» را باز کنید؛ مالیات پیش‌فرض یا مالیات ثابت/درصدی جدید اضافه کنید.
5. «گزارش‌ها» را باز کنید؛ باشگاه، دسته و بازه تاریخ را فیلتر کنید و CSV بگیرید.

همه پرداخت‌ها و تسویه‌ها شبیه‌سازی‌شده‌اند؛ هیچ پول واقعی جابه‌جا نمی‌شود.
