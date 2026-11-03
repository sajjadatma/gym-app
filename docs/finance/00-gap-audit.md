# ASCORA finance — repository audit and Phase 1 evidence

- **Branch:** `feat/ascora-finance`
- **Base:** `f3b37bce41ed25daa975a0927861b5c38b9b523b` (`origin/main`)
- **Scope:** Phase 0 repository audit plus the Phase 1 authoritative financial
  foundation from `ASCORA-FINANCE-PRD.md`.
- **Not in scope:** Phase 4+ (platform monetization, dashboards, plan limits)
  and Phase 5 readiness. Production was not touched.

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
| Permissions | a finance staff member is denied every athlete, program, template, exercise, member, gym-admin and superuser surface (exact 403/404 matrix), keeps only finance + gym identity; grant allow-list, IRR cap, disabled mode |
| Default flag | enabled with no settings row; only Superuser toggles |
| Concurrency | concurrent opening balance, concurrent correction, and concurrent restated openings each post exactly once |
| Control changes | settings/grant changes are re-read under the same per-gym lock, so a disable or lowered cap cannot be overtaken by an in-flight posting |
| Idempotency | `Idempotency-Key` is a required request header (422 when missing, matching the generated client); same key replays the same journal; changed payload is rejected |
| Audit | actor, action, reason, linkage asserted from `finance_audit` for settings, opening, correction, grants and period close |
| Migration | full upgrade → downgrade to pre-finance → upgrade; metadata check; real-Postgres constraints and deferred balance trigger |
| Restore | backup/restore drill with a posted journal and balance/line-count verification |
| Retention | a user with finance history is refused a hard delete with `409 user_has_finance_history` instead of a server error |
| No regression | full backend, frontend, unit and Playwright suites pass |

### Access boundary verification

`FINANCE_STAFF` is deliberately not part of `is_staff` or `is_admin`. A
dedicated boundary test asserts that the role cannot list or create athletes,
exercises, categories, templates or coaches; cannot read, edit, archive or
delete athletes or programs; cannot manage members, gym settings or ownership;
cannot open people overviews; and cannot use superuser routes. It retains only
its own finance workspace and gym identity. The role also carries no coaching
or program rights in the navigation.

### Idempotency contract

Financial writes require the `Idempotency-Key` header. The OpenAPI contract
declares it required, so a missing or empty header is rejected by request
validation (422) before any work, and the generated client cannot compile a
call without it. Replaying a key returns the original journal; reusing it with
different content returns `409 idempotency_key_reused`.

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


## Phase 2 — operational gym finance (status)

**Implemented and tested (backend and UI):**

1. **Catalog and invoices** — gym-scoped catalog items; draft/issue/void
   customer invoices; per-gym sequential numbers; immutable issued documents;
   line and bundle discounts with exact integer proration; installment
   schedules; receivables/revenue posting linked by source reference.
2. **Manual receipts and advances** — cash/POS/transfer receipts recorded by an
   authorized operator; one receipt across several same-gym invoices of the
   same customer; over-allocation and over-payment blocked; excess becomes a
   same-gym customer advance; advances apply to later invoices; receipts are
   sequential, idempotent and audited; paid invoices cannot be voided.
3. **Refunds and expenses** — requested → approved → recorded refunds capped at
   the collected/unrefunded amount or the remaining advance; sales-returns or
   advance-liability postings; rejection never posts; unpaid/paid expenses,
   accrual and settlement postings, and a duplicate-safe monthly repeat.
4. **Paid membership and athlete self-service** — paid access periods separate
   from identity membership; derived access from a configured downpayment;
   freeze/resume/cancel/transfer; time-proportional refund preview; athletes
   read only their own invoices, receipts, memberships, refunds and advance and
   can open a capped refund request.
5. **Permissions** — catalog, invoice, payment, refund, expense and membership
   actions are separate grantable permissions; admins hold them implicitly.
6. **Gym-admin workspace** — one finance page with Overview, Invoices, Catalog,
   Payments, Refunds, Expenses and Memberships tabs. The overview keeps the
   Phase 1 settings/journal/periods/grants and adds due-installment and
   renewal reminders. Every mutation uses the server-authoritative generated
   client, Jalali dates, RTL Material 3 components and per-gym tenant context.
7. **Athlete finance page** — `/gyms/$gymId/my/finance` (and the `/my/finance`
   redirect) shows only the signed-in athlete's invoices, installments,
   receipts, paid membership/access, advance balance, refund history and
   refund requests.
8. **Sale-time snapshots and refund method** — each sale records the
   acquisition source (`GYM`/`ASCORA`) and the party funding any discount
   (`GYM`/`COACH`/`ASCORA`/`MIXED`). Drafts may change them; issuing freezes
   them so Phase 3 allocation never rewrites history. Refunds default to the
   payment method that actually collected the money; a different method needs
   `finance.refund.manage` and a recorded override reason.
9. **Reminders** — computed on read, not scheduled: the next unpaid installment
   per issued invoice plus active memberships ending inside the requested
   horizon. The admin overview exposes 7/30/90-day horizons and the athlete
   page reuses the same calculation for the athlete's own rows.

**Deliberate Phase 2 deferrals (no missing approved behaviour):**

- **Receipt evidence files.** The PRD marks proof as optional. The existing
  storage service is body-analysis-specific (`body-analysis` object prefix,
  body-analysis upload limits and endpoints), so adding a second document
  lifecycle only for receipts would duplicate infrastructure. The receipt
  `reference` text remains the minimal evidence field; receipt reconciliation
  and attachments stay with Phase 3 reconciliation.
- **Recurring expenses beyond the explicit monthly repeat** and cash/bank
  reconciliation are Phase 3 scope, as approved.
- **Online payment** remains disabled by design pending a verified provider.
- **Decision 18, 30 and 46** remain deferred exactly as recorded in the PRD.

Phase 2 is **user-complete for the approved scope**. Phase 3 has not started.

## Phase 3 — coach contracts, allocation and settlement (status)

**Implemented and tested:**

1. **Versioned agreements** — effective-dated coach agreement versions with
   ordered fixed/percent terms for coach, ASCORA and gym recipients, `DIRECT`
   or `WATERFALL` distribution and explicit `ON_DATE`/`MANUAL` vesting.
2. **Sale snapshots** — issuing an invoice selects the highest active agreement
   effective on the issue date and freezes its version and terms on each coach
   line. A missing agreement leaves the line `UNRESOLVED` without blocking
   payment intake; issued records are never rewritten.
3. **Deterministic allocation** — confirmed receipts and applied advances are
   split across invoice lines by payable with largest-remainder integer math.
   Bundle discounts are borne by GYM, COACH, ASCORA or pro-rata for `MIXED`;
   the gym is the deterministic residual and recipient shares always sum to
   the collected net. Coach shares post a balanced expense/payable journal.
4. **Earnings and vesting** — calculated, vested, eligible and settled views;
   `ON_DATE` vesting derives from the receipt date plus the snapshot days;
   `MANUAL` vesting requires an audited reason. Fixed and waterfall terms are
   covered, and unresolved/unvested amounts are never eligible.
5. **Settlements** — manual and partial FIFO settlements capped by the vested
   eligible balance, a balanced payable-to-cash journal, and an audited
   recorded→confirmed lifecycle. Only confirmed payouts count as settled;
   recorded payouts stay reserved and cannot be settled twice. A recorded
   settlement can be cancelled before confirmation with an audited reason;
   cancellation releases the reservation and reverses the pending-settlement
   journal without touching cash. Confirmed settlements cannot be cancelled.
   Coach and finance users can read history.
6. **Refund discrepancies** — invoice refunds reverse the coach share
   proportionally. Unsettled share posts a balanced reversal; already-paid
   (confirmed) share becomes an OPEN discrepancy for a manual, audited
   resolution. A recorded but unconfirmed settlement remains reserved and is
   not treated as paid: no discrepancy or automatic clawback is created, and
   confirmation fails as `settlement_stale` if the reservation now exceeds
   entitlement so an operator cancels it instead of overpaying.
7. **Decision #66 correction** — drafts can provide an explicit bundle-discount
   share per line; the shares must sum to the invoice discount and fit each
   line. Proportional allocation remains the default.
8. **Decision #15/#71 (current limitation)** — reminders are **in-app and
   computed on read only**. There is no SMS, background scheduler or
   notification platform. The remaining proactive-reminder requirement stays
   open for a later approved reminder/delivery phase; no scheduler was added.
9. **UI** — a finance Coaches tab (agreements, earnings, settlements,
   discrepancies) and a coach `My earnings` page with per-gym calculated,
   vested, eligible and settled history.

10. **Settlement accounting (decision #36/AC-30)** — a `RECORDED` settlement
    reserves the earnings and posts coach payable to a pending-settlement
    liability (`2200`); cash (`1000`) is reduced only when the settlement is
    confirmed. Confirmation is locked, idempotent on retry and linked to a
    second balanced journal. `settled_irr` and `SETTLED` reflect confirmed
    payouts only; reserved amounts are reported separately and reduce
    eligibility. Cancellation of a recorded settlement is locked, idempotent,
    releases the reservation and posts `2200 → 2100` with no cash movement.
11. **Platform fee authority (decision #78)** — only a global Superuser can
    create or activate coach agreement terms naming `ASCORA` as a recipient;
    gym admins and finance staff keep coach/gym compensation management.
12. **Periodic fixed coach compensation (decision #83/AC-28)** — an active
    agreement can carry a monthly fixed amount. Accruing a period creates an
    unpaid expense/payable through the existing expense ledger, with
    per-agreement/per-period duplicate protection; no synthetic sale or fake
    payment is created. The accrual locks and reloads scope, validates the
    whole selected month inside the agreement's effective dates, and writes
    the expense, journal, audit entry and idempotency record in one commit.
13. **Cash/bank reconciliation (decision #36/AC-31)** — manual bank statement
    lines can be recorded, remain visible as `UNMATCHED`, and are matched
    manually to one confirmed receipt of the same amount. Matching sets the
    receipt's separate reconciliation flag; receipt confirmation and bank
    reconciliation remain distinct. No bank integration or automatic matching
    was added.

**Phase 3 deliberate exclusions:** automatic coach clawback (#30 remains
deferred), usage/attendance tracking (#18), advanced analytics (#46), and
platform monetization/settlement (Phase 4).

## Remaining phases

4. Superuser plans/contracts, platform fees, dashboards, exports, limits.
5. Readiness: gateway selection (only if enabled), restore/monitoring evidence,
   Iran legal/tax/provider checks, 3–5 gym pilot.

## Phase 4 — implemented locally (not merged/deployed)

Phase 4 is implemented on `feat/ascora-finance`; see
`docs/finance/phase4-evidence.md` for evidence and deviations. It covers
optional plans (including zero plans and agreements with no plan records),
all five monetization modes, gym/group agreements, separate platform
receivables/collections, append-only refunds/credits and unpaid-invoice
cancellation, single ASCORA recognition, Superuser authority with owner
read-only platform billing, separate cashflow/accrual reporting, role
dashboards and CSV/offboarding exports.

**Outstanding approved requirement:** proactive reminder delivery (#15/#71)
is not implemented. In-app reminders are explicitly `IN_APP_ONLY`; they do
not close the proactive requirement. Overdue `RESTRICTED` is informational
only; no core-feature lockout was added. Plan limits are stored/surfaced but
not enforced against core gym operations. #18, #30 and #46 remain deferred.

Phase 4 must not start without explicit approval.
