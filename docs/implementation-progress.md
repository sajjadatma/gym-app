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
- [x] Draft/active/archived lifecycle, immutable versions, one active program per athlete/gym.
- [x] Reusable templates with independent copies.
- [x] Persian RTL Material Design 3 UI, Jalali presentation, locale switch (fa/en), A4 print/PDF.
- [x] Responsive PWA manifest, icons and service worker; local production serving with SPA fallback.
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
  Evidence: `test_custom_exercise_is_gym_scoped`; `test_versioning_immutable_active_and_templates`; Playwright template/exercise pages.
- [x] **8. Each set has independent reps/weight/rest/duration/note.**
  Evidence: program payload and version tests; program builder; print PDF fixture.
- [x] **9. Athlete belongs to multiple gyms with independent profiles/programs; max one active program per athlete/gym; version history retained.**
  Evidence: multi-gym backend test; versioning/active tests; demo multi-athlete.
- [x] **10. Athlete views program/archive and prints Persian A4 PDF.**
  Evidence: Playwright `athlete sees active program, sets and can generate a Persian PDF`; PDF header check plus rendered PDF inspection.
- [x] **11. Responsive PWA works on desktop and emulated mobile; backend permissions tested.**
  Evidence: Playwright desktop + Pixel 5 projects; production `PWA_PROD=1` service-worker registration check; backend access-control suite.
- [x] **12. Persian/RTL default, Jalali display, ISO/Gregorian storage, translation resources, locale switch adjusts direction/formatting, Material Design 3 only.**
  Evidence: all visible strings in `src/i18n.tsx`; `DateField` Jalali picker; Playwright language switch (`dir=ltr`/`rtl`); Material 3 component layer (`src/components/M3.tsx`, `src/index.css`); no shadcn/Tailwind UI dependencies.

## Runtime decisions (documented assumptions)

- Local PostgreSQL 17 and Homebrew Mailpit are used instead of starting Docker Desktop. The approved Docker Compose files remain in the repository for environments where Docker is used.
- Athlete body measurements are stored on the gym-scoped `AthleteProfile` (latest values) rather than a separate measurement-history table; the profile still records the update timestamp. This is the simplest adequate model for MVP1.
- Custom exercises are shared with authorized staff of their own gym (not visible to other gyms); this keeps new coaches able to work with prior programs that use them.
- Template content is stored as a validated JSON snapshot; applying a template deep-copies it into normalized immutable program-version rows.
- PDF output uses the browser's A4 print-to-PDF flow. No server PDF renderer or font pipeline was added.
- Invitation tokens are purpose-bound JWTs; raw tokens are never logged or returned by the API.
- The local Super Admin password is generated/stored only in the Git-ignored `.env`. The tracked example file contains a placeholder; all tests use fake test credentials.

## Verification commands and latest results

Run from the repository root unless noted.

```sh
cd backend
uv run pytest -q
# 16 passed

cd ../frontend
bunx playwright test
# 16 passed (desktop + Pixel 5 + auth/PWA/manifest)

bun run build
PLAYWRIGHT_BASE_URL=http://localhost:8000 PWA_PROD=1 bunx playwright test
# 16 passed, including service-worker registration

cd ../backend
uv run alembic check
# No new upgrade operations detected

uv run python scripts/verify_superadmin_login.py
# Super Admin login: OK; Global superuser: OK

CONFIRM_RESET_GYM_APP=YES SEED_DEMO_DATA=YES bash scripts/reset_dev_db.sh
# reset -> migrations -> idempotent seed -> demo seed OK
```

The real Super Admin password and invitation tokens are deliberately absent from this document and all tracked files.

## Security review checklist

- [x] Gym-scoped queries validate `X-Gym-ID` against active membership on the server.
- [x] Coach access depends on the current `CoachAssignment`; ended assignments lose access.
- [x] Ownership transfer requires current owner or global Super Admin.
- [x] Only one current coach assignment and one active program version are enforced by partial unique indexes.
- [x] Published/archived versions are read-only through the API; new versions copy content.
- [x] Athlete responses never include `internal_coach_note`; print data does not include it either.
- [x] Body-analysis files are outside static serving and permission-checked on every download; magic bytes, MIME/extension and 10 MB cap validated.
- [x] Invitation/reset tokens are expiring, purpose-bound JWTs; used invitation tokens cannot be replayed.
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
