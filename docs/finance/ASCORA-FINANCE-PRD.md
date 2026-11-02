# ASCORA Financial Management — FINAL PRD & OpenCode Implementation Contract

> **Status:** **FINAL PRODUCT PRD — approved from Business Manager, Business Analyst, and Product Strategist viewpoints.** Implementation starts only after local code audit/baseline.  
> **Date:** 2026-11-02  
> **Target:** ASCORA Gym Management (`sajjadatma/gym-app`) — shared finance capabilities ready for future reservation verticals.  
> **Source of truth:** 92 approved/reviewed decisions: **89 accepted, 3 deferred** (#18, #30, #46), plus the approved flexible monetization addendum.  
> **Instruction to OpenCode:** This file is the **complete functional PRD and implementation contract**. Read its **traceability, flows, edge cases and acceptance scenarios below**. It is not permission to rewrite the application or deploy to production.

## 1. Executive decision — three roles

| Perspective | Final judgment | Non-negotiable priority |
|---|---|---|
| **Business Manager** | Viable, configurable SaaS/business-management monetization; gym is the customer and recipient of its sales receipts. | Separate ASCORA revenue from gym revenue, trace collectible platform fees, measure operating cost. |
| **Business Analyst (BA)** | Functional requirements and major edge cases are sufficiently clear for an implementation PRD; no new broad discovery round. | Precisely model invoices, real receipts, installment debts, revenue allocations, refunds, settlements, roles and document states. |
| **Product Strategist** | Finance must make gym/reservation operations easier—not turn ASCORA into a bank, fintech, ERP or generalized payroll system. | Deliver the smallest reliable solution; configurable monetization and useful dashboards before advanced automation. |

**Verdict:** Ready for **scoped implementation planning and staged coding**; **not** a statement that the existing repository is already technically ready or that real-money production use is safe. OpenCode must audit the actual checked-out branch first.

## 2. Business boundaries (locked)

1. ASCORA is gym/reservation management software with **integrated operational finance**, **not a funds-custody or payment-intermediary platform**. Gym is the legal recipient of gym sales. Actual transfers remain outside ASCORA unless a later approved provider integration supports them.
2. Finance is **enabled and required by default** per gym/branch. Only global Superuser can disable it. Disabled mode = **no new finance postings**, existing financial history is read-only/exportable; to make corrections, Superuser first re-enables the module. Disabling never erases records or pending claims.
3. Each gym/branch has its **own financial accounts, invoices, expenses, debts and settlements**; an authorized multi-branch owner has consolidated **reporting**, not merged ledgers. Global Superuser has full access to all gym finance data and all privileged finance workflows.
4. Gym admins manage their own gym. Finance staff (cashier/reception/accountant) receive granular gym-scoped permissions; coaches see only their own earnings by gym (with own cross-gym totals); athletes see only their own obligations, payments and receipts.
5. The financial primitives must be reusable for a future reservation/barbershop app. **Do not build that app now.** Reuse neutral concepts where natural; keep domain-specific membership/booking logic in its own module. Prefer **modular monolith**.
6. Preserve prior finalized financial records and historical pricing/contract terms. Posted records are not edited/deleted in place; issue auditable reversals/corrections.

### Critical monetization addendum (approved after question 92)

Superuser controls the platform's commercial model **without code edits**:

- **Subscription only**, **commission only**, **hybrid**, **free**, or **custom contracts**—all valid modes.
- Starter / Pro / Growth are **optional examples**, **not required plans**. Superuser may create/edit/activate/deactivate plans, leave **zero active subscription plans**, or define custom plans/prices/limits.
- Commissions may apply by gym, service/revenue category (membership, training program, private session, product, reservation, etc.), acquisition source (gym vs ASCORA), agreement and effective date; percentage, fixed, or agreed combined fees. Do **not** automatically tax all manually recorded sales.
- Each branch normally has independent ASCORA subscription/contract; Superuser may grant a **group contract, volume discount and consolidated platform invoice** while keeping per-branch allocations traceable.
- Platform billing/commission ledgers and dashboards are **distinct** from each gym's own customer sales and cash receipts. A posted commission receivable is **not** platform cash collected.
- Contract versions and applied calculation snapshots are immutable for historical finalized sales; changes take effect prospectively at the configured date.
- Disabling **subscription pricing** does **not** disable the **gym finance module**.

## 3. Confirmed functional scope

| Area | Required capabilities |
|---|---|
| **Catalog & sales** | Memberships, programs, private sessions, multi-session packs, physical products, reservation services, custom income/sales, bundled offers; invoice line items and per-line financial rules. Do not build inventory management. |
| **Membership finance** | Manual renewal, simple automated renewal reminders, optional future recurring collection only if payment infrastructure permits; configurable effective start, freeze, cancel, transfer, partial-payment access rules and documented refund policies. |
| **Invoicing** | Draft → issued → settled/partially paid or voided via document; branch-scoped sequential issued invoice numbers; no editing/deleting posted invoices; receipts and adjustments. Bundle discount proportionate across lines by default, with authorized override. |
| **Payments** | Cash, POS/card terminal, bank transfer and online gateway; manually entered payments by authorized staff; optional receipt/proof; distinct provider verification vs manual declaration vs bank reconciliation. Partial payments and installments, due dates and overdue balances. One receipt can allocate across multiple invoices without over-allocation. |
| **Deposits/overpayments** | Track unallocated customer credit **within the same gym** as a liability/advance; later allocate to invoice or refund. No user-to-user transfers or transferable wallets. |
| **Refunds** | Full/partial, policy-based, authorized, recorded with reason; original payment method preferred, approved documented exception allowed. Keep invoice/payment/refund and ledger history. |
| **Coach compensation** | Percentage of revenue, fixed per program, fixed per session, fixed periodic pay, or approved combination; contractual entitlement timing and weekly default settlement (configurable). Fixed periodic pay can be owed even with zero sales. |
| **Allocation** | Direct split or contractual waterfall split; bounded number of recipients; gym/coach/ASCORA splits (and multiple coaches when required), discounts funded by selected parties, gateway fee/tax treatment according to snapshotted agreement. |
| **Receivables/payables** | Athlete debt, coach payout liability, gym's platform-fee debt, refund due, negative balances and contractually authorized manual offsets. Weekly default settlement, manual/partial settlement and status tracking. |
| **Operating accounting** | Lightweight **double-entry** ledger; income, expenses (including simple recurring expense), liabilities, accrual/receipt distinction, adjustments and closing financial periods; bank/cash reconciliation manually or imported statement file first. Avoid full statutory accounting/ERP. |
| **Reporting** | Gym: collected today, sales, overdue debt, expiring memberships, coach payables, registered expenses and **estimated operating profit**. Superuser: platform MRR when applicable, **collected** commissions, receivables, cost-to-serve/contribution by gym, contract status. Coach/athlete: simple mobile-first personal financial views. Export for accountant and exit/offboarding. |
| **Controls** | Multi-tenant isolation; full Superuser scope; granular permission limits and amount thresholds for staff; audit trail; controlled period close, document numbering; versioned financial terms. |
| **Plans** | Configurable plan catalog (including none), per-plan usage/feature limits (active athletes, staff seats, advanced finance, SMS, storage), group billing optional, commercial enforcement without data loss. Numeric prices/limits can be configured after pilot. |

### Explicitly out of scope (do not smuggle back in)

- **#18:** Consumption/attendance tracking as a required finance input. Use existing delivery states, contractual time or authorized manual attestation for entitlement; don't create financial attendance infrastructure.
- **#30:** Automatic clawback of already-paid coach revenue after later customer refund. **Still** record the refund, financial discrepancy and authorized manual resolution; default refund payment responsibility is the gym.
- **#46:** Advanced AI analytics, predictive ranking, smart financial automation. Previously approved **basic renewal reminders and platform overdue reminders remain**.
- Fintech wallet, custody, automatic money transfers among parties, general ERP, full tax engine, statutory payroll, inventory system, generic visual rule builder, microservices, new reservation application.

## 4. Financial invariants (must be testable)

1. **Money:** Store amounts as **integer IRR**; allow Rial/Toman UI display; never use binary floating-point for balances/fees. Jalali display and gym-local reporting periods with normalized timestamps.
2. **Separation:** `Invoice issued ≠ Payment confirmed ≠ Revenue recognized ≠ Allocation vested ≠ Settlement paid`. Do not count one as another in any dashboard.
3. **Payment idempotency:** A successful gateway callback, retried API call or concurrent staff request causes **one and only one** confirmed receipt and ledger posting. Uncertain provider outcomes remain pending until verified.
4. **Balanced ledger:** Every posted financial event uses atomic, balanced debit/credit entries. Corrections, refunds and late changes are new referenced entries, not mutations of posted rows.
5. **Allocation integrity:** Total recipient allocations exactly match the relevant distributable amount after the contract-defined discount/tax/gateway fee order; deterministic rounding and a specified residual recipient. Never allocate more than confirmed collectible/vested amount.
6. **Installments:** Keep invoice balance and allocation of each receipt independent. Coach/platform shares ordinarily accrue on **confirmed collected portion**, respecting contractual vesting and refund policies; no share payout from merely promised future installments.
7. **Missing contract:** Do not silently assume coach share is zero. Mark the coach allocation unresolved, prevent its settlement until resolved and allow sale/payment recording.
8. **Refund after coach payout:** Gym handles customer refund; record obligation/discrepancy; adjustment with coach is authorized **manual** workflow; **no automatic deduction or clawback**.
9. **Audit & tenancy:** Every financially sensitive mutation records actor, gym, document reference, reason when needed, timestamp and before/after meaning. Gym roles may not cross tenants. Superuser may act across tenants but cannot bypass ledger integrity.
10. **Contract precedence:** Applicable custom effective-dated contract > permitted service override > platform defaults; **platform fee configuration exclusively Superuser-controlled**. Snapshot service, customer acquisition source, applicable rules and actual amounts per finalized sale.
11. **Settlement truth:** Proposed/recorded payouts are not confirmed money movements. Confirmation requires payer, payee, amount, date, method and reference/proof as applicable; reconciliation status separately tracked.
12. **Period close:** Posted closed-period records are protected; any discovered correction is recorded in an open period with reference to the original.
13. **Exit/disable:** Read/export history remains available under policy; deactivation, plan downgrade or cancellation cannot erase liabilities, refunds or historical invoices.
14. **Profit terminology:** Show **estimated operating profit**, not tax/audited net income; separately show receipts and outstanding obligations to avoid double counting.

## 5. Minimal domain / UX design (adapt to existing code; don't blindly create all entities)

Conceptual boundaries, not mandated table count:

- **Gym finance configuration:** tenant, active flag, currency/display preferences, membership/payment/refund rules, fiscal period and staff permissions.
- **Commercial catalog:** product/service, pricing, bundles, invoice + line items, discounts, deposits and customer credit.
- **Cash movements:** payment intent/receipt, provider reference, payment allocation, refunds, reconciliation records.
- **Accounting core:** chart of accounts **only as needed**, immutable journal + entries, expense, opening balance and period close.
- **Entitlements and sharing:** references to existing gym members/programs, versioned coach agreement, split rule snapshot, share/earning entitlement, settlement batch/item.
- **ASCORA commercial billing:** optional plan/catalog, gym/group contract, subscription billing, commission receivables and consolidated platform invoices.

**UX:** Use current Persian RTL, Vazirmatn and Material 3 patterns. Present role-specific task pages: Gym Admin financial overview/transactions/invoices/expenses/debts/coach settlement; Superuser monetization/plan controls/contracts/invoices/global overview; coach earnings; athlete bills/payments. Avoid a giant accounting console for ordinary users.

## 6. Delivery order (vertical slices; no big-bang build)

### Step 0 — Repository audit and baseline (mandatory, *before edits*)

1. Read actual branch, `AGENTS.md` if present, README, backend models/routes/permissions/migrations/tests, frontend routing/UI patterns and deployment guardrails. Compare with this brief; identify **already implemented / missing / conflicting** functionality. Confirm current git status and branch; **do not assume `main` matches the local working tree**.
2. Run existing backend/frontend checks in an isolated test environment; distinguish **pre-existing failures** from new failures. Verify test database safeguards and any existing protected promotion workflow.
3. Deliver a **short audit report and change list** before writing feature code. Check requirements with an independent self-review. If a genuine blocker exists (data corruption risk, migration impossibility or unresolved regulatory/payment-provider dependency), **stop that slice**, report it and continue with safe independent slices where possible.
4. Create a dedicated branch. Never modify production databases, expose credentials, bypass protected workflows or deploy to production implicitly.

**Repository snapshot note (read-only inspection of remote `main`, 2026-11-02):** `sajjadatma/gym-app` documents FastAPI + SQLModel + PostgreSQL/Alembic and React/Vite/TanStack; root tree has current gym/program/athlete route modules. No clearly named dedicated finance route was visible in the remote `main` file tree. This is **not** a local audit and must be verified by OpenCode against the actual checkout/branch.

### Step 1 — Safe finance foundation

- Reuse gym identity and scoped authorization; implement per-gym financial enable/disable, opening balance workflow, lightweight journal, invoice/document numbering and posted-entry corrections.
- Add migration, seeded minimal reference data if necessary, authoritative IRR amount helpers, date boundary policy, API permission tests and ledger balance tests.
- Deliver only when journal is balanced, tenant isolation is tested, and migration/rollback safety is demonstrated.

### Step 2 — Operational gym finance

- Implement sale catalog, bundled invoices/discounts, manual receipts, optional verified online payment behind an integration adapter **only when provider is selected**, invoice allocations, debts/installments, simple expenses and credits, refund/adjustment flows, membership renewal/freeze/cancel financial rules.
- Build focused Gym Admin + Athlete screens; wire business rules to existing membership/program references (avoid duplicating core gym entities).
- Validate full/partial payments, one payment-many invoices, overpay, refund and concurrent retry cases.

### Step 3 — Coach split and settlement

- Add agreements and effective dates, direct/waterfall distributions, flexible pay models, share vesting by contract/manual milestone, unresolved share handling, weekly configurable settlement batches, negative balances and manually resolved post-payout refund differences.
- Build coach earnings and gym payout views; ensure receipt ≠ vested share ≠ confirmed settlement in API/UI.

### Step 4 — Platform monetization and reports

- Implement full Superuser controls for **zero or more subscription plans**, independent platform commission agreements, free/commission/subscription/hybrid modes, per-branch plus optional group invoicing and explicit versioning.
- Introduce concise role dashboards and exports. Build only basic reminders. Plan limit enforcement must never erase or conceal posted financial history.

### Step 5 — Pilot and release gates

- Demo/staging first; then limited pilot with **3–5 different gyms** once security, finance integrity, restore drill, payment/legal contracts and provider compliance are verified. Record real user feedback and refine without scope explosion.
- Never auto-push/deploy to production, and never represent passing unit tests as sufficient for real-money release.

> Each step: implement the smallest coherent vertical slice → test → summarize evidence and files changed → self-review → commit on feature branch. Keep changes reversible; merge/promotion only through existing protected process.

## 7. Acceptance checklist (minimum gates)

- [ ] Staff cannot read/write finance data of unauthorized gyms; owner sees only authorized multi-branch aggregation; Superuser has full cross-gym financial visibility and actions.
- [ ] Finance disabled by Superuser prevents new postings, preserves read-only existing data and permits controlled re-enable.
- [ ] Invoices and ledger reconcile to the rial; issued invoice numbers are unique within each gym and never reused.
- [ ] Payment retry, duplicate webhook, simultaneous collection and gateway timeout do not double-credit or falsely confirm payment.
- [ ] Installment balance, customer advance, one receipt across multiple invoices and due reminders are consistent.
- [ ] Refund partial/full and post-coach-settlement refund create correct auditable records without automated clawback.
- [ ] Every share rule change preserves prior sale snapshots; missing coach contract remains unresolved, not silently zero.
- [ ] Direct and waterfall splits, multi-recipient allocation, discounts and rounding balance exactly.
- [ ] Settlement shows recorded vs confirmed state and preserves references; canceled/downgraded subscriptions don't remove claims.
- [ ] All monetization modes work, including **no subscription plan at all** and commission-only, with per-gym overrides and group invoices.
- [ ] Finance views consistently distinguish sales, confirmed receipts, recognized revenue, dues, confirmed settlements and estimated operating profit.
- [ ] Migration preserves existing gym/member/program data; test backups can actually be restored.
- [ ] Backend unit/integration/migration, frontend component/e2e, permission, financial invariants and failure tests pass; any pre-existing failures separately documented.
- [ ] Iran-specific contract, invoicing/tax, privacy and payment-provider assumptions checked **before** real-money public launch.

## 8. Anti-overengineering / anti-overthinking rules for OpenCode

**Must:** reuse current stack, API structure, authentication, permissions, migrations, design tokens and existing testing infrastructure; use incremental PR-sized slices; avoid duplicate entity ownership; explain any added dependency; perform self-review **before** introducing new architecture or modifying critical financial boundaries.

**Do not:** introduce microservices, Kafka/event-sourcing, distributed ledger/blockchain, generic workflow/rule editor, a general accounting suite, AI agents, new SaaS admin framework, full inventory or payroll, a second authentication system, or huge abstraction hierarchies. No speculative integrations or reservation app UI now.

**Decision rule:** If existing code already solves a requirement safely, **reuse it**. If two approaches both meet acceptance criteria, choose the simplest with fewer moving parts. Spend effort on money correctness, tenant authorization, audit, data migration and recovery—not architectural elegance. Do not ask the product owner for implementation minutiae that can be determined safely from the existing code. Escalate only a **material** business/legal contradiction or financial integrity blocker.

## 9. OpenCode starting instruction (copy/paste with this file)

> Read `ASCORA-FINANCE-OPENCODE-IMPLEMENTATION.md` as the approved finance scope. First inspect the real working branch/repository, existing domain models, permissions, API patterns, frontend conventions, migrations, test setup, current failures and security/deployment workflow. Produce a concise GAP ANALYSIS and an incremental implementation checklist, stating which existing components will be reused. Do not code until you have independently assessed the plan and identified no critical blockers for Step 1. Then implement Step 1 only, with migrations, tests and evidence; self-review before committing. Do not overengineer, do not invent missing business rules, do not overwrite existing gym behavior, do not deploy or merge to production. At the end report implemented items, test results, open risks and recommended next slice.

## 10. Implementation decisions and external launch dependencies (not a new business discovery round)

The 92 decisions establish binding business intent. Sections 11–19 below now define the functional PRD, state transitions, explicit traceability, test cases and safe defaults. Remaining implementation/provider specifics must be settled **by auditing code and writing tests**, not by opening a broad new business discovery:

- Exact account mapping, document/state transition table and revenue recognition dates; derive simple conventions consistent with the requirements and document them.
- Specific deterministic fee/tax/discount ordering and rounding residual rule per versioned contract; no hidden floating-point behavior.
- Which existing gym/program state can safely establish coach entitlement without new attendance tracking; authorized manual fallback.
- Selection and contractual capabilities of an **actual Iran payment provider** (online payments can remain behind a disabled adapter until checked).
- Actual numerical pricing, limits and monetization experiments: **Superuser-configurable, not hard-coded defaults**.

**Stop condition:** A required financial action cannot be represented without falsifying an existing ledger, bypassing permission scope or making an unsupported legal/payment assumption. Report the precise blocker and smallest safe option.

---

**Final verdict:** **Business scope is clear enough to draft the detailed technical PRD and begin the audited implementation process.** The repository's technical readiness, banking integration and production readiness still require evidence. The smallest trustworthy finance module is the target—not maximum feature count.


---

# FULL FUNCTIONAL PRD — the binding implementation annex

## 11. Document authority, definitions, boundaries

**Priority if any sentence conflicts:** (1) explicit user-approved decisions #1–#92 and post-#92 monetization addendum; (2) the scope/out-of-scope declarations in this file; (3) concrete acceptance tests; (4) implementation examples/defaults. A mere illustration never overrides an approved rule. An external provider/legal requirement must be verified before enabling that integration; never silently invent it.

**Business:** ASCORA provides gym/reservation management with embedded finance. **Gym / branch = tenant accounting boundary**. A branch's sales proceeds are owned/received by the gym, not by ASCORA. Separate ASCORA platform subscription/fee receivables from customer charges in every DB query and report. Multi-branch owners can aggregate authorized branches **for reporting**, not pool individual branch cash or journal entries. There is no general financial marketplace or custody feature.

**Three distinct concepts that MUST NOT be confused:**

1. Existing `GymMembership` is **user's identity/role membership** (`GYM_ADMIN`, `COACH`, `ATHLETE`) in a gym. Preserve it; it is not a paid product.
2. A **Paid Gym Membership / Member Service Entitlement** is a *commercial sale/access period* purchased by an athlete; reference existing user/gym/program data without redefining login roles.
3. An **ASCORA Platform Subscription** is the optional *B2B billing arrangement* between ASCORA and a gym/branch. It may be absent entirely (commission-only/free). It is unrelated to the athlete's purchased membership.

**Names used below:** `Tenant` = gym or branch; `Customer` = athlete or authorized service buyer; `Payee` = gym/coach/ASCORA as a contractual accounting recipient, **not an automatic banking beneficiary**; `Receipt` = asserted/verified money received; `Allocation` = contractual breakdown, not actual transfer; `Vesting` = when a calculated share becomes contractually earned; `Settlement` = recorded and, only if verified, completed payment between parties; `Customer advance` = refundable/allocatable liability *inside that one gym*, not a transferable wallet.

**User-facing language:** Persian, RTL, current Vazirmatn/Material 3, Jalali date UI, integer-rial accounting with a user-configurable Rial/Toman display. **Do not silently round away a non-multiple-of-10 rial amount when showing tomans.** Store instants in UTC and compute reporting boundaries using configured gym timezone.

### 11.1 Explicit business sign-off (three lenses)

| Role | Approval of user-defined business scope | Essential constraint |
|---|---|---|
| Business Manager | **APPROVED**: gym revenue and ASCORA's actual cash receipts/receivables are separate; revenue models can be changed from Superuser UI. | Check collectibility of commissions, gym cost-to-serve, debt and offboarding; no mandatory plan price. |
| Business Analyst | **APPROVED for PRD and audited implementation**: money states, permissions, historical contracts, failure handling and acceptance cases specified here. | Preserve accounting integrity and trace all 92 decisions. |
| Product Strategist | **APPROVED**: simple gym business-management finance with future reservation reuse. | No fintech, no ERP/payroll, no generic rule engine, no building future reservation app now. |

**Technical readiness sign-off is intentionally separate**: code, production services, legal compliance and real gateway behavior need on-device and staging evidence. These three perspectives are analytical reviews, not independent human or legal certifications.

## 12. Functional requirements — minimal bounded implementation

Each `FR` ID is stable and used by the decision matrix and tests. These are logical modules **inside the current monolith**, not mandatory microservices or one-table-per-term instructions.

| ID | Implementable behavior | Critical acceptance condition |
|---|---|---|
| `FR-CONF` | Finance on by default, *only* global Superuser may disable/re-enable per gym. Disabled mode is read/export-only for existing records; no new financial postings. | Other roles cannot change flag. Records persist; to resolve a pending financial obligation, Superuser re-enables before posting. |
| `FR-TENANT` | Independent branch ledger, invoice sequence, debts, receivables/payables and settlements. Authorized owners see *read-only financial aggregation* across their branches. | No cross-tenant leakage; aggregation cannot create merged accounting entries. |
| `FR-AUTH` | Gym-owner/admin scoped controls, staff permission grants by gym and monetary limits, coach-own records, athlete-own records, **global Superuser full read/write/access** to all financial documents/details across all tenants. | Server-side authorization on every endpoint; Superuser allowed to act alone with an audit trail, but still uses corrective journal for posted records. |
| `FR-SALE` | Sell subscriptions/memberships, training programs, private sessions, session packs, reservation services, physical goods and other custom items; bundle line pricing/discount allocation; optional standalone sale or income. | Line-item type sets relevant policy; physical goods sale/return works **without inventory**; no accidental duplication of athlete/program entities. |
| `FR-INVOICE` | Draft, issue, branch-scoped sequential final numbering, payment balance, installments/due dates, linked void/correction; never directly edit/delete issued or paid invoice. | Issued invoice immutability; correction links original; no reused number; no incorrect 'paid' state on partial receipt. |
| `FR-PAY` | Cash, card terminal, bank transfer, optional verified online; staff-entered receipt and optional proof; different declared/verified/reconciled facts; allocate a single receipt to multiple invoices. | Paid amount is not over-allocated; unknown gateway outcome remains pending; webhook/API retries cannot double-post. |
| `FR-CREDIT` | Deposits and overpayment become **per-gym customer advances**; allocate to future invoice or refund with audit. | Credit cannot move between customer accounts or gyms; liabilities reconcile; never described as transferable wallet. |
| `FR-AR` | Installments, partial payment, due/overdue state, gym-configured access requirement and simple reminders. | Amount outstanding = invoice payable less confirmed allocations and valid credits/corrections; overdue does not silently cancel service. |
| `FR-MEM` | Paid athlete membership: effective date at payment, chosen future date or after current term; manual renewal, basic reminders, configurable access with down payment, freeze/cancel/transfer/refund rules. | Distinct from role membership; gym policy governs status/refund; no attendance/usage tracking demanded. |
| `FR-REF` | Authorized partial/full refunds, reason and channel, original method preferred, other method documented with approval. Gym refunds customer when coach was previously settled, and handles coach discrepancy manually. | Correct reversal/adjustment with traceability; **no automatic clawback**. Refund cannot exceed refundable amount; legal refund rights are not blocked by product limitations. |
| `FR-LEDGER` | Small internal double-entry journal: balanced atomic posting, immutable finalized rows, open/closed periods, tracked opening balances and corrections in an open period. | Debits equal credits per journal; every posted business event has traceable entries; no edit-in-place or direct SQL deletion from UI. |
| `FR-EXP` | Gym operating expenses including category, date, amount, counterparty, payment method, description, optional proof, simple recurrence; fixed coach-period compensation may be payable with zero sales. | Unpaid expense and paid expense shown separately; recurrence cannot duplicate on retry. |
| `FR-AG` | Versioned, dated contract/commission rules (gym, item/service, source of acquisition, recipient, formula, caps), custom > permitted service overrides > defaults; ASCORA fee rules editable only by Superuser. | Sale snapshots applied agreement, rules and acquisition source; no retroactive changes to finalized transactions. |
| `FR-SHARE` | Direct or waterfall allocation; percentage/fixed/combined where agreed; multiple bounded payees; discount funding per contributor, tax/gateway treatment defined per contract, integer rounding. | Per-item allocations total exact distributable base; neither double counting nor negative surprise payouts; installments allocate on **confirmed collected proportion** subject to vesting. |
| `FR-COACH` | Coach per-sale %, per-program fixed, per-session fixed, periodic fixed, approved combinations; vest at contract event/time or authorized manual attestation. Missing agreement leaves entitlement unresolved, not 0. | 'Calculated' != 'vested' != 'payable'; coach sees only own breakdown, even across multiple gyms. |
| `FR-SET` | Weekly default configurable settlement cycle, manual/partial batch, recipient/payer/date/method/reference, draft/recorded/verified states, negative balance/manual permitted offsets. | 'Recorded' never falsely appears 'paid'; confirmed settlement must have credible proof/reference; payout cannot exceed available balance. |
| `FR-RECON` | Cash/bank reconciliation with manual matching or statement-file import first. | Confirmed payment and 'bank reconciled' are distinct; exceptions visible and traceable. |
| `FR-PLAN` | **Zero or more** optional ASCORA subscription plans; Superuser create/edit/activate/deactivate with versioned effective dates/limits; Starter/Pro/Growth optional examples. Per-branch default plan, group custom billing and volume discounts, individual allocation. | **Commission-only with zero active plans must work**; changing plans never deactivates gym finance or loses history. |
| `FR-FEE` | Platform revenue modes: free, subscription-only, commission-only, hybrid, custom; configurable per sale/source/service/branch; offline eligible fee becomes invoiced receivable; platform dues follow reminder/grace/restriction process. | No automatic fee on all recorded sales; platform **cash received** != gym gross sales; overdue restrictions never erase old records. |
| `FR-PORTAL` | Task-first finance interfaces: Gym Admin + delegated staff, Superuser complete finance/control, coach personal earnings, athlete invoices/installments/receipts/refund requests + authorized third-party payer without profile access. | Each user's visibility enforced at API and UI levels; mobile-first coach/athlete. |
| `FR-REPORT` | Gym daily confirmed collections, sales, overdue, renewals, coach payables, expenses, approximate operating profit; Superuser subscription MRR (when applicable), collected platform fees, debts, cost-to-serve, branch contributions. Export. | Labels never conflate collected money, invoiced totals, recognized income, estimated profit, or payables. |

### 12.1 Nonfunctional requirements and mandatory controls

- Use existing FastAPI/SQLModel/PostgreSQL/Alembic and React/TypeScript/TanStack; existing auth, `GymContext` and gym-scoped checks; reusable Material 3 UI. Do not add second app/auth service.
- Atomic DB transaction for journal + business record; idempotency unique keys/provider IDs and DB locks/constraints for concurrent number generation and allocations. Backend is the financial authority; front-end values are display only.
- Database-stored immutable posted journals with a reasoned reversal/adjustment path and audited sensitive actions. Store actor, tenant, timestamp, type, linkage and reason. Protected exports and archived evidence per existing security controls.
- Never depend on a scheduled job to make a *single* money movement correct. Simple overdue/renewal reminders may be scheduled; duplicate sends/recurrent expenses must be idempotent.
- Backups and an **actually tested restore**, error monitoring and least-privilege DB credentials before real financial production. Detect failed transaction verification; never mark as successful on timeout.
- No hardcoded plan count or percentages: configurability exists in normal Superuser UI/API, without editing source code.

## 13. End-to-end workflows, states and screen map

### 13.1 Gym Admin + authorized staff: invoice / payment / membership

1. In a selected gym, gym admin creates a catalog item or custom sale; selects athlete/customer, goods/service and line policies; optionally creates a multi-item package. **No athlete identity role is created automatically by a sale unless existing onboarding explicitly requires it.**
2. Add line discounts, funded-by allocations, taxes/fees only as configured, due dates or installment schedule. Preview net bill and contractual shares **before** issue; an unresolved coach agreement is visibly marked.
3. Issue invoice: immutable line snapshots, valid unique branch sequence, audit and ledger posting appropriate to recognition policy. A draft can be edited or discarded; an issued document can only be corrected via linked document.
4. Choose payment: authorized user records cash/POS/bank with method and optional proof; online checkout appears **only if a real integrated, validated provider has been enabled**. An authorized manual cash/POS/transfer receipt can be confirmed **by the authorized operator's attestation**, with verification source recorded; bank/cash reconciliation remains an independent later state. Online receipts may be confirmed **only** after genuine provider verification.
5. One confirmed receipt may be allocated to multiple invoices; residual can be customer advance (per gym), but cannot silently disappear or transfer gyms. Partial installment still shows due and access rules.
6. A paid gym membership's start/freeze/renewal/access is updated according to its **paid commercial contract**, independent of `GymMembership` (the existing role assignment).
7. Gym Admin can view outstanding debts, receipt status and member payment history; refund requests follow explicit authorization/refund process.

### 13.2 Coach earnings and payout

1. On sale, determine applicable snapshot agreement. If absent, mark the coach allocation unresolved and forbid payout until resolved, without blocking gym payment intake.
2. When a confirmed receipt arrives, calculate the portion earned/allocated under the specific agreement and its vesting rule (delivery status if already available, elapsed contractual date, or authorized manual confirmation). **Do not implement new usage tracking.**
3. Show separate values `calculated`, `vested`, `eligible for settlement`, `recorded payout` and `confirmed paid`. Each coach sees own items within each assigned gym, plus authorized personal aggregate.
4. Default settlements weekly; authorized gym finance operator can batch, record proof, partially settle, verify, reconcile. If paid coach share is followed by customer refund, the gym executes refund and manually resolves discrepancy—no automatic negative transfer from coach.

### 13.3 ASCORA Superuser: monetization and oversight

1. Superuser may leave all subscription plans disabled or create/configure new plans (Starter/Pro/Growth are names, not immutable code constants). Plan changes have validity dates, limits, versions and audited revisions.
2. Select per-gym or group commercial arrangement: free, plan fee, eligible commission, hybrid or negotiated custom; configure item/source fees, permitted caps/rounding, effective date, discounts and billing recipients. Group invoices are **ASCORA platform bills**; they do not merge branch financial ledgers.
3. For confirmed eligible gym sales, calculate platform receivable according to snapshotted terms, **not cash received**. For offline sales, bill the contractual fee on schedule. Mark platform collected only when actually paid/verified. Handle overdue via notices, grace and graduated restrictions; keep finance-history access and outstanding obligations.
4. Superuser has **full visibility and operations** across all gyms and sensitive documents, including adjustments; actions still generate proper audit and linked correction journals.
5. Monitor platform revenue separate from gym revenue, active gym agreements, monthly recurring subscription revenue (zero if no subscriptions), fees actually collected and gym-level cost-to-serve.

### 13.4 Athlete: self-service

Athlete's own scope contains invoice balance, installments, due dates, confirmed/unconfirmed receipts, renewal, refunds and downloadable receipts. Athlete may request refund under gym policy and initiate payment when a provider exists. A third-party payer can use a limited-purpose payment link or code if the existing authentication/security conventions safely support it; the payer does **not** gain athlete profile or program access. No need to build stored-value wallet.

### 13.5 Minimum UI routes / screens (reuse current router conventions)

| Persona | Screen(s) | Primary actions |
|---|---|---|
| Superuser | Platform finance overview; plans/monetization; branch/group contracts; platform invoices and payments; gym finance drill-down | Create/activate/deactivate plans, customize commission, inspect all documents/transactions, issue platform statements, authorized corrections. |
| Gym Admin | Finance overview; catalog/sales; invoices/payments; receivables/installments; expenses; coach agreements/settlements; reports/settings | Issue invoice, register and reconcile receipt, refund/adjust, configure membership policies, delegate limited staff permissions, close period. |
| Finance staff | Same screens **only if permission permits**, otherwise subset | Record payments, view assigned reports/expenses, never access forbidden actions. |
| Coach | My Earnings / Settlements (per gym and own aggregate) | View allocations, payable/pending/paid breakdown, settlement evidence. |
| Athlete | My Payments / Membership / Invoices | Pay when supported, view installments, renew, inspect receipts, request refund. |

Use an obvious status/empty state and avoid duplicate navigation across global/gym contexts. Do not build extra admin consoles for hypothetical future customers.

### 13.6 Separate state machines (illustrative normalized statuses, not compulsory exact DB enum names)

| Domain | Useful lifecycle | Guardrail |
|---|---|---|
| Invoice | `draft → issued → partially_paid → paid`; issued invoice can be `voided/corrected` **by linked posting** | `overdue` computed from due date + balance; refunds are separate linked records, not edits. |
| Payment | `initiated/recorded → pending_verification → confirmed` or `failed/reversed` | Operator-recorded cash and gateway-confirmed cash have different verification evidence; bank reconciliation is another dimension. |
| Refund | `requested → approved/rejected → recorded → confirmed/failed` | Authorization + policy + amount ceiling. A completed refund posts reversal/adjustments; gym bears external payout obligation. |
| Coach allocation | `unresolved → calculated → vested → eligible → settled` (where relevant); adjustments append entries | An incomplete coach contract cannot become eligible; a recorded payout is not settled until confirmed. |
| Settlement | `draft → recorded → confirmed/reconciled` or `canceled` before confirmation | Payee, payer, amount, date, method and reference/proof tracked. |
| Platform agreement | `draft → effective → expired/replaced/disabled` | Version history and sale snapshot immutable; plan disabled prevents new assignment but does not rewrite old obligations. |
| Financial period | `open → closed` | Late corrections post to currently open period and reference original closed-period document. |

States may be stored or derived as appropriate; do not store conflicting redundant statuses if safe derivation suffices. Do not assume **an invoice becoming paid automatically proves the service was delivered**.

## 14. Deterministic financial calculation policy and examples

### 14.1 Contract-driven order (implements #21, #24, #66, #77, #78, #80)

1. Finalized sale snapshots line-item base amounts, discount per line and proportional package discount (unless authorized line override), provider/tax settings **if actually supported**, acquisition source and effective contract versions.
2. Calculate integer-rial payable and confirmed receipt allocation; unpaid installments stay receivables, not settled amounts. `payment allocated to invoices ≤ confirmed receipt` and `cumulative allocations ≤ invoice payable` (excluding properly accounted linked credit/refund adjustments).
3. Compute each applicable fee/split **using the precise ordered formula stored in the relevant effective contract**: direct or waterfall, percentage/fixed/combined, discount sponsor, tax treatment, gateway fees, and designated residual recipient. No platform-wide tax percentage or fee is presumed.
4. For fractions use exact integer rational/decimal arithmetic with deliberate rounding policy, **never float**. Residual distribution is deterministic, assigned to the contracted residual beneficiary so the final component totals equal the distributable base **to the rial**. If terms don't specify a recipient, require the operator/Superuser to define it **before an affected agreement is activated**, rather than silently bias a coach/platform share.
5. For an installment, allocate only the portion attached to **confirmed collections**, subject to share vesting. For fixed-per-program/session and combinations, do not apply a percentage-only formula blindly. Cap cumulative earned/payable share at contracted maximum for that sale and correct through appended entries when necessary.
6. A refund or cancellation creates linked reversal/adjustment; if coach already received payout, gym refunds customer and unresolved contractual difference stays visible for authorized **manual** resolution.
7. When a payer/source or contract changes later, **do not retroactively recompute prior finalized sales**. A legal/manual correction is a linked document with actor, reason and date.

**Working arithmetic example — only where a program is fully delivered/recognized and the whole 1,000,000 IRR is confirmed collected:** contract direct distribution: gym 60%=600,000 IRR, coach 30%=300,000 IRR, ASCORA commission 10%=100,000 IRR. Gym holds collected funds and **owes** coach/platform amounts; it does not mean software transfers those amounts. Gross gym-facing sale 1,000,000 IRR is **not** platform revenue; ASCORA's fee receivable is 100,000 IRR, but platform cash received is 0 until actually collected. VAT, payment-provider fees, discounts, credits and deferred-service recognition are omitted **solely for this illustrative example**, not automatically assumed absent in real scenarios.

**Minimal refund/freeze calculation convention (only where the gym selected a time-proportional rule):** Proposed unused-time refund is based on the **actually received, refundable net amount** attributable to the unused interval, proportional to unused eligible days against total covered days, minus only configured, contract-permitted nonrefundable fees; clamp between zero and the remaining refundable paid amount after earlier refunds. A *no refund*, *fixed amount* or *authorized manual override* policy must use its own snapshot rule. For session/package goods refunds, use the explicitly configured policy and supporting records, not fabricated attendance data. Always preview the calculation and require authorized approval; no automatic payout.

**Correct basic journal semantics (when transaction is recognized):** invoice may debit gym receivable and credit a sale revenue or unearned revenue liability according to service recognition policy; receipt debits gym cash/bank and credits receivable; coach commission/payroll-like liability and ASCORA platform fee liability arise per effective terms, with matched gym operating expenses where applicable. ASCORA's own platform record is **separate**, not an additional 100,000 of gym cash. This is conceptual double-entry guidance: account chart and revenue recognition must be validated for the actual business workflow/provider without imposing a full statutory accounting engine.

### 14.2 Exact money invariants

- `gross_line - allocated_discounts + configured_taxes/charges = invoice_payable` according to contract-defined incidence and tax calculation; report components transparently.
- `invoice_outstanding = posted_payable - confirmed_allocated_receipts - valid_applied_advances - authorized_credit_adjustments` (with linked reversals properly signed). Never allow unexplained negatives; excess cash becomes customer advance or an authorized refund.
- `sum(payment_allocations) ≤ confirmed_receipt_amount` at all times; a receipt can cover several invoices **of that same gym**.
- `sum(allocated_recipient_shares) = distributable_base` for **resolved** allocation, per confirmed applicable tranche, without counting the gym's remaining share twice.
- `sum(debits) = sum(credits)` for every posted journal and across tenant accounts; corrections/reversals themselves balance and reference prior postings.
- Plan and platform fee calculations cannot consume or overwrite a gym's own accounting cash balance. Fees from the gym are a separate payable until paid.
- `estimated operating profit` is labeled estimated: **recognized revenue minus recognized operating expenses (including incurred coach/platform costs), without subtracting the related payables a second time**. Cashflow, receivables and payables have separate metrics; do not invent unrecorded expenses or platform cost-to-serve figures.

## 15. Minimal data model & API contract — align with actual code first

**Important:** Logical records below are **not** a mandate to create an equal number of tables or new services. OpenCode must reuse existing `Gym`, `User`, `GymMembership`, `AthleteProfile`, `CoachAssignment`, `WorkoutProgram` and authentication/tenant context wherever appropriate.

| Logical record | Essential data; indexing/constraints |
|---|---|
| Tenant finance settings | `gym_id`, enabled, Rial/Toman display, timezone/period policy, refund/access policy version. Only Superuser may toggle enabled. |
| Finance permissions | `gym_id`, user/role, action permission, optional amount limit and audit; reuse current role checks. |
| Catalog / offer / bundle | Tenant, service type, price, display title, optional linked training program/session/product, applicable contract/discount rules; no inventory ledger. |
| Invoice + invoice line | Tenant, customer, payment terms/due dates, line snapshot, calculated total, immutable issued sequence, contract source/date, original invoice linkage for corrections. |
| Payment receipt + allocations | Tenant, payment method, declared/verified/reconciled stages, provider or staff reference, idempotency key, each invoice allocation; DB uniqueness preventing duplicated confirmed receipt. |
| Advance / refund | Tenant/customer liability balance, allocated/refunded amounts, original payment/invoice links, authorized operator and reason. No cross-customer/tenant transfer. |
| Journal / journal line | Tenant, posting date, period, actor, event type, source doc ID, reversal-of ID; account, debit/credit integer IRR; transactionally balanced. |
| Expense / period / opening balance | Tenant, document evidence, recurring schedule key when used, financial period state, opening value and approval/correction. |
| Coach agreement / allocation / settlement | Tenant, coach, source sale, contract version, trigger, vesting/eligibility, allocated amount and settlement state/proof; multiple payees within bounded scope. |
| Platform plan / gym contract / group contract | Superuser-managed catalog with **0 plan records allowed**, effective-dated revisions, priced features/limits, group invoicing plus per-branch cost allocation; separate platform receivables. |
| Audit records | Who/what/when/where/reason/result for sensitive changes, minimal necessary information, consistent with current audit infrastructure. |

**Required constraints:** Tenant/gym ID on every tenant-owned financial record and every scoped query; foreign keys prevent cross-gym invoice allocation; unique `(gym_id, issued_invoice_number)`; unique external `(provider, transaction_reference)` within correct scope; unique idempotency token per operation scope; DB constraints for nonnegative individual receipt/invoice allocation; locked sequence generation in transaction; paid/posted historical data immutable via application path and protected permissions.

**API architecture:** Extend existing FastAPI `api/v1` style with gym-context dependencies and Superuser authorization. Prefer focused route groups (`finance`, `platform_billing`) only if existing project conventions support them. For each write endpoint, enforce server-side gym scope, permissions, input validation, optional idempotency and documented status/error codes. Regenerate existing typed frontend client through existing OpenAPI process if applicable; no parallel invented client model. Do not select an Iranian payment gateway by assumption; an offline/manual first slice is valid. Online gateway requires later provider selection/contract/compliance verification and a signed, idempotent callback.

### 15.1 Repository integration facts (read-only remote observations — not local certification)

Checked public GitHub repository: `sajjadatma/gym-app`, `main` (branch SHA previously observed `f3b37bce41`), plus tree snapshots for `deploy/vercel-pilot` (`a31aefe3b3`) and `feat/standard-motion-system` (`eaf0309859`) on **2026-11-02**.

- `README.md`: FastAPI / SQLModel / PostgreSQL / Alembic; React 19 / TypeScript / Vite / TanStack Router; Material Design 3/Vazirmatn; gym role and workout program product; Vercel/Neon deployment documented.
- `backend/app/models.py`: existing `Gym`, `GymMembership`/`GymMembershipRole`, `CoachAssignment`, `AthleteProfile`, `WorkoutProgram` models; **the existing GymMembership is role membership, not a paid subscription**.
- `backend/app/api/deps.py`: existing `GymContext`, Superuser checks and `require_gym_admin`/staff-style authorization points — **reuse them** and extend with financial permissions; do not make gym admin globally privileged.
- `backend/app/api/routes/gyms.py`: existing gym membership/user-management flows; do not change their meaning to implement billing.
- `backend/app/alembic/versions/`: existing migrations for MVP gym/program, identity, auth and related functionality. New finance schema must be a compatible additive migration rather than replacing core tables.
- Examined remote tree branches had **no specifically finance-named routes/migrations**. This is limited evidence, **not proof no finance code exists anywhere** (especially not in local uncommitted working copy).
- Existing release docs report security hardening, automated tests and staging/production verification history; **do not copy prior historical PASS counts as the current baseline**. Re-run tests against checked-out branch and investigate all current failures before coding.

**Mandatory audit output before code:** `repository branch/SHA + git status`, existing route/model/migration/tests inventory, current auth/role rules, existing financial features if any, snapshot of test failures, protected deploy/merge mechanism, and 1-page `already exists / modify / add / defer` gap table mapped to the FR IDs. If local branch differs from remote, **local branch wins**. Do not replace uncommitted work.

## 16. Complete decision traceability: #1–#92 and the additional monetization decision

`Approved` means the user's explicit yes or amended approval, **not** that the code has been implemented. `Deferred` means explicitly excluded from current version. Every row references at least one functional requirement or guardrail to verify in tests.

| Decision | Status | Binding requirement / where verified |
|---|---|---|
| 01 | Approved | Embedded operational management finance, `§11`, `FR-CONF`. |
| 02 | Approved | Not fintech/custody, `§11`, `FR-PAY`. |
| 03 | Approved | Gym is sales recipient, `§13`, `FR-PAY`. |
| 04 | Approved | Initial target small/medium gyms in Iran, release pilot `§18`. |
| 05 | Approved | Finance on by default; only Superuser can turn off, `FR-CONF`. |
| 06 | Approved | Gym is primary payer for ASCORA commercial service, `FR-PLAN`. |
| 07 | Approved | Starter/Pro/Growth as optional examples after addendum, `FR-PLAN`. |
| 08 | Approved | Free offering may have configurable limits, `FR-PLAN`. |
| 09 | Approved | Commission scope configurable by revenue/service category, `FR-FEE`. |
| 10 | Approved | Commission rules/source-of-customer configurable, `FR-FEE`. |
| 11 | Approved | Offline sale may incur contractual platform receivable billed later, `FR-FEE`. |
| 12 | Approved | Standard/custom effective-dated contracts preserve history, `FR-AG`. |
| 13 | Approved | Membership/program/session/product/reservation/custom catalog, `FR-SALE`. |
| 14 | Approved | Product type-specific financial policy over common invoice/payment, `FR-SALE`. |
| 15 | Approved | Manual renewal/basic reminder; automated charge only if approved infrastructure, `FR-MEM`. |
| 16 | Approved | Freeze/cancel/transfer/refund gym-configurable, `FR-MEM`. |
| 17 | Approved | Bundles with separate per-line values and share, `FR-SALE`. |
| 18 | **Deferred** | No usage/attendance tracking for finance; `§3` / `§13.2`. |
| 19 | Approved | Coach %/per-program/per-session/fixed periodic/mixed compensation, `FR-COACH`. |
| 20 | Approved | Direct vs waterfall split, `FR-SHARE`. |
| 21 | Approved | Split base after discount; taxes/provider fees contract-dependent, `FR-SHARE`. |
| 22 | Approved | Separate vesting time and collected money, `FR-COACH`. |
| 23 | Approved | Financial snapshots, no backward recalculation, `FR-AG`. |
| 24 | Approved | Discount funding by gym/coach/platform/combinations, `FR-SHARE`. |
| 25 | Approved | Cash/POS/transfer/online payments, `FR-PAY`. |
| 26 | Approved | Authorized manual receipt with optional proof/extra approval, `FR-PAY`, `FR-AUTH`. |
| 27 | Approved | Installments/partial receipts, balances and access policy, `FR-AR`. |
| 28 | Approved | Pending/confirmed/failed/reversed + idempotency/provider verification, `FR-PAY`. |
| 29 | Approved | Authorized partial/full refund and audit, `FR-REF`. |
| 30 | **Deferred** | No automatic post-payout coach clawback, `§3` / `FR-REF`. |
| 31 | Approved | Light internal double-entry ledger, `FR-LEDGER`. |
| 32 | Approved | Invoiced/collected/recognized/payable distinct, `FR-LEDGER`, `FR-REPORT`. |
| 33 | Approved | Weekly default; manual/partial/configurable settlement, `FR-SET`. |
| 34 | Approved | Platform overdue notice/grace/gradual restrictions, `FR-FEE`. |
| 35 | Approved | Negative coach balance/unpaid debt visible; contract-only offset, `FR-SET`. |
| 36 | Approved | Manual/imported bank/cash reconciliation, `FR-RECON`. |
| 37 | Approved | Operating income/expense/debt/profit + accountant export, no general accounting, `FR-REPORT`. |
| 38 | Approved | Delegated gym-scoped finance staff permissions, `FR-AUTH`. |
| 39 | Approved | Coach own gym/cross-gym earnings only, `FR-PORTAL`. |
| 40 | Approved | Athlete receipts/invoices/installments/refund request/third-party payer, `FR-PORTAL`. |
| 41 | **Approved as amended** | **Global Superuser FULL access to all financial records and sensitive details**, `FR-AUTH`. |
| 42 | Approved | Sensitive transaction approvals and amount limits, `FR-AUTH`. |
| 43 | Approved | Gym action-first finance dashboard, `FR-REPORT`. |
| 44 | Approved | ASCORA own revenue/MRR/collected fees/receivables/cost-to-serve, `FR-REPORT`. |
| 45 | Approved | Simple mobile-first coach and athlete finance views, `FR-PORTAL`. |
| 46 | **Deferred** | No advanced/smart analytics or AI automation; basic reminders retained, `§3`. |
| 47 | Approved | Shared multi-tenant engine, isolated branch records, full SU, `FR-TENANT`. |
| 48 | Approved | Future reservation reuse of primitives, not build now, `§11`, `§15`. |
| 49 | Approved | Atomic DB, idempotency/concurrency/error logging and tests, `§12.1`, `§17`. |
| 50 | Approved | Backups, restoration drill, monitoring, safe unknown payments, `§18`. |
| 51 | Approved | Gradual additive migration, opening balances, verified history only, `§15`, `§18`. |
| 52 | Approved | Incremental staged delivery and gate per slice, `§6`, `§18`. |
| 53 | Approved | Pilot 3–5 distinct gyms, `§18`. |
| 54 | Approved | Financial integrity, refunds, tenant tests, restore, pilot criteria, `§17`, `§18`. |
| 55 | Approved | Export/offboarding with retention and ongoing obligations, `FR-REPORT`, `§18`. |
| 56 | Approved | Iran-specific contract/privacy/tax/provider checks before real-money launch, `§18`. |
| 57 | Approved | Each branch separate ledger and authorized consolidated reporting, `FR-TENANT`. |
| 58 | Approved | Branch subscription by default, optional group contract/discount/invoice, `FR-PLAN`. |
| 59 | Approved | Disabled finance allows read/export only, `FR-CONF`. |
| 60 | Approved | Integer IRR persisted, Rial/Toman display, `FR-LEDGER`. |
| 61 | Approved | Jalali interface, gym timezone, reports per selected range, `FR-REPORT`. |
| 62 | Approved | Manual standalone income/expense/sale with categories, `FR-SALE`, `FR-EXP`. |
| 63 | Approved | Paid membership effective payment/future/after prior term, `FR-MEM`. |
| 64 | Approved | Access after complete/minimum downpayment or admin approval, `FR-MEM`. |
| 65 | Approved | Freeze/cancel/refund calculations under gym rules + approval, `FR-MEM`. |
| 66 | Approved | Proportional bundle discount default; optional line allocation, `FR-SALE`. |
| 67 | Approved | Physical goods sale/return only; no inventory, `FR-SALE`. |
| 68 | Approved | Per-customer, per-tenant advance/overpayment credit, not wallet, `FR-CREDIT`. |
| 69 | Approved | Manual receipt valid as declaration; bank/cash reconciliation separate, `FR-PAY`. |
| 70 | Approved | One confirmed payment splits across many same-gym invoices, `FR-PAY`. |
| 71 | Approved | Late installment reminders and service restriction only if package policy, `FR-AR`. |
| 72 | Approved | Refund original route preferred; alternative authorized/reason, `FR-REF`. |
| 73 | Approved | Gym customer refund obligation after coach paid; manual contractual resolution, `FR-REF`. |
| 74 | Approved | No direct edit/delete issued/paid invoice, new linked corrective doc, `FR-INVOICE`. |
| 75 | Approved | Missing coach agreement => unresolved not 0, `FR-COACH`. |
| 76 | Approved | Limited multiple payees with validated share sum, `FR-SHARE`. |
| 77 | Approved | Installment shares on confirmed collected tranches plus vesting, `FR-SHARE`. |
| 78 | Approved | Contract precedence and Superuser-only platform fee control, `FR-AG`. |
| 79 | Approved | Acquisition source on creation/sale, snapshotted and audited changes, `FR-AG`. |
| 80 | Approved | Deterministic contractual discount/tax/fee/split order and rounding, `§14`. |
| 81 | Approved | Settlement parties, amount, date, method, reference and approval, `FR-SET`. |
| 82 | Approved | Weekly default eligibility and contractual hold period, `FR-SET`. |
| 83 | Approved | Periodic coach fixed obligation even without a sale, `FR-COACH`, `FR-EXP`. |
| 84 | Approved | Recognized revenue less costs/related obligations, **estimated** operating profit, `FR-REPORT`. |
| 85 | Approved | Expense category/amount/time/counterparty/method/proof/recurrence, `FR-EXP`. |
| 86 | Approved | Financial period closing, late correction in open period, `FR-LEDGER`. |
| 87 | Approved | Tenant unique sequential final invoice numbers not reused, `FR-INVOICE`. |
| 88 | Approved | Gym Admin approves opening balance, Superuser correction with audit, `FR-LEDGER`. |
| 89 | Approved | Superuser can act without second person's approval; audited, `FR-AUTH`. |
| 90 | Approved | Granular actions and amount limits for staff, `FR-AUTH`. |
| 91 | Approved | Plan limits for active athletes/seats/features/SMS/storage, configured after pilot, `FR-PLAN`. |
| 92 | Approved | Release requires tested ledger/payments/refunds, privacy/tenancy, restore, legal and real pilot, `§18`. |
| `ADD-01` | **Approved** | **Revenue-model-agnostic Superuser controls:** optional/zero plans, free/subscription/commission/hybrid/custom, configurable rates/categories/sources, historical preservation, `FR-PLAN`/`FR-FEE`. |

### 16.1 Coverage audit instruction

OpenCode must create a minimal checklist with each decision number and the related FR/test evidence (or `deferred`). **Do not mark a decision implemented merely because it appears in this document.** Any feature postponed to a later implementation slice remains `planned`, never `passed`. If a decision would require a new, unapproved business behavior, choose a conservative non-destructive default and flag a *specific* blocker rather than expanding scope.

## 17. Acceptance scenarios / test contract

The following cases are **required outcome tests**. OpenCode may implement the most economical unit/API/Playwright combination, but must not skip failure paths that can misstate money. Use disposable Postgres and test files only.

| Test ID | Given / action | Expected result / FR |
|---|---|---|
| `AC-01` | New gym created with no finance override | Finance enabled by default; only Superuser can change enable flag (`FR-CONF`). |
| `AC-02` | Superuser disables finance with outstanding invoice + refund | No new posting; all original records read/exportable; re-enabling allows properly authorized correction (`FR-CONF`). |
| `AC-03` | Admin/staff from gym A uses gym B invoice ID or payment ID | 403/404 safe response; zero information leakage or ledger mutation; Superuser can access both (`FR-AUTH`, `FR-TENANT`). |
| `AC-04` | Owner owns gym A+B, not C | Consolidated authorized view A+B only; A/B individual ledgers preserved, no access to C (`FR-TENANT`). |
| `AC-05` | Superuser opens detailed sensitive financial document across gyms and performs correction | Full access allowed; immutable correction journal and audit created (`FR-AUTH`). |
| `AC-06` | Cashier without refund/contract permission tries refund or percent change; amount over approval limit | Server rejects despite UI manipulation (`FR-AUTH`). |
| `AC-07` | Gym role membership exists, no paid athlete membership | Existing gym role/access is unchanged; commercial enrollment starts only via legitimate sale/administrative process (`FR-MEM`). |
| `AC-08` | Program/physical goods/private session/reservation custom item sold | Correct item type, line value and contract context; no inventory subsystem (`FR-SALE`). |
| `AC-09` | Bundle 2+ lines with single discount and optional override | Default discount proration exact to rial; manual override audited; no missing/extra discount (`FR-SALE`). |
| `AC-10` | Invoice draft edited; then issued and payment recorded | Draft editable; issued immutable; correction linked; payment balance reflects actual allocations (`FR-INVOICE`). |
| `AC-11` | Two concurrent issued invoices in same gym | Unique and non-reused sequence numbers; separate gym sequence independent (`FR-INVOICE`). |
| `AC-12` | Confirmed bank receipt allocated to 2 invoices | Sum allocated ≤ receipt, both remaining balances accurate; over-allocation blocked (`FR-PAY`). |
| `AC-13` | 200,000 IRR prepayment for 150,000 IRR bill | Remaining 50,000 IRR is customer advance liability **same gym only**, can apply or refund; never disappears (`FR-CREDIT`). |
| `AC-14` | Customer tries transferring advance to another user or gym | Rejected, no wallet-like transfer (`FR-CREDIT`). |
| `AC-15` | Duplicate payment API call and duplicate signed provider callback | One confirmed receipt and one posting, not two (`FR-PAY`). |
| `AC-16` | Gateway times out or verification fails | Pending/failed, no false confirmed receipt or access grant; can reconcile on retry safely (`FR-PAY`). |
| `AC-17` | Cash receipt entered by cashier without bank reconciliation | Declared receipt recorded under authorized action; distinct unreconciled indicator remains (`FR-PAY`, `FR-RECON`). |
| `AC-18` | Installment due; member has paid only minimum downpayment | Correct remaining debt, policy-driven membership access; reminders only, no automatic unauthorized cancellation (`FR-AR`, `FR-MEM`). |
| `AC-19` | Membership renewed before current term expires | Configured effective date and unused term preserved as selected; role membership unaffected (`FR-MEM`). |
| `AC-20` | Membership freeze/cancel with refund policy | Proposed amount from configured rules; approval, reason and linked posting; no attendance dependency (`FR-MEM`, `FR-REF`). |
| `AC-21` | Athlete requests partial/full refund | Approval policy, channel preference, refund amount ceiling and independent history hold (`FR-REF`). |
| `AC-22` | Gym refunded customer after coach payout already confirmed | Gym refund posted; coach discrepancy visibly unresolved and manually actionable; **no automated clawback** (`FR-REF`). |
| `AC-23` | Sale with no coach agreement | Sale and receipt allowed; coach share marked unresolved and cannot be settled as 0 (`FR-COACH`). |
| `AC-24` | Coach agreement changes after original issued sale | Old allocation snapshot unchanged; new sale gets new effective agreement (`FR-AG`). |
| `AC-25` | Same service has different acquisition-source and commission settings | Correct source is snapshotted for each sale; only authorized changed source has audit (`FR-FEE`, `FR-AG`). |
| `AC-26` | Split direct and waterfall, several beneficiaries, roundoff | Sum components equal correct base in integer rial; contract precedence/caps enforced (`FR-SHARE`). |
| `AC-27` | Invoice paid in 3 tranches, coach share requires vesting | No payout for uncollected or unvested portions; total cannot exceed agreed cap (`FR-SHARE`, `FR-COACH`). |
| `AC-28` | Fixed periodic coach fee without sales | A payable and expense exists with no synthetic sale or fake payment (`FR-COACH`, `FR-EXP`). |
| `AC-29` | Settlement requested then recorded but proof not verified | Visible as not yet confirmed; after legitimate verification, correct payable reduced, transaction auditable (`FR-SET`). |
| `AC-30` | Partial settlement, negative balance and prohibited offset | Balances visible; unauthorized offset blocked; no duplicate confirmation on retry (`FR-SET`). |
| `AC-31` | Bank report import with unmatched transaction | Unmatched remains visible; confirmed receipt not conflated with bank reconciliation (`FR-RECON`). |
| `AC-32` | Closed financial period, error discovered later | Original closed posting immutable; corrective posting created in open period and references original (`FR-LEDGER`). |
| `AC-33` | Opening balance entered by gym admin and corrected by Superuser | Verified opening journal and traceable subsequent adjustment, no inferred past sales (`FR-LEDGER`). |
| `AC-34` | Every posted invoice/payment/refund/settlement transaction | Balanced debit/credit journal and source linkage, zero imbalance to IRR (`FR-LEDGER`). |
| `AC-35` | No subscription plans exist, but gym commission agreement active | Gym finance works; fees accrue only for eligible contractual revenue, no subscription invoice fabricated (`FR-PLAN`, `FR-FEE`). |
| `AC-36` | Platform set to free, subscription only or hybrid | Each mode produces only its configured obligations; historical agreement preserved (`FR-PLAN`). |
| `AC-37` | Group contract for 3 gyms with volume discount | One ASCORA-side consolidated bill and traceable per-branch allocation, no merging gym ledger entries (`FR-PLAN`, `FR-TENANT`). |
| `AC-38` | Gym overdue in platform dues | Reminders/grace/restrictions as configured; historical records and athlete program history preserved (`FR-FEE`). |
| `AC-39` | Superuser changes plan availability and feature limits | Existing historical bills preserved; newly effective policies applied correctly; finance doesn't turn off (`FR-PLAN`). |
| `AC-40` | Gym dashboard/report for paid invoice, open invoice and coach payable | Separately reports sales, cash collected, recognized income, payables, approximate operating profit (`FR-REPORT`). |
| `AC-41` | Coach in gyms A and B opens earnings | Own A+B earnings shown; other coach's financial data not accessible (`FR-PORTAL`). |
| `AC-42` | Athlete opens own and another's invoice; third-party payment link used | Own allowed, another's blocked; payer cannot view athlete private profile (`FR-PORTAL`). |
| `AC-43` | Existing gym data migrated; backfill has insufficient historic evidence | Original accounts/roles/programs unchanged; only verified history imported and opening balance approved (`§18`). |
| `AC-44` | Plan expires or gym offboards | Export invoices, receipts, contracts and balances available according to policy; no obligations erased (`FR-REPORT`). |
| `AC-45` | Tests and production release attempted | CI/test, backup restore, tenant checks, verified payment provider/legal requirements and 3–5 gym pilot are preconditions; no implicit production deployment (`§18`). |
| `AC-46` | Simple debt/renewal reminders enabled while analytics disabled | Basic existing approved reminders work; no AI predictive/smart automation implemented (`#15`, `#34`, `#46`). |

**Contract test rule:** at least one negative/unauthorized test for each financially sensitive endpoint, and at least one concurrency/retry test for every pathway creating a confirmed payment, refund, invoice number or settlement. Where acceptance expects external provider verification, a stub in CI is not enough for real-money launch; verify the selected provider in staging.

## 18. Execution phases, release gates and deliverables for OpenCode

### Phase 0 — audit only (no feature code)

- Inspect **the exact local working checkout** (including uncommitted changes), Git branch, repository instructions and actual recent app behavior. Identify current regressions and do not use stale remote CI as proof.
- Identify role system, multi-gym scope, paid-membership gaps, finance schema if any, migration strategy, money type handling, existing backup and release process.
- Deliver `docs/finance/00-gap-audit.md` with one page: `{exists, reuse, add, conflict, defer}` for the `FR` set, baseline test status, critical risks and smallest safe plan. Path is a suggested location; honor repository conventions.
- Do a **self-review before writing code**: verify no requirement adds unapproved behavior, no retroactive mutation, no tenant crossover, no schema name collision, no unnecessary abstraction. Report explicit blockers for a slice; safe unrelated slices may proceed.

### Phase 1 — authoritative financial foundation

- Finance activation/read-only, tenant/permission primitives (reuse existing roles), integer IRR, period/sequence, opening balance, journal + reversal, minimal API/tests. Additive Alembic migrations with test rollback/upgrade safety.
- Gate: balanced journal, tenant isolation, migration, Superuser full access, correct default flag, no regression in existing gym operations.

### Phase 2 — invoices, manual payments, member billing, expenses

- Catalog and service/bundle sales, invoices, manual cash/POS/transfer, installments, one receipt-many invoices, customer advance, debt, paid gym membership financial policy and expenses, partial/full refund and admin/athlete screens.
- Do **not** enable actual online payment until provider and legal/preproduction check is complete; API adapter can be left disabled behind flag.
- Gate: invoice states, idempotent manual receipts, refunds, advance invariants, member access rules and preserved role membership.

### Phase 3 — coach contracts, share and settlement

- Snapshot agreements, acquisition source, direct/waterfall, multi-party allocation, coach fixed/mixed compensation, vesting/manual attestation, weekly/partial settlements, proof, cash reconciliation, post-payout refund manual discrepancy.
- Gate: sample deterministic integer math, no payout from unpaid/unvested sales, no automated clawback, no contract regression.

### Phase 4 — Superuser revenue controls and dashboards

- Plans **optional** (including zero plans), all five monetization modes, gym and group contracts, fee receivables/payment histories, conservative progressive overdue restrictions, four role-specific dashboards/export and simple reminders.
- Gate: commission-only with zero subscriptions, separate ASCORA cash vs gym sales, effective-dated changes, permission matrix, offboarding export.

### Phase 5 — readiness and pilot (no public release without evidence)

- Run backend/frontend/lint/migration/API/integration/e2e and financial concurrency/failure cases; run restores; exercise transaction reconciliation and tenant isolation; verify operational monitoring.
- Obtain Iran-specific finance/legal/tax/provider confirmation **before turning on real online payments**. Provider choice and actual plan prices/limits are deployment configurations, not grounds to invent fake production behavior.
- Pilot with **3–5 real gyms** representing small, multi-coach and private-program sales, initially using safe demo data; then limited real data only after gates. Record acceptance and unresolved concerns.
- Offboarding/export and privacy retention contract must be tested. Promotion only through protected existing branch/CI/review workflow; do not merge/push/deploy production as a side effect of implementing this PRD.

### Required evidence for EACH phase

1. `What existed` and `what changed`, linked to requirement/decision and tests.
2. Migration and rollback/data-loss considerations (none should silently rewrite existing athlete/role/program state).
3. Commands run and actual pass/fail results, distinguishing pre-existing issues.
4. Manual QA notes for Superuser, Gym Admin, finance staff, coach and athlete where affected.
5. A one-paragraph independent self-review and concrete remaining risks.
6. Exact commit/branch if committed; release/production status remains explicit and unchanged unless separately authorized.

### Product safety / operational guardrails

- Real money must **never** use a guessed gateway, fake verification, or unverified payout state. An integration can remain disabled until ready; the rest of the app may proceed.
- Protect current production and user data. All migrations are additive/tested on disposable DB first; never run destructive operations on live Neon/Postgres without explicit deployment authorization.
- Maintain **gym-scoped historical accounting data** when closing a branch or changing plan; Superuser can inspect and perform auditable operations in all branches.
- Do not interpret a fixed coach periodic payment as statutory payroll or extend to employee tax/deductions.
- No consumer payment wallet, no provider-to-provider transfer, no inventory management, no 'AI finance agent', no new reservation frontend.

## 19. FINAL OpenCode command — paste with this file

```text
You are implementing ASCORA Finance. Read this WHOLE file as the APPROVED FINAL PRD,
including §12 functional contracts, §13 workflows, §14 money math, §16 mapping of
all 92 decisions + ADD-01, §17 acceptance tests and §18 phase gates.

Your first task is AUDIT ONLY. Inspect my CURRENT local checkout, uncommitted work,
actual branch, README/AGENTS instructions, backend models/routes/migrations/permissions,
frontend Material 3 + RTL routing, current CI/test failures and deployment controls.
Explicitly distinguish GymMembership (user/role) from paid gym membership and
ASCORA's optional B2B subscription. Reuse what's there. Give me a concise
exists/reuse/add/defer GAP TABLE and independently self-review before code changes.

Then implement ONLY the earliest safe vertical slice (Phase 1), with additive
migrations, server-side permissions, balanced integer-IRR journal, tests,
evidence and self-review. Do not start later phases until current gate passes.
Never broaden scope, invent policy, add microservices/rule engines/ERP, change
historic finance data, change existing gym core behavior, or auto-deploy.

There are NO mandatory Starter/Pro/Growth plans: Superuser may disable all plans
and run commission-only/free/hybrid/custom models without changing code.
Superuser retains FULL cross-gym finance access; other roles are strictly scoped.
Deferred: #18 usage tracking, #30 automatic post-payout coach clawback,
#46 advanced AI/smart analytics. Basic reminder obligations remain.

At the end, report files changed, explicit requirement IDs, actual test results,
remaining financial risks and the next smallest safe slice. Stop ONLY for a
material unresolvable legal/payment/data-integrity conflict, and identify it
precisely; do not overthink ordinary implementation details.
```

## 20. Final verdict

- **Business Manager:** APPROVED — configurable subscription/commission/free revenue without compulsory plan pricing; separate platform collections and business sales.
- **BA:** APPROVED — all decisions traceable; main flows, states, arithmetic constraints, edge cases and acceptance scenarios specified.
- **Strategist:** APPROVED — keep finance embedded in a gym/reservation business tool, reuse the existing monolith, prioritize reliability and actual gym value.
- **Engineering:** **ready for OpenCode's local repository audit and incremental Phase 1 implementation**, **not** proof that local code is compatible, tests currently pass, a specific online gateway is available, or public production finance is legally/operationally ready.

**No material business clarification is outstanding.** Only implementation mapping, external payment/provider/legal confirmation, numeric price experiments and live release evidence remain; those are not permission to invent or change approved product scope.
