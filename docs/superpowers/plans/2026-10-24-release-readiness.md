# Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close evidenced cache, import-boundary, destructive-action, regression-isolation and verification gaps in the existing local MVP without adding product features.

**Architecture:** Keep the existing FastAPI/SQLModel routes, generated client, React Material 3 components and Playwright foundation. Add build-scoped app-shell caching, bounded import reads, narrowly targeted mutation safety and reusable disposable E2E data; finish with a non-resetting local verification entry point and accurate runbooks. Do not restructure unrelated code or change the database schema.

**Tech Stack:** Python 3.14, FastAPI, SQLModel, PostgreSQL 17 on the accepted Homebrew path, Alembic, Pytest; Node.js 22+, Bun 1.3+, React 19, TypeScript, Vite, React Aria, Playwright; Node built-in test/assert/vm modules (no new dependency).

**Spec:** `docs/implementation-progress.md`, `README.md`; local execution details in `docs/local-testing.md` and `development.md`. These are the available scope authorities, not a new product specification.

## Global Constraints

- “The product is **local development/manual acceptance only**.”
- “There is no deployment, public hosting, real email provider or cloud storage in scope.”
- “UI system: Material Design 3 only.” Retain Persian/RTL defaults, English/LTR support, Jalali presentation and Gregorian/ISO storage.
- “PWA is minimal: app-shell/offline navigation cache only; no offline data synchronization.” Do not cache API responses or private body-analysis downloads.
- “Physical iPhone testing is not required or performed; desktop and emulated mobile viewports are used as approved.”
- “The real password must not be written to source, docs, tests, logs, screenshots or Git history.” Use existing fake demo/test credentials only.
- Backend tests use the existing guarded `_test` database; E2E tests may mutate only their registered fake athletes in the local demo gym. Never run the reset script, alter `.env`, change history or reseed automatically.
- Preserve current API contracts unless explicitly changed below; notably, **do not add an archive-before-delete API requirement**. The existing API supports direct deletion and this plan only improves the UI's existing confirmation/recovery.
- No new packages, migration, CI, hosting or deployment work. Do not run the unsafe autofixing frontend `lint` command as a verification check.
- Execution is assigned to **DeepSeek V4.1 Flash in the parent session** after plan approval; the planner changes only this file and does not commit.

## Review Focus

1. Rebuild over an installed PWA / offline or failed HTML response: next full online navigation uses the new shell; errors do not poison offline fallback, unrelated origin caches survive (Task 1 tests).
2. Malformed or oversized import and a non-manager/foreign-gym coach: bounded reads, structured existing error codes, no unauthorized records or invitations (Task 2 tests).
3. One successful and one failed permanent deletion: retry only the failed target, announce the failure and do not dismiss an in-flight mutation (Task 3 tests).
4. Same athlete in two gyms / archive-restore access cutover: deleting gym A must preserve gym B's profile, program and file; former coach access stays revoked until valid restoration (Task 3 tests).
5. Failed/repeated E2E runs and phone-sized admin workflows: teardown removes registered records even after a test throws; seeded athletes remain untouched; archive/import dialogs stay usable without page overflow (Task 4 tests).

---

## Evidence and chosen boundaries

- At `465a6af`, `frontend/public/sw.js:1-28` uses the fixed `formyar-shell-v1` and deletes **all** other origin caches. Navigation and asset handlers cache non-success responses and do not extend event lifetime for writes. `frontend/src/main.tsx:33-37` registers only on production load; `frontend/tests/pwa.spec.ts` checks assets/registration, not upgrade/offline/error behavior. Hashed assets and network-first HTML already exist: **stale-bundle root cause is not established**. Test and fix these demonstrated lifecycle weaknesses, not a presumed need for a new PWA framework or automatic reload.
- Import already has 5 MiB / 500-row limits in `backend/app/services/athlete_import.py`, but both route handlers call unbounded `await file.read()` before the byte check. `_read_csv` does not catch reader errors (e.g. field-size errors); XLSX open errors are already mapped to `invalid_file`. Import tests cover templates, mixed rows, XLSX preview and staff-email conflict; not write/preview permission boundaries or foreign-gym default coaches.
- Lifecycle tests already cover owner restore/delete and coach rejection for those two actions. Missing high-risk cases are archive permission, wrong-gym mutations, preservation of another gym's data and restore access cutover. No new lifecycle policy is needed.
- `DeleteAthletesDialog.tsx:48-80` retries every original target after partial success; a successful target's subsequent 404 prevents eventual recovery. `M3.Dialog` permits header-close/Escape while its caller is busy; footer disabling does not stop those exits. Focus trapping/restoration, text-field labels and error alerts already exist—retain and test them rather than replace the dialog system.
- Archive tests clean up only at the successful end; import tests archive but never delete their created athlete. Program-authoring tests also create athletes. `playwright.config.ts` gives the Pixel 5 project only `athlete.spec.ts`; there are small-viewport admin/control smoke tests, but no emulated-mobile archive/import journey.
- Read-only collection on 2026-10-24 found **30 backend tests** and **37 Playwright project cases**, versus the progress document's 20 / 31 / 25 historical passed claims. Collection is not proof of passing. `uv run alembic check` succeeded with “No new upgrade operations detected.” `.env.example:10` references absent `scripts/bootstrap_local.sh`; `docs/local-testing.md:125-129` has cumulative `cd` commands that do not execute as a single root-started sequence. Optional Compose still targets PostgreSQL 18 / `app`, unlike the accepted Homebrew 17 / `gym_app` path; do not claim it is verified.

## File structure / responsibility map

| Task | Files | Responsibility |
|---|---|---|
| 1 | Modify `frontend/public/sw.js`, `frontend/src/main.tsx`, `frontend/package.json`; create `frontend/scripts/build-service-worker.mjs`, `frontend/tests-unit/build-service-worker.test.mjs`, `frontend/tests-unit/service-worker.test.mjs`; modify `frontend/tests/pwa.spec.ts` | Build-scoped worker, cache lifecycle unit tests, real-browser production smoke |
| 2 | Modify `backend/app/api/routes/athletes.py`, `backend/app/services/athlete_import.py`, `backend/tests/api/routes/test_athlete_import.py` | Bounded upload helper, CSV error mapping, import access/boundary tests |
| 3 | Modify `frontend/src/components/M3.tsx`, `frontend/src/components/DeleteAthletesDialog.tsx`, `frontend/src/components/AthleteImportDialog.tsx`; create `frontend/tests/athlete-safety.spec.ts`; modify `backend/tests/api/routes/test_athlete_lifecycle.py` | Busy dismissal guard, deletion retry bookkeeping, UI safety and backend lifecycle regression tests |
| 4 | Create `frontend/tests/fixtures/athlete-data.ts`, `frontend/tests/test-data.spec.ts`; modify `frontend/tests/athlete-archive.spec.ts`, `frontend/tests/athlete-import.spec.ts`, `frontend/tests/program-authoring.spec.ts`, `frontend/tests/athlete-safety.spec.ts`, `frontend/playwright.config.ts` | Owned test-data teardown and phone-sized admin regression matrix |
| 5 | Create `scripts/verify-local.mjs`, `scripts/tests/verify-local.test.mjs`; modify `package.json`, `README.md`, `docs/local-testing.md`, `docs/implementation-progress.md`, `development.md`, `.env.example` | Fail-fast, non-resetting verification and truthful local runbooks |

Use existing large route/component files without unrelated splitting. Generated SDK files, lockfiles and Compose configuration need no edits. Each task is independently verifiable; Task 4 deliberately replaces duplication introduced/used in Task 3 tests, not product interfaces. Task 5 runs the verification introduced by preceding tasks.

### Task 1: Make installed PWA cache updates build-scoped and non-poisoning

**Files:** All Task 1 files in the map above. Relevant current sections: `sw.js:1-72`, `main.tsx:33-37`, `package.json:scripts.build`, `pwa.spec.ts:32-44`.

**Interfaces:**
- Consumes: existing Vite output directory `backend/app/frontend`, worker template `frontend/public/sw.js`, browser Cache/ServiceWorker APIs.
- Produces: `export async function buildServiceWorker(outputDir: string, workerTemplatePath?: string): Promise<string>` in `frontend/scripts/build-service-worker.mjs` (JSDoc types), returning a 16-character lowercase SHA-256 prefix and writing `<outputDir>/sw.js`. The optional template path defaults to the repository's public worker; unit tests pass a temporary template, never edit product files.
- Worker cache key is `formyar-shell-${buildId}`; template placeholder is exactly `__FORMYAR_BUILD_ID__`. Build ID hashes worker template bytes, emitted `index.html` bytes and sorted relative `/assets/` filenames. Do not hash a previously generated output worker or timestamps.
- Production registration remains `/sw.js`, with `{ updateViaCache: "none" }`; explicitly call `registration.update()` after registration. Catch registration/update rejection without an unhandled promise; no automatic reload or new update UI.

- [ ] **Step 1: Write deterministic failing tests.** Use `node:test` and `node:assert/strict`, temporary output fixtures and `node:vm` to evaluate the actual worker source with fake `self`, `fetch`, CacheStorage and extendable events. Drain all `waitUntil` promises; no sleeps or application server for these tests.
  - `build id changes with shell, assets or worker but is stable for identical builds`: identical fixture yields identical ID (`assert.equal(id1, id2)`); changing each input independently yields a different ID (`assert.notEqual(changedId, id1)`); `assert.ok(output.includes("formyar-shell-" + id1))`, `assert.equal(output.includes("__FORMYAR_BUILD_ID__"), false)`; a second invocation is stable.
  - `activation removes only obsolete FormYar caches`: starting with `formyar-shell-v1`, current key and `unrelated-cache`, `assert.deepEqual(deletedKeys, ["formyar-shell-v1"])` and `assert.equal(claimCalls, 1)` after awaiting activation.
  - `navigation refreshes shell and preserves last good shell on server errors`: 200 HTML `new shell` replaces `old shell` (`assert.equal(await cached.text(), "new shell")`); 500 HTML and 200 JSON do not; network rejection returns last good shell from **this worker's** cache, not an unrelated cache (`assert.equal(await offline.text(), "new shell")`). Missing fallback: `assert.equal(response.type, "error")`.
  - `only successful static responses enter this build cache`: 404/500 assets do not cache (`assert.equal(putCalls, 0)`); 200 assets cache before event completion (`assert.equal(putCalls, 1)`); API paths (including body-file download), non-GET and foreign-origin requests never call `respondWith` or `cache.put` (`assert.equal(respondWithCalls, 0)`).
  - `updated worker replaces old shell on the next online navigation`: run two VM worker instances against shared fake CacheStorage with IDs A/B and distinct HTML; activate B, perform successful B navigation, then offline navigation; `assert.equal(await offline.text(), "B shell")` and `assert.equal((await caches.keys()).includes("formyar-shell-A"), false)`.

- [ ] **Step 2: Run the failing tests.** From root: `node --test frontend/tests-unit/build-service-worker.test.mjs frontend/tests-unit/service-worker.test.mjs`. Expect missing build helper plus assertions failing on global cache deletion/error caching; do not treat a test-runner setup error as evidence of the worker defect.

- [ ] **Step 3: Implement build scoping and cache rules.** Add the post-build helper and append `&& node scripts/build-service-worker.mjs` to the existing frontend build command, with default CLI output resolved relative to the helper (not caller CWD). Read the public worker template via its module URL; missing output/index must exit nonzero. Preserve current navigation-network-first and hashed-asset-cache-first behavior. Cache only `response.ok` HTML navigation responses and successful static responses, use `event.waitUntil` for writes, and scope lookup to the current cache. Activation deletes only other `formyar-shell-` keys (including legacy v1); preserve unrelated keys. Keep `skipWaiting()`/`clients.claim()` and existing precache list. Update registration as specified; no API/private-data caching.

- [ ] **Step 4: Add and run real-browser verification.** Add production-only test `production worker controls a warmed shell without caching private API data` to `pwa.spec.ts`, with empty storage state. First visit `/manifest.webmanifest` (same origin, no app registration), create `unrelated-cache` via page evaluation, then visit `/login` and await service-worker readiness/controller after reload; sentinel must survive. Warm `/login`; poll CacheStorage until `/` and the successfully loaded same-origin `/assets/` resource URLs from this controlled page's Performance entries are present, rather than sleeping. Reload offline and `await expect(page.getByRole("button", { name: "ورود", exact: true })).toBeVisible()`; return online and verify the worker's cache keys contain no `/api/` request after a health-check fetch. Verify the active cache suffix matches the ID in the served worker. Keep the existing manifest test. Commands from root:
  ```sh
  node --test frontend/tests-unit/build-service-worker.test.mjs frontend/tests-unit/service-worker.test.mjs
  (cd frontend && bun run build)
  (cd frontend && bunx tsc --noEmit)
  (cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test tests/pwa.spec.ts --project=chromium)
  ```
  Expect unit/type/build checks and production PWA tests to pass. FastAPI must already be serving the freshly built local output; do not start/reset/seed it in tests. Document that a full refresh after rebuild is required for already-open screens; unsaved editor state must not be auto-reloaded.

- [ ] **Step 5: Commit.**
  ```sh
  git add frontend/public/sw.js frontend/src/main.tsx frontend/package.json frontend/scripts/build-service-worker.mjs frontend/tests-unit/build-service-worker.test.mjs frontend/tests-unit/service-worker.test.mjs frontend/tests/pwa.spec.ts
  git commit -m "fix: scope PWA caches to local builds and preserve good shells"
  ```

### Task 2: Bound import reads and pin authorization/error boundaries

**Files:** Modify `backend/app/api/routes/athletes.py:330-367`, `backend/app/services/athlete_import.py:169-186`; test `backend/tests/api/routes/test_athlete_import.py`.

**Interfaces:**
- Consumes: existing `MAX_IMPORT_BYTES = 5 * 1024 * 1024`, `MAX_IMPORT_ROWS = 500`, `GymAdminDep`, `_setup`/`_csv` test helpers and the unchanged import service signatures.
- Produces: `async def _read_import_upload(file: UploadFile) -> bytes` in the athletes route module. Read once with `MAX_IMPORT_BYTES + 1`; raise HTTP 400 / `import_file_too_large` above the limit, otherwise return bytes. Both preview and import routes use it.
- `_read_csv(content: bytes) -> list[list[Any]]` retains its signature and encoding/delimiter behavior; strict CSV reader failures become HTTP 400 / `invalid_file`, not a server exception. No generated client or schema changes.

- [ ] **Step 1: Write boundary/permission tests first.** Extend the existing test module; use `asyncio.run` for the async helper (no pytest-asyncio dependency).
  - `test_import_upload_read_is_bounded`: an `UploadFile` with an `AsyncMock` read returning `b"x" * MAX_IMPORT_BYTES` is returned unchanged (`assert result == content`); `read.assert_awaited_once_with(MAX_IMPORT_BYTES + 1)`. Returning one more byte raises `HTTPException`: `assert exc.value.status_code == 400` and `assert exc.value.detail == "import_file_too_large"`. Test both parameter cases.
  - `test_preview_and_import_reject_oversized_uploads`: parameterize `/import/preview` and `/import`; send `MAX_IMPORT_BYTES + 1` bytes with otherwise valid manager/form parameters; assert 400 and exact detail. Assert a unique email in the payload has no profile afterwards.
  - `test_preview_and_import_report_malformed_csv`: both endpoints, CSV `b'email,full_name\n"unterminated'`; assert 400 / `invalid_file`, no record created. Also exercise a field longer than the standard CSV field limit, still below 5 MiB; it must return structured 400, not 500.
  - `test_import_preview_and_write_require_gym_admin`: both endpoints with existing coach headers and valid payload/password; assert 403 / `gym_admin_required`, list count unchanged, `email_outbox == []`.
  - `test_import_rejects_foreign_gym_default_coach`: create a second isolated `_setup` gym; give gym A owner the gym B coach ID for both endpoints; assert 400 / `invalid_coach`, no athlete created in either gym. Explicit gym B `coach_email` instead yields preview row `status == "error"`, `messages == ["coach_not_found"]`; submitting it yields `created == 0` and the same failed-row message.
  - `test_import_row_limit_is_enforced_before_writes`: parameterize both endpoints with 501 nonblank unique rows; assert 400 / `too_many_rows` and unchanged list count. Retain existing successful CSV/XLSX/mixed-row tests for compatibility.

- [ ] **Step 2: Run red.** `(cd backend && uv run pytest tests/api/routes/test_athlete_import.py -q)`. Expect missing bounded helper and malformed CSV failures; permission regressions may already pass. Do not weaken passing permission contracts to manufacture a red test.

- [ ] **Step 3: Implement only the bounded helper and CSV error mapping.** Import the existing byte-limit constant in the route, use the helper in both endpoints, set `strict=True` on the existing reader and catch `csv.Error` around iteration, mapping to `invalid_file`. Preserve current row limits, per-row savepoints, mixed-result semantics and manager dependencies. No general import rewrite or email transport change.

- [ ] **Step 4: Run green.** `(cd backend && uv run pytest tests/api/routes/test_athlete_import.py -q)` then `(cd backend && uv run pytest -q)`. All new and existing cases pass, including XLSX/mixed valid-skipped-error results. Backend tests must still use the guarded test database; no real credentials or email.

- [ ] **Step 5: Commit.**
  ```sh
  git add backend/app/api/routes/athletes.py backend/app/services/athlete_import.py backend/tests/api/routes/test_athlete_import.py
  git commit -m "fix: bound athlete import reads and cover permission boundaries"
  ```

### Task 3: Make destructive mutation recovery safe and test lifecycle isolation

**Files:** Modify `frontend/src/components/M3.tsx:599-694, ConfirmDialog`, `frontend/src/components/DeleteAthletesDialog.tsx:29-109`, `frontend/src/components/AthleteImportDialog.tsx:318-326`; create `frontend/tests/athlete-safety.spec.ts`; extend `backend/tests/api/routes/test_athlete_lifecycle.py`. No backend product change is planned: the new lifecycle cases pin existing behavior.

**Interfaces:**
- Consumes: existing `DeleteAthleteTarget`, delete/archive/restore endpoints, dialog callbacks and translation keys; existing lifecycle `_setup`, gym and program helpers.
- Produces: optional `dismissible?: boolean` (default `true`) on `Dialog`'s current props; `dismissible={false}` disables header close and ignores Escape. Read current dismissibility via a ref, like existing `onCloseRef`, so busy-state changes do not rerun initial-focus/restoration effects. `ConfirmDialog` forwards `dismissible={!loading}`; delete/import dialogs pass `dismissible={!busy}`. Existing footer buttons remain responsible for their busy disabling. No changed return types or new translation keys.
- Delete dialog keeps per-open `remainingTargets: DeleteAthleteTarget[]`, initialized from `athletes` when opening, and a cumulative success count. A batch tries only remaining targets; on partial failure retain only failures for retry, invalidate existing queries, keep an alert visible and preserve typed confirmation. Confirmation/title/expected word remain based on the original operation; do not make a bulk retry suddenly require one athlete's email. On all-success close and call `onDeleted` exactly once. Reopening clears counts, confirmation and error.

- [ ] **Step 1: Write UI and backend regressions.** For initial UI setup copy the existing archive spec's API-create helper, but immediately register every created ID and use `try/finally` cleanup with original gym headers. Task 4 will centralize this. Use request interception only for targeted DELETE failures/delays; teardown API requests must bypass UI routes.
  - `partial permanent deletion retries only failed athletes`: two unique archived athletes, select just their filtered rows; incorrect/empty confirmation keeps submit disabled (`await expect(submit).toBeDisabled()`). Let first DELETE reach the real API via `route.continue()`, return 500 once for second, then let its retry reach the API. Assert dialog `role=alert` contains localized counts (one deleted, one failed), focus remains within dialog, and `expect(deletedIds).toEqual([first.athleteId, second.athleteId, second.athleteId])` (never first twice). Second attempt succeeds, `await expect(dialog).toHaveCount(0)`, both exact emails absent from active+archived API listing. Parameterize the first failure as HTTP 500 and `route.abort("failed")`; for both, the failed athlete remains until retry and alert is visible.
  - `busy delete cannot be dismissed or submitted twice`: hold DELETE response behind a promise; submit, press Escape and attempt header close; dialog remains visible, close/cancel/submit disabled, DELETE count is 1. Release response and assert completion. In the idle/cancel case, initial focus is the confirmation field; Shift+Tab/Tab stays inside; Escape closes and restores focus to the still-mounted initiating delete button. Never rely on fixed timeouts.
  - `archive confirmation cannot close while the mutation is pending`: hold POST `/archive`, confirm, Escape/header close cannot dismiss; release and verify one request/success. Covers `ConfirmDialog` propagation without changing archive policy.
  - `import mutation cannot be dismissed while submitting`: use a valid preview and hold import POST; Escape/header close cannot dismiss or reopen a second import. Release a structured mixed result and assert result visible; the upload file input has an accessible name (add `aria-label={t("athletes.importFile")}` to the existing hidden input).
  - Backend `test_archive_requires_admin_and_wrong_gym_mutations_do_not_change_target`: coach archive returns 403 / `gym_admin_required`; gym B owner using B headers against A-only athlete gets 404 / `athlete_not_found` for archive, restore and DELETE. A owner's profile/program JSON is unchanged.
  - Backend `test_delete_in_one_gym_preserves_other_gym_profile_program_and_file`: create same email in A/B, publish one program and upload a tiny valid PDF in each. Archive/delete A; A profile and download are unavailable; B profile JSON and published-version JSON equal their pre-delete snapshots; B file download bytes unchanged; global account still exists (B detail has same user ID). Restore and repeat operations only against test-owned data.
  - Backend `test_archive_restore_cuts_off_and_restores_coach_access_without_duplicate_assignment`: coach detail 200 initially, 404 after owner archive, 200 after owner restore with original coach; restore twice, `assert sum(row["ended_at"] is None for row in detail["assignments"]) == 1` and `assert sum(row["ended_at"] is not None for row in detail["assignments"]) == 1`. Profile user/gym IDs and program JSON survive (do not require archive-updated profile timestamps to remain unchanged). Existing restore/delete permission test stays intact.

- [ ] **Step 2: Run red.**
  ```sh
  (cd frontend && bunx playwright test tests/athlete-safety.spec.ts --project=chromium)
  (cd backend && uv run pytest tests/api/routes/test_athlete_lifecycle.py -q)
  ```
  UI retry/busy/input-name assertions should fail on current code; backend regression assertions should already pass. If backend behavior differs, stop and report the precise failing contract before broadening this task—do not silently invent lifecycle policy.

- [ ] **Step 3: Implement dialog guards and retry bookkeeping.** Keep the existing dialog's focus trap, popover Escape handling, focus restoration and appearance. Guard both Escape and the header button with `dismissible`, forwarded by `ConfirmDialog` and the delete/import callers. In deletion, snapshot original targets on open, iterate remaining targets and retain failed IDs; do not reset state when query invalidation rerenders the parent. Keep the existing localized summary and `role="alert"`; give the error container `tabIndex={-1}` plus a ref and focus it when a new failure summary appears, so focus does not remain on a now-disabled submit control/outside the dialog. Add the import input name, not a new upload control. No optimistic deletion or treating arbitrary 404s as successful user deletions.

- [ ] **Step 4: Run green.** Run both Step 2 commands, then `(cd frontend && bunx playwright test tests/athlete-archive.spec.ts tests/athlete-import.spec.ts tests/controls.spec.ts --project=chromium)` and `(cd frontend && bunx tsc --noEmit && bun run build)`. All pass; existing nested-select/date-picker Escape behavior and idle dialog cancellation remain functional.

- [ ] **Step 5: Commit.**
  ```sh
  git add frontend/src/components/M3.tsx frontend/src/components/DeleteAthletesDialog.tsx frontend/src/components/AthleteImportDialog.tsx frontend/tests/athlete-safety.spec.ts backend/tests/api/routes/test_athlete_lifecycle.py
  git commit -m "fix: guard busy athlete mutations and recover partial deletions"
  ```

### Task 4: Isolate athlete E2E data and exercise admin archive/import on mobile

**Files:** All Task 4 files in the map. Existing creation/cleanup duplication lives throughout `athlete-archive.spec.ts`, `athlete-import.spec.ts:23-84`, and both `program-authoring.spec.ts` tests.

**Interfaces:**
- Consumes: existing admin auth state, `API_URL`/`DEMO_PASSWORD`, `CoachPublic`, local demo gym with Reza coach; unchanged athlete routes. Capture gym ID/token after the dashboard is ready; keep those headers immutable for teardown even if the UI switches gyms.
- Produces in `frontend/tests/fixtures/athlete-data.ts`:
  ```ts
  export type ManagedAthlete = {
    athleteId: string; email: string; headers: Record<string, string>
  }
  export type AthleteData = {
    marker: string
    headers: Record<string, string>
    coach: CoachPublic
    create(options?: { name?: string; archived?: boolean }): Promise<ManagedAthlete>
    trackEmail(email: string): void
    cleanup(): Promise<void>
  }
  // export const test = base.extend<{ athleteData: AthleteData }>(...)
  // export { expect } from "@playwright/test"
  ```
  `marker` is `e2e-${randomUUID()}`. `create` registers the unique email **before** its POST; `trackEmail` rejects emails not starting with `${marker}-`. Cleanup looks up registered exact emails (including archived), archives then deletes owned matches, accepts 404 for already-removed targets, asserts other responses, attempts all targets before reporting aggregated failures, and is idempotent. No prefix-wide or seeded-record deletion. Fixture teardown calls cleanup in `finally`.
- Add project `mobile-admin`, using `devices["Pixel 5"]`, admin storage state and `admin-setup` dependency, with `testMatch: /athlete-(archive|import)\.spec\.ts/`. Keep current `chromium` and athlete `mobile` projects unchanged, `workers: 1`, no parallelization against shared demo state.

- [ ] **Step 1: Write the fixture contract and mobile journey tests.** Create `test-data.spec.ts` importing the new fixture (initially absent).
  - `managed athlete cleanup is idempotent and preserves seeded athletes`: record active+archived count and Nima's exact profile; create one active and one archived managed athlete, call cleanup twice, `expect(missing.status()).toBe(404)` for each ID, `expect(after.count).toBe(before.count)` and `expect(nimaAfter).toEqual(nimaBefore)`.
  - `managed athlete cleanup runs after a thrown test operation`: register a marker-owned email before simulating import via API, throw inside a `try` and call cleanup in `finally`; catch the deliberate error outside that block and assert exact-email count zero. This tests the same finalizer path without making the suite itself intentionally fail.
  - `managed athlete cleanup refuses unowned email`: `expect(() => athleteData.trackEmail("nima@example.com")).toThrow()` and Nima remains unchanged.
  - Extend archive test `archived athletes can be restored or permanently deleted`: assert idle cancellation makes **no DELETE**, typed confirmation gate works, dialog fits viewport; restore/delete actions remain reachable in the table's horizontal scroll container. Assert `document.documentElement.scrollWidth <= window.innerWidth + 1` on archive page and dialog, not that the intentionally scrollable table has no overflow.
  - Extend import test `manager imports athletes from CSV after previewing rows`: accessible file input, invalid-email explanation, missing-coach recovery, mixed result, reopen resets file/preview/password; same page/dialog width assertion. Do not add XLSX browser-generation dependencies (backend already covers it).

- [ ] **Step 2: Run red.** `(cd frontend && bunx playwright test tests/test-data.spec.ts --project=chromium)` fails for the missing fixture. `(cd frontend && bunx playwright test tests/athlete-archive.spec.ts tests/athlete-import.spec.ts --project=mobile-admin)` initially fails because the project is absent. Existing desktop happy paths need not fail.

- [ ] **Step 3: Implement test ownership/teardown and project configuration.** Implement the typed fixture using existing API/credential patterns; migrate archive, import, safety and **both** authoring tests to it. Use marker-owned emails and names for unique selectors; call `trackEmail` before UI import. Remove success-only cleanup from migrated tests. Register `mobile-admin` exactly as above. Do not change shared seeded Nima/Reza assignments or move all admin suites into a new project. If the new viewport assertions fail, report the actual CSS/interaction defect before expanding the product-file list—no speculative responsive redesign is planned.

- [ ] **Step 4: Verify repeatability and matrix.**
  ```sh
  (cd frontend && bunx tsc --noEmit)
  (cd frontend && bunx playwright test tests/test-data.spec.ts tests/athlete-safety.spec.ts tests/program-authoring.spec.ts --project=chromium)
  (cd frontend && bunx playwright test tests/athlete-archive.spec.ts tests/athlete-import.spec.ts --project=chromium --project=mobile-admin --repeat-each=2)
  (cd frontend && bunx playwright test --list)
  ```
  Expect all executed tests to pass twice without accumulating owned athletes; list contains archive/import cases under both chromium and mobile-admin. In one temporary local verification run, throw immediately after fixture creation, verify the test fails for that deliberate error and its exact email is absent afterwards, then remove that throw before committing. Do not run any reset to achieve repeatability.

- [ ] **Step 5: Commit.**
  ```sh
  git add frontend/tests/fixtures/athlete-data.ts frontend/tests/test-data.spec.ts frontend/tests/athlete-archive.spec.ts frontend/tests/athlete-import.spec.ts frontend/tests/program-authoring.spec.ts frontend/tests/athlete-safety.spec.ts frontend/playwright.config.ts
  git commit -m "test: isolate athlete fixtures and cover mobile admin lifecycle"
  ```

### Task 5: Provide fail-fast local verification and reconcile release-readiness docs

**Files:** All Task 5 files in the map. Relevant docs sections: README setup/tests/PWA/reset; progress verification/known limits; local-testing automated commands and archive/import walkthroughs; `.env.example:10` comment only.

**Interfaces:**
- Consumes: existing `uv`, Bun/Node executables and running local PostgreSQL; Task 1 worker unit/build command; existing Alembic environment uses development `DATABASE_URL` for **read-only checks**, Pytest continues using guarded `TEST_DATABASE_URL`.
- Produces `scripts/verify-local.mjs` exports (JSDoc types):
  ```ts
  type VerificationStep = {
    label: string; cwd: string; command: string; args: string[]
  }
  getVerificationSteps(rootDir: string): VerificationStep[]
  runVerification(
    steps: readonly VerificationStep[],
    run: (step: VerificationStep) => number,
  ): number
  ```
  The direct CLI uses `spawnSync` with `shell: false`, inherited stdio, each explicit CWD, maps spawn error/null exit to 1, and stops at first nonzero status. Importing the module does not execute checks. Root package command: `"verify:local": "node --test scripts/tests/verify-local.test.mjs && node scripts/verify-local.mjs"`.
- Ordered steps: backend `uv run alembic current --check-heads`; backend `uv run alembic check`; backend `uv run pytest -q`; frontend `node --test tests-unit/build-service-worker.test.mjs tests-unit/service-worker.test.mjs`; frontend `bunx tsc --noEmit`; frontend `bun run build`. **No** upgrade, reset, bootstrap, seed, secret-login script, auto-start, dependency install or E2E mutation in this command. Browser acceptance is a separate explicitly invoked command with demo prerequisites.

- [ ] **Step 1: Write failing verification-runner tests.** Use Node built-in test/assert, with injected fake `run`, never real commands.
  - `verification steps use explicit root-relative working directories`: assert each ordered command/args/CWD exactly matches the interface above, independent of process CWD.
  - `verification stops at first failure and preserves exit code`: fake third step returns 7; `assert.equal(result, 7)` and `assert.deepEqual(calls, steps.slice(0, 3))`; all-success `assert.equal(runVerification(steps, () => 0), 0)`.
  - `verification plan never mutates development data or prints credentials`: assert steps contain neither `upgrade`, `reset`, `initial_data`, `seed_demo`, `verify_superadmin_login`, nor shell/env-dump commands; no E2E command. Read `.env.example` only to assert the nonexistent `bootstrap_local.sh` reference is absent; never read `.env`.

- [ ] **Step 2: Run red.** `node --test scripts/tests/verify-local.test.mjs` fails because the runner exports do not exist. After implementing runner, the stale example-comment assertion should still fail until docs are corrected.

- [ ] **Step 3: Implement the runner and correct runbooks.** Add the small step array/loop and package script; fix only the stale database-creation comment in `.env.example` to refer to README `createdb` instructions. Make docs runnable from repo root using subshells, not cumulative ambiguous `cd` sequences. Document:
  1. `npm run verify:local` gates and effects (read-only migration checks, destructive **test-DB-only** Pytest fixtures, ignored build-output replacement; never reset/seed development DB).
  2. E2E demo setup is manual; default Playwright starts/reuses Vite but requires local API/Postgres/demo accounts. Run `(cd frontend && bunx playwright test)` separately; running these tests mutates and cleans up owned demo records.
  3. Production sequence: `(cd frontend && bun run build)`, run the documented local FastAPI server in another terminal, then `(cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test)`. Include the new mobile-admin project, full-refresh update semantics, warmed-shell-only offline limitation, no offline private data. Historical manual “clear site data” is troubleshooting, not normal upgrade acceptance.
  4. Archive/restore/permanent-delete confirmation and CSV/XLSX import walkthroughs; import limits remain **5 MiB, 500 nonblank rows**, preview does not write, mixed results are possible. Reset remains a separately documented explicitly destructive operation, never a verification step.
  5. Clearly mark retained Compose as **not acceptance-verified for this path**, with PostgreSQL 18 / `app` differing from Homebrew 17 / `gym_app`; do not change its services, claim Compose parity or run it in this task.
  Replace stale “latest passed” numbers with dated, freshly observed command outcomes: executed/passed/skipped and project matrix where available. Preserve historical claims only when explicitly labeled historical. A collected count must be labeled **collected**, never **passed**; if services prevent a run, record the blocker, not guessed results. Retain all MVP exclusions.

- [ ] **Step 4: Run final verification and record exact evidence.**
  ```sh
  node --test scripts/tests/verify-local.test.mjs
  npm run verify:local
  (cd frontend && bunx playwright test)
  (cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test)
  git diff --check
  ```
  Expect runner tests/checks and both browser matrices to pass (production-only PWA smoke is explicitly skipped in the dev run). API/production server must already be running; if unavailable, report incomplete browser acceptance and do not label the release ready. Verify docs match these exact commands/results, the new plan's non-goals remain unchanged, and only intended files changed. Do not run reset, touch `.env` or commit any auth state/reports/build artifacts.

- [ ] **Step 5: Commit.**
  ```sh
  git add scripts/verify-local.mjs scripts/tests/verify-local.test.mjs package.json README.md docs/local-testing.md docs/implementation-progress.md development.md .env.example
  git commit -m "chore: add safe local verification and reconcile MVP runbooks"
  ```

## Not in scope / explicitly deferred

- No deployment/hosting/TLS, real email/cloud storage, CI, attendance, workout performance logging, analytics, chat, nutrition, payments, AI program generation or native app.
- No full offline synchronization, automatic app reload/update prompt, PWA framework or guarantee that an unvisited lazy-loaded route works offline. A user may explicitly refresh after saving edits.
- No pagination/virtualization/N+1 rewrite: unbounded athlete listing exists, but no measured local-MVP release-blocking scale failure was established. Do not invent a production architecture to address it.
- No Compose version/database migration, dependency upgrades, template removal, global lint cleanup or unrelated refactor. Record the optional Compose discrepancy instead of expanding the supported acceptance matrix.
- No automated backup/restore/reset execution or new backup subsystem; existing reset guards remain, and destructive reset is not part of verification. New migrations are unnecessary for the selected gaps.
- No new lifecycle semantics (including archive-first deletion), bulk endpoint, role redesign or optimistic data deletion. Unsupported new findings require a focused parent decision, not silent scope growth.

## Self-review completed

- **Spec coverage:** Local-only permissions/privacy, manual acceptance, PWA, responsive Persian-first UI and honest verification are covered; approved excluded features remain excluded. Existing program/catalog/auth functionality is regression-checked, not redesigned.
- **Unambiguous steps:** Each task names exact files, public/helper signatures, test names/assertions, red/green commands and an explicit staging/commit boundary. Passing regression tests are not misrepresented as necessarily red; concrete defect tests provide each relevant red gate. No planner implementation or commit was performed.
- **Type/signature consistency:** Worker template token/cache prefix/build helper agree; import reuses the existing 5 MiB constant and HTTP 400 code; `dismissible` is optional/default-true; Task 4 fixture uses generated `CoachPublic` and explicit `Record<string, string>` headers; runner uses JSDoc in `.mjs`, not a new TS runtime.
- **Review focus:** All five listed failure classes have named owning-task tests, including upgrade simulation, malformed input, partial failure, cross-gym preservation and failed-run cleanup/mobile repetition.
- **Proportion:** Five independently testable commits, no migration/new dependency or broad subsystem replacement. Task 3's backend tests pin current safety; Task 4 centralizes test setup rather than adding product code. New defects outside the named files/behavior are escalation points, not open-ended implementation instructions.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-24-release-readiness.md`. Please review the plan. Does it capture what you want?

Execution is already assigned to **DeepSeek V4.1 Flash in the parent session**. Preserve that method; wait for review/confirmation before implementation. Use the required execution skill for the parent's chosen native or subagent-driven workflow; do not start implementation in this planning session.
