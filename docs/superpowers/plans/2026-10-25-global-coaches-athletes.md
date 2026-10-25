# Global Coaches and Athletes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add superuser-only global coach and athlete pages with cross-club lists, creation, and club-scoped archive/restore/delete.

**Architecture:** Add a nullable account phone, superuser-only `/api/v1/superuser` endpoints with explicit club ids, and two global frontend pages. Athlete lifecycle logic is extracted from the existing gym-scoped routes into a service reused by both route families; coach actions are new membership-scoped service logic. All mutations run in one transaction and are scoped to the selected club.

**Tech Stack:** Python 3.14, FastAPI, SQLModel, PostgreSQL, Alembic, Pytest; React 19, TypeScript, TanStack Router/Query, Vite, Playwright, Biome.

**Spec:** `docs/superpowers/specs/2026-10-25-global-coaches-athletes-design.md`

## Global Constraints

- Club-scoped isolation: every coach/athlete mutation names its club; operations in one club never touch another club.
- Coach archive is allowed only for coach-only memberships (not owner, not acting superuser, no athlete profile, roles == {COACH}).
- Coach/athlete archive and delete end active `CoachAssignment` rows in the same transaction and preserve rows with `ended_at` (history).
- Coach delete removes only the `COACH` role; it deletes the membership only when no roles remain, the user is not the owner, and no athlete profile exists. User accounts are never deleted.
- Athlete phone stays `AthleteProfile.phone`; `User.phone` is the account/coach phone and never overwrites a non-empty value.
- Athlete creation still requires an active coach (`coach_required`).
- Backend authorization is independent of the frontend: every new endpoint uses `CurrentSuperuser`.
- No new dependencies; reuse existing M3 components, services, helpers and error codes.

## Review Focus

- **Owner who is also a coach:** deleting the coach role must leave ownership/admin access intact; archiving must be rejected.
- **Coach in two clubs:** archiving/deleting in one club leaves the other club's membership, roles, assignments and permissions untouched.
- **Coach with an athlete profile or GYM_ADMIN role:** archive hidden/rejected; delete removes only COACH.
- **Athlete lifecycle with extra roles:** archive/delete must not remove GYM_ADMIN/COACH or memberships needed in other clubs.
- **Existing account reuse:** creating a coach for an existing email reuses the user and never overwrites a non-empty phone or duplicates memberships.
- **Archived coach assignments:** after archive/restore, athletes show no stale active coach; history rows remain.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models.py` | `User.phone`; superuser coach/athlete schemas; member phone |
| `backend/app/alembic/versions/*_add_user_phone.py` | nullable `user.phone` |
| `backend/app/services/membership.py` | activation accepts phone (fill-only) + coach assignment termination helper |
| `backend/app/services/athlete_lifecycle.py` (new) | shared create/archive/restore/delete athlete logic |
| `backend/app/api/routes/athletes.py` | delegates lifecycle to the service |
| `backend/app/api/routes/superuser_coaches.py` (new) | coach list/create/archive/restore/delete |
| `backend/app/api/routes/superuser_athletes.py` (new) | athlete list/create/archive/restore/delete |
| `backend/app/api/main.py` | register the two routers |
| `backend/tests/api/routes/test_superuser_coaches.py` (new) | coach API regressions |
| `backend/tests/api/routes/test_superuser_athletes.py` (new) | athlete API regressions |
| `backend/tests/utils/helpers.py`, `test_members.py` | phone fixture + validation |
| `frontend/src/client/*` | regenerated client |
| `frontend/src/pages/SuperuserCoachesPage.tsx` (new) | global coach list + actions |
| `frontend/src/pages/SuperuserAthletesPage.tsx` (new) | global athlete list + actions |
| `frontend/src/routes/_app.coaches.tsx`, `_app.athletes.index.tsx` | global routes + club redirects |
| `frontend/src/components/AppShell.tsx` | global-only nav items |
| `frontend/src/pages/ProfilePage.tsx`, `MembersPage.tsx` | phone field / required coach phone |
| `frontend/src/i18n.tsx` | fa/en strings |
| `frontend/tests/superuser-context.spec.ts` | end-to-end coverage |

---

### Task 1: Account phone and coach phone requirement

**Files:** `backend/app/models.py`, `backend/app/alembic/versions/`, `backend/app/services/membership.py`, `backend/app/api/routes/gyms.py`, `backend/tests/api/routes/test_members.py`, `backend/tests/utils/helpers.py`, `frontend/src/pages/ProfilePage.tsx`, `frontend/src/pages/MembersPage.tsx`, `frontend/src/i18n.tsx`

**Interfaces:**
- Produces: `User.phone: str | None`; `activate_user(..., phone: str | None = None)` fills phone only when the user has none; `MemberCreate.phone: str | None`; coach creation rejects a blank phone with `400 coach_phone_required`.

- [ ] **Step 1: Write failing tests**: coach creation without phone → 400 `coach_phone_required`; with phone → saved on the user; creating a second coach membership for an existing user with a phone keeps the original phone.
- [ ] **Step 2: Run** `cd backend && uv run pytest tests/api/routes/test_members.py -q` → the new cases fail.
- [ ] **Step 3: Add** `User.phone` (max 50), Alembic revision on `d5e6f7a8b9c0` adding a nullable column, `MemberCreate.phone`, validation in `create_member` when `COACH` is in roles, and phone handling in `activate_user`.
- [ ] **Step 4: Add** the phone field to the profile editor (`UserUpdateMe`, `UserMePublic`) and the member dialog (required when coach is selected); add i18n keys.
- [ ] **Step 5: Run** the backend tests, `uv run ruff check app tests`, `uv run mypy app`, and `bun run generate-client`.
- [ ] **Step 6: Commit** `feat: add account phone and require it for coaches`.

---

### Task 2: Superuser coach API

**Files:** `backend/app/models.py`, `backend/app/services/membership.py`, `backend/app/api/routes/superuser_coaches.py` (new), `backend/app/api/main.py`, `backend/tests/api/routes/test_superuser_coaches.py` (new)

**Interfaces:**
- Consumes: `activate_user`, `ensure_membership`, `add_roles`, `get_membership_roles`.
- Produces: `GET/POST /api/v1/superuser/coaches`, `POST /{membership_id}/archive`, `POST /{membership_id}/restore`, `DELETE /{membership_id}`; responses `SuperuserCoachesPublic`, `SuperuserCoachRow`, `SuperuserCoachCreated`, `Message`.

- [ ] **Step 1: Write failing tests**: non-superuser 403; list across two clubs with gym name/phone; phone required; archive ends active assignments and hides the coach from the active list; restore reactivates; delete removes only COACH (admin role kept); multi-club delete leaves the other club intact; owner-coach archive rejected; owner's membership preserved on delete; athlete-profile coach archive rejected; last-membership delete preserves the user account.
- [ ] **Step 2: Run** `uv run pytest tests/api/routes/test_superuser_coaches.py -q` → collection/failures.
- [ ] **Step 3: Implement** schemas and the router. Archive guard: roles == {COACH}, not owner, not acting superuser, no athlete profile. Archive/delete call a helper that ends active assignments (`ended_at`, same transaction). Delete removes the COACH role row, deletes the membership only when no roles/owner/athlete profile. No account deletion.
- [ ] **Step 4: Register the router**; run new tests + `test_members.py` + `test_gym_isolation.py`; ruff/mypy.
- [ ] **Step 5: Commit** `feat: add superuser coach management API`.

---

### Task 3: Superuser athlete API with shared lifecycle

**Files:** `backend/app/services/athlete_lifecycle.py` (new), `backend/app/api/routes/athletes.py`, `backend/app/api/routes/superuser_athletes.py` (new), `backend/app/api/main.py`, `backend/tests/api/routes/test_superuser_athletes.py` (new)

**Interfaces:**
- Produces: `create_athlete_record`, `archive_athlete_record`, `restore_athlete_record`, `delete_athlete_record` used by both routers; superuser endpoints `GET/POST /superuser/athletes`, `POST /{gym_id}/{athlete_user_id}/archive|restore`, `DELETE /{gym_id}/{athlete_user_id}`.

- [ ] **Step 1: Extract** the existing athlete create/archive/restore/delete bodies into `services/athlete_lifecycle.py` **without behavior changes**; make the existing routes delegate. Run the full existing athlete/lifecycle/privacy suites green before adding new endpoints.
- [ ] **Step 2: Write failing tests**: non-superuser 403; cross-club list with gym/coach/phone; create requires coach; archive/restore/delete are club-scoped; deleting in club A leaves the same user's profile/program in club B; extra staff roles are preserved; assignments are ended on archive and history kept.
- [ ] **Step 3: Implement** superuser list/create/actions using the shared service and a `GymContext` for the target club (`is_superuser=True`).
- [ ] **Step 4: Run** new tests + all athlete/program/gym-isolation tests; ruff/mypy.
- [ ] **Step 5: Commit** `feat: add superuser athlete management API`.

---

### Task 4: Global frontend pages

**Files:** client regen; `frontend/src/pages/SuperuserCoachesPage.tsx`, `SuperuserAthletesPage.tsx`, `frontend/src/routes/_app.coaches.tsx`, `_app.athletes.index.tsx`, `AppShell.tsx`, `i18n.tsx`

**Interfaces:**
- Consumes: generated superuser services from Task 1–3.
- Produces: `/coaches` and `/athletes` global pages, visible only for a superuser with no active club.

- [ ] **Step 1: Generate the client** (`bun run generate-client`) and confirm the superuser operations exist.
- [ ] **Step 2: Add routes/nav**: global superuser nav → dashboard, clubs, coaches, athletes. `/coaches` redirects to `/gyms/:id/members` inside a club; `/athletes` keeps the club redirect and renders the global list only for a global superuser. Non-superusers redirect to their home.
- [ ] **Step 3: Build the pages**: search + club filter + archived filter; columns as in the spec; archive/restore/delete with confirmation; create dialogs (club picker, phone required for coaches, coach picker for athletes with disabled empty state); snackbars + error mapping; i18n fa/en.
- [ ] **Step 4: Verify** `bun run lint:check`, `bunx tsc -p tsconfig.build.json --noEmit`, `bun run build`.
- [ ] **Step 5: Commit** `feat: add global coaches and athletes pages`.

---

### Task 5: End-to-end coverage, docs, full regression

**Files:** `frontend/tests/superuser-context.spec.ts`, `README.md` (test setup if needed), `docs/implementation-progress.md`

- [ ] **Step 1: Playwright** superuser journey: nav items present only in global mode; lists show club/phone; create coach (phone required) and athlete; archive/restore/delete; club redirects; a club admin does not see the nav.
- [ ] **Step 2: Run** the superuser project against the disposable DB and the full existing suite against the dev demo.
- [ ] **Step 3: Run** backend full suite, ruff, mypy; frontend lint, typecheck, build, full Playwright.
- [ ] **Step 4: Update docs** (global management behavior, phone rule) and record exact counts.
- [ ] **Step 5: Commit** `docs: document global coach and athlete management`.

## Out of scope

- Coach role editing beyond archive/delete, bulk actions, pagination, CSV export, account deletion, invitation resend, changing athlete-requires-coach.
