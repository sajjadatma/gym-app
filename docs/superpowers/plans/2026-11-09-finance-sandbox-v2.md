# Finance Sandbox V2 — Focused Implementation Plan

**Goal:** Add an isolated, test-only financial subsystem to the existing multi-gym platform: platform/gym/coach contracts, taxes, simulated split payments, settlements, refunds, reporting and auditability.

**Branch/worktree:** `codex/finance-sandbox-v2` at `/Users/sajad/.local/share/opencode/worktree/886215/finance-sandbox-v2`
**Base:** `origin/main` (`f3b37bc`)
**Databases:** `gym_finance_sandbox_v2`, `gym_finance_sandbox_v2_test` on `127.0.0.1:5432`
**Ports:** API `8010`, UI `5180`

## Constraints

- Local synthetic data only; no deployment, merge, push, providers or real money.
- Preserve existing auth, roles, athlete/coach features and design system.
- Backend authorization on every financial endpoint.
- Exact basis-point arithmetic; allocations always sum to the athlete payment.
- Historical snapshots are immutable; settlements and completed records are never rewritten.
- Persian RTL UI, clear non-accounting language, visible units.

## Tasks

1. **Models and migration**
   - Add `backend/app/finance_models.py` and register it from `app.models`.
   - Tables: platform contracts/rates, tax definitions, coach contracts, sales/taxes, payments, allocations, settlements/items, refunds/adjustments, audit.
   - Add one Alembic migration with constraints and default VAT seed.
2. **Services**
   - Platform policy resolution/overlap checks.
   - Coach contract validation and platform-percentage matching.
   - Sale preview/create with tax and allocation snapshots.
   - Simulated payments, idempotency and row locks.
   - Settlements pending/completed/cancelled and auto-settle.
   - Refunds with allocation snapshots and settlement adjustment links.
   - Report aggregation + CSV data.
3. **Routes and permissions**
   - Superuser global contracts/taxes/overview.
   - Gym admin coach contracts/sales/payments/settlements/refunds/reports for own gym only.
   - Audit list.
4. **Backend tests**
   - Approved 10/40/50 + VAT example; category/gym overrides; percentage/fixed taxes; 100% validation; platform tampering; snapshots; role isolation; payment failure/duplicate/retry/concurrency; partial/full/after-settlement refunds; rounding; report/export consistency.
5. **Seed and environment**
   - Sandbox seed: default VAT, default platform contract, gym override, coach contracts, demo sales/payments.
   - Verify actual DB name/host before migrations; never touch other DBs.
6. **Frontend**
   - Navigation and separate pages: overview, contracts, sales/payments, taxes, settlements, reports.
   - Persian RTL wording, units, live preview, validation, loading/empty/error/permission states.
   - Superuser platform contract/tax pages and cross-gym overview.
7. **Verification**
   - Backend suite, migration on dedicated DB, frontend lint/build.
   - Playwright admin and superuser journeys, mobile/RTL/no-overflow checks.
   - Final report with branch/worktree, DBs, URLs, tests, limitations and Persian guide.

## API Shape

- `GET/POST /finance/platform-contracts`, `POST /finance/platform-contracts/{id}/activate|archive`
- `GET /finance/platform-policy?gym_id&category&on_date`
- `GET/POST/PATCH /finance/taxes`
- `GET/POST /finance/gyms/{gym_id}/coach-contracts`, activate/archive
- `GET /finance/gyms/{gym_id}/coaches`
- `POST /finance/gyms/{gym_id}/sales/preview`, `GET/POST /sales`, `GET /sales/{id}`
- `POST /finance/gyms/{gym_id}/sales/{id}/payments`, `GET /payments`
- `POST /finance/gyms/{gym_id}/payments/{id}/refunds`
- `GET/POST /finance/gyms/{gym_id}/settlements`, complete/cancel/auto
- `GET /finance/overview`, `GET /finance/reports`, `GET /finance/reports/export`
- `GET /finance/gyms/{gym_id}/audit`

## Money Rules

- IRR integers; UI converts toman (÷10) and labels the unit.
- Percentages are basis points (`1000 = 10%`).
- Taxes: percent on base, or fixed; no compounding.
- Shares are on total paid (base + taxes).
- `platform = total * platform_bp // 10000`; `coach = total * coach_bp // 10000`; `gym = total - platform - coach` (residual to gym).
