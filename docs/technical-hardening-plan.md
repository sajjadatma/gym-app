# Gym App — Evidence-Gated Technical Hardening Plan

**Audience:** OpenCode (implementing agent)  
**Repository:** `https://github.com/sajjadatma/gym-app`  
**Audit reference:** `main` at `465a6afe37bcfe3139ad107f395dca371a3e13fe` (2026-10-24)  
**Goal:** Make the existing Gym Management MVP1 codebase more trustworthy without adding product features or rewriting working architecture.

> **MANDATORY — INDEPENDENT VERIFICATION BEFORE EVERY FIX**  
> The findings below are **audit hypotheses / risks, not instructions to blindly change code**. You are an independent reviewer. For **each** item, first inspect the **current** implementation, the latest approved specification, existing tests, and relevant call sites; reproduce or otherwise demonstrate the failure where feasible. **Apply a fix ONLY if your own technical review confirms a real defect or a necessary, in-scope security/reliability gap.** If the finding is false, already fixed, an intentional documented behavior, or not justified for the current local-only MVP, mark it **REJECTED / ALREADY FIXED / DEFERRED** with precise evidence; **do not change code** for that item. If a fix requires an unresolved product decision, mark **BLOCKED: PRODUCT DECISION** and explain the smallest choice needed. Do not invent requirements or silently change existing approved behavior.

## 0. Operating contract

1. Work in the existing repository. Verify `git status`, current branch/commit, README, `docs/implementation-progress.md`, approved MVP1 specification, migration history, and test commands. Never assume the audit reference is still HEAD.
2. Preserve the approved stack and existing product experience: FastAPI, SQLModel, PostgreSQL, React/Vite/TypeScript, Alembic, Pytest, Playwright, Persian RTL, Jalali, Material Design 3, and the local-first scope. **No framework migration, broad refactor, new infrastructure, new product feature, or speculative architecture.**
3. First run a baseline on a **dedicated test database**. Do not reset, truncate, or migrate real/development data without explicit authorization. Never execute `reset_dev_db.sh` on existing user data. Make a backup before any destructive migration, if one becomes necessary.
4. For each candidate issue, record: `Evidence → Independent verdict → Minimal fix (if confirmed) → Regression test → Verification`. Prefer a failing regression test **before** the fix (red/green), when reproducible.
5. Protect multi-gym isolation, current coach assignments, athlete privacy, archived-history semantics, and uniqueness constraints. All privileged operations must be enforced **server-side**; UI affordances are not authorization.
6. Favor a small, readable, maintainable change over introducing libraries, layers, queues, microservices, or distributed systems. Do not suppress exceptions, remove tests, weaken type checks, or alter specifications to make tests green.
7. Work in independently reviewable stages, with an atomic commit after each completed stage. If GitHub push is supported and authorized by the existing workflow, push after a successfully verified stage; otherwise report local commit hashes. Do not force-push or bypass branch protections.
8. If a finding is unverified or blocked, continue with the remaining independent tasks where safe. **Do not ask for blanket approval to start:** the explicit approval is to perform *evidence-validated, in-scope* fixes. Ask only about truly ambiguous product policy or potentially destructive actions.
9. Do **not** make claims of successful test execution unless the commands actually ran and produced passing output. Do not count a successful build as proof of security or concurrent correctness.

## 1. Stage A — Establish a trustworthy baseline (no behavioral changes)

**A1. Reconcile source of truth**
- Identify the current commit and any changes since `465a6afe`.
- Locate the **latest** approved MVP1 specification and later recorded decisions. In particular, `docs/implementation-progress.md` documents **editable ACTIVE workout program versions** (2026-10-22). **Do not automatically convert ACTIVE to immutable or force creating a new version** based on an older assumption. Distinguish deliberate product behavior from an implementation defect.
- Check for existing fixes, tests, CI workflows, policies, and security controls before proposing replacements.

**A2. Run and document the baseline**
- Backend: `cd backend && uv sync && uv run pytest -q && uv run ruff check . && uv run ty check . && uv run alembic check` (adjust only when repository instructions require it; `TEST_DATABASE_URL` must point to a disposable `_test` database).
- Frontend: `cd frontend && bun install --frozen-lockfile && bun run build` (use the repository's actual lockfile and supported install flags).
- Run Playwright against the documented isolated demo/test environment if available. Record test counts, failures, skipped tests, tool versions and setup constraints.
- Review whether the existing reported `20 passed`, `31 passed`, and `25 passed` are still reproducible; they are **historical reports**, not proof of the current commit.
- Create `docs/technical-hardening-audit.md` with a findings table: ID, severity, evidence (file/function + lines), independent verdict, test/reproduction, fix commit, verification result, remaining risk.

**Stage A exit:** a factual baseline and a validated/rejected/deferred decision for every finding below. Only then begin code modifications.

## 2. Stage B — Authentication and security (highest risk first)

### SEC-01 — Password-reset token replay
**Inspect:** `backend/app/api/routes/login.py` (`reset_password`), `backend/app/utils.py` (`_generate_token`, `decode_purpose_token`), user/security models.  
**Hypothesis:** password-reset JWTs remain valid until expiry even after successful use or password change.  
**Independent gate:** reproduce reuse of the **same reset token** for two successful password resets; confirm no existing invalidation mechanism elsewhere.  
**If confirmed:** implement a minimal, server-validated one-time or version-based invalidation that survives restarts; invalidate prior recovery tokens on successful reset as appropriate. Keep purpose, expiry, and secret validation. Consider concurrent redemption.  
**Regression:** first redemption succeeds; second fails; expired, wrong-purpose, malformed, and previously invalidated tokens fail; no sensitive token is logged.

### SEC-02 — Long-lived login JWTs after password changes / account revocation
**Inspect:** `backend/app/core/config.py` (`ACCESS_TOKEN_EXPIRE_MINUTES` currently appears to default to 8 days), `backend/app/api/deps.py` (`get_current_user`), `backend/app/api/routes/users.py`, logout behavior in `frontend/src/auth.tsx`.  
**Hypothesis:** a stolen valid bearer token continues working after a password change (until expiry), since the JWT verifier does not check revocation or credential-change version.  
**Independent gate:** demonstrate using an old token after a password change; examine whether this is intentionally accepted for the local-only MVP and whether server-side role/member removal already takes effect (do not misreport role-revocation behavior).  
**If justified:** use the smallest robust server-side token invalidation rule (e.g., auth/session version or `tokens_valid_after`) and test reset/change-password/logout semantics separately. Do **not** add full refresh-token/session infrastructure without a demonstrated need.  
**Regression:** stale token rejected after the relevant revoking event; new token works; current membership and gym authorization still operate correctly.

### SEC-03 — Login/recovery abuse controls
**Inspect:** login and recovery endpoints, middleware, existing rate limits, test environment and deployment scope.  
**Hypothesis:** no protections against repeated authentication guesses/recovery requests.  
**Independent gate:** confirm actual absence; determine whether public/network deployment is within scope.  
**If justified for current scope:** add narrowly scoped, tested throttling with sane error handling and no account enumeration. If a durable multi-instance limiter would require new infrastructure outside MVP1, **defer with a clear production-release blocker**, rather than silently adding Redis.  
**Regression:** normal login/recovery unaffected; abusive attempts receive expected response; failure message does not reveal account existence.

### SEC-04 — Browser token storage and XSS surface (risk assessment, not automatic rewrite)
**Inspect:** `frontend/src/api.ts`, `frontend/src/auth.tsx`, any raw HTML/unsafe rendering, dependency versions, CSP and the SPA/PWA service worker.  
**Hypothesis:** bearer tokens stored in `localStorage` can be exposed if XSS occurs.  
**Independent gate:** establish the actual threat and whether there is a feasible XSS vector. `localStorage` alone is **not evidence of an XSS vulnerability**.  
**Action:** fix any confirmed injection issue. Document the storage tradeoff. **Do not migrate blindly to cookies** (that changes CSRF, same-site and session design). If a storage redesign is warranted only for public hosting, make it a clearly labeled production-readiness item, not an unapproved MVP rewrite.

## 3. Stage C — Data integrity and authorization

### DATA-01 — File deletion and DB commit are not atomic
**Inspect:** `backend/app/api/routes/athletes.py` (`delete_athlete`) and `backend/app/services/storage.py` (`delete_stored_file`).  
**Hypothesis:** files are deleted **before** `session.commit()`; a subsequent transaction failure could leave DB metadata pointing to missing files.  
**Independent gate:** trace the code and test an injected DB commit failure with temporary files/test DB.  
**If confirmed:** use a minimal, well-documented deletion/compensation strategy that keeps filesystem and DB consistent or safely retryable. Prefer a reversible staging operation or post-commit cleanup with reliable recovery. **Do not introduce an external job queue for a local-only MVP.** Handle missing files idempotently.  
**Regression:** simulated commit failure preserves/recovers all user files and DB records; successful deletion removes both; repeated cleanup is safe.

### DATA-02 — Uploads can orphan files when DB commit fails
**Inspect:** `backend/app/api/routes/athletes.py` (`upload_body_file`), `backend/app/services/storage.py` (`save_body_analysis_upload`).  
**Hypothesis:** file is written before its DB row is committed and is left orphaned if commit fails.  
**Independent gate:** prove via injected commit failure; check for existing cleanup hooks.  
**If confirmed:** add the smallest safe rollback cleanup/compensation and deterministic exception handling.  
**Regression:** failed DB save leaves no orphan; successful upload remains permission-checked.

### DATA-03 — Deleting ACTIVE/ARCHIVED program versions
**Inspect:** `backend/app/api/routes/programs.py` (`delete_program_version`) and approved lifecycle requirements.  
**Hypothesis:** API allows deletion of any version, potentially destroying published or archived history.  
**Independent gate:** prove role-authorized ACTIVE and ARCHIVED deletion through direct API calls and compare to the **latest** approved behavior.  
**If confirmed as a defect:** limit destructive deletion to the explicitly allowed states (usually DRAFT); preserve archived history and ensure no inconsistent active-program state. Do not invent retention rules.  
**Regression:** allowed deletion succeeds; prohibited status is rejected; history and one-active-program invariant remain intact.

### DATA-04 — Archived athlete remains editable through backend API
**Inspect:** `backend/app/api/routes/athletes.py` (`update_athlete`, body-file operations, archive/restore), `backend/app/api/deps.py` (`get_athlete_access(allow_archived=True)`).  
**Hypothesis:** staff can still update archived athlete profiles despite UI claiming they are read-only.  
**Independent gate:** call the PATCH endpoint on an archived athlete as an authorized admin and verify if mutation succeeds. Check the spec for any permissible archived mutations.  
**If confirmed:** reject unauthorized archived mutations server-side; keep restore/delete/read behaviors as approved.  
**Regression:** archived profile immutability via direct API; restoring re-enables allowed editing; coach and cross-gym access cannot bypass rules.

### DATA-05 — Concurrent program edits cause silent lost updates
**Inspect:** `backend/app/api/routes/programs.py` (`update_program_version`), `backend/app/services/programs.py` (`replace_version_days`), related frontend editor.  
**Hypothesis:** two editors save the same version and the later write silently overwrites the earlier changes.  
**Independent gate:** reproduce with two sessions or requests against the same version. Evaluate importance for intended multi-coach operation.  
**If confirmed and in scope:** implement lightweight optimistic concurrency (e.g., revision/expected revision with HTTP 409), with a clear user-facing conflict path. Migration only if essential. Avoid locking schemes or event sourcing.  
**Regression:** concurrent/stale update is rejected without data loss; retry after refresh is possible; normal save works; preserve **approved editable ACTIVE** behavior.

### DATA-06 — Version number race
**Inspect:** `backend/app/services/programs.py` (`next_version_number`, currently `MAX + 1`), `backend/app/models.py` (`uq_program_version_number`), draft creation routes.  
**Hypothesis:** simultaneous draft creation can collide and surface an unhandled database error.  
**Independent gate:** reproduce with concurrent transactions (or explain why current handling is sufficient); existing DB uniqueness is a positive control and must remain.  
**If confirmed:** use a small transaction-safe allocation/retry or explicit conflict response; do not remove the unique constraint.  
**Regression:** concurrent request behavior is deterministic; no duplicate versions and no HTTP 500 from a routine conflict.

### DATA-07 — Delete scope and cross-gym identity safety
**Inspect:** athlete deletion, assignment/profile/program cascades, membership/role checks, and shared global `User` identity.  
**Risk to verify:** deleting one gym's athlete must never destroy an account or data still needed by a different gym or an ownership/admin relationship.  
**Independent gate:** exercise multi-gym users with overlapping roles, membership and assigned programs. Confirm scope in database, not only UI.  
**If confirmed:** fix the smallest scope/retention bug and add a regression. No blanket changes to account deletion policy.

## 4. Stage D — Upload safety, quality gates, recovery

### HARD-01 — Unbounded request read before import file-size check
**Inspect:** `backend/app/api/routes/athletes.py` (`await file.read()` in both import endpoints), `backend/app/services/athlete_import.py` (`MAX_IMPORT_BYTES`, `MAX_IMPORT_ROWS`, XLSX/CSV parsing).  
**Hypothesis:** the server reads the entire uploaded file into memory before applying the application-level 5 MB limit.  
**Independent gate:** demonstrate request-processing behavior, checking whether an upstream request-size limit already exists.  
**If confirmed:** stream/read at most `MAX_IMPORT_BYTES + 1`, reject oversize as 413, preserve current CSV/XLSX row-validation semantics. Consider XLSX decompression/memory risks only where demonstrable; no generic file-processing framework.  
**Regression:** oversized content rejected without full buffering; valid/invalid CSV/XLSX behave as before.

### HARD-02 — Migration path is not exercised by API test fixture
**Inspect:** `backend/tests/conftest.py` (currently appears to use `SQLModel.metadata.drop_all/create_all`), Alembic migrations and the reported `alembic check`.  
**Hypothesis:** passing API tests do not prove that real schema migrations work from an older DB.  
**Independent gate:** confirm fixture behavior and existence of separate migration tests.  
**If confirmed:** add a **separate** automated migration smoke test on disposable DB: baseline upgrade, upgrade to head, schema checks, and a representative data-preservation migration path when applicable. Preserve fast API fixture if valuable. **Never run migration tests on the user's main DB.**

### HARD-03 — Quality checks mutate code / no enforced CI
**Inspect:** `frontend/package.json` (`lint` appears to use `--write --unsafe`), `.github/workflows`, backend lint/type configs, status checks, README.  
**Independent gate:** verify what already exists; absence of a `backend.yml` alone does not prove all CI is absent.  
**If confirmed:** add a non-mutating `lint:check` (e.g., `biome check` without `--write/--unsafe`), preserve explicit `lint:fix`; configure the smallest suitable CI gates for the repo's intended workflow (backend tests/lint/type, frontend build/lint, migration test). Avoid deploying/hosting changes. Treat external CI availability as separately verifiable.

### HARD-04 — Negative/security and recovery tests
**Inspect:** current Pytest/Playwright coverage and API authorization boundaries.  
**Independent gate:** map current tests first; do not duplicate existing scenarios.  
**Add only missing high-value regressions** for: cross-gym data access; revoked coach permissions; archived edit/delete constraints; reset token replay; stale JWTs where revocation is required; file upload/download ownership; transaction failure and rollback; concurrent editor/version creation; empty/oversized imports; restore with cross-gym roles.  
**Evidence:** report executed commands, test counts and specific test names. Do not claim coverage percentage without measuring it.

### HARD-05 — Backup/recovery and lifecycle operational checks
**Inspect:** existing backup docs, test DB reset script, Alembic migration instructions.  
**Independent gate:** determine intended scope. A local-only MVP does **not** need an invented cloud backup platform.  
**If justified:** document and **test on disposable sample data** a minimal PostgreSQL backup/restore procedure and body-analysis-file recovery procedure. Include verification that a restored athlete's profile, workout history and private attachments remain consistent. Do not copy or expose private user data in logs/artifacts.

## 5. Mandatory execution sequence

1. **Audit pass only.** Validate each finding and produce the verdict table in `docs/technical-hardening-audit.md`. Mark each as `CONFIRMED`, `REJECTED`, `ALREADY FIXED`, `DEFERRED` or `BLOCKED: PRODUCT DECISION`, including evidence. Do not change application behavior during this pass.
2. **Implement confirmed critical/high findings first:** SEC-01, SEC-02 (if justified), DATA-01, DATA-02, DATA-03, DATA-04, DATA-07. Recheck the verdict immediately before each edit.
3. **Implement confirmed medium findings:** DATA-05, DATA-06, HARD-01, then SEC-03/SEC-04 according to release scope.
4. **Strengthen verification:** HARD-02, HARD-03, HARD-04, HARD-05. Avoid writing tests that only assert mocked happy paths while missing the production failure mode.
5. **Run full verification after each stage**, not only at the end. Do not mark a stage complete if relevant tests fail; distinguish pre-existing failures with recorded evidence.
6. **Final independent review:** reread all changed files as a reviewer; inspect for hidden breaking changes, incorrect tenant filters, information disclosure, excessive complexity and missing rollback/negative tests. Verify the README/progress doc aligns with actual behavior. Commit the audit report and any approved changes.

## 6. Definition of Done (strict)

- Every hypothesis has an **independent verdict with code/test evidence**; unconfirmed findings caused **no edits**.
- Every confirmed and in-scope defect has a **minimal fix** plus at least one targeted regression test demonstrating the failure mode.
- No unauthorized cross-gym data access; no new exposure of athlete notes/files; no accidental deletion or corruption of existing history.
- Backend tests, lint/type checks, frontend build/lint, applicable Playwright suites, and migration smoke tests pass **or** remaining failures are specifically documented as blockers. No misleading green status.
- No production credentials, tokens, real user datasets, or sensitive files added to git/logs/test fixtures.
- No unrelated new features, architecture rewrites, renaming campaigns, or dependency upgrades unless a demonstrated vulnerability requires it.
- Final `docs/technical-hardening-audit.md` contains: baseline commit and final commit, verdicts, high-risk changes, exact tests and outputs, CI status, remaining risks, and **GO / NO-GO for use with real user data** (a code-only review is insufficient for unconditional production GO).

## 7. Final response required from OpenCode

Return a concise factual summary with:

1. Current repo commit, original baseline and final commit(s).
2. A table: `ID | Verdict | Evidence | What changed (or why not) | Tests`.
3. Exact passing/failing commands and counts; highlight any test not run.
4. Breaking behavior / migration notes and rollback instructions where relevant.
5. Outstanding blockers and a defensible `GO / NO-GO` recommendation.

**Success criterion:** the result is more reliable and independently evidenced—not simply a longer test suite, a completed checklist, or an agent claiming that everything passed.
