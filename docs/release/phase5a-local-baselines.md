# Phase 5A.0 — Local Acceptance Baselines

**Date:** 2026-11-03
**Branch:** `feat/ascora-finance`
**Scope:** Phase 5A local hardening and acceptance only
**Status:** Approved baseline for 5A.1–5A.7

## Approval record

The project owner approved the local-first Phase 5A plan at commit `d0511cf` and instructed that 5A.0 and 5A.1 begin. That instruction is the approval for these baselines.

This record intentionally does **not** invent signatures, external reviewers, auditors, legal sign-off or provider approval. Where an external role is required, it is listed as a future Phase 5B dependency, not as completed.

## Execution boundary

- All work remains local.
- Only existing local PostgreSQL, backend, frontend and Docker tooling may be used.
- No Vercel/Neon deployment or configuration changes.
- No remote staging or production deployment.
- No new hosting, DNS, SMTP provider, monitoring service or payment gateway.
- No real financial data; all acceptance data is synthetic and disposable.
- No merge to `main`.
- No new product features, redesign or unrelated refactoring.

## 1. Local security thresholds

| Criterion | Approved threshold | Evidence owner |
|---|---|---|
| Critical/High findings | **0 open** at 5A.1 exit | Security audit |
| Tenant isolation | **100%** of cross-gym attempts denied across API, exports, forged `X-Gym-ID`, forged path IDs and client filters | 5A.1 matrix |
| Authentication/token review | Logout and password change revoke existing tokens; reset and invitation tokens are single-use/expiring; CSRF enforced for cookie-auth unsafe requests; no token leakage in logs | 5A.1 |
| Secrets | **0** local secrets committed, baked into images, printed in logs, fixtures or screenshots | 5A.1 |
| Sensitive financial data | **0** real financial PII in logs, exports, test fixtures or screenshots | 5A.1 |
| Local backup access | Backups readable only by the operator; file modes restrictive; checksums verified; no application-runtime access | 5A.1 / 5A.4 |

## 2. Local accounting thresholds

| Criterion | Approved threshold |
|---|---|
| Closed-period reconciliation | **0 IRR unexplained delta** |
| Journal balance | **0** unbalanced journals |
| Duplicate financial facts | **0** after retry/idempotency tests |
| Allocation/credit/sequence consistency | **0** mismatches |
| Report date semantics | **100%** of financial report endpoints covered by conformance tests |
| Owner-facing unbilled amounts | **0** unbilled amounts labeled overdue |

## 3. Local recovery thresholds

| Criterion | Approved threshold |
|---|---|
| Docker backup/restore | PASS with nonempty platform financial data |
| Restored counts | Exact match with the backup |
| Journal/ledger integrity | All journals balanced; allocations, credits and sequences reconcile |
| Local restore duration | **≤ 60 minutes** on the reference development machine |
| Operational RPO/RTO | Not a Phase 5A target; deferred to Phase 5B |

Phase 5A proves local recoverability, not a production service level.

## 4. Local migration thresholds

| Criterion | Approved threshold |
|---|---|
| Upgrade → downgrade → upgrade | PASS on a disposable local database |
| Migration tests | PASS at the expected head |
| Existing data preservation | No athlete, role, program or finance history silently rewritten |
| Full local regression | PASS after defect fixes |

## 5. Local UI/UX thresholds

| Criterion | Approved threshold |
|---|---|
| Required role journeys | **100%** pass for Superuser, gym admin, finance staff, coach and athlete |
| Cross-role visibility | **0** cases where a role sees another role's or gym's data |
| Critical/High usability defects | **0** blocking a required journey |
| Local load/error check | Key finance screens load without errors; measured time recorded, not treated as a production SLA |
| Scope | No redesign, no new feature, no unrelated refactor |

## 6. Local defect-closure thresholds

| Criterion | Approved threshold |
|---|---|
| Critical/High defects | Fixed with a focused regression test |
| Medium/Low defects | Explicit accept/fix decision with owner |
| Full local regression after fixes | PASS |
| Unrelated refactoring | Not allowed |

## 7. Baseline change control

Any change to these thresholds after approval requires:

1. a recorded reason,
2. the project owner's approval,
3. the affected evidence record updated,
4. a note in the 5A.7 LOCAL GO/NO-GO report.

## 8. Evidence map

| Baseline area | Primary evidence |
|---|---|
| Security and tenancy | `docs/release/phase5a-security-audit.md` |
| Financial acceptance | `docs/release/phase5a-local-financial-acceptance.md` |
| Reconciliation/date semantics | `docs/finance/date-semantics.md`, `docs/release/phase5a-reconciliation.md` |
| Migration/recovery | `docs/release/phase5a-migration-recovery.md` |
| UI/UX | `docs/release/phase5a-local-ui-acceptance.md` |
| Final decision | `docs/release/phase5a-local-go-no-go.md` |
