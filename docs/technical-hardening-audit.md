# Technical Hardening Audit — Stage A

**Repository:** `/Users/sajad/Documents/Tasks/gym-app`  
**Plan:** `docs/technical-hardening-plan.md` (binding contract)  
**Audit reference:** `main` at `465a6afe37bcfe3139ad107f395dca371a3e13fe`  
**Baseline commit audited:** `91e447b5e95f837e353462670e30bb310bfb71b5` (`docs: add evidence-gated technical hardening plan`)  
**Date:** 2026-10-24  
**Stage:** A only — audit pass, no application behavior changed, no production code edited.

This document records the independent verification required by the plan. The findings below are the auditor's verdicts against the **current** code at `91e447b`, not the older audit reference. All reproduction probes were temporary, were run against the disposable `gym_app_test` database, and were deleted before the audit commit.

---

## 1. Source-of-truth reconciliation (A1)

### 1.1 HEAD vs audit reference

`HEAD` moved from `465a6afe` to `91e447b` with five commits:

| Commit | Subject | Relevance to the plan |
| --- | --- | --- |
| `39c264a` | `docs: add release readiness plan` | Documents deliberate release scope and E2E expectations |
| `066ae01` | `fix: scope PWA caches to local builds and preserve good shells` | Not a plan finding; fixes PWA cache scoping |
| `0b46706` | `fix: bound athlete import reads and cover permission boundaries` | **HARD-01 already implemented**; adds import/permission tests |
| `1536861` | `fix: guard busy athlete mutations and recover partial deletions` | Adds athlete lifecycle/DATA-07 tests and UI busy-state safety; **does not** make file/DB deletion atomic |
| `b1039aa` | `test: disposable athlete fixture and mobile admin coverage` | E2E isolation and mobile admin coverage |
| `91e447b` | `docs: add evidence-gated technical hardening plan` | This contract |

The audit reference's historical test counts (`20 passed`, `31 passed`, `25 passed`) are **not** reproducible at HEAD and are treated as historical reports only.

### 1.2 Approved scope and deliberate behavior

`README.md` and `docs/implementation-progress.md` confirm:

- Local-first multi-gym MVP1; **local development/manual acceptance only**, no deployment, public hosting, real email provider, cloud storage, or public CI (`README.md:7,145-151`).
- PostgreSQL/SQLModel/FastAPI/React/Vite/Alembic/Pytest/Playwright stack remains approved.
- **ACTIVE workout program versions are deliberately editable** (`docs/implementation-progress.md:118-122`; `docs/local-testing.md:97-99`). This audit does **not** treat editable ACTIVE versions as a defect.
- Archived program versions are documented as read-only, but the deletion policy for ACTIVE/ARCHIVED versions is not explicitly specified. That ambiguity is handled in DATA-03 below.
- Athlete archive/restore/permanent-delete, body-file privacy, coach reassignment, and one-active-program invariants are deliberate product behavior.

### 1.3 Existing controls already present at HEAD

- Server-side gym scoping via `X-Gym-ID` and current membership (`backend/app/api/deps.py:106-144`).
- Current coach assignment checked per request (`backend/app/api/deps.py:183-192,248-264`).
- One active program per program and one current coach assignment enforced by partial unique indexes (`backend/app/models.py:272-280,723-728`).
- Private coach note omitted from athlete/self responses; body files permission-checked and magic-byte validated.
- Import reads bounded before parsing and oversize imports tested.
- Test database guard requires a `_test` suffix (`backend/tests/conftest.py:21-24`); reset script requires explicit confirmation and only targets `gym_app` (`backend/scripts/reset_dev_db.sh:6-20`).
- No public signup route; invitation tokens cannot be replayed after successful activation because activation requires `hashed_password` to be unset (`backend/app/api/routes/login.py:91-105`).

---

## 2. Baseline results (A2)

### 2.1 Toolchain and environment

| Item | Value |
| --- | --- |
| OS | macOS (`darwin`), arm64 |
| `uv` | 0.11.27 (Homebrew 2026-07-06) |
| Backend Python | 3.14.6 (uv-managed; project requires `>=3.14,<4.0`) |
| Bun | 1.3.14 |
| Node | v22.23.1 |
| Database | local PostgreSQL 17 |
| `TEST_DATABASE_URL` | `postgresql://sajad@localhost:5432/gym_app_test` (verified database name `gym_app_test`) |
| Dev servers | FastAPI at `http://localhost:8000` and Vite at `http://localhost:5173` were already running |
| CI | No `.github/workflows` directory exists |

**Database safety:** only `gym_app_test` was used for pytest. The conftest fixture runs `SQLModel.metadata.drop_all/create_all` and per-test `TRUNCATE ... CASCADE` on that disposable test database (`backend/tests/conftest.py:67-89`). No reset script was run. `alembic check` connects to the configured development `DATABASE_URL` for a read-only schema comparison; it did not migrate or modify data.

### 2.2 Backend

| Command | Result | Notes |
| --- | --- | --- |
| `cd backend && uv sync` | Pass | Resolved 83 packages, checked 79; no changes |
| `uv run pytest -q` | **42 passed**, 1 warning, 28.91s | Warning: Starlette `TestClient`/`httpx` deprecation |
| `uv run ruff check app tests` | **1 error**, exit 1 | Pre-existing `I001` import-order failure in `tests/api/routes/test_athlete_import.py:1-22` |
| `uv run mypy app` | **Success**, 32 source files, exit 0 | Authoritative type check used for this audit |
| `uv run ty check app` | **All checks passed**, exit 0 | `ty` is declared in `backend/pyproject.toml` and present in the lockfile; run opportunistically as a cross-check |
| `uv run alembic check` | **No new upgrade operations detected**, exit 0 | Compares metadata to current DB; does not exercise an old-schema upgrade |

**Type-check substitution:** the plan says `ty check`, while the task brief said the repository uses mypy and that `ty check` does not exist. At HEAD, `ty` **is** configured (`[tool.ty]` in `backend/pyproject.toml`) and installed. Both `mypy app` and `ty check app` were run; both pass. The authoritative baseline command recorded here is `mypy app`, per the task brief.

### 2.3 Frontend

| Command | Result | Notes |
| --- | --- | --- |
| `cd frontend && bun install --frozen-lockfile` | Pass | 220 installs / 279 packages, no changes |
| `bun run build` | Pass | TypeScript + Vite build + service worker; `[pwa] service worker cache build 719bbdbc05f85289` |
| `bunx biome check` | **4 errors, 11 warnings**, exit 1 | Non-mutating check. Errors: formatting in `playwright/.auth/admin.json`, `playwright/.auth/athlete.json`, `public/sw.js`, `test-results/.last-run.json`. Warnings: 10 `noDescendingSpecificity` in `src/index.css`, 1 unused parameter in `tests-unit/service-worker.test.mjs` |

The two `playwright/.auth/*.json` and `test-results/.last-run.json` files are local, Git-ignored artifacts from prior runs; `public/sw.js` is tracked source and is a genuine formatting failure. The `lint` script itself mutates code (`--write --unsafe`), which is HARD-03.

### 2.4 Playwright

| Command | Result | Notes |
| --- | --- | --- |
| `cd frontend && bunx playwright test --reporter=line` | **50 total: 49 passed, 1 skipped**, 1.0m | Skipped: production-worker-only test at `tests/pwa.spec.ts:46-49` |
| `PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test tests/pwa.spec.ts --reporter=line` | **3 passed** | Includes `admin-setup` plus both PWA tests; run against the production build served at `:8000` |

The skipped test is intentionally gated by `PWA_PROD=1`; it passed in the production run above. Playwright exercised the running dev server at `:5173` for the main suite and the built production app at `:8000` for the PWA subset. The disposable-athlete fixture (`frontend/tests/fixtures/athlete-data.ts`) cleans up its own records; `test-data.spec.ts` passed.

### 2.5 Historical-count comparison

| Reported historical count | Reproduced at `91e447b`? |
| --- | --- |
| Backend `20 passed` | No — now **42 passed** (suite expanded) |
| Playwright `31 passed` | No — now **50 total / 49 passed / 1 skipped** |
| Production PWA `25 passed` | No — the old suite no longer exists; the current PWA subset is **3 passed** (including setup) |

These are baseline facts, not claims that the current suite covers every risk. Coverage gaps are recorded under HARD-04.

---

## 3. Reproduction method

A temporary pytest file (`backend/tests/api/routes/test_zz_audit_repro.py`) containing nine probes was run with:

```sh
cd backend && uv run pytest -q tests/api/routes/test_zz_audit_repro.py
# 9 passed
```

The probes demonstrated: reset-token replay, stale access token after password change, archived-athlete PATCH success, file-unlink-before-commit inconsistency, orphaned upload on commit failure, silent program overwrite, unhandled version-number collision, owner-as-athlete delete `500`, and absence of login throttling. The file and its `__pycache__` entry were deleted before this document was committed; it is not part of the audit commit and no production code was changed.

---

## 4. Findings and verdicts

### 4.1 Summary table

| ID | Severity | Verdict | Evidence (current code) | Reproduction / test | Fix commit | Verification / remaining risk |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-01 | High | **CONFIRMED** | `backend/app/api/routes/login.py:74-88`; `backend/app/utils.py:102-137`; `backend/app/models.py:33-39` | Temporary probe: same reset token accepted twice, both HTTP 200; login with second password succeeded | `7d3aa70` | Fixed with `User.token_version` carried in reset/access JWTs and incremented atomically on reset/change. Tests: `test_token_invalidation.py::test_reset_token_cannot_be_redeemed_twice`, `::test_concurrent_reset_redemption_succeeds_at_most_once`, `::test_invalid_reset_tokens_are_rejected`. Full suite passes (71 tests). |
| SEC-02 | High | **CONFIRMED** | `backend/app/core/config.py:25-26`; `backend/app/core/security.py:22-26`; `backend/app/api/deps.py:42-66`; `backend/app/api/routes/users.py:83-101` | Temporary probe: old bearer token still returned 200 from `/users/me` after password change; new password worked | `7d3aa70` | Fixed by the same `token_version` claim: stale tokens fail after password change/reset. Tests: `test_token_invalidation.py::test_access_token_is_rejected_after_password_change`, `::test_access_token_is_rejected_after_password_reset`, `::test_each_password_change_invalidates_the_previous_generation`, `::test_legacy_tokens_without_version_claim_are_version_zero`. Role/membership revocation remains immediate. |
| SEC-03 | Medium | **DEFERRED** | `backend/app/api/routes/login.py:36-52,55-71`; `backend/app/main.py:26-40`; no limiter/middleware found | Temporary probe: 8 bad logins all returned 400, no 429/lockout | — (deferred) | No code change. Local-only MVP scope (`README.md`); a durable limiter is a production-release blocker before any network deployment. |
| SEC-04 | Low / informational | **REJECTED** (for MVP1) | `frontend/src/api.ts:8-11`; `frontend/src/auth.tsx:53-62,160-168`; `frontend/index.html:1-23`; `backend/app/main.py:26-40`; `frontend/public/sw.js:30-45` | Static review: no `dangerouslySetInnerHTML`, `innerHTML`, `eval`, or raw HTML sink found; React escapes rendered data; service worker excludes `/api/` and `/docs` | — (rejected) | No code change. Bearer token in `localStorage` is a documented tradeoff, not evidence of XSS. CSP/storage review remains a production-readiness item only. |
| DATA-01 | High | **CONFIRMED** | `backend/app/api/routes/athletes.py:604-613` (unlink) vs `:645-654` (commit); `backend/app/services/storage.py:56-60` | Temporary probe: injected `Session.commit` failure on athlete DELETE returned 500; stored file disappeared; DB body-file row remained and download returned 404 | `e0772b5` | Files are now unlinked only after the DB commit is durable. Test: `test_privacy_files.py::test_delete_commit_failure_preserves_body_file_row_and_file` proves a failed commit preserves row and file; idempotent cleanup remains. |
| DATA-02 | Medium | **CONFIRMED** | `backend/app/api/routes/athletes.py:681-704` (save then commit); `backend/app/services/storage.py:18-53` | Temporary probe: injected commit failure on upload returned 500; an extra file appeared under `BODY_ANALYSIS_DIR`; DB listing was empty | `e0772b5` | Upload now rolls back and deletes the written file when the row cannot commit. Test: `test_privacy_files.py::test_failed_upload_commit_does_not_leave_orphan_file`. |
| DATA-03 | Medium | **BLOCKED: PRODUCT DECISION** | `backend/app/api/routes/programs.py:222-242` (no status guard); UI delete affordance `frontend/src/pages/AthleteDetailPage.tsx:969-980`; explicit test `backend/tests/api/routes/test_programs.py:462-519` | Existing test proves ACTIVE, DRAFT, and ARCHIVED deletion all return 200 for staff; athlete is forbidden | — (blocked) | No change pending the product decision: keep any-status deletion, or restrict destructive deletion to DRAFT and require archive/copy for published history. |
| DATA-04 | Medium | **CONFIRMED** | `backend/app/api/deps.py:178-180,235-246`; `backend/app/api/routes/athletes.py:399-443`; `allow_archived=True` at `:408-410` | Temporary probe: owner archived an athlete, then `PATCH /athletes/{id}` returned 200 and changed `phone` while `is_archived` stayed true | `e0772b5` | Archived profile/program mutations now return 409 `athlete_archived`. Test: `test_athlete_lifecycle.py::test_archived_athlete_profile_and_program_authoring_are_read_only` (admin, coach, cross-gym, restore re-enables editing). |
| DATA-05 | Medium | **CONFIRMED** | `backend/app/models.py:713-748` (no revision field); `backend/app/api/routes/programs.py:179-219`; `frontend/src/pages/ProgramEditorPage.tsx:167-179` | Temporary probe: two snapshots of the same version; editor A saved 200, then editor B saved a stale snapshot 200 and overwrote A; no `revision`, ETag, or 409 | `384faf5` | Added `revision` + `expected_revision` optimistic concurrency with HTTP 409 and a frontend conflict path; ACTIVE editing preserved. Tests: `test_program_concurrency.py::test_stale_program_version_update_is_rejected_and_retry_works`, `::test_active_program_version_stays_editable_and_publishable_with_revision`. Migration `d5e6f7a8b9c0`. |
| DATA-06 | Medium | **CONFIRMED** | `backend/app/services/programs.py:382-388`; `backend/app/models.py:713-729`; `backend/app/api/routes/programs.py:126-154,263-283` | Temporary probe: injected a colliding `next_version_number` result; `POST /program-versions/{id}/new-draft` returned 500 | `384faf5` | Version allocation now retries unique collisions and maps exhaustion to 409; unique constraint retained. Tests: `test_program_concurrency.py::test_new_draft_retries_version_number_collision`, `::test_exhausted_version_number_collision_returns_409`, `::test_concurrent_new_drafts_get_unique_version_numbers`. |
| DATA-07 | Medium | **CONFIRMED** (narrow residual) | `backend/app/api/routes/athletes.py:632-653`; `backend/app/api/routes/gyms.py:148-158,372-381`; `backend/app/models.py:110` | Existing cross-gym test passes (`test_athlete_lifecycle.py:183-283`). Temporary probe: owner-as-athlete DELETE returned 500; owner could still log in | `1ad1714` | Owner/role overlap now preserves the owner membership and account and removes only the ATHLETE role; deterministic 200 instead of FK 500. Tests: `test_athlete_lifecycle.py::test_deleting_owner_as_athlete_keeps_account_and_gym_ownership`, `::test_deleting_athlete_of_other_gym_owner_keeps_account_and_other_gym`. |
| HARD-01 | Medium | **ALREADY FIXED** | `backend/app/api/routes/athletes.py:307-311`; `backend/app/services/athlete_import.py:37-39,210-214`; tests `tests/api/routes/test_athlete_import.py:238-271` | Existing passing tests assert `read(MAX_IMPORT_BYTES + 1)`, oversized reject, and both endpoints reject oversize | `0b46706` (pre-audit) | Bounded read and 400 `import_file_too_large` retained. Tests: `test_import_upload_read_is_bounded`, `test_preview_and_import_reject_oversized_uploads`; empty-file cases added under HARD-04. |
| HARD-02 | Medium | **CONFIRMED** | `backend/tests/conftest.py:67-89` (`drop_all`/`create_all`); no test references `alembic`; `alembic check` only compares current metadata to the current DB | Baseline: `uv run alembic check` passed; code search found no migration smoke test | `45998ac` | Added `backend/tests/test_migrations.py` (marked `migrations`). It recreates the disposable `gym_app_migration_test` database derived from `TEST_DATABASE_URL`, runs `alembic upgrade head`, runs `alembic check`, verifies the applied revision equals head, and spot-checks `user.token_version` / `workout_program_version.revision` as NOT NULL DEFAULT 0. Guard rejects non-`_test` and the dev DB; database is dropped after the test. |
| HARD-03 | Medium | **CONFIRMED** | `frontend/package.json:9` (`biome check --write --unsafe`); `.pre-commit-config.yaml:27-32` invokes the same mutating `npm run lint`; no `.github/workflows` | `bunx biome check` failed with 4 errors / 11 warnings (see 2.3); `ruff check` failed with 1 error | `4cf4b44` | Added non-mutating `lint:check`; `lint:fix` (and legacy `lint`) remain mutating; pre-commit now runs `lint:check`. Excluded Git-ignored generated artifacts (`openapi.json`, Playwright auth/report/test-results) from Biome, formatted the tracked `public/sw.js` template, disabled the false-positive `noDescendingSpecificity` rule, and removed the unused test parameter. The pre-audit ruff import order was already green at Stage D start. `bun run lint:check` is green. |
| HARD-04 | Medium | **CONFIRMED** (partial work already done) | Existing suites: `test_gym_isolation.py:16`, `test_programs.py:71`, `test_athlete_lifecycle.py:65-311`, `test_privacy_files.py:17,123`, `test_athlete_import.py:238-350` | Baseline 42 backend tests / 50 Playwright tests; temporary probes exposed the missing cases | `7d3aa70`, `e0772b5`, `1ad1714`, `384faf5`, `89de887` | Earlier stages closed reset replay, stale JWT, archived edit, rollback/orphan, concurrency, and owner overlap. Stage D added the remaining gaps: `test_preview_and_import_reject_empty_files` (empty and header-only CSV), `test_body_analysis_files_are_scoped_to_the_requesting_gym` (cross-gym coach/owner list/download/upload all 404), and `test_restore_preserves_cross_gym_staff_membership_and_roles` (restore in one gym leaves another gym's COACH membership/access intact; wrong-gym restore 404). 71 backend tests pass. |
| HARD-05 | Low | **DEFERRED** | No backup/restore procedure in `README.md` or `docs/`; reset script is destructive and explicitly guarded (`backend/scripts/reset_dev_db.sh:6-20`); release plan says no automated backup/reset execution (`docs/superpowers/plans/2026-10-24-release-readiness.md:265`) | Documentation review only; no destructive operation performed | — (deferred) | No change. Recorded as a production-readiness/operational blocker before real user data is relied on; a minimal `pg_dump`/upload-directory procedure would be a documentation task, not a code fix. |

### 4.2 Detailed notes on the non-obvious verdicts

#### DATA-03 — why this is a product decision, not a unilateral fix

The API has no status guard, the UI renders a delete button for every version the user can edit, and `test_staff_can_delete_program_versions_in_any_status` explicitly asserts 200 for ARCHIVED, DRAFT, and ACTIVE. That is strong evidence the behavior is intentional. However, `docs/implementation-progress.md:18,45,101,120` says archived history is retained and archived versions are read-only, and the hardening plan says not to invent retention rules. The two positions conflict only on **permanent deletion**; editing is already correctly blocked (`programs.py:198-199`). The smallest product choice is therefore: preserve current any-status deletion, or restrict DELETE to DRAFT and require archive/copy for published versions. No code change should be made until that is answered.

#### DATA-07 — what is fixed and what remains

The cross-gym case is genuinely fixed: deleting athlete A in gym A preserves the global user, gym B profile, gym B program, and gym B file; the existing test asserts all of it. The remaining defect is a role-overlap edge: an owner has no explicit `GYM_ADMIN` membership role (owner is implicit), so an owner who is also an athlete in the same gym has a membership whose only role is `ATHLETE`. `delete_athlete` deletes that membership because `roles <= {"ATHLETE"}`, then treats the user as unowned and calls `session.delete(user)`. `gym.owner_id` is `ondelete="RESTRICT"`, so the commit raises and the request returns 500. The correct behavior is either to reject deleting an owner-as-athlete with a clear 400/409, or to preserve the owner's membership/account and remove only the athlete profile/ATHLETE role. Also ensure the file cleanup path is not entered before this validation (DATA-01).

#### HARD-01 — 400 vs 413

The plan suggested 413 for oversize imports. The implementation uses 400 (`import_file_too_large`) in both the route guard and the service guard, and the frontend maps the `detail` key to a localized message. Existing tests assert 400. There is no broken client behavior. If API semantics are later standardized, switching to 413 would require coordinated test/frontend changes; it is not a security gap and was not changed in Stage A.

---

## 5. Baseline failures that must not be mistaken for audit regressions

These were present before the audit and are recorded so later stages do not claim a fully green baseline:

1. `uv run ruff check app tests` fails with one `I001` in `backend/tests/api/routes/test_athlete_import.py` (import block ordering).
2. `bunx biome check` fails on formatting of tracked `frontend/public/sw.js` and local Git-ignored artifacts (`playwright/.auth/*.json`, `test-results/.last-run.json`), and reports 11 warnings. The `lint` script would rewrite these because it uses `--write --unsafe`.
3. No CI workflow exists, so the above are not enforced anywhere.

These were in scope for HARD-03/HARD-04, not for Stage A. **Resolved/verified in Stage D:** ruff was already green at Stage D start; Biome is green through the non-mutating `lint:check`; generated/local artifacts are excluded; hosted CI remains a documented scope choice (README says no public CI).

---

## 6. Proposed execution order for later stages (CONFIRMED items only)

### Stage B — authentication/security

1. **SEC-01 + SEC-02 together**: add a server-side token version (smallest robust option: a `User.token_version` integer carried as a JWT claim, incremented atomically on password reset/change; reset tokens also carry the version). This survives restarts, invalidates the same reset token after first use (including concurrent redemption if the increment is conditional), and invalidates stale access tokens after a password change. Keep purpose/expiry/secret checks. Do not build refresh-token/session infrastructure.
2. Regression tests: first reset succeeds, second fails; expired/wrong-purpose/malformed tokens fail; old access token fails after change/reset; issued-after-change token works; role/membership revocation behavior is unchanged.

### Stage C — data integrity and authorization

1. **DATA-01 + DATA-02**: one storage transaction strategy for upload and delete. Prefer a post-commit cleanup for successful deletes and a compensating cleanup for failed uploads/commits; do not add a queue. Add injected-commit-failure tests proving no orphan and no metadata-without-file state.
2. **DATA-04**: reject `PATCH /athletes/{id}` for archived profiles unless a specific approved mutation exists; apply the same rule to program authoring paths that currently use `allow_archived=True`. Keep restore/delete/read behavior. Test admin, coach, and cross-gym access.
3. **DATA-07**: fix delete semantics for owner/role overlap; never delete an owner membership or the `User` row while an ownership relationship remains. Return a deterministic 4xx rather than an FK 500. Add owner-as-athlete and coach-as-athlete regressions.
4. **DATA-05**: add a lightweight revision to program versions and require the expected revision (or `If-Match`) on update; return 409 with a clear conflict path. Preserve editable ACTIVE behavior and the frontend refresh/retry flow. Migration only if essential.
5. **DATA-06**: make version allocation transaction-safe (retry on unique violation or map collision to 409). Keep `uq_program_version_number`; add a concurrency/collision regression.

**Before Stage C:** obtain the DATA-03 product decision. Do not add or remove deletion capabilities until then.

### Stage D — verification, quality gates, recovery

1. **HARD-02**: add a separate migration smoke test on a disposable DB: baseline revision -> upgrade head, schema checks, and a representative data-preservation path. Never run it against the development DB.
2. **HARD-03**: add a non-mutating `lint:check` (`biome check` without `--write/--unsafe`), keep `lint:fix`, exclude local artifacts from Biome, fix the existing `sw.js` formatting and the `ruff` `I001`, and add the smallest local/CI gate the project actually intends to run. Hosted CI remains a scope choice because README documents no public CI.
3. **HARD-04**: add the missing regressions not already landed with Stage B/C; map each test to a finding. Do not duplicate existing cross-gym/file/import coverage.
4. **HARD-05**: deferred. If real user data will be used, add a documented, disposable-DB-tested `pg_dump`/restore and upload-directory recovery procedure; do not build a backup platform.

**No code action:** HARD-01 (already fixed), DATA-03 (blocked on product decision), SEC-03 (deferred to production readiness), SEC-04 (rejected for MVP1, production note only).

---

## 7. Stage A exit and release posture

- **Stage A verdict:** every plan hypothesis has an independent verdict with code/test evidence. No application behavior was changed.
- **Stage A interim GO/NO-GO (historical):** **NO-GO for public/networked use or real user data.** **CONDITIONAL GO for local manual acceptance with disposable/demo data**, with known high-risk behavior: reset-token replay (SEC-01), stale tokens after password change (SEC-02), and non-atomic file/DB delete/upload paths (DATA-01/02).
- **Final Stage D posture:** **GO for local manual acceptance with disposable/demo data.** **NO-GO for public/networked use or real user data** until the deferred production-readiness items are addressed: login/recovery abuse controls (SEC-03), a documented and tested backup/restore procedure (HARD-05), and a public-hosting CSP/session-storage review (SEC-04 note). DATA-03 remains blocked on the deletion-policy product decision. See section 9 for the final verification evidence.

---

## 8. Stage A commit (historical)

Only this document was committed at `7356a12`. The temporary reproduction test was deleted; no fix commits existed at Stage A.

---

## 9. Stage B–D commits and final verification

### 9.1 Fix commits

| Stage | Finding(s) | Commit | Subject |
| --- | --- | --- | --- |
| B | SEC-01, SEC-02 | `7d3aa70` | `fix: invalidate tokens on password reset and change` |
| C | DATA-01, DATA-02, DATA-04 | `e0772b5` | `fix: make file lifecycle consistent and guard archived athletes` |
| C | DATA-07 | `1ad1714` | `fix: preserve gym owners when deleting athlete records` |
| C | DATA-05, DATA-06 | `384faf5` | `fix: reject stale program edits and resolve version number races` |
| D | HARD-02 | `45998ac` | `test: add alembic migration smoke test` |
| D | HARD-03 | `4cf4b44` | `chore: non-mutating frontend lint check and clean baseline` |
| D | HARD-04 | `89de887` | `test: cover remaining hardening regressions` |
| D | HARD-01 | `0b46706` (pre-audit) | `fix: bound athlete import reads and cover permission boundaries` |

### 9.2 HARD-04 coverage map

| Risk | Existing or added coverage |
| --- | --- |
| Reset-token replay / concurrent redemption | `test_token_invalidation.py::test_reset_token_cannot_be_redeemed_twice`, `::test_concurrent_reset_redemption_succeeds_at_most_once` |
| Stale JWT after password change/reset | `test_token_invalidation.py::test_access_token_is_rejected_after_password_change`, `::test_access_token_is_rejected_after_password_reset`, `::test_each_password_change_invalidates_the_previous_generation`, `::test_legacy_tokens_without_version_claim_are_version_zero` |
| Archived profile/program edit | `test_athlete_lifecycle.py::test_archived_athlete_profile_and_program_authoring_are_read_only` |
| File/DB transaction failure | `test_privacy_files.py::test_delete_commit_failure_preserves_body_file_row_and_file`, `::test_failed_upload_commit_does_not_leave_orphan_file` |
| Concurrent program edit / version race | `test_program_concurrency.py` (5 tests) |
| Owner/role-overlap delete | `test_athlete_lifecycle.py::test_deleting_owner_as_athlete_keeps_account_and_gym_ownership`, `::test_deleting_athlete_of_other_gym_owner_keeps_account_and_other_gym` |
| Cross-gym data access / revoked coach | `test_gym_isolation.py`, `test_athlete_lifecycle.py::test_archive_restore_cuts_off_and_restores_coach_access_without_duplicate_assignment` |
| Body-file ownership (same gym, other athlete) | `test_privacy_files.py::test_body_analysis_file_is_private_and_validated` |
| Body-file ownership across gyms **(added)** | `test_privacy_files.py::test_body_analysis_files_are_scoped_to_the_requesting_gym` |
| Oversized import | `test_athlete_import.py::test_import_upload_read_is_bounded`, `::test_preview_and_import_reject_oversized_uploads` |
| Empty/header-only import **(added)** | `test_athlete_import.py::test_preview_and_import_reject_empty_files` (2 paths × 2 contents) |
| Restore with cross-gym roles **(added)** | `test_athlete_lifecycle.py::test_restore_preserves_cross_gym_staff_membership_and_roles` |
| Migration from an older schema **(added)** | `test_migrations.py::test_fresh_database_upgrades_to_head_and_matches_models` |

### 9.3 Final verification (2026-10-25)

Run from `backend/` unless noted. The migration test used only `gym_app_migration_test`, derived from `TEST_DATABASE_URL`; it was dropped after the run. `DATABASE_URL` (development `gym_app`) was never migrated or modified.

| Command | Result |
| --- | --- |
| `uv run ruff check app tests` | **All checks passed!** exit 0 |
| `uv run mypy app` | **Success: no issues found in 32 source files** exit 0 |
| `uv run pytest -q` | **71 passed**, 4 warnings, 41.99s |
| `uv run pytest -q -m migrations` | **1 passed**, 70 deselected, 0.57s |
| `cd frontend && bun run lint:check` | **Checked 100 files. No fixes applied.** exit 0 |
| `cd frontend && bunx tsc -p tsconfig.build.json --noEmit` | exit 0 (no diagnostics) |
| `cd frontend && bun run build` | Pass; Vite build + service worker cache build `ffc97436874269a7` |
| `cd frontend && node --test tests-unit/build-service-worker.test.mjs tests-unit/service-worker.test.mjs` | Pass |

Warnings are the pre-existing Starlette `TestClient`/`httpx` deprecation and an Alembic `path_separator` configuration deprecation; neither fails a gate.

### 9.4 Remaining risks / non-goals

- **DATA-03:** deletion policy for ACTIVE/ARCHIVED program versions is still a product decision; behavior unchanged.
- **SEC-03:** no login/recovery throttling; production blocker before network exposure.
- **HARD-05:** no automated/tested backup-restore procedure; production blocker before real user data.
- **SEC-04:** `localStorage` bearer-token tradeoff accepted for local MVP1; CSP/storage review required before public hosting.
- **Hosted CI:** not added; the non-mutating local/pre-commit gates are the project's documented scope.

