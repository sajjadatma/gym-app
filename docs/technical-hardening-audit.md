# Technical Hardening Audit — Stage A

**Repository:** `/Users/sajad/Documents/Tasks/gym-app`  
**Plan:** `docs/technical-hardening-plan.md` (binding contract)  
**Audit reference:** `main` at `465a6afe37bcfe3139ad107f395dca371a3e13fe`  
**Baseline commit audited:** `91e447b5e95f837e353462670e30bb310bfb71b5` (`docs: add evidence-gated technical hardening plan`)  
**Date:** 2026-10-24; decisions and CI status updated 2026-10-25 (Stage D2)  
**Stage:** A audit pass plus Stages B–D fixes and Stage D2 decisions; application behavior changed only in the fix commits listed in §9.1.

This document records the independent verification required by the plan. The findings below were the auditor's verdicts against the code at `91e447b`, not the older audit reference; §§9–10 record the fix commits, the later Stage D2 decisions, and CI status. All reproduction probes were temporary, were run against the disposable `gym_app_test` database, and were deleted before the audit commit.

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

- Local-first multi-gym MVP1; **local development/manual acceptance only**, no deployment, public hosting, real email provider, or cloud storage (`README.md:7,145-151`). A minimal GitHub Actions CI workflow was added in Stage D2 (§10); no deploy steps are included.
- PostgreSQL/SQLModel/FastAPI/React/Vite/Alembic/Pytest/Playwright stack remains approved.
- **ACTIVE workout program versions are deliberately editable** (`docs/implementation-progress.md:118-122`; `docs/local-testing.md:97-99`). This audit does **not** treat editable ACTIVE versions as a defect.
- Archived program versions are documented as read-only. The deletion policy for ACTIVE/ARCHIVED versions was ambiguous; it was resolved on 2026-10-25 as deliberate any-status deletion (DATA-03 below).
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
| CI | No `.github/workflows` directory existed at the audit baseline (historical; a minimal workflow was added in Stage D2 — see §10) |

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
| SEC-02 | High | **CONFIRMED** | `backend/app/core/config.py:25-26`; `backend/app/core/security.py:22-26`; `backend/app/api/deps.py:42-66`; `backend/app/api/routes/users.py:83-101` | Temporary probe: old bearer token still returned 200 from `/users/me` after password change; new password worked | `7d3aa70` | Fixed by the same `token_version` claim: stale tokens fail after password change/reset. Tests: `test_token_invalidation.py::test_access_token_is_rejected_after_password_change`, `::test_access_token_is_rejected_after_password_reset`, `::test_each_password_change_invalidates_the_previous_generation`, `::test_legacy_tokens_without_version_claim_are_version_zero`. Role/membership revocation remains immediate. **Logout is still client-side only**: it discards the local token but does not invalidate the JWT server-side, so the token remains valid until expiry. Bumping `token_version` on logout would invalidate every session for the user; no product decision authorized that, so it remains an accepted MVP1 risk (§11.3). |
| SEC-03 | Medium | **DEFERRED** | `backend/app/api/routes/login.py:36-52,55-71`; `backend/app/main.py:26-40`; no limiter/middleware found | Temporary probe: 8 bad logins all returned 400, no 429/lockout | — (deferred) | No code change. Local-only MVP scope (`README.md`); a durable limiter is a production-release blocker before any network deployment. |
| SEC-04 | Low / informational | **REJECTED** (for MVP1) | `frontend/src/api.ts:8-11`; `frontend/src/auth.tsx:53-62,160-168`; `frontend/index.html:1-23`; `backend/app/main.py:26-40`; `frontend/public/sw.js:30-45` | Static review: no `dangerouslySetInnerHTML`, `innerHTML`, `eval`, or raw HTML sink found; React escapes rendered data; service worker excludes `/api/` and `/docs` | — (rejected) | No code change. Bearer token in `localStorage` is a documented tradeoff, not evidence of XSS. CSP/storage review remains a production-readiness item only. |
| DATA-01 | High | **CONFIRMED** | `backend/app/api/routes/athletes.py:604-613` (unlink) vs `:645-654` (commit); `backend/app/services/storage.py:56-60` | Temporary probe: injected `Session.commit` failure on athlete DELETE returned 500; stored file disappeared; DB body-file row remained and download returned 404 | `e0772b5` | Files are now unlinked only after the DB commit is durable. Test: `test_privacy_files.py::test_delete_commit_failure_preserves_body_file_row_and_file` proves a failed commit preserves row and file; idempotent cleanup remains. |
| DATA-02 | Medium | **CONFIRMED** | `backend/app/api/routes/athletes.py:681-704` (save then commit); `backend/app/services/storage.py:18-53` | Temporary probe: injected commit failure on upload returned 500; an extra file appeared under `BODY_ANALYSIS_DIR`; DB listing was empty | `e0772b5` | Upload now rolls back and deletes the written file when the row cannot commit. Test: `test_privacy_files.py::test_failed_upload_commit_does_not_leave_orphan_file`. |
| DATA-03 | Medium | **RESOLVED — approved as intentional product behavior** (decision 2026-10-25) | `backend/app/api/routes/programs.py:222-242` (no status guard); UI delete affordance `frontend/src/pages/AthleteDetailPage.tsx:969-980`; explicit test `backend/tests/api/routes/test_programs.py:462-519` | Existing test proves ACTIVE, DRAFT, and ARCHIVED deletion all return 200 for staff; athlete is forbidden | — (decision 2026-10-25; no code change) | Any-status version deletion is kept as deliberate product behavior. Remaining risk: gym admins can permanently delete archived history; accepted tradeoff. |
| DATA-04 | Medium | **CONFIRMED** | `backend/app/api/deps.py:178-180,235-246`; `backend/app/api/routes/athletes.py:399-443`; `allow_archived=True` at `:408-410` | Temporary probe: owner archived an athlete, then `PATCH /athletes/{id}` returned 200 and changed `phone` while `is_archived` stayed true | `e0772b5` | Archived profile/program mutations now return 409 `athlete_archived`. Test: `test_athlete_lifecycle.py::test_archived_athlete_profile_and_program_authoring_are_read_only` (admin, coach, cross-gym, restore re-enables editing). |
| DATA-05 | Medium | **CONFIRMED** | `backend/app/models.py:713-748` (no revision field); `backend/app/api/routes/programs.py:179-219`; `frontend/src/pages/ProgramEditorPage.tsx:167-179` | Temporary probe: two snapshots of the same version; editor A saved 200, then editor B saved a stale snapshot 200 and overwrote A; no `revision`, ETag, or 409 | `384faf5` | Added `revision` + `expected_revision` optimistic concurrency with HTTP 409 and a frontend conflict path; ACTIVE editing preserved. Tests: `test_program_concurrency.py::test_stale_program_version_update_is_rejected_and_retry_works`, `::test_active_program_version_stays_editable_and_publishable_with_revision`. Migration `d5e6f7a8b9c0`. **Deliberate back-compat (review round):** `expected_revision` stays optional; a client that omits it bypasses the stale-write guard and simply bumps `revision`. Pinned by `test_update_without_expected_revision_still_succeeds_and_bumps_revision`; the current UI always sends the field. Accepted risk: unmaintained older clients can overwrite newer edits (§11.3). |
| DATA-06 | Medium | **CONFIRMED** | `backend/app/services/programs.py:382-388`; `backend/app/models.py:713-729`; `backend/app/api/routes/programs.py:126-154,263-283` | Temporary probe: injected a colliding `next_version_number` result; `POST /program-versions/{id}/new-draft` returned 500 | `384faf5` | Version allocation now retries unique collisions and maps exhaustion to 409; unique constraint retained. Tests: `test_program_concurrency.py::test_new_draft_retries_version_number_collision`, `::test_exhausted_version_number_collision_returns_409`, `::test_concurrent_new_drafts_get_unique_version_numbers`. |
| DATA-07 | Medium | **CONFIRMED** (delete fixed; archive overlap fixed in final review) | `backend/app/api/routes/athletes.py:488-514,632-653`; `backend/app/api/deps.py:229-240`; `backend/app/api/routes/gyms.py:148-158,372-381`; `backend/app/models.py:110` | Existing cross-gym test passes (`test_athlete_lifecycle.py:183-283`). Temporary probe: owner-as-athlete DELETE returned 500; owner could still log in. Final review: owner-as-athlete ARCHIVE deactivated the only membership (owner has no explicit `GYM_ADMIN` role), after which every gym-scoped call returned 403 `not_a_gym_member`, including restore — an unrecoverable lockout without superuser intervention. | `1ad1714`, `e55ace6` | Delete: owner/role overlap preserves the owner membership and account and removes only the ATHLETE role; deterministic 200 instead of FK 500. Archive: owner membership is no longer deactivated, and an owner/admin can access and restore their own archived profile. Tests: `test_athlete_lifecycle.py::test_deleting_owner_as_athlete_keeps_account_and_gym_ownership`, `::test_deleting_athlete_of_other_gym_owner_keeps_account_and_other_gym`, `::test_archiving_owner_as_athlete_keeps_gym_access_and_allows_self_restore`, `::test_owner_archive_lockout_when_membership_deactivation_is_not_preserved`. |
| HARD-01 | Medium | **ALREADY FIXED** | `backend/app/api/routes/athletes.py:307-311`; `backend/app/services/athlete_import.py:37-39,210-214`; tests `tests/api/routes/test_athlete_import.py:238-271` | Existing passing tests assert `read(MAX_IMPORT_BYTES + 1)`, oversized reject, and both endpoints reject oversize | `0b46706` (pre-audit) | Bounded read and 400 `import_file_too_large` retained. Tests: `test_import_upload_read_is_bounded`, `test_preview_and_import_reject_oversized_uploads`; empty-file cases added under HARD-04. |
| HARD-02 | Medium | **CONFIRMED** | `backend/tests/conftest.py:67-89` (`drop_all`/`create_all`); no test references `alembic`; `alembic check` only compares current metadata to the current DB | Baseline: `uv run alembic check` passed; code search found no migration smoke test | `45998ac` | Added `backend/tests/test_migrations.py` (marked `migrations`). It recreates the disposable `gym_app_migration_test` database derived from `TEST_DATABASE_URL`, runs `alembic upgrade head`, runs `alembic check`, verifies the applied revision equals head, and spot-checks `user.token_version` / `workout_program_version.revision` as NOT NULL DEFAULT 0. Guard rejects non-`_test` and the dev DB; database is dropped after the test. |
| HARD-03 | Medium | **CONFIRMED** | `frontend/package.json:9` (`biome check --write --unsafe`); `.pre-commit-config.yaml:27-32` invokes the same mutating `npm run lint`; no `.github/workflows` at audit time | `bunx biome check` failed with 4 errors / 11 warnings (see 2.3); `ruff check` failed with 1 error | `4cf4b44`, `efc49cf` | Added non-mutating `lint:check`; `lint:fix` (and legacy `lint`) remain mutating; pre-commit now runs `lint:check`. Excluded Git-ignored generated artifacts (`openapi.json`, Playwright auth/report/test-results) from Biome, formatted the tracked `public/sw.js` template, disabled the false-positive `noDescendingSpecificity` rule, and removed the unused test parameter. The pre-audit ruff import order was already green at Stage D start. `bun run lint:check` is green. Stage D2 added the minimal GitHub Actions workflow (`.github/workflows/ci.yml`); it has not run yet (§10). |
| HARD-04 | Medium | **CONFIRMED** (partial work already done) | Existing suites: `test_gym_isolation.py:16`, `test_programs.py:71`, `test_athlete_lifecycle.py:65-311`, `test_privacy_files.py:17,123`, `test_athlete_import.py:238-350` | Baseline 42 backend tests / 50 Playwright tests; temporary probes exposed the missing cases | `7d3aa70`, `e0772b5`, `1ad1714`, `384faf5`, `89de887` | Earlier stages closed reset replay, stale JWT, archived edit, rollback/orphan, concurrency, and owner overlap. Stage D added the remaining gaps: `test_preview_and_import_reject_empty_files` (empty and header-only CSV), `test_body_analysis_files_are_scoped_to_the_requesting_gym` (cross-gym coach/owner list/download/upload all 404), and `test_restore_preserves_cross_gym_staff_membership_and_roles` (restore in one gym leaves another gym's COACH membership/access intact; wrong-gym restore 404). 71 backend tests pass. |
| HARD-05 | Low | **DEFERRED** | No backup/restore procedure in `README.md` or `docs/`; reset script is destructive and explicitly guarded (`backend/scripts/reset_dev_db.sh:6-20`); release plan says no automated backup/reset execution (`docs/superpowers/plans/2026-10-24-release-readiness.md:265`) | Documentation review only; no destructive operation performed | — (deferred) | No change. Recorded as a production-readiness/operational blocker before real user data is relied on; a minimal `pg_dump`/upload-directory procedure would be a documentation task, not a code fix. |

### 4.2 Detailed notes on the non-obvious verdicts

#### DATA-03 — decision and accepted tradeoff

The API has no status guard, the UI renders a delete button for every version the user can edit, and `test_staff_can_delete_program_versions_in_any_status` explicitly asserts 200 for ARCHIVED, DRAFT, and ACTIVE. That is strong evidence the behavior is intentional. `docs/implementation-progress.md:18,45,101,120` says archived history is retained and archived versions are read-only, but that concerns **editing**, which is already correctly blocked (`programs.py:198-199`).

**Decision 2026-10-25:** any-status version deletion is kept as deliberate product behavior; no code change. The remaining risk is that gym admins can permanently delete archived program history. This is an accepted tradeoff for MVP1, not a defect. The existing test remains the regression that documents the behavior.

#### DATA-07 — what is fixed and what remains

The cross-gym case is genuinely fixed: deleting athlete A in gym A preserves the global user, gym B profile, gym B program, and gym B file; the existing test asserts all of it. The role-overlap delete defect is also fixed: an owner has no explicit `GYM_ADMIN` membership role (owner is implicit), so an owner who is also an athlete in the same gym has a membership whose only role is `ATHLETE`. `delete_athlete` now detects `gym.owner_id == user.id`, removes only the ATHLETE role, keeps the membership active, and never deletes the owning account. `gym.owner_id` is `ondelete="RESTRICT"`, so the previous path raised an FK error and returned 500. File cleanup remains post-commit (DATA-01).

The final review found the same overlap in the **archive** path. `archive_athlete` deactivated a membership whenever `roles <= {"ATHLETE"}`; for an owner-as-athlete that is their only membership, so it became inactive. `get_gym_context` rejects inactive memberships with 403 `not_a_gym_member`, and restore itself needs a gym context, so the owner could not recover without a superuser. `archive_athlete` now skips membership deactivation when `ctx.gym.owner_id == access.user.id` (mirroring delete). `get_athlete_access` also permits an owner/admin to read their own archived profile when `allow_archived=True`, which is required for self-restore while ordinary athlete self-service remains hidden. No remaining DATA-07 code defect is known; the behavior is pinned by the four tests above.

#### HARD-01 — 400 vs 413

The plan suggested 413 for oversize imports. The implementation uses 400 (`import_file_too_large`) in both the route guard and the service guard, and the frontend maps the `detail` key to a localized message. Existing tests assert 400. There is no broken client behavior. If API semantics are later standardized, switching to 413 would require coordinated test/frontend changes; it is not a security gap and was not changed in Stage A.

---

## 5. Baseline failures that must not be mistaken for audit regressions

These were present before the audit and are recorded so later stages do not claim a fully green baseline:

1. `uv run ruff check app tests` fails with one `I001` in `backend/tests/api/routes/test_athlete_import.py` (import block ordering).
2. `bunx biome check` fails on formatting of tracked `frontend/public/sw.js` and local Git-ignored artifacts (`playwright/.auth/*.json`, `test-results/.last-run.json`), and reports 11 warnings. The `lint` script would rewrite these because it uses `--write --unsafe`.
3. No CI workflow existed at the audit baseline, so the above were not enforced anywhere.

These were in scope for HARD-03/HARD-04, not for Stage A. **Resolved/verified in Stage D and D2:** ruff was already green at Stage D start; Biome is green through the non-mutating `lint:check`; generated/local artifacts are excluded; a minimal GitHub Actions workflow was added in Stage D2 (§10), though it has not run yet.

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

**DATA-03 (resolved 2026-10-25):** any-status version deletion is retained as deliberate product behavior; no code change was made.

### Stage D — verification, quality gates, recovery

1. **HARD-02**: add a separate migration smoke test on a disposable DB: baseline revision -> upgrade head, schema checks, and a representative data-preservation path. Never run it against the development DB.
2. **HARD-03**: add a non-mutating `lint:check` (`biome check` without `--write/--unsafe`), keep `lint:fix`, exclude local artifacts from Biome, fix the existing `sw.js` formatting and the `ruff` `I001`, and add the smallest local/CI gate the project actually intends to run. A minimal GitHub Actions workflow was added in Stage D2 (§10).
3. **HARD-04**: add the missing regressions not already landed with Stage B/C; map each test to a finding. Do not duplicate existing cross-gym/file/import coverage.
4. **HARD-05**: deferred. If real user data will be used, add a documented, disposable-DB-tested `pg_dump`/restore and upload-directory recovery procedure; do not build a backup platform.

**No code action:** HARD-01 (already fixed), DATA-03 (resolved by decision: any-status deletion retained), SEC-03 (deferred to production readiness), SEC-04 (rejected for MVP1, production note only).

---

## 7. Stage A exit and release posture

- **Stage A verdict:** every plan hypothesis has an independent verdict with code/test evidence. No application behavior was changed.
- **Stage A interim GO/NO-GO (historical):** **NO-GO for public/networked use or real user data.** **CONDITIONAL GO for local manual acceptance with disposable/demo data**, with known high-risk behavior: reset-token replay (SEC-01), stale tokens after password change (SEC-02), and non-atomic file/DB delete/upload paths (DATA-01/02).
- **Final Stage D2 posture:** **GO for local manual acceptance with disposable/demo data.** **NO-GO for public/networked use or real user data** until the deferred production-readiness items are addressed: login/recovery abuse controls (SEC-03), a documented and tested backup/restore procedure (HARD-05), and a public-hosting CSP/session-storage review (SEC-04 note). SEC-04 remains rejected for MVP1. DATA-03 was resolved by decision on 2026-10-25: any-status version deletion is deliberate, and permanent deletion of archived history by gym admins is an accepted tradeoff. A minimal CI workflow now exists but has not run yet; it is a quality gate, not proof of production readiness. See sections 9–10 for verification evidence and CI status.

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
| D2 | HARD-03 (CI gate) | `efc49cf` | `ci: minimal hardening gates for backend and frontend` |

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

These commands were re-run during Stage D2 after adding CI and produced the same results (backend: ruff/mypy green, **71 passed**; frontend: Biome, `tsc`, and build green). The install commands used by CI (`cd backend && uv sync --frozen`, `cd frontend && bun install --frozen-lockfile`) were also verified locally without changing either lockfile.

### 9.4 Remaining risks / non-goals

- **DATA-03 (resolved 2026-10-25):** any-status deletion of ACTIVE/ARCHIVED program versions is deliberate product behavior; no code change. Remaining risk: gym admins can permanently delete archived history — accepted tradeoff.
- **SEC-02 / logout (accepted MVP1 risk):** logout is client-side only; it clears the stored token but does not revoke it server-side, so a captured bearer token stays valid until expiry. Bumping `token_version` on logout was rejected because it would invalidate all sessions for that user and no product decision authorized that behavior.
- **DATA-05 / `expected_revision` back-compat (accepted MVP1 risk):** `expected_revision` remains optional. A client that omits it still saves successfully and bumps `revision`, bypassing the stale-write guard. The current UI always sends it; this is deliberate back-compat for older clients, pinned by a test.
- **DATA-05 / server defaults (harmless drift):** `token_version` and `revision` are added by migrations with `server_default="0"` while the SQLModel fields use Python-side defaults. Fresh `create_all` and migrated schemas therefore differ only in server-default metadata; `alembic check` is clean because both are represented in metadata. No code change; acceptable.
- **SEC-03:** no login/recovery throttling; production blocker before network exposure.
- **HARD-05:** no automated/tested backup-restore procedure; production blocker before real user data.
- **SEC-04:** `localStorage` bearer-token tradeoff accepted for local MVP1; CSP/storage review required before public hosting.
- **CI status:** `.github/workflows/ci.yml` exists and defines backend + frontend gates, but it **has not run yet** — pending the first push/PR trigger. Do not treat it as a green signal until a real run is observed. Playwright is intentionally excluded. Status remains pending after the final review round; it is left for the parent to finalize.

---

## 10. Stage D2 — product decisions and CI (2026-10-25)

### 10.1 DATA-03 decision

**Decision:** keep any-status program-version deletion as deliberate product behavior. No production code, route guard, UI affordance, or test was changed.

- Rationale: the route has no status guard, the UI exposes deletion for every editable version, and `test_staff_can_delete_program_versions_in_any_status` explicitly asserts ACTIVE/DRAFT/ARCHIVED deletion. Editing archived versions remains blocked, so the original conflict concerned permanent deletion only.
- Accepted tradeoff / remaining risk: a gym admin can permanently delete archived program history. This is an accepted MVP1 behavior, not a defect.
- Regression documenting the behavior: `backend/tests/api/routes/test_programs.py::test_staff_can_delete_program_versions_in_any_status`.

### 10.2 Minimal CI workflow

**File:** `.github/workflows/ci.yml` (added in `efc49cf`, `ci: minimal hardening gates for backend and frontend`).

- Triggers: push to `main` and all pull requests. Permissions are read-only.
- **`backend` job:** Postgres 17 service (`gym_app_test` database + health check); `uv sync --frozen`; `uv run ruff check app tests`; `uv run mypy app`; `uv run pytest -q -m "not migrations"`; then a separate `uv run pytest -q -m migrations` step. `TEST_DATABASE_URL` points at the service database, from which the migration test derives and drops its disposable `gym_app_migration_test` database. `DATABASE_URL` is a distinct name so the migration guard's disposable-database checks remain meaningful.
- **`frontend` job:** Bun 1.3.14 + Node 22; `bun install --frozen-lockfile`; `bun run lint:check`; `bunx tsc -p tsconfig.build.json --noEmit`; `bun run build`.
- **Playwright is intentionally excluded.** It requires a running backend, the frontend server, seeded demo data, and a browser; that is a heavier integration environment outside this minimal gate. The exclusion is documented in the workflow header comment.
- Actions are pinned to commit SHAs and `persist-credentials: false` is set, consistent with the repository's `zizmor` pre-commit hook. `uv run zizmor .github/workflows/ci.yml` reports no findings.
- **CI status:** **added, not yet run.** No push was made, so no GitHub Actions run exists. The workflow is unverified in GitHub-hosted CI; the first push/PR trigger is pending. Local command equivalents pass, but that is not evidence that the hosted workflow passes (runner image, Python/Bun installation, service startup, and action versions remain unexercised).
- **Validation performed locally:** YAML parses; `zizmor` clean; the exact lint/type/test/build commands and both frozen install commands pass locally. `actionlint` was not available in this environment.

---

## 11. Final independent review round (2026-10-25)

An independent review of the hardening work found eight issues after the Stage D2 commits. The reviewer fixed two before handoff (migration-test password handling and the root lint script); the remaining findings were addressed here. Application behavior changed only in `e55ace6`; the other commits in this round are tests or documentation.

### 11.1 Review-round commits

| Finding | Commit | Subject |
| --- | --- | --- |
| Review fix — migration-test DB password | `04b5a5a` | `review: preserve database password in alembic migration test` |
| Review fix — root lint script | `448206b` | `review: add root lint:check script for pre-commit hook` |
| 3 (HIGH) — owner-archive lockout | `e55ace6` | `fix: preserve gym owner access when archiving own athlete profile` |
| 4 (LOW/MEDIUM) — optional `expected_revision` back-compat | `d395cc7` | `test: pin optional expected_revision back-compat` |
| 6 (LOW) — migration upgrade with existing data | `c8c4549` | `test: exercise migration upgrade with existing data` |
| 7 (docs) — this audit record | this docs commit | `docs: record final review findings and back-compat tradeoffs` |
| 8 (docs) — verification counts | follow-up docs commit | `docs: refresh verification counts and Playwright status` |

### 11.2 Dispositions

3. **Owner-archive lockout (fixed).** `archive_athlete` now keeps an owner's membership active even when their only role is `ATHLETE`. `get_athlete_access` also lets an owner/admin read their own archived profile when the endpoint explicitly allows archived records, which is what self-restore needs. Regressions: `test_archiving_owner_as_athlete_keeps_gym_access_and_allows_self_restore` (fails pre-fix with 403 `not_a_gym_member`) and `test_owner_archive_lockout_when_membership_deactivation_is_not_preserved` (documents that the pre-fix deactivation is unrecoverable without the fix).
4. **Optional `expected_revision` (deliberate back-compat, pinned).** No API change. `test_update_without_expected_revision_still_succeeds_and_bumps_revision` documents that a request without `expected_revision` succeeds and bumps `revision`, deliberately preserving old clients; the current UI always sends it. Accepted risk: an unmaintained client can overwrite a newer edit.
5. **Client-side logout (accepted MVP1 risk).** No code change. Clearing `token_version` on logout would end all sessions for the user, and no product decision authorized that. The bearer token remains valid until expiry; recorded under SEC-02 and §9.4.
6. **Migration upgrade-with-data (covered).** `test_upgrade_with_existing_data_backfills_new_columns` recreates the disposable `gym_app_migration_test` database, upgrades to `2a61e7c0b94a`, inserts a user with a hashed password plus a gym/program/version, upgrades to head, runs `alembic check`, and asserts `token_version` and `revision` are backfilled to `0`, NOT NULL, and that existing values were preserved. The fixture now recreates and drops the database per test.
7. **`server_default` vs model default (harmless drift, documented).** No code change. Migrations declare `server_default="0"` while the model fields use Python defaults; both schemas behave the same and `alembic check` is clean. Recorded in §9.4.
8. **Progress-doc counts (refreshed).** `docs/implementation-progress.md` now reports the real current numbers: 77 backend tests, 4 migration-marked tests, and the full Playwright suite at 50 total / 49 passed / 1 production-only skip. `PWA_PROD=1` on the production build at `:8000` passes 3/3, including the skipped worker test.

### 11.3 Accepted risks / notes from this round

- **DATA-05 back-compat:** optional `expected_revision` is intentional and test-pinned; stale clients can bypass conflict detection. Do not remove without an approved breaking-change decision.
- **SEC-02 logout:** tokens survive client-side logout until expiry. A server-side logout/revocation design (single session vs all sessions) needs an explicit product decision before production.
- **Schema metadata drift:** the `server_default` difference is harmless and visible to Alembic as a non-difference; no migration was added.
- **CI status:** unchanged and still pending the first real GitHub Actions run (see §10.2). Left for the parent to finalize after the push.
- **Verification for this round:** `ruff`, `mypy`, full `pytest` (77 passed), migration tests (4 passed), Biome `lint:check`, `tsc`, production build, full Playwright (50 total / 49 passed / 1 skipped), and the production PWA subset (3 passed) all ran locally.

