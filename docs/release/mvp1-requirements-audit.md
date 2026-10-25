# MVP1 Requirements Audit

**Audit date:** 2026-10-25
**Audited commit:** `fbb9a22` (`feat: persist list state and server-search selectors`)
**Audit type:** Independent release-readiness audit
**Status:** Complete against the tracked acceptance criteria; original v1.6 specification is not present in the repository.

## 1. Baseline and authority

The repository does not contain the original **“approved Gym Management MVP1 v1.6”** document. The tracked authorities used for this audit are:

- `README.md` — product scope, local-only boundary, stack and setup.
- `docs/local-testing.md` — accepted MVP1 walkthroughs and known limits.
- `docs/implementation-progress.md` — Section 14 acceptance criteria and recorded decisions.
- `docs/superpowers/specs/2026-10-25-superuser-club-context-design.md` — global superuser context amendment.
- `docs/superpowers/specs/2026-10-25-global-coaches-athletes-design.md` — global coach/athlete amendment.
- `docs/technical-hardening-audit.md` — accepted risks and deferred production items.

This is a documented audit limitation, not a product defect: the acceptance criteria can be traced and tested, but they cannot be independently reconciled against the missing v1.6 text.

## 2. Method

- Static review of routes, services, models, migrations, frontend routes/pages, tests and operational files.
- Full backend suite: `uv run ruff check app tests`, `uv run mypy app`, `uv run pytest -q`, `uv run pytest -q -m migrations`, `uv run alembic check`.
- Full frontend gates: `bun run lint:check`, `bunx tsc -p tsconfig.build.json --noEmit`, `bun run build`, service-worker unit tests.
- Full Playwright suite on a disposable database, plus production PWA smoke.
- Runtime probes for cross-gym isolation, role enforcement, login/recovery abuse behavior, security headers, DB-failure health behavior and email template escaping.
- No application code or production data was modified.

## 3. Requirement traceability

### 3.1 Section 14 acceptance criteria

| Requirement | Implementation | Independent evidence | Status |
|---|---|---|---|
| 1. Super Admin creates gyms, assigns owners, creates multiple admins; ownership transfer restricted | `backend/app/api/routes/gyms.py` (`create_gym`, `transfer_ownership`, `update_gym`); `frontend/src/pages/GymsPage.tsx`, `GymDetailPage.tsx` | `test_gym_isolation.py::test_ownership_transfer_permissions`, `::test_owner_without_explicit_role_has_implicit_admin_and_loses_it_after_transfer`; Playwright `admin.spec.ts` owner/settings journeys; superuser journey | PASS |
| 2. One account can hold different roles in several gyms; active gym changes data and no cross-gym leak | `backend/app/api/deps.py` (`get_gym_context`), all gym-scoped routes; `frontend/src/auth.tsx` | `test_gym_isolation.py::test_gym_and_coach_data_are_isolated`; `test_auth_onboarding.py::test_athlete_can_belong_to_two_gyms_with_independent_profiles`; Playwright `admin.spec.ts` gym/role switching | PASS |
| 3. Coach sees/manages only assigned athletes in the active gym | `get_athlete_access`, coach-assignment scoping in athlete/program routes | `test_gym_isolation.py::test_gym_and_coach_data_are_isolated` (list and cross-gym 404); `test_programs.py` reassignment tests | PASS |
| 4. Reassignment preserves history, moves access, new coach can use old programs | `athletes.py::reassign_coach`, `programs.py`, `CoachAssignment` history | `test_programs.py::test_coach_reassignment_preserves_history_and_moves_access`; `test_athlete_lifecycle.py::test_archive_restore_cuts_off_and_restores_coach_access_without_duplicate_assignment` | PASS |
| 5. Authorized coach creation/invitation; athlete invite and initial-password activation; bootstrap Super Admin login | `membership.py::activate_user`, `login.py::accept_invitation`, `initial_data.py` | `test_auth_onboarding.py` invitation/initial-password/first-login tests; bootstrap account login probe returned 200 and `is_superuser=true` | PASS |
| 6. Athlete profile completion, body-file authorization, private coach note never exposed | `athletes.py`, `services/storage.py`, response models (`AthleteSelfDetail` excludes note) | `test_privacy_files.py::test_private_coach_note_is_never_exposed_to_athlete`, `::test_body_analysis_file_is_private_and_validated`, `::test_body_analysis_files_are_scoped_to_the_requesting_gym` | PASS |
| 7. Global/custom exercises and reusable templates with independent copies | `exercises.py`, `exercise_categories.py`, `templates.py`, `services/programs.py` | `test_exercises.py::test_custom_exercise_is_gym_scoped`; `test_exercise_categories.py`; `test_programs.py::test_versioning_editable_active_and_templates`; Playwright `categories.spec.ts` | PASS |
| 8. Each set has independent reps/weight/rest/duration/note targets | `models.py` (`WorkoutSet`, `SetInput`), program editor/print | Backend set validation + `test_programs.py`; Playwright `program-authoring.spec.ts`, `athlete.spec.ts` | PASS |
| 9. Multi-gym independent profiles/programs; one active program per athlete/gym; history retained | `WorkoutProgram` unique constraint, partial unique ACTIVE index, version lifecycle | `test_programs.py`, `test_program_concurrency.py`, `test_auth_onboarding.py` multi-gym test | PASS |
| 10. Athlete views program/archive and prints Persian A4 PDF | `MyProgramPage.tsx`, `MyProgramDetailPage.tsx`, `PrintPage.tsx` | Playwright `athlete.spec.ts::athlete sees active program, sets and can generate a Persian PDF` (asserts PDF header/content) | PASS |
| 11. Responsive PWA on desktop/emulated mobile; backend permissions tested | `AppShell`, M3 responsive CSS, `manifest.webmanifest`, `sw.js`; API access tests | Full Playwright desktop + Pixel 5 projects (69 passed, 1 skipped); production PWA smoke 2 passed; `test_gym_isolation.py` | PASS |
| 12. Persian/RTL default, Jalali display, ISO storage, locale switch, M3 only | `i18n.tsx`, `DateField`, M3 components, RTL CSS | Playwright `admin.spec.ts` language switch; `controls.spec.ts` Jalali/leap-year/LTR; `field-labels.spec.ts`; build has no shadcn/Tailwind UI layer | PASS |

### 3.2 Feature/workflow traceability

| Workflow | Implementation | Evidence | Status |
|---|---|---|---|
| Global Super Admin administration | `superuser_coaches.py`, `superuser_athletes.py`; global pages; `CurrentSuperuser` | 14 superuser Playwright tests; superuser API tests; non-superuser 403 runtime probe | PASS |
| Club creation/management/ownership | `gyms.py`; `GymsPage`, `GymDetailPage` | Backend ownership tests; Playwright admin owner/settings journeys | PASS |
| Multiple gym admins | `members.py` role editing; `gyms.py` membership routes | `test_members.py`; ownership/admin tests; Playwright team page | PASS |
| Coach onboarding/management | `members.py`, `superuser_coaches.py`, membership lifecycle | Coach invite/phone tests; superuser coach tests; Playwright global coach CRUD | PASS |
| Athlete onboarding/management | `athletes.py`, `services/athlete_lifecycle.py`, import | Lifecycle/import/privacy tests; Playwright create/archive/restore/delete/import | PASS |
| Multi-club memberships | `GymMembership` unique `(user, gym)`, owner/staff preservation logic | `test_gym_isolation.py`; `test_auth_onboarding.py` multi-gym; `test_athlete_lifecycle.py` cross-gym preservation | PASS |
| RBAC and isolation | `deps.py`, route dependencies, `get_athlete_access`, superuser dependencies | Isolation, privacy, superuser 403 and cross-gym 404 runtime probes | PASS |
| Profiles/intake/body files | `athletes.py`, `storage.py`, `AthleteProfile` models | Privacy/file tests including magic bytes, size, cross-gym and transaction failure | PASS |
| Exercise catalog/categories | `exercises.py`, `exercise_categories.py` | Catalog permission/isolation/snapshot tests; Playwright categories journey | PASS |
| Program authoring/per-set targets | `programs.py`, `services/programs.py`, editor | Program tests, concurrency tests, Playwright program-authoring | PASS |
| Templates | `templates.py`, `ProgramTemplate` JSON snapshot | Template tests; Playwright template/categories flows | PASS |
| Assignment/activation/history/archive | `CoachAssignment`, `WorkoutProgramVersion`, lifecycle services | Reassignment, publish/archive/history tests; Playwright archive/restore | PASS |
| Athlete program/print | `MyProgram*`, `PrintPage` | Athlete Playwright journey + PDF output assertions | PASS |
| Search/filter/pagination/URL state | Server pagination endpoints; `Pagination.tsx`; `list-search.ts` | Backend pagination suite; Playwright pagination/URL/Back/async picker tests | PASS |
| Global and club management UIs | Superuser pages; club pages under `/gyms/:gymId/...` | Superuser project 14/14; full Playwright suite | PASS |
| Auth/recovery/session | `login.py`, `security.py`, token versioning, `auth.tsx` | Auth/token/reset tests; login/recovery runtime probes. Logout remains client-only (accepted local risk). | PASS within local scope |
| PWA/RTL/Jalali/responsive | `sw.js`, manifest, M3, i18n, DateField | Production PWA smoke 2/2; mobile projects; controls/locale tests | PASS |

### 3.3 Correctly excluded features

No attendance, workout-performance logging, analytics, chat, nutrition, payments, AI generation, native apps, public hosting, real email provider or cloud storage were treated as MVP1 obligations. They remain excluded.

## 4. Incomplete, partial and unverified items

| Item | Classification | Evidence / impact |
|---|---|---|
| Original approved MVP1 v1.6 document | **UNVERIFIED / documentation gap** | Not present in the repository; only the Section 14 checklist and feature design docs are available. Traceability is therefore against the tracked acceptance criteria. |
| Production deployment controls (TLS, backups, monitoring, rate limiting, CSP) | **PARTIAL / out of local scope** | README explicitly limits MVP1 to local development/manual acceptance. These are release blockers for pilot/production, not defects in the approved local MVP. |
| Client-side logout | **ACCEPTED LIMITATION** | `auth.tsx` clears local token; no server revocation. Token remains valid until expiry. Documented in hardening audit. |
| Permanent deletion of program versions in any status | **ACCEPTED BUSINESS DECISION** | Explicit decision dated 2026-10-25; test `test_programs.py::test_staff_can_delete_program_versions_in_any_status` pins it. |
| Production PWA worker test | **PASS in this audit** | Run with `PWA_PROD=1 --no-deps` against the built app served by FastAPI: 2/2 passed. |
| Operational backup/restore proof | **NOT VERIFIED** | No `pg_dump`/restore procedure or restoration test exists; deferred as HARD-05. |
| Production-mode configuration | **PARTIAL / defect** | `FASTAPI_ENV=production` is rejected by the settings literal; see security/ops report H-4. |

## 5. Functional verdict

**Feature Completeness: COMPLETE against the tracked MVP1 acceptance criteria.**

No missing or broken approved local feature was found. The only completeness caveat is that the original v1.6 text is absent, so the audit cannot prove that every original wording-level requirement survived into the repository. The recorded Section 14 criteria, amendments and excluded scope are fully represented and independently exercised.
