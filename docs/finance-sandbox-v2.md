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
- Frontend dev also uses a git-ignored `frontend/.env` with
  `VITE_API_URL=http://localhost:8010`; the Vite server proxies `/api` to the
  same local backend.
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
- A gym-specific contract fully replaces the default for that gym; when no current gym contract exists (or it is archived), the default applies.
- Every saved contract is active immediately; there is no separate draft/activation step.
- Each save or edit creates a new version and archives the previous current contract. Only one active default and one active contract per gym are allowed.
- All three category rates are required. Saved contracts report their source (`PLATFORM_DEFAULT` or `GYM_OVERRIDE`).
- All contracts, including archived versions, can be edited; editing creates a new current version.

### Coach contracts

- Per gym, coach and sales category (`NUTRITION`, `TRAINING`). Membership is not a coach category.
- Platform percentage is resolved server-side, displayed read-only, and revalidated on save and sale creation.
- Gym and coach percentages are gym-admin controlled.
- Saving or editing activates the contract immediately and archives the previous active version for the same gym, coach and category.
- Exact 100% allocation is enforced in the backend database/service and in the form.
- Coach must be an active `COACH` member of the same gym.
- When a platform contract changes, active coach contracts are automatically versioned: the coach share stays fixed and the gym share absorbs the difference. A platform change that would make the gym share negative is rejected until the coach contract is adjusted.

### Coach sales plans

- A plan is independent of the financial contract and stores title, description, base price and active status.
- Each coach has at most one active training plan per gym, enforced by a partial unique index.
- The coach and gym administrators can manage plans. Coaches only manage their own plans.
- Prices are base amounts in IRR; active VAT is added at purchase time.
- Editing or deactivating a plan never changes previous purchases or their sale snapshots.
- Nutrition plans are intentionally left for the future nutrition-coach feature; only `TRAINING` is currently available.

### Athlete plan purchase and program request

- An athlete sees only the active training plan of their current coach in the same gym.
- The offer shows base price, tax, total and projected platform/gym/coach shares.
- A simulated payment success creates exactly one program request and one purchase snapshot; a failed/cancelled payment creates none.
- Payment idempotency keys prevent duplicate purchases and duplicate requests.
- The athlete can list their requests; the coach can list their own requests; gym admins can list all requests for the gym.
- The request is the hand-off to the coach. Program construction remains a coach task based on the athlete profile.
- Membership sales are club-only: no coach, no coach share and no coach contract. They are accessed from the gym details page.

### Program origins and purchase gating

- Program versions record their origin separately from draft/active/archived status:
  - `PURCHASED`: created from a paid program request.
  - `FREE`: explicitly created as a tracked free exception with a reason.
  - `LEGACY`: pre-existing history from before this feature.
- New programs are always classified as `PURCHASED` or `FREE`; the `LEGACY` value is reserved for rows that existed before this feature.
- When a coach has an active sales plan, creating a program requires either a paid request or a recorded free reason; otherwise the API returns `program_purchase_required`.
- When no sales plan exists, new programs are still recorded as `FREE` with an automatic system reason, so no new untracked program can bypass the origin distinction.
- Creating a copy/new draft is subject to the same rule, so copying cannot bypass payment.
- One successful purchase can be consumed by exactly one program version. Editing that version is allowed without another purchase; a new independent version requires a new purchase or free exception.

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
| Full backend suite (dedicated `_test` DB) | **181 passed** |
| Migration suite | **4 passed**; also **4 passed** under `TZ=UTC` |
| Backend lint (Ruff) | Clean |
| Backend types (Mypy) | Clean (45 source files) |
| Finance browser journey | **5 passed** (admin, mobile/RTL, global admin, coach plan purchase/request) |
| Full Playwright suite | **115 passed, 18 skipped** |
| Frontend lint | Clean |
| Frontend build | Passed |

The mobile-admin archive action helper now dispatches the menu action directly, avoiding a Playwright auto-scroll that closed the fixed menu and caused the previous flaky focus behavior.

## 7. Limitations

- Test/simulation only; no real payment provider, bank API, settlement rail, tax filing or remittance.
- No partial payment; one successful simulated payment covers the full sale.
- A refund is blocked while a settlement is pending; complete or cancel the pending settlement first.
- Platform has no closed-period lock; the implementation does not add one.
- Contract uniqueness is enforced by partial unique indexes for the active default, active gym contract and active coach contract. Overlap windows are no longer used because a new save replaces the current contract.
- Only training plans are sold in this iteration; the nutrition-coach feature and nutrition plan purchase flow are intentionally deferred.
- Purchasing creates the request; the coach still builds and publishes the personalized program manually from the athlete profile.
- Existing programs from before this feature are marked `LEGACY`; they are not retroactively treated as paid or free exceptions.
- The full superuser-context Playwright spec was not used as acceptance evidence because it exercises unrelated invitation email flows; the finance global-admin journey is covered by `finance-sandbox.spec.ts`.
- The work is committed locally and **not pushed**; no deployment, merge or production data is involved.

## 8. Persian guide for trying both journeys

### مدیر باشگاه (`ali@example.com`)

1. وارد <http://localhost:5180> شوید.
2. از منوی کنار صفحه، «مالی» را باز کنید.
3. «قراردادها و درصدها» را باز کنید. یک قرارداد جدید بسازید:
   - مربی را انتخاب کنید.
   - دسته فروش را انتخاب کنید؛ حق عضویت در قرارداد مربی وجود ندارد.
   - درصد پلتفرم را ببینید؛ این عدد خواندنی است و از قرارداد پلتفرم می‌آید.
   - درصد باشگاه و مربی را وارد کنید تا «درصد باقی‌مانده» صفر شود.
   - «ذخیره و اعمال فوری» را بزنید؛ قرارداد بلافاصله فعال می‌شود. برای تغییر، «ویرایش» را بزنید.
4. «فروش و پرداخت‌ها» را باز کنید و «فروش جدید» را بزنید:
   - دسته، توضیح و مبلغ پایه به تومان را وارد کنید.
   - مالیات پیش‌فرض را انتخاب کنید.
   - برای برنامه تمرینی/تغذیه مربی را انتخاب کنید؛ برای حق عضویت مربی وجود ندارد.
   - «محاسبه پیش‌نمایش» را بزنید و سهم پلتفرم، باشگاه و مربی را ببینید.
   - «ثبت فروش» و سپس «پرداخت موفق» را بزنید. سهم‌ها ایجاد می‌شوند.
5. «تسویه‌ها» را باز کنید:
   - «درخواست تسویه» بسازید؛ وضعیت «در انتظار تسویه» است.
   - «تکمیل تسویه» را بزنید تا تسویه شبیه‌سازی‌شده کامل شود.
6. «گزارش‌ها» را باز کنید؛ فعالیت دوره و مانده تا تاریخ را ببینید و «خروجی CSV» بگیرید.
7. در «جزئیات باشگاه»، کارت «حق عضویت باشگاه» را ببینید؛ فروش عضویت از همان‌جا آغاز می‌شود و سهم مربی ندارد.

### مربی و مدیر پلن (`reza@example.com` یا `ali@example.com`)

1. «پلن و درخواست‌ها» را باز کنید.
2. «پلن جدید» را بزنید؛ عنوان، توضیحات، قیمت پایه به تومان و وضعیت را وارد کنید.
3. با فعال‌کردن پلن جدید، پلن فعال قبلی همان مربی در همان باشگاه غیرفعال می‌شود.
4. پس از خرید ورزشکار، درخواست در جدول پایین دیده می‌شود. برای ساخت برنامه، از «ورزشکاران» پروندهٔ ورزشکار را باز کنید و در «ساخت برنامه» درخواست خرید را انتخاب کنید. اگر برنامه رایگان است، دلیل آن را ثبت کنید.

### ورزشکار (`nima@example.com`)

1. «برنامه من» را باز کنید.
2. کارت «پلن تمرینی مربی» قیمت پایه، مالیات و مبلغ نهایی را نشان می‌دهد.
3. «خرید و ارسال درخواست» را بزنید، توضیح خود را بنویسید و پرداخت آزمایشی را تأیید کنید.
4. فقط پس از پرداخت موفق، درخواست در «درخواست‌های من» و برای مربی ثبت می‌شود.
5. ساخت و تحویل برنامه توسط مربی انجام می‌شود؛ برنامه‌های خریداری‌شده و رایگان در سوابق با منشأ جداگانه مشخص می‌شوند.

### مدیر سراسری (`finance-sandbox-admin@example.com`)

1. وارد <http://localhost:5180> شوید.
2. «مالی» را باز کنید و نمای کلی سراسری و مقایسه باشگاه‌ها را ببینید.
3. «قراردادهای پلتفرم» را باز کنید:
   - قرارداد پیش‌فرض یا اختصاصی باشگاه بسازید.
   - درصد هر سه دسته را وارد کنید و «ذخیره و اعمال» را بزنید؛ قرارداد بلافاصله جایگزین قرارداد جاری همان دامنه/باشگاه می‌شود.
   - برای هر ردیف، از «ویرایش» می‌توانید نسخه جدید بسازید؛ نسخه قبلی در سوابق می‌ماند.
4. «مالیات‌ها» را باز کنید؛ مالیات پیش‌فرض یا مالیات ثابت/درصدی جدید اضافه کنید.
5. «گزارش‌ها» را باز کنید؛ باشگاه، دسته و بازه تاریخ را فیلتر کنید و CSV بگیرید.

همه پرداخت‌ها و تسویه‌ها شبیه‌سازی‌شده‌اند؛ هیچ پول واقعی جابه‌جا نمی‌شود.
