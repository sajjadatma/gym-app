# MVP1 implementation progress

Specification: approved Gym Management MVP1 v1.6 (local development and manual acceptance only).
This checklist is keyed to section 14 acceptance criteria. Stale claims must be re-verified against code/tests before reporting completion.

## Slice checkpoints

- [x] Approved FastAPI template copied into `sajjadatma/gym-app`; stack and conventions retained.
- [x] Local PostgreSQL, Mailpit, environment separation and Git-ignored secrets.
- [x] Alembic migration for gym-scoped identity, ownership, memberships/roles, coach assignments, athlete profiles/files, exercises, programs/versions/days/exercises/sets, templates.
- [x] Idempotent bootstrap: global Super Admin, 54 global exercises.
- [x] Authentication: email login, forced first-password change, password recovery, invitation activation; no public registration.
- [x] Super Admin gym creation, owner assignment, multiple admins/coaches, ownership transfer; owner implicit admin.
- [x] Athlete profiles, field-authorization, private coach note, body-analysis upload/download.
- [x] Coach assignment history and reassignment access cutover.
- [x] Exercise library and gym custom exercises.
- [x] Program builder with per-set reps/weight/intensity/rest/duration/note.
- [x] Draft/active/archived lifecycle, editable active versions, archived history, one active program per athlete/gym.
- [x] Reusable templates with independent copies.
- [x] Persian RTL Material Design 3 UI, Jalali presentation, locale switch (fa/en), A4 print/PDF.
- [x] Responsive PWA manifest, icons and service worker; local production serving with SPA fallback.
- [x] Production-quality Material 3 Select, searchable ComboBox and Persian/Gregorian React Aria DatePicker controls.
- [x] Owner/admin-only category and exercise management; categorized program/template days with athlete/print labels and preserved historical snapshots.
- [x] Automated backend tests and Playwright tests (desktop + emulated mobile + production PWA).
- [x] Local reset/bootstrap/verification scripts and documentation.

## Section 14 acceptance criteria

- [x] **1. Super Admin creates multiple gyms, assigns owners and multiple admins; only current owner or Super Admin transfers ownership.**
  Evidence: backend gym/ownership tests; UI gym detail transfer; Super Admin bootstrap script; manual owner transfer flow.
- [x] **2. One account can be Owner+Coach in A, Coach in B and Admin in C; active gym changes access and data never leaks across gyms.**
  Evidence: seed `ali@example.com`; backend multi-gym isolation tests; Playwright gym/role switching.
- [x] **3. Coach sees/manages only athletes assigned in the active gym.**
  Evidence: `test_gym_and_coach_data_are_isolated`; coach list/direct-URL checks.
- [x] **4. Admin/Super Admin reassigns athlete; history remains; new coach can open old programs and create a new version; old coach loses access.**
  Evidence: `test_coach_reassignment_preserves_history_and_moves_access`.
- [x] **5. Coach registration only by authorized creation/invitation; athlete activation works with invite and initial-password methods; Super Admin local account created after secure reset and login tested.**
  Evidence: invitation/initial-password backend tests; real Mailpit invite check; reset script guard + reset run; `verify_superadmin_login.py` OK.
- [x] **6. Athlete profile completion and body-analysis upload authorization; private coach note never exposed to athlete/API/print.**
  Evidence: `test_private_coach_note_is_never_exposed_to_athlete`; `test_body_analysis_file_is_private_and_validated`; Playwright athlete print test.
- [x] **7. Global/custom exercises and athlete-independent templates with independent editable copies.**
  Evidence: `test_custom_exercise_is_gym_scoped`; `test_versioning_editable_active_and_templates`; Playwright template/exercise pages.
- [x] **8. Each set has independent reps/weight/rest/duration/note.**
  Evidence: program payload and version tests; program builder; print PDF fixture.
- [x] **9. Athlete belongs to multiple gyms with independent profiles/programs; max one active program per athlete/gym; version history retained.**
  Evidence: multi-gym backend test; versioning/active tests; demo multi-athlete.
- [x] **10. Athlete views program/archive and prints Persian A4 PDF.**
  Evidence: Playwright `athlete sees active program, sets and can generate a Persian PDF`; PDF header check plus rendered PDF inspection.
- [x] **11. Responsive PWA works on desktop and emulated mobile; backend permissions tested.**
  Evidence: Playwright desktop + Pixel 5 projects; production `PWA_PROD=1` service-worker registration check; backend access-control suite.
- [x] **12. Persian/RTL default, Jalali display, ISO/Gregorian storage, translation resources, locale switch adjusts direction/formatting, Material Design 3 only.**
  Evidence: all visible strings in `src/i18n.tsx`; React Aria + `@internationalized/date` Jalali/Gregorian DatePicker, Select and searchable ComboBox; Playwright language switch (`dir=ltr`/`rtl`), ISO round-trip and leap-year tests; Material 3 component layer (`src/components/M3.tsx`, `src/index.css`); no shadcn/Tailwind UI dependencies.

## Runtime decisions (documented assumptions)

- Local PostgreSQL 17 and Homebrew Mailpit are used instead of starting Docker Desktop. The approved Docker Compose files remain in the repository for environments where Docker is used.
- Athlete body measurements are stored on the gym-scoped `AthleteProfile` (latest values) rather than a separate measurement-history table; the profile still records the update timestamp. This is the simplest adequate model for MVP1.
- Categories and custom exercises are created by gym owners/admins; coaches have read-only catalog access. New movements require a category ID. Days store multiple category IDs and saved category names. Legacy mixed days remain supported.
- Custom exercises are shared with authorized staff of their own gym (not visible to other gyms); this keeps new coaches able to work with prior programs that use them.
- Template content is stored as a validated JSON snapshot; applying a template deep-copies it into normalized program-version rows.
- PDF output uses the browser's A4 print-to-PDF flow. No server PDF renderer or font pipeline was added.
- Invitation tokens are purpose-bound JWTs; raw tokens are never logged or returned by the API.
- Access tokens and password-reset tokens carry a per-user `token_version`. A successful password change or reset increments it atomically, so previously issued access tokens and reset links stop working. Reset tokens are single-use (including concurrent redemption); after changing your own password, the client returns to the login page to obtain a fresh token.
- Browser sessions use HttpOnly/SameSite cookies plus double-submit CSRF; Bearer tokens remain for API clients and tests. Server logout increments `token_version`, revoking existing sessions.
- Login/recovery/reset/invitation endpoints are rate-limited server-side (in-process, per worker) and return `429` with `Retry-After`.
- The local Super Admin password is generated/stored only in the Git-ignored `.env`. The tracked example file contains a placeholder; all tests use fake test credentials.

## Verification commands and latest results

Run from the repository root unless noted.

Latest verified 2026-10-25 by the production-hardening pass, against a disposable database (`:8001` backend, `:5174` Vite):

```sh
cd backend
uv run ruff check app tests
# All checks passed

uv run mypy app
# Success: no issues found in 40 source files

uv run pytest -q
# 124 passed

uv run pytest -q -m migrations
# 4 passed, 120 deselected

uv run alembic check
# No new upgrade operations detected

cd ../frontend
bun run lint:check
bunx tsc -p tsconfig.build.json --noEmit
bun run build
node --test tests-unit/*.test.mjs
# lint/type/build pass; 6 unit tests pass

VITE_API_URL=http://localhost:8001 \
PLAYWRIGHT_BASE_URL=http://localhost:5174 \
PLAYWRIGHT_API_URL=http://localhost:8001 \
PLAYWRIGHT_SUPERUSER_EMAIL=... PLAYWRIGHT_SUPERUSER_PASSWORD=... \
bunx playwright test
# 69 passed, 1 skipped (70 total)
# The skip is the PWA_PROD-gated service-worker test.

PWA_PROD=1 PLAYWRIGHT_BASE_URL=http://localhost:8001 \
PLAYWRIGHT_API_URL=http://localhost:8001 VITE_API_URL=http://localhost:8001 \
bunx playwright test tests/pwa.spec.ts --project=chromium --no-deps
# 2 passed

cd backend
CONFIRM_RESET_GYM_APP=YES SEED_DEMO_DATA=YES bash scripts/reset_dev_db.sh
# reset -> migrations -> idempotent seed -> demo seed OK
```

Release hardening evidence, including the isolated backup/restore drill, is in `docs/release/production-hardening-results.md`.

Playwright status: full desktop + emulated Pixel 5 suite is green locally (69 passed; 1 skipped — the production-only PWA service-worker test, covered by the separate `PWA_PROD=1` run). CI also runs 25 critical journeys and 2 PWA smoke tests against the built Docker image. Docker image build/startup, migrations, restart persistence, concurrent-start migration locking, config failure, runtime rate limiting and backup/restore are now **VERIFIED IN CI** (run `40210663931`). Traefik/ACME/public TLS and real SMTP delivery remain **NOT VERIFIED** until a real host/domain and provider credentials are supplied.

The real Super Admin password and invitation tokens are deliberately absent from this document and all tracked files.

## Security review checklist

- [x] Gym-scoped queries validate `X-Gym-ID` against active membership on the server.
- [x] Coach access depends on the current `CoachAssignment`; ended assignments lose access.
- [x] Ownership transfer requires current owner or global Super Admin.
- [x] Only one current coach assignment and one active program version are enforced by partial unique indexes.
- [x] Active versions can be edited through the API; archived versions are read-only and can be copied into new drafts.
- [x] Athlete responses never include `internal_coach_note`; print data does not include it either.
- [x] Body-analysis files are outside static serving and permission-checked on every download; magic bytes, MIME/extension and 10 MB cap validated.
- [x] Invitation/reset tokens are expiring, purpose-bound JWTs; used invitation and reset tokens cannot be replayed.
- [x] Password change/reset invalidates all older access tokens and reset links; stale bearer tokens receive `401 invalid_credentials`.
- [x] Initial passwords force a password change before other protected API use.
- [x] No public signup or free coach registration route.
- [x] Test database guard prevents tests from wiping the development database.
- [x] Reset script refuses unconfirmed/unknown databases.
- [x] `.env`, uploads and Playwright auth state are Git-ignored.

## Known limitations / non-goals

- Local-only; no deployment, hosting, TLS, real email provider, cloud storage or public CI.
- No attendance, actual workout performance logging, progress analytics, chat, nutrition, payments, AI generation or native app (approved scope exclusions).
- PWA is minimal: app-shell/offline navigation cache only; no offline data synchronization.
- Physical iPhone testing is not required or performed; desktop and emulated mobile viewports are used as approved.

### Program authoring updates — 2026-10-22

- Active programs support in-place edits by authorized staff while preserving active status and publication time. Empty active structures are rejected atomically. Archived programs remain read-only.
- New-program dialogs reset title, goal and dates each time they open. Editor state is scoped to the selected version and background refetches preserve unsaved edits.
- Workout days support several categories with visible checkbox chips, combined movement filtering, day navigation and exercise/set counts. Removing a used category requires first moving/removing its movements. Athlete and print views show all selected categories.
- Category snapshots survive templates and copies; singular category payloads remain compatible. Migration c9324e715a60 preserves existing day selections.

### Superuser global context — 2026-10-25

- A superuser no longer auto-binds to the first club at login: `/` shows a global dashboard (club cards with an "enter gym" action) and the top bar shows no club name or mode chip. Every fresh login returns there.
- Entering a club uses the real workspace route `/gyms/:gymId`; reloading keeps that club context. Club settings live at `/gyms/:gymId/settings`.
- "All clubs" in the club switcher clears the active club and returns to the global dashboard.
- Owners, coaches and athletes keep today's behavior, routes and headers; inner club pages still rely on active-club state.
- Superuser Playwright coverage is gated on `PLAYWRIGHT_SUPERUSER_EMAIL`/`PLAYWRIGHT_SUPERUSER_PASSWORD` and documented in the README; it uses a disposable database, never `gym_app`.

### Club-scoped routes — 2026-10-25

- All club pages now live under `/gyms/:gymId/...`: dashboard, athletes (list/archived/detail), members, exercise library, templates (list/new/edit), program editor, athlete self pages (`/my`, `/my/profile`, `/my/programs/:versionId`) and club settings. The URL, not localStorage alone, identifies the active club.
- Club links in the dashboard, lists, editors, tabs and sidebar all carry `gymId`. Switching clubs navigates directly to the target club workspace.
- Legacy root URLs (`/athletes`, `/members`, `/exercises`, `/templates`, `/my`, `/programs/:id/edit`, …) redirect into the active club's scoped route, or to `/gyms` when no club is active.
- Route-level role guards: staff sections redirect athletes to the club dashboard; `/members` requires admin; athlete self pages redirect non-athletes. The guards use the union of the user's club roles, matching backend authorization.
- Non-superusers landing on `/` are redirected to their active club workspace; the `/` route is the superuser global dashboard only when no club is active.
- Print preview remains at `/print/:versionId` and uses the active club context from the same browser session.
- Superusers inside a club no longer see the global clubs item in the sidebar; the app header offers a «داشبورد سراسری» action on every club page, and «همه باشگاه‌ها» remains in the club switcher for leaving from any club page.

### Global coach and athlete management — 2026-10-25

- Superusers in global mode get **مربیان** (`/coaches`) and **ورزشکاران** (`/athletes`) pages listing people across all clubs with club name, email, phone, status, and assigned coach (athletes). Both disappear inside a club and redirect to the club pages.
- Coaches are club memberships: one row per coach per club. Create requires a club and a phone; existing accounts are reused and a non-empty account phone is never overwritten. `User.phone` is optional at the database level (migration `f0a1b2c3d4e5`) and editable from the profile.
- Coach **archive** deactivates the membership only when it carries just the COACH role and is not the owner, the acting superuser, or linked to an athlete profile. Archive and delete end that club's active coach assignments in the same transaction; assignment history is preserved and restore does not recreate assignments.
- Coach **delete** removes only the COACH role from that club, deleting the membership only when nothing else remains; accounts, other roles, other clubs, athletes, and workout history are preserved.
- Athlete actions are club-scoped and reuse the existing lifecycle rules (archive/restore/delete, extra roles preserved, account retained for other clubs). Global athlete creation still requires an active coach; the dialog disables creation when the club has none.
- Backend exposes superuser-only `/api/v1/superuser/coaches` and `/api/v1/superuser/athletes` endpoints with explicit club ids; non-superusers receive 403 independently of the UI.

### Global people pages aligned with the gym pattern — 2026-10-25

- `/coaches` and `/athletes` now use the same list language as the gym-scoped athletes page: active/archived tabs, deferred search with a clear action, club filter, result-count chip, persisted card/table view toggle, structured loading/empty/error states, and card/table layouts built from the existing M3 classes.
- Global tables use the shared `m3-data-table` identity cells, status badges, and row actions; cards show avatar, club, coach/phone metadata and the same actions.
- Global athlete destructive delete is available only on archived rows, matching the gym workflow (active rows offer archive; archived rows offer restore and delete). Coach delete remains available on active rows because multi-role/protected coaches cannot be archived.
- Intentional contextual differences preserved: the global pages keep a required club filter and club column; bulk selection/import, athlete detail navigation and active-program badges remain club-scoped.

### Independent review outcomes — 2026-10-25

- Coach removal wording now distinguishes removing a role from deleting an account: the action and confirmation say **حذف از باشگاه / Remove from club**, the confirmation states that active athlete assignments in that club end, that the action is irreversible, and that the account, other roles, other clubs and history are preserved. The success toast is specific to the coach removal.
- Global coach-list rows are now assembled from one batched role lookup per page instead of one lookup per row.

### Server-side list pagination — 2026-10-25

- Gym athletes (cards/table), archived athletes, members, global athletes and global coaches paginate on the server with validated `offset`/`limit` (default 10, maximum 50), 10/25/50 page sizes, previous/next controls, current-page status, and automatic reset when search, club filter or active/archived tab changes.
- `count` in every list response is the total number of authorized matching rows, not the page length. The client derives the page count from it; an out-of-range page after archiving or deleting clamps back to the last valid page.
- Authorization, search, club isolation, coach assignment scope, archive status and staff-only membership filtering run in SQL before counting and slicing. Gym athletes accepts `is_archived`, `assigned_to_me`; members accepts `staff_only`; global lists accept `is_archived` / `is_active`. Existing `include_archived` behavior is preserved for compatibility.
- Ordering has a unique tie-breaker (`user_id`, `membership_id`, `GymMembership.id`) so rows cannot move between pages when sort values tie. Offset paging still shifts boundaries if records are inserted or deleted concurrently; it is not a snapshot.
- Per-row lookups on the page were batched: athlete summaries fetch assignments, coach names and active program versions for the whole page; member and coach roles are fetched with one grouped query. A test counts SELECT statements for `limit=1` and a full page and requires them to match.
- Select-all means **the current page** and the confirmation count includes selections made on other pages. Selecting individual rows across pages is retained; moving the search/filter/tab clears the selection.
- List state is URL-backed: `page`, `size`, `q`, `club` and `tab` are validated and stripped from links when they hold their defaults. Refresh, shared links and Back/Forward restore the list; malformed values fall back safely.
- Older rows are marked as updating and cannot be selected or mutated until the requested page arrives. The pager reports the range of the rows actually on screen, not the page still loading, and clamps after out-of-range mutations with a replaced history entry.
- Selector data sources use server search with a bounded first page, debounced input, loading/empty/error/retry states, stale-selection blocking and keyboard-accessible **Load more**. This covers the template athlete picker, the superuser coach picker and the per-club coach pickers; the per-club coach endpoint is now paginated and searchable too. The import dialog's optional default-coach list is capped at 50 with an explicit hint when more coaches exist.
- Tables that are not list views (athlete-import preview, program structure editor, print sheet) are intentionally not paginated.
- Playwright tests that select athletes by name search first; tests pin paging, page-size changes, server `count`, page resets, URL restore/Back, async picker search/load-more, and the page-only select-all label.

### Pagination performance measurement — 2026-10-25

- Measured on a disposable 50,000-athlete database distributed across 100 clubs. Per-club athlete page 1 took ~3.7 ms, a deep offset (~400) ~2.2 ms, and the matching count ~2.3 ms. PostgreSQL used the existing `ix_athlete_profile_gym_id` and `ix_gym_membership_gym_id` indexes; trial composite indexes were not selected by the planner and were not added, so no migration was needed.
- Global lists still sort the joined result set before slicing (about 33 ms at 50k rows). Supporting that ordering with an index would require denormalising gym/user names; it remains an accepted local-MVP limit.
- Offset paging remains live rather than snapshot-based; concurrent inserts/deletes can shift boundaries. Mutation invalidation and page clamping keep the UI consistent.
