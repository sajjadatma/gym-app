# ASCORA finance — repository audit and Phase 1 evidence

- **Branch:** `feat/ascora-finance`
- **Base:** `f3b37bce41ed25daa975a0927861b5c38b9b523b` (`origin/main`)
- **Scope:** Phase 0 repository audit plus the Phase 1 authoritative financial
  foundation from `ASCORA-FINANCE-PRD.md`.
- **Not in scope:** Phase 2+ (catalog, invoices, payments, coach settlements,
  platform monetization). Production was not touched.

## Baseline (Phase 0, before finance code)

| Check | Result |
| --- | --- |
| Backend `pytest` (incl. migration smoke test) | 156 passed |
| Backend Ruff / Mypy (backend config) | passed |
| Frontend Biome / TypeScript / production build | passed |
| Frontend Node unit tests | 16 passed |
| Playwright (desktop + mobile projects) | 111 passed, 18 skipped, 0 failed |
| Docker backup + restore drill | passed (pre-finance schema) |
| Environment contract | passed |

The 18 Playwright skips are the pre-existing superuser journey (no
credentials in that run) and project filters; they were not introduced here.

## Existing architecture reused

| Area | Reused |
| --- | --- |
| Stack | FastAPI, SQLModel, PostgreSQL 17, Alembic, React 19, Vite, TanStack Router/Query |
| Identity | Existing cookies/bearer tokens, CSRF, invitations, account lifecycle |
| Tenancy | `GymContext`, `X-Gym-ID`, memberships, owner/admin/staff dependencies |
| Domain | `Gym`, `User`, `GymMembership`, `AthleteProfile`, `CoachAssignment`, programs |
| UI | Material 3 components, `DateField`, dialogs, snackbar, Persian RTL, i18n |
| Tests | Pytest API/security/concurrency, disposable migration DB, Playwright |
| Release | GitHub CI, backup/restore scripts, manual production workflow |

## Gap analysis (mapped to the PRD functional requirements)

`reuse` = existing code covers it; `add` = new finance code required.

| FR | Existing | Phase 1 outcome |
| --- | --- | --- |
| `FR-CONF` | gym activation (unrelated) | **Add** finance enable flag, default on, Superuser-only toggle, read-only when disabled |
| `FR-TENANT` | gym isolation, ownership | **Reuse** context; **add** gym-owned finance rows and scoped reads |
| `FR-AUTH` | role dependencies | **Add** `FINANCE_STAFF` role + explicit action grants with IRR caps |
| `FR-LEDGER` | SQL transactions | **Add** accounts, periods, balanced journal, opening balance, reversals |
| `FR-INVOICE` | program numbering | **Add** per-gym document sequence + journal entry numbers (invoices in Phase 2) |
| `FR-SALE` | — | Phase 2 |
| `FR-PAY` | — | Phase 2 |
| `FR-CREDIT` | — | Phase 2 |
| `FR-AR` | — | Phase 2 |
| `FR-MEM` | `GymMembership` is identity only | Phase 2 (paid entitlement remains separate) |
| `FR-REF` | — | Phase 2/3 |
| `FR-EXP` | — | Phase 2 |
| `FR-AG` | program snapshots | Phase 2/3 |
| `FR-SHARE` | — | Phase 3 |
| `FR-COACH` | coach identity/assignment | Phase 3 |
| `FR-SET` | — | Phase 3 |
| `FR-RECON` | — | Phase 3 |
| `FR-PLAN` | — | Phase 4 |
| `FR-FEE` | — | Phase 4 |
| `FR-PORTAL` | role-specific pages | **Add** gym finance workspace; athlete/coach views in Phase 2/3 |
| `FR-REPORT` | operational counts | Phase 2/4 |
| `#18`, `#30`, `#46` | — | **Deferred** (no attendance tracking, no automatic clawback, no AI analytics) |

## Phase 1 — implemented

**Database (additive migrations `b2d4e6f8a0c1` → `c3e5f7a9b1d2` → `d4f6a8b0c2e3`)**

- `finance_settings`, `finance_audit`
- `finance_account`, `finance_period`, `finance_sequence`
- `finance_journal`, `finance_journal_line`, `finance_operation`
- `finance_grant`
- `FINANCE_STAFF` added to the membership role constraint
- Partial unique indexes: one active grant per permission, one open period per
  gym, one opening balance per gym, one reversal per journal
- `BIGINT` IRR columns, single-sided line checks, non-negative amounts
- Append-only triggers on posted journals, journal lines and audit rows

**Service and API**

- `GET/PATCH /api/v1/finance/settings`
- `GET /api/v1/finance/accounts`
- `GET /api/v1/finance/journal`, `GET /api/v1/finance/journal/{id}`
- `POST /api/v1/finance/opening-balance` (idempotent, balanced, once per gym)
- `POST /api/v1/finance/journal/{id}/correct` (Superuser only, linked reversal)
- `GET /api/v1/finance/periods`, `POST /api/v1/finance/periods/close`
- `GET /api/v1/finance/grants`, `PUT /api/v1/finance/grants/{user_id}`

**UI**

- Gym finance workspace (settings, opening balance, journal, periods, grants)
- Finance-only role and navigation; no operational access for finance staff
- Rial/Toman display with exact integer helpers; 105 IRR renders as 10.5 toman
- Persian RTL and Jalali dates through the existing components

**Access decision (refinement 1)**

The existing gym-scoped membership plus explicit finance grants was reviewed
first. A zero-role membership is rejected by `get_gym_context`, and granting
`GYM_ADMIN` would overgrant coaching/program access. The smallest safe change
was a dedicated `FINANCE_STAFF` role that carries no operational rights plus
explicit action grants. No generic RBAC layer was built.

## Phase 1 gate evidence

| Gate | Evidence |
| --- | --- |
| Balanced journal | service + API tests; DB line checks; restore drill asserts balance |
| Tenant isolation | cross-gym read/posting tests; Superuser cross-gym access test |
| Permissions | staff/coach/athlete denial, grant allow-list, IRR cap, disabled mode |
| Default flag | enabled with no settings row; only Superuser toggles |
| Concurrency | concurrent opening balance and concurrent correction each post once |
| Control changes | settings/grant changes are re-read under the same per-gym lock, so a disable or lowered cap cannot be overtaken by an in-flight posting |
| Idempotency | same key replays the same journal; changed payload is rejected |
| Audit | actor, action, reason, linkage asserted from `finance_audit` for settings, opening, correction, grants and period close |
| Migration | full upgrade → downgrade to pre-finance → upgrade; metadata check; real-Postgres constraints and deferred balance trigger |
| Restore | backup/restore drill with a posted journal and balance/line-count verification |
| Retention | a user with finance history is refused a hard delete with `409 user_has_finance_history` instead of a server error |
| No regression | full backend, frontend, unit and Playwright suites pass |

### Corrections semantics

A correction is an immutable reversal that references the original. So the
original is voided but never edited. Because only one opening balance may be
*active* per gym, a superuser who entered a wrong opening corrects it by
reversing it and then posting the restated opening; the journal keeps both
documents linked. `uq_finance_journal_reversal` guarantees a journal can be
reversed once, and the "one active opening" rule is enforced under the per-gym
finance lock (SQL cannot express "not referenced by a reversal" without
mutating posted rows).

### Date policy

Instants are stored in UTC. Journal `posting_date` is an explicit gym-local
calendar date supplied by the authorized operator, and it is required for both
opening balances and corrections. Reporting-range conversion using the stored
gym timezone arrives with the Phase 4 reports; until then the setting is
recorded but not used for calculations.


## Remaining phases

2. Catalog, invoices, manual receipts, installments, advances, refunds,
   expenses, paid membership policy, athlete screens.
3. Coach agreements and allocation, vesting, settlements, reconciliation.
4. Superuser plans/contracts, platform fees, dashboards, exports, limits.
5. Readiness: gateway selection (only if enabled), restore/monitoring evidence,
   Iran legal/tax/provider checks, 3–5 gym pilot.

Phase 2 must not start without explicit approval.
