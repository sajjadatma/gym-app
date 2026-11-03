# Phase 5A.1 — Independent Security and Tenant-Isolation Audit

**Date:** 2026-11-03
**Branch:** `feat/ascora-finance`
**Audited baseline:** `d0511cf` plus the local 5A.1 fixes in this change set
**Scope:** Local-only authentication, authorization, tenant isolation, sensitive financial data, local backup access and secret handling
**Mode:** Read-only audit by a fresh-context independent reviewer, followed by focused local fixes and regression tests. No remote services, deployments, real data or real financial operations were used.

## 1. Method and evidence

- Independent fresh-context reviewer inspected the actual route/service code, ran targeted security suites and the full local backend suite, and built reproducible probes outside the repository.
- The reviewer's pre-fix baseline: **42 targeted security/isolation tests passed** and **299 full-suite tests passed**.
- Findings were re-verified against the code and reproduced before fixes.
- Focused failing tests were written first for the Critical and High findings; both failed for the expected reasons before the fixes.
- Post-fix targeted security suite: **60 passed**.
- Post-fix full local backend suite: **301 passed**.
- Ruff: clean. Mypy: clean.

## 2. Findings and disposition

| ID | Severity | Finding | Status |
|---|---|---|---|
| SEC-5A-01 | **Critical** | Cross-tenant account takeover of pending invited users via `activate_user` | **Fixed** |
| SEC-5A-02 | **High** | Amount limits accepted for every finance permission but enforced only for opening balances | **Fixed (fail-closed)** |
| SEC-5A-03 | Medium | Production/local secret files world-readable | **Mitigated locally** |
| SEC-5A-04 | Medium | Backup directory not Git-ignored; Docker build context includes secret files | **Accepted for local 5A; Phase 5B follow-up** |
| SEC-5A-05 | Low | Uploaded files/directories use permissive default modes | **Accepted for local synthetic data; Phase 5B follow-up** |
| SEC-5A-06 | Low | Invitation acceptance is not atomic | **Accepted; Phase 5B follow-up** |
| SEC-5A-07 | Low | Email change does not require re-authentication | **Accepted; Phase 5B follow-up** |
| SEC-5A-08 | Low | No admin-initiated session revocation on membership deactivation | **Accepted; Phase 5B follow-up** |
| SEC-5A-09 | Low | Reset/invitation tokens travel in query strings | **Accepted; Phase 5B follow-up** |
| SEC-5A-10 | Low | API JSON responses lack explicit `Cache-Control: no-store` | **Accepted; Phase 5B follow-up** |
| SEC-5A-11 | Low | Database password appears in `pg_dump`/`pg_restore` command lines | **Accepted for local 5A; use `.pgpass` in Phase 5B** |

## 3. Critical finding — SEC-5A-01

### Root cause

`backend/app/services/membership.py:124` (`activate_user`) allowed any caller with member/athlete creation permission to set an initial password for an **existing** user whose account was still pending (`hashed_password=None`).

Affected paths:
- Gym member creation: `backend/app/api/routes/gyms.py`
- Athlete creation: `backend/app/services/athlete_lifecycle.py`
- Bulk athlete import: `backend/app/services/athlete_import.py`

### Reproduction (pre-fix)

1. Create Gym A with an owner who has a password.
2. As Superuser, create Gym B with `activation_method="invite"`; its owner is pending with no password.
3. As the Gym A owner/admin, create a member in Gym A using the Gym B owner's email, `activation_method="password"` and an attacker-chosen password.
4. The pre-fix response returned the attacker password as `initial_password`.
5. Login as the Gym B owner with the attacker password succeeded.
6. The attacker then read Gym B members and finance settings as the victim owner.

This was a full cross-tenant takeover, not only a data-read issue.

### Fix

`backend/app/services/membership.py:178` now **never** sets a password for an existing user. An existing passwordless user must accept an invitation, which proves control of the email address. The caller-supplied `initial_password` is ignored and no password is returned.

### Regression test

`backend/tests/api/routes/test_gym_isolation.py:323`
`test_gym_admin_cannot_set_password_for_pending_user_in_another_gym`

The test failed before the fix with `initial_password == "attacker-set-pass-123"` and passes after the fix. It also proves:
- the attacker password cannot log in;
- the victim can still accept the invitation;
- the victim retains Gym B owner access.

## 4. High finding — SEC-5A-02

### Root cause

`FinanceGrantItem.amount_limit_irr` is accepted for every grantable permission, but `FinanceScope.amount_limit` was enforced only by `post_opening_balance` (`backend/app/services/finance.py:663`). A finance staff member with a configured expense/receipt/refund/invoice/membership/settlement limit could exceed it.

### Reproduction (pre-fix)

1. Owner grants `finance.expense.manage` with `amount_limit_irr=1000`.
2. Staff creates an expense of `1,000,000`.
3. Pre-fix response: `200`; the limit was ignored.

### Fix

`backend/app/services/finance.py:1021` (`replace_grants`) now fails closed: an amount limit is rejected for any permission other than `finance.opening.manage` with `400 finance_amount_limit_not_supported`. The UI only exposed the opening-balance limit, so no supported workflow is removed.

This closes the false-control vulnerability. Full per-action amount enforcement remains outstanding and is recorded as a Partial status for decisions #42 and #90.

### Regression test

`backend/tests/api/routes/test_finance_grants.py:417`
`test_amount_limit_is_rejected_for_permissions_without_enforcement`

The test failed before the fix (`200` instead of `400`) and passes after the fix. It also confirms that `finance.expense.manage` without a limit is still grantable.

## 5. Medium findings

### SEC-5A-03 — Secret file modes

Observed `644` on `.env.local`, `.env.stage` and `.vercel/.env.production.local`. These contain local/remote credentials and were not committed. They were tightened to `600` locally, along with `.env` and `.env.dev`. No values were printed or committed.

Decision: **mitigated locally**. If the workstation is shared or synced, rotate any credentials that may have been exposed.

### SEC-5A-04 — Backup/Docker context hygiene

`backups/` is not Git-ignored, and `.dockerignore` does not exclude `.env*`, `.vercel`, `backups`, `uploads` or `backend/uploads`. No backup directory or remote Docker builder is in use for local 5A.

Decision: **accepted for local-only 5A**. Add these exclusions and move the default backup directory outside the repository before Phase 5B or any remote build.

## 6. Low findings (accepted for local 5A)

- Invitation acceptance lacks a row lock; concurrent redemptions can race.
- Email change does not require re-authentication or bump `token_version`.
- Membership deactivation does not revoke existing sessions; no admin revocation endpoint.
- Reset/invitation tokens appear in query strings and may reach browser history.
- Authenticated API JSON lacks explicit `Cache-Control: no-store`.
- `pg_dump`/`pg_restore` receive the database URL (including password) on the command line.
- Login timing can reveal account existence.

None is a Critical/High blocker for local synthetic acceptance. Each is recorded for Phase 5B hardening; no redesign was attempted.

## 7. Confirmed-safe areas

- Access cookie is `HttpOnly`, `SameSite=lax`, and `Secure` is enforced in production/hosted staging.
- CSRF double-submit is enforced for cookie-authenticated unsafe methods; bearer requests are intentionally exempt.
- Login and recovery enforce trusted-origin checks and IP/identity rate limits with `Retry-After`.
- Logout increments `token_version` and clears cookies; password change/reset revokes old tokens under row locks.
- Reset tokens are single-use and version-bound; invitation/reset tokens are purpose-bound and expiring.
- Superuser routes use `CurrentSuperuser`; finance routes resolve a gym-scoped `FinanceScope`; finance staff are denied operational/admin routes.
- Platform owner views are read-only and gym-scoped; platform writes remain Superuser-only.
- Cross-gym path IDs return `404`; forged `X-Gym-ID` is rejected without membership.
- Finance/platform exports are gym-scoped; platform exports are Superuser-only.
- Body-analysis files are gym/athlete-scoped, permission-checked and validated by type/size/magic bytes.
- Logs include request IDs and redacted paths, not bodies or query strings; Sentry PII and request bodies are disabled.
- No real secrets were found in tracked Git history; `.env*` files are gitignored.
- Backup scripts use restrictive modes, checksums and confirmation-gated restore.

## 8. 5A.1 follow-up hardening

Two narrow follow-ups were completed after the initial 5A.1 report:

- **Legacy grant limits:** no unsupported legacy grants existed in the local development database, but the read model now normalizes any legacy unsupported `amount_limit_irr` to `None` while preserving the stored grant row and audit history. A regression test inserts a legacy row directly and proves the API no longer presents it as an enforced limit.
- **Initial-password return:** `activate_user` now returns an initial password only for a newly created user (`created=True`). An existing user never receives a caller-supplied password in the response. A regression test proves the response is `None` and the attacker-supplied password cannot log in.

Follow-up evidence:
- Targeted 5A.1 security/isolation suite: **62 passed**.
- Full backend suite after the follow-ups and 5A.2 additions: **308 passed**.
- Ruff and Mypy clean.

## 9. Verdict

**5A.1 PASS — LOCAL GO for this workstream.**

- Zero open Critical/High findings after the fixes and follow-ups.
- Every fix has a focused regression test that failed before the fix and passes after it.
- Full local backend regression is green.
- Medium/Low findings are accepted for local-only 5A with explicit Phase 5B follow-ups.
- Decisions #42 and #90 are corrected to **Partial** because per-action amount enforcement is not complete; the immediate false-control vulnerability is closed.
- 5A.2 was subsequently executed under separate approval; 5A.3–5A.7 have not started.
- No merge to `main`, remote deployment, provider integration or real financial data was performed.
