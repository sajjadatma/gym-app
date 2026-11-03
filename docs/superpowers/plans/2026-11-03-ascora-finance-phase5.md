# ASCORA Finance Phase 5A — Local Hardening and Acceptance Plan

> **For agentic workers:** This is a local-only planning and acceptance document. Do not begin Phase 5A implementation until the owner explicitly approves it. Use `superpowers:executing-plans` only after that approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the accepted Phase 4 finance implementation is secure, tenant-safe, financially correct and operationally recoverable **entirely in the local environment**, then produce an evidence-based LOCAL GO/NO-GO report.

**Architecture:** Reuse the existing local FastAPI/SQLModel/PostgreSQL, React/TanStack, pytest and Docker Compose tooling. Add no new services, abstractions, hosting, providers, features or redesigns. Phase 5A is an audit, acceptance and defect-closure exercise.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Alembic, pytest, React 19, TypeScript, Playwright, Docker Compose, existing local backup/restore scripts.

**Spec:** `docs/finance/ASCORA-FINANCE-PRD.md` §17–§18, `docs/finance/phase4-evidence.md`, and the accepted Phase 4 closeout at `2fe1109`.

**Base commit:** `1b6db70` on `feat/ascora-finance` (the prior Phase 5 plan commit; this revision changes only the plan).

---

## 1. Strategy change: local-first

The owner has decided that all ASCORA Finance features remain **local for now**. The former Phase 5 four-gate strategy is replaced by:

- **Phase 5A — Local Hardening & Acceptance** (this plan; authorized only after explicit approval).
- **Phase 5B — External Readiness, Legal Signoff, Pilot and Release** (deferred; not authorized; requires a separate approved plan).

### Phase 5A scope

1. Independent security and tenant-isolation audit.
2. Authentication, authorization and sensitive financial-data review.
3. Complete local financial workflow acceptance tests.
4. Accounting reconciliation and date-semantics verification.
5. Migration, concurrency, idempotency and Docker backup/restore tests.
6. Local UI/UX acceptance for Superuser, gym admin, finance staff, coach and athlete.
7. Fix confirmed Critical/High defects with focused regression tests.
8. Produce an evidence-based LOCAL GO/NO-GO report.

### Explicitly out of scope for Phase 5A

- Remote staging or production deployment.
- New hosting, DNS, TLS/ACME, SMTP provider, Sentry/log shipping or monitoring infrastructure.
- Vercel or Neon deployment/configuration changes.
- Payment-provider integration or online payments.
- Real financial data or real gym operations.
- Legal, tax or privacy signoff work.
- A real-gym pilot or public release.
- Merging the finance branch into `main`.
- New product features, redesigns, speculative refactors or performance infrastructure.

All infrastructure readiness, legal/provider signoff, real-gym pilot and public-release gates move to **Phase 5B**, which is not authorized by this document.

### Approval boundary

- Writing and revising this plan is authorized.
- Executing any Phase 5A task requires explicit approval of this plan.
- Phase 5A may use the existing local PostgreSQL, backend, frontend and Docker tooling only.
- Phase 5A must not create remote resources, use real financial data, or change Vercel/Neon deployment configuration.
- Phase 5B work must not begin until a separate plan is approved.

---

## 2. Global constraints

- All development and verification remain local.
- Use existing local PostgreSQL, backend, frontend and Docker tools; do not add hosting or provider dependencies.
- No remote staging or production deployment.
- No new hosting, DNS, SMTP provider, Sentry/log shipping, monitoring service or payment gateway.
- No Vercel or Neon deployment/configuration changes.
- No real financial data; all acceptance data is synthetic and disposable.
- Do not merge the finance branch into `main`.
- Preserve all 92 PRD decisions and `ADD-01`. Update the individual matrix in `docs/finance/phase4-evidence.md` only with Phase 5A evidence; never replace or renumber decisions.
- Keep #18, #30 and #46 **Deferred**.
- #15/#71, #34 and #91 remain **Partial/Outstanding** unless their actual code and tests are implemented. Manual local SOPs are temporary mitigations, not completed features.
- Money remains integer IRR in PostgreSQL; no floating point. Posted financial rows remain append-only.
- Platform money remains separate from gym money.
- Avoid new features, redesign and overengineering. Fix only confirmed Critical/High defects with focused regression tests.
- Every workstream produces an evidence record; a passing test suite alone is not acceptance evidence.

---

## 3. Review focus

These are the failure modes most likely to invalidate a LOCAL GO even when functional tests pass. Each has an owning workstream and acceptance evidence.

1. **Tenant escape** — a gym owner, finance staff, coach or athlete reads or mutates another tenant's financial data through APIs, exports or forged identifiers.
2. **Authentication/token weakness** — session revocation, CSRF, token leakage, reset/invitation token reuse or authorization bypass.
3. **Sensitive financial data exposure** — PII or financial details in logs, exports, error responses, fixtures or screenshots.
4. **Money misstatement** — duplicated receipts/payments/accruals, over-allocation, unbalanced journals or platform/gym money mixing.
5. **Date-semantics inconsistency** — owner overdue, Superuser receivables, per-gym revenue and journal totals disagree without an explicit tested reconciliation.
6. **Silent restore loss** — Docker restore passes while platform rows, allocations, credits, sequences or balanced journals are missing.
7. **Role UI failure** — a required role cannot complete its finance journey locally, or sees another role's data.
8. **Scope drift** — Phase 5A turns into feature work, redesign or external readiness.

---

## 4. Phase 5A execution workstreams

### 5A.0 — Local acceptance baselines (must precede execution)

**Artifacts:**
- `docs/release/phase5a-local-baselines.md` (signed by product, engineering, security and finance/accounting owners).

**Depends:** Approval of this plan.

- [ ] Record and approve these **local security thresholds**:
  - Zero open Critical or High findings (CVSS ≥ 7.0 or any finding affecting authentication, authorization, tenant isolation, money integrity or local backup confidentiality).
  - 100% of cross-tenant attempts denied across API, export, forged `X-Gym-ID`, forged path IDs and client filters.
  - Zero secrets or real financial PII in Git, fixtures, logs, screenshots, exports or local backup metadata.
  - Authentication/token review passes: logout/password-change revocation, single-use reset/invitation tokens, CSRF enforcement and no token leakage.
- [ ] Record and approve these **local accounting thresholds**:
  - 0 IRR unexplained delta for every closed synthetic period.
  - 0 unbalanced journals.
  - 0 duplicate financial facts after retries.
  - 0 allocation, credit, sequence or payment-consistency mismatches.
  - 100% of financial report endpoints covered by date-semantics conformance tests.
- [ ] Record and approve these **local recovery thresholds**:
  - Docker backup/restore drill passes with nonempty platform financial data.
  - Restored counts match exactly; every journal balances; allocations, credits and sequences reconcile.
  - Local restore drill completes within 60 minutes on the reference development machine.
  - Operational RPO/RTO targets remain Phase 5B items; Phase 5A proves recoverability, not production service levels.
- [ ] Record and approve these **local UI/UX thresholds**:
  - Every required role journey passes on the local stack.
  - No role sees another role's data.
  - No Critical/High usability defect blocks a required journey.
  - Key finance screens load without errors on the reference local machine; measured load time is recorded, not treated as a production SLA.
- [ ] Record and approve these **local migration thresholds**:
  - Upgrade → downgrade → upgrade succeeds on a disposable local database.
  - Migration tests pass at the expected head.
  - No existing athlete, role, program or finance history is silently rewritten.
- [ ] Any baseline change after approval requires a recorded decision with owner and reason.

**Acceptance evidence:**
- Signed baseline document with the exact values above.
- The document is referenced by the 5A.1–5A.7 evidence records.

---

### 5A.1 — Independent security and tenant-isolation audit

**Covers:** Scope items 1 and 2.

**Artifacts:**
- `docs/release/phase5a-security-audit.md`
- Focused regression tests only where a confirmed defect is fixed.

**Depends:** 5A.0.

- [ ] Review **authentication and token handling**: HttpOnly/SameSite/Secure cookies, CSRF double-submit, bearer-token paths, access/refresh expiry, server-side logout and `token_version` revocation, password-reset and invitation token single-use/expiry, session fixation and login throttling.
- [ ] Review **authorization** for every finance/platform route by role: Superuser, gym owner, gym admin, finance staff, coach and athlete.
- [ ] Run a tenant-isolation matrix covering:
  - cross-gym owner read and staff write;
  - cross-gym platform invoice, receivable, credit, payment and group access;
  - forged `X-Gym-ID` and path IDs;
  - export scoping and CSV/offboarding access;
  - Superuser-only boundaries.
- [ ] Review **sensitive financial data protection**:
  - logs and error responses;
  - Sentry/error-handler payload settings;
  - CSV/offboarding exports;
  - uploaded proof access;
  - local fixtures and test data containing no real PII;
  - audit-event content and local retention.
- [ ] Review **local backup access controls**: who can read/write the local backup directory, file permissions, checksum integrity, and whether any local process outside the operator can read backups.
- [ ] Review local secret handling: `.env` files, shell history, Docker image layers, test fixtures and CI logs.
- [ ] Recheck dependency advisories for backend and frontend; record accepted risks.
- [ ] Classify every finding Critical/High/Medium/Low with owner and due workstream.

**Acceptance evidence:**
- Signed audit report with dedicated sections for authentication/token handling, authorization, tenant isolation, financial-data protection and local backup access.
- Tenant-isolation matrix with every attempt denied and no cross-tenant row returned.
- Token review proves revocation, single-use reset/invitation tokens and no token leakage.
- No real PII or financial data in logs, exports, fixtures or screenshots.
- Zero unresolved Critical/High findings.
- Each fixed defect has a focused regression test.

---

### 5A.2 — Complete local financial workflow acceptance

**Covers:** Scope item 3.

**Artifacts:**
- `docs/release/phase5a-local-financial-acceptance.md`
- Existing pytest/Playwright suites; add scenarios only where coverage is missing.

**Depends:** 5A.0 and 5A.1 security clearance for test data handling.

- [ ] Create local synthetic gyms representing small, multi-coach and program/private-sales profiles.
- [ ] Run the complete local workflow:
  - membership sale → invoice → issue → partial receipt → final receipt;
  - refund request → approval → refund record;
  - platform credit → platform invoice → partial platform payment → final payment;
  - subscription accrual and commission recognition;
  - credit application, unapplied credit and overdue standing;
  - coach agreement → earning → vesting → settlement → proof → post-payout refund manual discrepancy;
  - group agreement → volume discount → group invoice → per-branch lines → partial payment → cancellation/reissue.
- [ ] Verify role views: Superuser full access, gym admin, finance staff, coach own earnings, athlete account.
- [ ] Verify CSV/offboarding export labels and scoping.
- [ ] Exercise failure and retry paths:
  - duplicate receipt/payment/accrual/invoice/cancellation/refund submissions;
  - changed-payload idempotency-key reuse rejected;
  - aborted transaction leaves no partial business row or journal;
  - failed verification is never marked successful.
- [ ] Confirm no workflow requires a remote service, real SMTP, payment gateway or real data.

**Acceptance evidence:**
- Each workflow has a scenario ID and pass/fail result.
- Amounts reconcile at every step across receivable, invoice, payment, credit, journal, gym summary and platform overview.
- One business fact and one balanced journal per retried operation.
- No cross-gym data in any role view or export.
- No real financial data used.

---

### 5A.3 — Accounting reconciliation and date-semantics verification

**Covers:** Scope item 4.

**Artifacts:**
- `docs/finance/date-semantics.md` (binding local decision record)
- `docs/release/phase5a-reconciliation.md`
- Focused regression tests in `backend/tests/api/routes/test_platform_reports.py` and owner-standing tests.

**Depends:** 5A.2.

- [ ] Inventory every financial report, dashboard, export and owner-facing dues/reminder view, and record its canonical date field and basis.
- [ ] Decide and record canonical semantics:
  - **Billed vs unbilled:** owner-facing overdue and reminders cover issued invoices only; accrued but uninvoiced receivables are reported separately as unbilled and never labeled overdue to the owner.
  - **Superuser receivable reporting:** show billed invoice balance and unbilled receivable balance separately; if a combined number remains, label it `total_exposure` and document the formula.
  - **Revenue range:** the journal `posting_date` is the ledger truth for the headline; per-gym reports either use the same posting date or publish a reconciliation line.
- [ ] Ensure all financial report date semantics are consistent; no endpoint may mix receivable due dates, invoice due dates, accrual dates and posting dates without an explicit, labeled reconciliation.
- [ ] Reproduce the Phase 4 boundary scenarios as tests:
  - receivable overdue but invoice not due;
  - credit created after `as_of`;
  - discount journal posted at `period_end` while the invoice was issued earlier;
  - report range splitting the two dates.
- [ ] Reconcile a closed synthetic month:
  - journal recognized revenue vs per-gym recognized revenue;
  - gym summary platform payable vs platform receivable and available credit;
  - cash collected vs payment allocations and platform cash journal.
- [ ] Confirm 0 IRR unexplained delta and 0 unbalanced journals.
- [ ] Update the 92-decision evidence for #37, #44, #54, #61 and #84 with local evidence.

**Acceptance evidence:**
- `date-semantics.md` signed by product/accounting owner, including the full report-endpoint inventory.
- All four boundary scenarios pass.
- Every listed report endpoint passes the date-semantics conformance suite.
- Closed-period reconciliation delta is 0 IRR; any explained delta has a named source and approval.
- No owner-facing screen labels unbilled receivables as overdue.

---

### 5A.4 — Migration, concurrency, idempotency and Docker backup/restore

**Covers:** Scope item 5.

**Artifacts:**
- `docs/release/phase5a-migration-recovery.md`
- Existing migration, concurrency, backup and restore tests/scripts.

**Depends:** 5A.0; can run alongside 5A.2.

- [ ] Run the full local backend suite, migration suite, Ruff and Mypy.
- [ ] Run upgrade → downgrade → upgrade on a disposable local database at the expected head.
- [ ] Confirm no existing athlete, role, program or finance history is silently rewritten.
- [ ] Exercise concurrency:
  - concurrent receipt allocation against one invoice;
  - concurrent platform payment against one invoice;
  - concurrent subscription accrual and platform fee recognition;
  - concurrent invoice cancellation and payment;
  - concurrent credit application and invoice issue;
  - concurrent migration/bootstrap on a fresh local database.
- [ ] Exercise idempotency:
  - duplicate receipt, platform payment, subscription accrual, invoice issue, cancellation and refund;
  - changed-payload reuse rejected;
  - failed/aborted transaction leaves no partial fact.
- [ ] Run the Docker backup/restore drill with nonempty platform data:
  - platform agreement, receivable, credit, credit application, invoice/line, payment/allocation, balanced journal and sequences;
  - isolated restore and live restore;
  - exact count, balance, allocation, credit and sequence verification.
- [ ] Confirm no backup or restore step touches a remote host or real data.
- [ ] Record the local restore duration against the 60-minute local threshold.

**Acceptance evidence:**
- Backend and migration suites pass; lint/type checks clean.
- Upgrade/downgrade/upgrade succeeds with no data loss.
- Concurrency scenarios produce one valid fact and safe rejection elsewhere.
- Idempotency scenarios produce one fact and one balanced journal.
- Docker restore passes with `ok:true`, exact platform counts and balanced journals.
- Local restore completes within 60 minutes.
- No remote resource or real data used.

---

### 5A.5 — Local UI/UX acceptance by role

**Covers:** Scope item 6.

**Artifacts:**
- `docs/release/phase5a-local-ui-acceptance.md`
- Existing Playwright suites plus a short manual checklist where automation is missing.

**Depends:** 5A.2 and a stable local stack.

- [ ] **Superuser:** platform overview, plans/versions, agreements/groups, invoices/lines, payments, dues/reminders, costs, cancellation reason and export.
- [ ] **Gym admin:** finance dashboard, invoices, receipts, refunds, platform billing read-only view and export.
- [ ] **Finance staff:** permitted finance actions, amount limits, denied operational areas and read/export behavior.
- [ ] **Coach:** own earnings, vesting and settlements; no other coach or gym data.
- [ ] **Athlete:** own bills, receipts, installments and refund request; no staff finance data.
- [ ] Verify responsive behavior at desktop and emulated mobile viewports used by the existing suite.
- [ ] Verify Persian RTL and Jalali dates on finance screens.
- [ ] Record usability findings; fix only Critical/High blockers. Do not redesign.

**Acceptance evidence:**
- Role-by-role acceptance matrix with pass/fail and screenshots where useful.
- No role sees another role's data.
- Every required finance journey is completable locally.
- No Critical/High usability defect blocks a required journey.
- No redesign or new feature added.

---

### 5A.6 — Critical/High defect closure

**Covers:** Scope item 7.

**Artifacts:**
- Defect log with severity, reproduction, owner and regression test.
- Focused code changes only for confirmed Critical/High defects.

**Depends:** 5A.1–5A.5 findings.

- [ ] Triage every finding from 5A.1–5A.5.
- [ ] Fix confirmed Critical/High defects with the smallest safe change.
- [ ] Add a focused regression test for each fix.
- [ ] Re-run the affected suite and the full local regression.
- [ ] Record Medium/Low findings with an explicit accept/fix decision; do not expand scope.
- [ ] Do not add features, redesign UI or refactor unrelated code.

**Acceptance evidence:**
- Zero open Critical/High defects.
- Every fix has a regression test and a linked finding.
- Full local regression green after fixes.
- Medium/Low findings have owners and target dates or explicit acceptance.

---

### 5A.7 — LOCAL GO/NO-GO report

**Covers:** Scope item 8.

**Artifacts:**
- `docs/release/phase5a-local-go-no-go.md`

**Depends:** 5A.1–5A.6.

- [ ] Assemble evidence: security audit, tenant matrix, financial acceptance, reconciliation, date semantics, migration/concurrency/idempotency, Docker restore, UI/UX matrix and defect log.
- [ ] Reconcile the 92-decision matrix and `ADD-01`; keep #18/#30/#46 Deferred and #15/#71/#34/#91 Partial/Outstanding unless implemented and tested.
- [ ] Record LOCAL GO, CONDITIONAL LOCAL GO or LOCAL NO-GO with named conditions.
- [ ] List Critical blockers separately from non-blocking improvements.
- [ ] State explicitly that a LOCAL GO does not authorize remote staging, production, legal/provider work, a real-gym pilot, public release or a merge to `main`.
- [ ] Recommend the next action: stop locally, fix remaining blockers, or prepare a separate Phase 5B plan for later approval.

---

## 5. Local GO/NO-GO criteria

### LOCAL GO requires all of the following

- [ ] Zero open Critical/High security or tenant-isolation findings.
- [ ] Authentication/token, authorization, financial-data and local backup-access reviews signed.
- [ ] Complete local financial workflows pass for all roles.
- [ ] Failure/retry/idempotency and concurrency scenarios pass with one fact per operation.
- [ ] Migration upgrade/downgrade/upgrade passes with no data loss.
- [ ] Docker backup/restore passes with nonempty platform data, exact counts and balanced journals; local restore ≤60 minutes.
- [ ] Every financial report endpoint passes date-semantics conformance; closed-period unexplained delta = 0 IRR.
- [ ] Local UI/UX acceptance passes for Superuser, gym admin, finance staff, coach and athlete.
- [ ] Zero open Critical/High defects; every fix has a regression test.
- [ ] All evidence uses synthetic local data only.
- [ ] No remote resource, Vercel/Neon change, real data or merge to `main`.
- [ ] 92 decisions + `ADD-01` preserved; #18/#30/#46 Deferred; #15/#71/#34/#91 Partial/Outstanding.

### LOCAL NO-GO triggers

- Any Critical/High security, authentication or tenant-isolation defect.
- Any money mismatch, unbalanced journal, duplicate financial fact or unexplained reconciliation delta.
- Any financial report endpoint with unverified or mixed date semantics.
- Any migration data loss or failed upgrade/downgrade/upgrade.
- Docker restore cannot recover nonempty platform financial data or exceeds the local threshold.
- A required role cannot complete its finance journey.
- Any use of real financial data, remote deployment, Vercel/Neon change, provider integration or merge to `main`.

### Non-blocking local improvements

- #15/#71 proactive reminders — remains Partial.
- #34 configurable overdue restrictions — remains Partial.
- #91 plan-limit enforcement — remains Partial.
- Richer dashboards, bulk group editing, multi-term agreement UI.
- Performance tuning beyond the local acceptance threshold.

---

## 6. Classification of approved remaining requirements (local-first)

| Requirement | Local-first classification | Status rule | Phase 5A evidence |
|---|---|---|---|
| **#15 / #71 proactive reminder delivery** | Local non-blocking; temporary manual SOP only | Remains **Partial** unless scheduled delivery plus tests exist | In-app reminder behavior reviewed; no proactive delivery claimed |
| **#34 configurable overdue restrictions** | Local non-blocking; temporary manual SOP only | Remains **Partial** unless configurable notice/grace/restriction plus tests exist | Informational standing reviewed; no automatic restriction claimed |
| **#91 plan-limit enforcement** | Local non-blocking | Remains **Partial** unless numeric limits and enforcement plus tests exist | Usage visibility reviewed; enforcement not claimed |
| **#53 real-gym pilot** | Deferred to Phase 5B | Not satisfied locally | None; requires later authorization |
| **#54 financial integrity / refunds / tenant / restore / pilot criteria** | Local integrity portion covered; pilot portion deferred | Local evidence supports the requirement; full satisfaction needs Phase 5B | 5A.1–5A.4 evidence |
| **#56 Iran legal / tax / privacy / provider** | Deferred to Phase 5B | Not satisfied locally | None; requires later authorization |
| **#92 release requirements** | Deferred to Phase 5B | Not satisfied locally | None; LOCAL GO is not release approval |
| **#18, #30, #46** | **Deferred — unchanged** | Remains Deferred | No work |

No other decision is reclassified. All 92 decisions and `ADD-01` remain in force; Phase 5A only adds local evidence and status updates.

---

## 7. Dependencies and recommended execution order

### Dependency graph

```
Approval of this plan + 5A.0 baselines
        │
        ├── 5A.1 security/tenant/auth review ─────────────┐
        │                                                 │
        ├── 5A.2 local financial workflows ── 5A.3 reconciliation/date semantics
        │                                                 │
        ├── 5A.4 migration/concurrency/backup-restore ────┤
        │                                                 │
        └── 5A.5 local UI/UX by role ──────────────────────┤
                                                          │
                                                    5A.6 defect closure
                                                          │
                                                    5A.7 LOCAL GO/NO-GO
```

### Recommended order

1. **Approve this plan and the 5A.0 baselines.**
2. **Run 5A.1 security/tenant/auth review** before broad workflow testing.
3. **Run 5A.2 local financial workflows** with synthetic data.
4. **Run 5A.3 reconciliation and date semantics** immediately after the workflows.
5. **Run 5A.4 migration/concurrency/idempotency/backup-restore** in parallel where the local stack allows.
6. **Run 5A.5 local UI/UX acceptance** for all five roles.
7. **Close Critical/High defects** in 5A.6 and re-run affected suites plus the full local regression.
8. **Produce 5A.7 LOCAL GO/NO-GO report.**
9. **Stop.** Do not start Phase 5B, remote deployment, legal/provider work, pilot or release without separate approval.

### Parallel tracks

- 5A.1 security review and 5A.4 migration/recovery can start early.
- 5A.5 UI/UX can run once the local stack is stable; it must not wait for external infrastructure.
- 5A.6 is continuous for Critical/High findings but is finalized after 5A.1–5A.5.
- No Phase 5B work runs in parallel.

---

## 8. Phase 5B — Deferred external readiness (not authorized)

The following former Phase 5 gates are moved to a later, separately authorized phase. They are **not** part of Phase 5A and must not be started, planned in detail or inferred as approved.

- **Infrastructure readiness:** remote staging/production hosts, DNS, TLS/ACME, SMTP provider, monitoring/log shipping, least-privilege production database roles and target-storage restore.
- **Legal/tax/privacy/provider:** Iran-specific legal and tax validation, privacy/retention terms, payment-provider approval only if online/provider-based payments are enabled.
- **Controlled pilot:** 3–5 real gyms, synthetic first then limited real data, real-gym onboarding and operations.
- **Release decision:** measurable GO/NO-GO for public release, deployment authorization and production operations.
- **Operational RPO/RTO:** production service-level targets and target-storage recovery evidence.

Phase 5A evidence should feed Phase 5B, but a LOCAL GO is not a production, pilot, legal or release approval. Phase 5B requires a separate plan and explicit owner authorization.

---

## 9. Decision preservation

- `docs/finance/phase4-evidence.md` remains the authoritative individual matrix for decisions 1–92 and `ADD-01`.
- Phase 5A updates statuses only with local evidence; it does not delete, merge or renumber rows.
- #18, #30 and #46 remain **Deferred** throughout.
- #15, #71, #34 and #91 remain **Partial/Outstanding** unless their actual code and tests are implemented; manual local SOPs are temporary mitigations and never count as completion.
- #53, #54, #56 and #92 remain deferred or partially evidenced until Phase 5B.
- Any proposed new decision or behavior requires explicit approval before implementation.

---

## 10. Approval required before execution

This document is a plan only. No Phase 5A implementation, code change, test-data load, deployment, merge or provider integration may begin until the owner explicitly approves:

1. this local-first Phase 5A plan and the 5A.0 baselines,
2. the named local environment and tools,
3. the synthetic-data acceptance approach,
4. the scope boundary that excludes Phase 5B, remote infrastructure, legal/provider work, real data and release,
5. any later Phase 5B plan as a separate authorization.

A LOCAL GO from 5A.7 does not authorize a merge to `main`, remote deployment, a real-gym pilot, public release or any real financial operation.
