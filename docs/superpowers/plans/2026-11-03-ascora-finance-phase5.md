# ASCORA Finance Phase 5 — Production Readiness and Controlled Pilot Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after explicit approval. This plan is **operational and release-engineering work**, not a feature build. Do not implement, deploy, enable real payments, or touch production data until the approval gate named in each task is explicitly cleared. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the accepted Phase 4 finance implementation is safe to operate with 3–5 real gyms under controlled conditions, then make an evidence-based GO/NO-GO decision for public release.

**Architecture:** Reuse the existing FastAPI/SQLModel/PostgreSQL, React/TanStack, Docker Compose, Traefik, backup/restore, preflight and smoke-test architecture. Add no new services, abstractions or monetization behavior. Phase 5 closes operational evidence gaps, resolves the two documented reporting-boundary discrepancies, and runs a bounded pilot.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL 17, Alembic, pytest, React 19, TypeScript, Playwright, Docker Compose, Traefik + Let's Encrypt, existing backup/restore scripts, Sentry/log shipping.

**Spec:** `docs/finance/ASCORA-FINANCE-PRD.md` §17–§18, `docs/finance/phase4-evidence.md`, `docs/release/staging-production-readiness.md`, `docs/release/production-deployment-runbook.md`, `docs/release/staging-deployment-runbook.md`, and `docs/superpowers/plans/2026-11-03-ascora-finance-phase4.md`.

**Base commit:** `2fe1109` on `feat/ascora-finance` (Phase 4 closeout accepted).

---

## 1. Phase 5 scope and non-goals

### In scope

- Independent security, tenancy and sensitive-data review, including explicit review of existing authentication/token handling, tenant isolation, financial data protection and backup access controls.
- Staging and, only if separately authorized, production-candidate infrastructure, TLS, SMTP, secrets, database roles, backups, restore and monitoring.
- Resolution of the documented due-date-source and report-period-boundary discrepancies, with consistent and tested financial report date semantics before Gate 2 acceptance.
- Full synthetic financial acceptance on staging, including failure and concurrency paths.
- A controlled pilot with exactly 3–5 gyms, synthetic data first and real data only after all applicable security, operational and legal gates pass.
- Iran-specific legal, tax and privacy validation before any real financial use; payment-provider approval only if online/provider-based payments are enabled.
- Monitoring, feedback, rollback and incident procedures.
- A measurable release decision.

### Explicit non-goals

- No public release, production deployment or real financial operation in this planning step.
- No online payment gateway unless an Iran-qualified provider is approved and legal/tax/privacy signoff is obtained; otherwise the pilot remains manual-only.
- No new finance product features beyond the approved remaining requirements listed in §8.
- No merge to `main`, no production data migration, no production credential creation.
- No AI analytics (#46), attendance finance input (#18) or automatic coach clawback (#30).

### Approval boundary

- Writing this plan is authorized.
- Executing **Gate 1** requires explicit approval of the plan, the named staging environment/host, and a **staging-only authorization**. Staging must use its own Compose project, host/resources, domain, secrets, database, volumes, backups and provider accounts, and must never read, write, network with or otherwise affect production resources.
- Executing **Gate 2** requires Gate 1 exit evidence and the staging-only authorization record.
- Executing **Gate 3** requires Gate 2 exit evidence, Iran legal/tax/privacy signoff, and a signed pilot charter. Payment-provider approval is additionally required only if online/provider-based payments are enabled.
- **Gate 4** is a decision, not an automatic deployment. Any production deployment requires separate explicit authorization after Gate 4.

---

## 2. Global constraints

- Preserve all 92 decisions and `ADD-01`. Update the individual matrix in `docs/finance/phase4-evidence.md` with Phase 5 evidence; never replace or renumber decisions.
- Keep #18, #30 and #46 **Deferred**.
- Do not mark a requirement complete because code exists. Mark it complete only with the acceptance evidence named here.
- Reuse existing scripts and runbooks: `scripts/preflight_env.py`, `scripts/deploy_stack.sh`, `scripts/smoke_stack.sh`, `scripts/smoke-production.sh`, `scripts/backup_compose.sh`, `scripts/restore_compose.sh`, `scripts/verify_restore.py`, `scripts/check_backup_freshness.sh`, `scripts/ci/backup-restore-drill.sh`.
- Money remains integer IRR in PostgreSQL; no floating point. Posted financial rows remain append-only.
- Platform money remains separate from gym money.
- The in-process rate limiter requires `WEB_CONCURRENCY=1`; do not raise it without a shared limiter.
- One Linux host with Docker Compose is the accepted pilot topology. No HA, read replica or point-in-time recovery is introduced.
- Any new configuration must be additive and reversible. Any schema change must be additive and migration-tested.
- Every gate produces a signed evidence record; a passing test suite alone is not deployment evidence.
- Staging is a separate Compose project and never shares databases, volumes, networks, secrets, backups, DNS or provider accounts with production. A staging-only authorization must be recorded before any staging deployment.
- Iran legal, tax and privacy validation is mandatory before any real financial data or transaction. Payment-provider approval is conditional on enabling online/provider-based payments; without it, only manual cash/POS/bank-transfer flows may be used.
- #15/#71, #34 and #91 remain **Partial** or **Outstanding** unless their actual code and tests are implemented. Manual pilot SOPs are temporary mitigations and never count as completed features.
- Measurable RPO, RTO, security, accounting-reconciliation and performance acceptance thresholds must be recorded and approved before Gate 1 execution (see G1.0).

---

## 3. Review focus

These are the failure modes most likely to invalidate a pilot even when functional tests pass. Each has an owning gate task and acceptance evidence.

1. **Money is misstated across gym boundaries** — one gym's credit, invoice or payment must never change another gym's receivable, standing or export.
2. **Due dates and report ranges disagree** — owner-facing overdue and Superuser billing must not contradict each other without an explicit, tested reconciliation.
3. **Restore succeeds but silently loses financial rows** — a restore must fail on missing platform tables, unbalanced journals, broken allocation/credit links or missing sequences.
4. **Privilege or tenant escape** — a gym owner, finance staff, coach or athlete must not read or mutate another tenant's financial data, including exports and platform billing.
5. **Retry creates money twice** — duplicate receipts, payments, accruals, invoice issuance, cancellations or refunds must produce one fact and one journal.
6. **Production is configured but not actually proven** — TLS/ACME, SMTP, target-storage restore, monitoring and rollback must be exercised on the real host, not inferred from local tests.
7. **A real-money obligation is enabled before legal/tax/privacy or provider clearance** — online payment or contractual tax behavior must remain disabled until written signoff.

---

## 4. Gate 1 — Production Readiness

**Purpose:** Make the environment, database, security posture and reporting boundaries safe enough to run synthetic acceptance on staging and prepare a controlled pilot.

**Entry:** Phase 4 closeout accepted at `2fe1109`; a **staging-only authorization** is signed; host, DNS, legal/tax/privacy owner and credential ownership are assigned; G1.0 baselines are approved.

**Exit:** All Gate 1 tasks pass; no open Critical or High security finding; staging (and, only if separately authorized, production-candidate configuration) validated; target-storage restore and monitoring proven; date semantics recorded, consistent across every financial report and tested before Gate 2.

### G1.0 — Approved measurable acceptance baselines (must precede Gate 1 execution)

**Artifacts:**
- `docs/release/phase5-acceptance-baselines.md` (signed by product, engineering, security, finance/accounting and operations).

**Depends:** Approval of this plan and the staging-only authorization.

- [ ] Record and approve these RPO/RTO targets:
  - **RPO ≤ 24 hours** — a verified backup exists within the previous 24 hours; maximum accepted financial-data loss is 24 hours.
  - **RTO ≤ 4 hours** — from restore decision to a ready service with verified financial data; measured during the target-storage restore drill.
  - Restore completeness is exact: all expected platform/gym counts match, every journal is balanced, and allocation/credit/sequence integrity checks pass.
- [ ] Record and approve these security thresholds:
  - **Zero open Critical or High findings** (CVSS ≥ 7.0 or any finding affecting authentication, authorization, tenant isolation, money integrity or backup confidentiality).
  - **100% of cross-tenant attempts denied** in the tenant-isolation matrix, including API, export, forged `X-Gym-ID`, path-ID and client-filter attempts.
  - **Zero secrets** in Git, images, logs, exports or backup metadata; runtime database role is least-privilege.
  - **Zero Critical dependency advisories**; High advisories fixed or explicitly accepted with compensating controls.
  - No financial PII or request bodies in Sentry/logs; backup access is authenticated, encrypted and audited.
- [ ] Record and approve these accounting thresholds:
  - **0 IRR unexplained delta** for every closed period: journal recognized revenue vs per-gym recognized revenue, platform receivable vs gym-summary payable, cash collected vs allocations.
  - **0 unbalanced journals**, **0 duplicate financial facts**, **0 allocation/credit/sequence mismatches**, **0 owner-facing unbilled amounts labeled overdue**.
  - **100% of financial report endpoints** covered by date-semantics conformance tests.
- [ ] Record and approve these performance thresholds on a pilot-scale dataset (5 gyms, 10,000 invoices, 25,000 receipts/payments, 100,000 journal lines):
  - Login p95 ≤ 1.0 s.
  - Finance/platform dashboard API p95 ≤ 2.0 s.
  - Invoice/receivable list of 100 rows p95 ≤ 1.0 s.
  - 12-month CSV export of 10,000 invoices completes ≤ 30 s.
  - Zero unexpected 5xx during acceptance; 429 only during deliberate abuse tests.
- [ ] Any baseline change after approval requires a recorded decision with owner and reason.

**Acceptance evidence:**
- Signed baseline document with the exact values above.
- The document is referenced by the Gate 1, Gate 2 and Gate 4 evidence records.

### G1.1 — Independent security and tenancy audit

**Artifacts:**
- `docs/release/phase5-security-audit.md`
- Test additions only where a reproducible defect is found.

**Depends:** None.

- [ ] Review existing **authentication and token handling**: cookie `HttpOnly`/`SameSite`/`Secure` behavior, double-submit CSRF, bearer-token expiry and storage, server-side logout/`token_version` revocation, password-reset and invitation token single-use/expiry, session fixation, login throttling and account lifecycle.
- [ ] Review authorization for every finance/platform route by role: Superuser, gym owner, gym admin, finance staff, coach, athlete.
- [ ] Run a tenant-isolation matrix that attempts cross-gym reads and writes through APIs, exports, invoice IDs, payment IDs, credit IDs, group IDs, forged `X-Gym-ID` and client-generated filters.
- [ ] Review **financial data protection**: TLS in transit, encryption at rest where the host supports it, export authorization and watermarking/retention, uploaded proof access, audit retention, and PII/body redaction in logs and Sentry.
- [ ] Review **backup access controls**: encryption at rest, separate read/write credentials, least-privilege restore authorization, off-host copy protection, access logging, key custody/rotation and retention/immutability. Confirm the application runtime cannot read backup storage.
- [ ] Review secret handling: environment files, image contents, backup contents, shell history, CI logs and credential rotation.
- [ ] Recheck dependency advisories for backend and frontend; record accepted risks explicitly.
- [ ] Classify every finding Critical/High/Medium/Low with owner and due gate.

**Acceptance evidence:**
- Signed audit report with zero unresolved Critical/High findings and dedicated sections for authentication/token handling, tenant isolation, financial data protection and backup access controls.
- Tenant-isolation matrix attached, including at least: cross-gym owner read, cross-gym staff write, cross-gym platform invoice read, forged `X-Gym-ID`, forged path IDs, export scoping and Superuser-only boundaries.
- Token review proves revocation after logout/password change, single-use reset/invitation tokens and no token leakage in logs.
- Backup-access review proves encrypted storage, least-privilege read/write/restore roles and audited access.
- Each fixed defect has a regression test.
- Medium/Low findings have an explicit accept/fix decision and target gate.

### G1.2 — Database least privilege and credential separation

**Artifacts:**
- `compose.deploy.yml` / environment templates (additive variables only).
- Migration or bootstrap change for runtime/migration roles.
- `docs/release/database-roles.md`.

**Depends:** G1.1 review of current credentials.

Current deployment connects as the PostgreSQL bootstrap superuser (`postgres`). That is a production-readiness gap.

- [ ] Define a runtime role with DML-only access to application tables and sequences, plus the minimum functions required by the app.
- [ ] Define a migration role with schema-change rights, used only by the backend entrypoint/bootstrap.
- [ ] Keep `postgres` for database initialization only; do not expose it to the application process.
- [ ] Verify migrations, initial data, backup and restore work with the new roles.
- [ ] Document credential rotation and emergency recovery.

**Acceptance evidence:**
- Application starts and passes readiness with the runtime role.
- Runtime role cannot create/drop tables, alter schema, create roles or read unrelated databases.
- Migration path still applies `alembic upgrade head` at the expected revision.
- Backup/restore drill passes with the production role model.
- Credentials are absent from Git and from the image.

### G1.3 — Hosting, TLS, SMTP and environment isolation

**Artifacts:**
- `docs/release/phase5-environment-evidence.md`
- `docs/release/phase5-staging-authorization.md`
- Existing `.env.staging` / `.env.production` files, never committed.

**Depends:** G1.2 for database credentials and a signed staging-only authorization.

- [ ] Record the staging-only authorization: named host/resources, project name, domain, credential owner and explicit confirmation that no production resource is reachable or shared.
- [ ] Provision the staging host and, only if separately approved, a production-candidate host; keep the production-candidate environment synthetic, with no real users or real money until Gate 4 authorizes deployment.
- [ ] Prove staging and production (if provisioned) use different Compose projects, hosts/volumes, networks, databases, secrets, domains, backups and provider accounts.
- [ ] Point real DNS records at each approved host and prove HTTP→HTTPS redirect, ACME issuance, HSTS behavior and security headers.
- [ ] Configure a real SMTP provider; prove invitation and password-recovery delivery to a controlled recipient.
- [ ] Confirm staging uses the staging CA and production uses the production CA; confirm production rejects email redirection.
- [ ] Run `preflight_env.py` positive and negative cases for each approved environment.
- [ ] Verify no database or backend port is publicly reachable.

**Acceptance evidence:**
- Signed staging-only authorization with resource list and isolation statement.
- `smoke-production.sh https://<domain>` passes for the approved staging host, or the documented staging equivalent.
- Certificate chain, expiry and renewal path recorded.
- SMTP delivery IDs and timestamps recorded.
- Preflight rejects reused projects, domains, secrets and wrong ACME directories.
- External port scan shows only 80/443.
- A connectivity check from staging cannot resolve or reach production databases, internal networks or backup storage.

### G1.4 — Backups, target-storage restore and disaster recovery

**Artifacts:**
- `docs/release/phase5-restore-evidence.md`
- Existing backup/restore scripts; no new backup product.

**Depends:** G1.2 and G1.3.

- [ ] Configure encrypted off-host backup storage and retention with access controls: separate write credentials for backup jobs, read/restore credentials restricted to named operators, access logging, key custody and an immutable or versioned copy where the provider supports it.
- [ ] Confirm the application runtime role cannot read or write backup storage or backup credentials.
- [ ] Run `backup_compose.sh` against the target deployment with nonempty platform data.
- [ ] Verify `platform-counts.txt`, checksums and freshness marker.
- [ ] Restore into an isolated database and verify counts, journal balance, payment/allocation consistency, credit links and sequences.
- [ ] Run the destructive live-restore path against staging with a deliberate corruption, then prove the corruption is reverted.
- [ ] Prove backup-freshness alerting and a stale-backup failure case.
- [ ] Measure and record RPO and RTO against the approved G1.0 thresholds: **RPO ≤ 24 hours** and **RTO ≤ 4 hours**. Report the actual measured values.

**Acceptance evidence:**
- Isolated restore `ok:true` with all platform counts matching.
- Live restore reverts the corruption and readiness returns 200 within the approved RTO.
- RPO evidence: newest verified backup is ≤24 hours old at the test point; stale-backup alert fires.
- RTO evidence: measured restore-start-to-ready duration ≤4 hours.
- Backup access-control matrix: who can write, read, restore and rotate keys; all access audited.
- A host-loss scenario is documented and, where feasible, rehearsed on staging.
- Restore evidence names the exact backup timestamp and checksums.

### G1.5 — Monitoring, alerting and durable audit retention

**Artifacts:**
- `docs/release/phase5-monitoring.md`
- External monitor/alert configuration; no new in-app observability service.

**Depends:** G1.3.

- [ ] Enable external HTTPS readiness checks for `/health`, `/api/v1/utils/ready/` and login.
- [ ] Ship structured logs, including audit events, to durable access-controlled storage with a defined retention period.
- [ ] Configure Sentry (or equivalent) with PII and request bodies disabled.
- [ ] Alert on: readiness failure, 5xx rate, latency, database health/connections, disk, certificate expiry, backup freshness, backup failure, abnormal 429 volume.
- [ ] Define a financial-reconciliation alert: any unbalanced journal, failed daily reconciliation or nonzero unexplained delta.
- [ ] Verify each alert with a controlled test event and record delivery.

**Acceptance evidence:**
- Alert test matrix with delivery timestamps.
- Log-retention policy and retrieval proof.
- Sentry event shows environment and no PII/body.
- On-call/escalation owner named.

### G1.6 — Due-date and report-period reconciliation decision

**Artifacts:**
- `docs/finance/date-semantics.md` (binding decision record)
- Focused regression tests in `backend/tests/api/routes/test_platform_reports.py` and owner-standing tests.
- Updated `docs/finance/phase4-evidence.md`.

**Depends:** G1.1 finance review.

Phase 4 documented two pre-existing boundaries: owner standing/reminders use invoice due dates while Superuser receivables use receivable due dates; per-gym revenue uses accrual dates while the headline uses journal posting dates.

- [ ] Decide and record canonical semantics:
  - **Billed vs unbilled:** owner-facing overdue and reminders cover **issued invoices only**; accrued but uninvoiced receivables are reported separately as unbilled and are never labeled overdue to the owner.
  - **Superuser receivable reporting:** show billed invoice balance and unbilled receivable balance separately; if a combined number remains, label it `total_exposure` and document the formula.
  - **Revenue range:** the journal `posting_date` is the ledger truth for the headline; per-gym reports must either use the same posting date or publish a reconciliation line. A closed-period unexplained delta must be zero.
- [ ] Inventory every financial report, dashboard, export and owner-facing dues/reminder view, and record its canonical date field and basis.
- [ ] Ensure all financial report date semantics are consistent: no endpoint may mix receivable due dates, invoice due dates, accrual dates and posting dates without an explicit, labeled reconciliation.
- [ ] Reproduce the Phase 4 reviewer scenarios as tests: receivable overdue but invoice not due; credit created after `as_of`; discount journal posted at `period_end` while the invoice was issued earlier; report range splitting the two dates.
- [ ] Resolve any material discrepancy in code or by an explicit report contract, with no silent mixed-basis number.
- [ ] Run the full date-semantics conformance suite before Gate 2 acceptance; a red or unlisted report endpoint blocks Gate 2 entry.
- [ ] Update the 92-decision evidence for decisions #37, #44, #54, #61 and #84.

**Acceptance evidence:**
- `date-semantics.md` signed by product/accounting owner, including the full report-endpoint inventory.
- Tests assert the documented outputs for all four boundary scenarios and for every listed endpoint.
- For a closed synthetic month, `journal recognized revenue − sum(per-gym recognized revenue) = 0 IRR`, or the documented reconciliation line explains the full delta with 0 IRR unexplained.
- No owner-facing screen labels unbilled receivables as overdue.
- Gate 2 entry evidence includes the green date-semantics conformance report.

### G1.7 — Rollback and incident readiness

**Artifacts:**
- `docs/release/phase5-rollback-runbook.md`
- Incident severity matrix and communication template.

**Depends:** G1.3–G1.5.

- [ ] Define rollback triggers: money mismatch, tenant leak, auth bypass, data loss, failed migration, failed restore, provider outage.
- [ ] Document rollback by restoring the last verified backup and deploying the previous tested image; confirm no automatic schema downgrade on real data.
- [ ] Define a finance-freeze procedure that stops new financial writes without deleting history.
- [ ] Rehearse rollback on staging.
- [ ] Define incident severities, owners, customer communication and post-incident review.

**Acceptance evidence:**
- Staging rollback rehearsal record.
- Named incident commander and escalation path.
- Finance-freeze and resume procedure tested or tabletop-reviewed.

### Gate 1 exit criteria

- [ ] G1.0–G1.7 complete.
- [ ] Approved measurable baselines exist and are referenced by the evidence pack.
- [ ] Signed staging-only authorization is recorded; staging cannot reach production resources.
- [ ] Zero open Critical/High security findings, including authentication/token, tenant-isolation, financial-data and backup-access reviews.
- [ ] Staging deployed on a real host with working TLS, SMTP, backups and monitoring.
- [ ] Target-storage restore and live-restore drill pass with nonempty platform data, measured RPO ≤24h and RTO ≤4h.
- [ ] Date-semantics decision recorded; every financial report endpoint is consistent and the conformance suite is green before Gate 2.
- [ ] No real users, no online payments and no real financial transactions have occurred; production deployment authorization remains at Gate 4.

---

## 5. Gate 2 — Staging Acceptance

**Purpose:** Exercise complete financial workflows with synthetic data on the real staging deployment, including failure and recovery paths, before any real gym is onboarded.

**Entry:** Gate 1 exit criteria met, including a signed staging-only authorization and a green date-semantics conformance suite covering every financial report endpoint.

**Exit:** Full synthetic acceptance suite passes on staging; all financial reports use consistent, tested date semantics; reconciliations are zero-delta; a backup is taken and restored during the acceptance window; rollback is rehearsed.

### G2.1 — End-to-end financial workflow script

**Artifacts:**
- `docs/release/phase5-staging-acceptance.md`
- Reuse existing Playwright/API tests; add scenario scripts only where coverage is missing.

**Depends:** Gate 1.

- [ ] Create 3 synthetic gyms representing small, multi-coach and program/private-sales profiles.
- [ ] Run: membership sale → invoice → issue → partial receipt → final receipt → refund request → approval → refund record → platform credit → platform invoice → partial platform payment → final payment.
- [ ] Run coach agreement → sale → earning → vesting → settlement → proof → post-payout refund manual discrepancy.
- [ ] Run group agreement → volume discount → group invoice → per-branch lines → partial payment → cancellation/reissue.
- [ ] Run subscription accrual, commission recognition, credit application, unapplied credit and overdue standing.
- [ ] Verify owner read-only platform billing, coach own-earnings, athlete account and Superuser full access.
- [ ] Export CSV/offboarding data and verify labels and scoping.

**Acceptance evidence:**
- Each workflow has a traceable scenario ID and pass/fail result.
- Amounts reconcile at every step: receivable, invoice, payment, credit, journal, gym summary and platform overview.
- Owner-visible and Superuser-visible numbers are consistent with the date-semantics decision.
- No cross-gym data appears in any export.

### G2.2 — Failure, retry and idempotency scenarios

**Depends:** G2.1.

- [ ] Duplicate receipt, platform payment, subscription accrual, invoice issue, cancellation and refund submissions with the same idempotency key.
- [ ] Changed-payload reuse of an idempotency key is rejected.
- [ ] Failed/aborted transaction leaves no partial business row or journal.
- [ ] Unknown/failed provider-verification path is never marked successful.
- [ ] SMTP failure does not corrupt financial state.
- [ ] Restore and resume after a mid-workflow failure.

**Acceptance evidence:**
- Exactly one business fact and one balanced journal per retried operation.
- No dangling allocation, credit application, invoice line or sequence gap.
- Failure logs include request IDs but no sensitive payloads.

### G2.3 — Concurrency and locking

**Depends:** G2.1.

- [ ] Concurrent receipt allocation against the same invoice.
- [ ] Concurrent platform payment against the same invoice.
- [ ] Concurrent subscription accrual and platform fee recognition.
- [ ] Concurrent invoice cancellation and payment.
- [ ] Concurrent credit application and invoice issue.
- [ ] Concurrent migration/bootstrap on a fresh staging database.

**Acceptance evidence:**
- One winner where only one fact is valid; safe rejection otherwise.
- No over-allocation, double recognition, negative balance or unbalanced journal.
- Documented lock order and retry guidance.

### G2.4 — Accounting reconciliation and period close

**Depends:** G2.1–G2.3.

- [ ] Reconcile platform recognized revenue to the platform journal for a closed synthetic month.
- [ ] Reconcile per-gym recognized revenue to the journal using the date-semantics contract.
- [ ] Reconcile gym summary platform payable to platform receivable and available credit.
- [ ] Reconcile cash collected to payment allocations and platform cash journal.
- [ ] Close a finance period, post a late correction and verify the correction lands in an open period.
- [ ] Verify zero unexplained deltas and zero unbalanced journals.

**Acceptance evidence:**
- Reconciliation workbook/report with line-by-line tie-out.
- Closed-period delta = 0 IRR.
- Any explained delta has a named source document and approval.

### G2.5 — Backup/recovery during acceptance

**Depends:** Gate 1 restore tooling.

- [ ] Take a backup immediately before the acceptance window.
- [ ] Take a second backup after the workflows.
- [ ] Restore the second backup into isolation and verify all finance/platform counts, balances and allocations.
- [ ] Perform a live staging restore and confirm readiness plus a post-restore financial smoke test.
- [ ] Confirm backup freshness and alerting remain green.

**Acceptance evidence:**
- Both backups have checksums and freshness markers.
- Restored totals match the pre-backup totals.
- Post-restore smoke includes at least one invoice, one receipt and one platform payment read.

### G2.6 — Performance and operational limits

**Depends:** G2.1.

- [ ] Measure login, dashboard, invoice list, platform overview and export latency against the approved G1.0 performance thresholds at pilot scale (5 gyms, 10,000 invoices, 25,000 receipts/payments, 100,000 journal lines).
- [ ] Verify single-worker rate limiting and document the `WEB_CONCURRENCY=1` constraint.
- [ ] Verify upload/import size limits and disk usage.
- [ ] Record accepted limits; do not add caching or HA unless a measured blocker appears.

**Acceptance evidence:**
- Latency table with p50/p95 for named pages/endpoints and pass/fail against G1.0.
- Zero unexpected 5xx; 429 only during deliberate abuse tests.
- No endpoint exceeds the approved pilot threshold without a recorded exception and owner.
- Disk headroom ≥2× expected backup size.

### Gate 2 exit criteria

- [ ] G2.1–G2.6 complete.
- [ ] All synthetic workflows and failure/concurrency scenarios pass.
- [ ] Every financial report endpoint passes the date-semantics conformance suite with 0 IRR unexplained delta.
- [ ] Backup/restore during acceptance passes within the approved RPO/RTO targets.
- [ ] Performance meets the approved G1.0 thresholds.
- [ ] No Critical/High incident; all Medium findings have owners.
- [ ] Staging rollback rehearsed after the acceptance window.

---

## 6. Gate 3 — Controlled Pilot

**Purpose:** Operate with 3–5 real gyms under explicit guardrails, collect evidence and feedback, and determine whether the product is safe for wider release.

**Entry:** Gate 2 exit criteria met; signed pilot charter; **Iran legal, tax and privacy signoff**; payment-provider approval only if online/provider-based payments are enabled (otherwise manual-only); synthetic data first, then real data only after all applicable security, operational and legal gates pass.

**Exit:** Pilot duration and participation thresholds met; no unresolved Critical blocker; financial reconciliation and restore evidence complete; GO/NO-GO recommendation prepared.

### G3.1 — Pilot charter, gym selection and onboarding

**Artifacts:**
- `docs/release/phase5-pilot-charter.md`
- Per-gym onboarding checklist and signed participation agreement.

**Depends:** Gate 2.

- [ ] Select 3–5 distinct gyms: at least one small gym, one multi-coach gym and one with program/private sales.
- [ ] Define eligibility: real operating gym, nominated finance contact, willingness to use manual receipts, ability to attend weekly review.
- [ ] Define pilot duration: minimum 4 consecutive weeks and at least one complete billing cycle per gym.
- [ ] Define data use, retention, export and exit terms.
- [ ] Onboard with synthetic/demo data first; enable limited real data only after Gate 1 security/operational evidence, Gate 2 acceptance, and G3.3 legal/tax/privacy signoff are all recorded.
- [ ] Keep online/provider-based payments disabled unless payment-provider approval is separately recorded.
- [ ] Train each gym on invoice, receipt, refund, platform billing and export flows.
- [ ] Record baseline metrics and known limitations.

**Acceptance evidence:**
- 3–5 signed charters.
- Onboarding checklist complete per gym.
- Each gym has a named finance contact and support channel.
- No real financial data before legal/tax/privacy signoff; no online payments unless provider approval is recorded.

### G3.2 — Pilot operations and reconciliation cadence

**Depends:** G3.1.

- [ ] Run a daily reconciliation check: platform receivables, credits, invoice balances, payments and journal balance.
- [ ] Run a weekly full reconciliation and resolve every delta within one business day.
- [ ] Review overdue/dues standing with each gym weekly.
- [ ] Track incidents, support tickets, data corrections and manual workarounds.
- [ ] Record actual usage per gym: invoices, receipts, refunds, platform invoices, payments, exports.
- [ ] Preserve append-only corrections; never edit posted amounts.

**Acceptance evidence:**
- Daily reconciliation log with zero unresolved deltas older than one business day.
- Weekly review notes and action items.
- Incident/ticket log with severity, resolution and prevention.

### G3.3 — Iran legal, tax, privacy and payment-provider verification

**Artifacts:**
- `docs/release/phase5-iran-compliance.md`
- Signed counsel/accountant/provider confirmations.

**Depends:** Parallel track from Gate 1. **Legal, tax and privacy signoff is mandatory before any real financial data or transaction.** Payment-provider approval is mandatory only if online/provider-based payments are enabled.

- [ ] Engage Iran-qualified legal and tax counsel.
- [ ] Confirm contract terms for gym/platform relationships, fee ownership, refunds and dispute handling.
- [ ] Confirm tax treatment, invoice requirements, VAT/sales-tax obligations and record-retention periods.
- [ ] Confirm privacy/consent, data residency, cross-border transfer and retention obligations.
- [ ] Obtain written legal/tax/privacy signoff before any real financial data is loaded or any real transaction is recorded.
- [ ] Decide whether the pilot remains manual-only or enables an online provider. If online is desired, confirm the licensed provider/intermediary, contract and verification requirements; do not enable it before separate provider approval.
- [ ] Confirm settlement, reconciliation and chargeback obligations for any enabled provider.
- [ ] Convert findings into product/config constraints; do not invent legal behavior in code.
- [ ] Record written approval for the exact payment methods enabled in the pilot.

**Acceptance evidence:**
- Signed legal/tax/privacy memo covering contracts, invoices, tax, privacy, retention and permitted payment methods.
- Approved tax-invoice template and retention policy.
- Written authorization to load real financial data and record real transactions.
- If online payments are enabled: provider due-diligence and approval record.
- If online payments are not approved: an explicit manual-only decision and disabled provider path.
- No real financial data or transaction before legal/tax/privacy signoff; no online payment before provider approval.

### G3.4 — Monitoring, support and feedback loop

**Depends:** G1.5 and G3.1.

- [ ] Confirm all Gate 1 alerts remain live during the pilot.
- [ ] Add a pilot issue tracker with severity, owner and SLA.
- [ ] Run a weekly feedback interview or survey with each gym.
- [ ] Track task completion, error rates, support volume and manual workarounds.
- [ ] Publish a weekly pilot status note to the decision owner.
- [ ] Define escalation for suspected financial error or tenant leak.

**Acceptance evidence:**
- Alert delivery log for the pilot period.
- Weekly feedback and status notes.
- Support SLA performance.
- At least one structured usability finding per gym, with disposition.

### G3.5 — Incident, rollback and stop conditions

**Depends:** G1.7 and G3.1.

- [ ] Exercise the finance-freeze procedure during the pilot (tabletop or controlled).
- [ ] Rehearse rollback to the previous tested image and backup on staging during the pilot window.
- [ ] Define stop conditions: money mismatch, tenant data leak, auth bypass, data loss, failed restore, legal/tax/privacy or provider breach.
- [ ] Define customer communication and compensation handling.
- [ ] Conduct a post-incident review for every High/Critical event.

**Acceptance evidence:**
- Rehearsal record.
- Stop-condition decision log.
- No unresolved Critical incident at Gate 3 exit.

### G3.6 — Pilot exit review and offboarding test

**Depends:** G3.1–G3.5.

- [ ] Verify each gym meets the minimum usage and duration threshold.
- [ ] Test offboarding/export for at least one gym, including finance and platform history.
- [ ] Verify retention and deletion obligations with counsel.
- [ ] Summarize acceptance criteria, defects, workarounds and residual risks.
- [ ] Obtain written pilot feedback from each gym.
- [ ] Prepare the Gate 4 evidence pack.

**Acceptance evidence:**
- Offboarding export verified by the gym and internal reviewer.
- Pilot exit report with measured outcomes.
- Written recommendation from product, engineering, security and operations.

### Gate 3 exit criteria

- [ ] 3–5 gyms completed at least 4 weeks and one billing cycle; synthetic data preceded any real data.
- [ ] Daily and weekly reconciliations complete; no unresolved delta older than one business day.
- [ ] Iran legal/tax/privacy signoff recorded before real financial data; payment-provider approval recorded if online/provider-based payments were enabled.
- [ ] No unresolved Critical incident; High incidents remediated or explicitly accepted.
- [ ] Offboarding export tested.
- [ ] Rollback and finance-freeze rehearsed.
- [ ] Pilot feedback and exit report complete.

---

## 7. Gate 4 — Release Decision

**Purpose:** Make an explicit, evidence-based GO/NO-GO decision. This gate does not deploy anything.

### G4.1 — Evidence pack and decision meeting

**Artifacts:**
- `docs/release/phase5-release-decision.md`

**Depends:** Gate 3 exit criteria.

- [ ] Assemble Gate 1–3 evidence: security, environment, restore, date semantics, staging acceptance, pilot metrics, compliance, incidents, feedback.
- [ ] Reconcile the 92-decision matrix and `ADD-01` with Phase 5 evidence; keep #18/#30/#46 Deferred.
- [ ] List every open defect with severity, owner and target date.
- [ ] Hold a decision meeting with product, engineering, security, finance/accounting and operations.
- [ ] Record GO, CONDITIONAL GO or NO-GO with named conditions and expiry.
- [ ] If GO or CONDITIONAL GO, require a separate explicit deployment authorization; this plan does not authorize deployment.

### G4.2 — Measurable GO criteria

All must be true:

- [ ] Zero open Critical security findings; zero open High findings affecting auth, tenancy, money, backup confidentiality or restore.
- [ ] Staging and production-candidate configuration validated; TLS/ACME, SMTP and monitoring proven on the approved target hosts; staging-only isolation proven.
- [ ] Target-storage backup and restore passed, including nonempty platform financial data; measured RPO ≤24h and RTO ≤4h against the approved G1.0 thresholds.
- [ ] Every financial report endpoint passes date-semantics conformance; closed-period unexplained delta = 0 IRR; no unbalanced journal.
- [ ] Full staging acceptance and failure/concurrency suite passed; approved performance thresholds met.
- [ ] 3–5 gyms completed the pilot duration and billing cycle; synthetic data preceded real data.
- [ ] Zero unresolved pilot financial discrepancies; no tenant-isolation incident.
- [ ] Iran legal/tax/privacy signoff recorded before real data; payment-provider approval covers every enabled online method, or the pilot is explicitly manual-only.
- [ ] Rollback, finance-freeze and incident procedures rehearsed.
- [ ] 92 decisions + ADD-01 matrix updated with evidence; no decision silently reclassified.
- [ ] #15/#71, #34 and #91 remain Partial/Outstanding unless genuinely implemented and tested.

### G4.3 — NO-GO and non-blocking improvements

**Immediate NO-GO if any of these is true:**

- Any Critical/High security or tenant-isolation defect.
- Any unresolved money mismatch, unbalanced journal or unexplained closed-period delta.
- Restore cannot recover nonempty platform financial data within the approved RTO.
- Legal/tax/privacy signoff missing before real financial data, or payment-provider approval missing for an enabled online method.
- Fewer than 3 or more than 5 pilot gyms, or pilot duration below the charter threshold.
- Monitoring, rollback or incident response not proven.
- Production/staging environments share secrets, volumes, networks or provider accounts.

**Non-blocking improvements (may ship after the decision with owners and dates):**

- Proactive reminder delivery (#15/#71) — remains **Partial** unless actually implemented and tested.
- Configurable overdue restrictions (#34) — remains **Partial** unless actually implemented and tested.
- Plan-limit enforcement (#91) — remains **Partial** unless actually implemented and tested.
- Performance tuning, richer dashboards, bulk group-member editing, multi-term agreement UI.
- HA, read replicas, point-in-time recovery, shared rate limiter, higher worker count.

Manual pilot SOPs for #15/#71, #34 or #91 are temporary mitigations only. They do not change any decision to Implemented and must be replaced by code plus tests before those requirements are marked complete.

---

## 8. Classification of approved remaining requirements

| Requirement | Classification | Rationale | Required evidence / trigger |
|---|---|---|---|
| **#15 / #71 proactive reminder delivery** | **Partial; pilot-safe deferral with temporary manual SOP** | In-app reminders exist and are explicitly `IN_APP_ONLY`; proactive delivery is not implemented. A controlled pilot may use a manual follow-up SOP, but that does not complete the requirement. | Manual reminder SOP signed by pilot ops; weekly overdue review. Status stays **Partial** until scheduled delivery plus tests exist. Revisit before public release if pilot shows material collections/retention impact. |
| **#34 configurable overdue restrictions** | **Partial; pilot-safe deferral with temporary manual SOP; conditional release blocker** | Current behavior is informational only. Manual enforcement is a temporary pilot mitigation, not the approved configurable restriction feature. | Pilot charter states manual enforcement. Status stays **Partial** until configurable notice/grace/restriction behavior plus tests exist. Required before any contract that promises automatic restrictions. |
| **#91 plan-limit enforcement** | **Partial; post-pilot by design; non-blocking** | PRD says numeric limits are configured after pilot. Usage is surfaced; enforcement is not implemented. | Monitor usage manually. Status stays **Partial** until numeric limits and enforcement plus tests exist. |
| **#53 pilot 3–5 gyms** | **Release-blocking** | Required by decision #53 and #92. | Exactly 3–5 gyms, ≥4 weeks and one billing cycle each, synthetic first, signed charters and exit review. |
| **#54 financial integrity / refunds / tenant / restore / pilot criteria** | **Release-blocking** | Required by decision #54 and #92. | Gate 1 security/tenancy, Gate 2 acceptance and reconciliation, Gate 3 pilot evidence, restore drill. |
| **#56 Iran legal / tax / privacy / provider** | **Legal/tax/privacy release-blocking; provider conditional** | Legal, tax and privacy validation is mandatory before real financial data or transactions. Payment-provider approval is required only if online/provider-based payments are enabled. | Signed legal/tax/privacy memo and real-data authorization; provider diligence only if online payments are enabled, otherwise explicit manual-only decision. |
| **#92 release requirements** | **Release-blocking** | It is the release decision itself. | Gate 4 evidence pack and explicit decision. |
| **#18, #30, #46** | **Deferred — unchanged** | Out of scope by approved decision. | No work in Phase 5; do not mark complete. |

No other decision is reclassified by this plan. All 92 decisions and `ADD-01` remain in force; Phase 5 only adds evidence and status updates.

---

## 9. Dependencies and recommended execution order

### Dependency graph

```
Approval of this plan + staging-only authorization + G1.0 baselines
        │
        ├── G1.1 security/tenancy ── G1.2 DB roles ── G1.3 staging/TLS/SMTP ── G1.4 restore ── G1.5 monitoring
        │                                                        │
        ├── G1.6 date semantics ────────────────────────────────┤
        │                                                        │
        └── G3.3 legal/tax/privacy (mandatory) + provider (conditional) ── Gate 2 ── Gate 3 ── Gate 4
                                                                 │
                                                        G1.7 rollback
```

### Recommended order

1. **Approve the plan, the measurable baselines (G1.0), the staging-only authorization, and name owners** (product, engineering, security, finance/accounting, operations, legal).
2. **Start G3.3 legal/tax/privacy immediately** in parallel; it has the longest external lead time. Start payment-provider diligence only if online payments are intended.
3. **Run G1.1 security/tenancy audit** before exposing any staging host to real users.
4. **Implement G1.2 database roles**, then **G1.3 staging/TLS/SMTP**, **G1.4 restore**, **G1.5 monitoring**, **G1.6 date semantics**, **G1.7 rollback**.
5. **Gate 1 review**; do not start staged workflows until it passes.
6. **Run Gate 2** in order: workflows → failure/retry → concurrency → reconciliation → backup/recovery → performance.
7. **Gate 2 review**; do not onboard real gyms until it passes.
8. **Run Gate 3** with exactly 3–5 gyms; synthetic first, real data only after all applicable security, operational and legal gates; maintain daily/weekly reconciliation.
9. **Run Gate 4** evidence pack and decision meeting.
10. **Separate deployment authorization** if the decision is GO/CONDITIONAL GO.

### Parallel tracks

- Legal/tax/privacy (G3.3) from day 1; provider diligence only if online payments are planned.
- Monitoring/alerting configuration can begin once the approved staging host exists.
- Documentation and evidence templates can be prepared during Gate 1.
- No feature implementation starts until Gate 2 evidence identifies a measured blocker.

---

## 10. Acceptance criteria summary

### Gate 1

- Baselines: RPO/RTO, security, reconciliation and performance thresholds approved before execution (G1.0).
- Security audit: zero Critical/High open; auth/token, tenant, financial-data and backup-access reviews signed.
- Tenant matrix: all cross-tenant attempts denied.
- Database: runtime role least-privilege and migration role separate.
- Staging: staging-only authorization signed; real TLS/ACME, SMTP, isolation and preflight proven; no production resource reachable.
- Restore: target-storage restore and live restore pass with platform data; measured RPO ≤24h and RTO ≤4h.
- Monitoring: all named alerts tested.
- Date semantics: every financial report endpoint consistent and tested; closed-period unexplained delta zero; conformance suite green before Gate 2.
- Rollback: rehearsed.

### Gate 2

- End-to-end synthetic workflows pass for all roles.
- Failure/retry/idempotency: one fact per operation.
- Concurrency: no double recognition or over-allocation.
- Reconciliation: zero unexplained deltas on every report endpoint.
- Backup/recovery during acceptance passes within approved RPO/RTO.
- Performance meets approved thresholds.
- No Critical/High incident.

### Gate 3

- Exactly 3–5 gyms, ≥4 weeks and one billing cycle each; synthetic data first.
- Daily/weekly reconciliation with no unresolved delta older than one business day.
- Iran legal/tax/privacy signoff before real data; payment-provider approval only if online payments enabled.
- No unresolved Critical incident; no tenant-isolation incident.
- Offboarding export tested.
- Rollback and finance-freeze rehearsed.
- Written pilot feedback and exit report.

### Gate 4

- All measurable GO criteria met.
- Explicit GO/CONDITIONAL GO/NO-GO recorded.
- Critical blockers separated from non-blocking improvements.
- #15/#71, #34 and #91 remain Partial/Outstanding unless implemented and tested.
- Deployment requires a separate authorization.

---

## 11. Risk register

| Risk | Impact | Mitigation | Owner gate |
|---|---|---|---|
| Due-date/report-boundary discrepancy misstates dues | Owner disputes, wrong collections | G1.6 canonical decision + boundary tests; zero closed-period delta | Gate 1 |
| Runtime DB uses superuser | Blast radius of credential leak | G1.2 dedicated roles and rotation | Gate 1 |
| Restore passes but loses platform rows | Financial data loss | G1.4 nonempty platform restore and sequence/credit checks | Gate 1 |
| Tenant isolation escape | Cross-gym data breach | G1.1 matrix, regression tests, monitoring | Gate 1 |
| Retry/concurrency duplicates money | Incorrect balances | Gate 2 duplicate/concurrency scenarios | Gate 2 |
| TLS/ACME/SMTP differ from local | Pilot outage | G1.3 real-host proof | Gate 1 |
| Legal/tax/privacy or provider signoff delayed | Cannot use real financial data or enable online payments | Start G3.3 day 1; legal/tax/privacy mandatory; manual-only fallback if provider not approved | Gate 3 |
| Staging accidentally shares production resources | Production impact or data leak | Staging-only authorization, separate projects/volumes/networks/secrets, connectivity checks | Gate 1 |
| Pilot scope creep | Delay and instability | No new features before Gate 2 evidence; strict non-goals | All |
| Manual reminders/restrictions create operational load | Missed follow-ups | Pilot SOP, weekly review, revisit #15/#71/#34 | Gate 3 |
| In-process rate limiter limits scale | Abuse or outage | Keep `WEB_CONCURRENCY=1`; accept pilot scale; shared limiter post-pilot | Gate 3/4 |

---

## 12. Stop conditions

Stop the current gate and escalate immediately if any of the following occurs:

- Any confirmed cross-tenant financial data exposure.
- Any unbalanced journal, unexplained money mismatch or duplicated financial fact.
- A restore that cannot recover nonempty platform financial data.
- An authentication or authorization bypass.
- A real financial data load or transaction before legal/tax/privacy signoff, or an online payment enabled without provider approval.
- Loss or corruption of posted financial history.
- A production/staging environment sharing secrets, volumes, networks or provider accounts.

Resume only after the root cause is fixed, regression-tested, and the decision owner records the resolution.

---

## 13. Decision preservation

- `docs/finance/phase4-evidence.md` remains the authoritative individual matrix for decisions 1–92 and `ADD-01`.
- Phase 5 updates statuses only with evidence; it does not delete, merge or renumber rows.
- #18, #30 and #46 remain **Deferred** throughout.
- #15, #71, #34 and #91 remain **Partial/Outstanding** unless their actual code and tests are implemented; manual pilot SOPs are temporary mitigations and never count as completion.
- #53, #54, #56 and #92 are satisfied only by Gate 3–4 evidence.
- Any proposed new decision or behavior requires explicit approval before implementation.

---

## 14. Approval required before execution

This document is a plan only. No implementation, deployment, staging data load, real financial operation, merge or provider integration may begin until the decision owner explicitly approves:

1. this Phase 5 plan and the measurable G1.0 baselines,
2. a staging-only authorization naming the staging host/resources and confirming no production resource is reachable or shared,
3. the named owners (product, engineering, security, finance/accounting, operations, legal),
4. the pilot charter and data-use terms,
5. the exact payment methods allowed during the pilot (manual-only unless provider approval is recorded),
6. the separate deployment authorization if Gate 4 returns GO or CONDITIONAL GO.
