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
- The local Super Admin password is generated/stored only in the Git-ignored `.env`. The tracked example file contains a placeholder; all tests use fake test credentials.

## Verification commands and latest results

Run from the repository root unless noted.

Latest verified 2026-10-25 against the local dev servers (`:8000` backend, `:5173` Vite):

```sh
cd backend
uv run pytest -q
# 93 passed

uv run pytest -q -m migrations
# 4 passed, 89 deselected

uv run alembic check
# No new upgrade operations detected

uv run python scripts/verify_superadmin_login.py
# Super Admin login: OK; Global superuser: OK

cd ../frontend
bunx playwright test
# 67 total: 54 passed, 13 skipped
# Skipped: 12 superuser-journey tests without PLAYWRIGHT_SUPERUSER_* credentials
# and the production-service-worker-only test (tests/pwa.spec.ts:46-49),
# gated by PWA_PROD=1; not failures.

bun run build
PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test tests/pwa.spec.ts
# 3 passed (admin-setup dependency + manifest/install + production service-worker
# registration and offline shell), including the test skipped above.

cd ../backend
CONFIRM_RESET_GYM_APP=YES SEED_DEMO_DATA=YES bash scripts/reset_dev_db.sh
# reset -> migrations -> idempotent seed -> demo seed OK
```

Playwright status: full desktop + emulated Pixel 5 suite is green (54 passed; 13 skipped — 12 superuser tests without `PLAYWRIGHT_SUPERUSER_*` credentials and 1 production-only PWA skip); the superuser project is green (12 passed) against a disposable database on `:8001`/`:5174`; the production PWA subset is also green when run against the built app at `:8000` with `PWA_PROD=1`. No Playwright failures are known.

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
