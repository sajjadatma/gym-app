# Person Overview Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every athlete and coach a dedicated read-only page showing all stored information and a chronological history, reachable from a Details button in the list tables.

**Architecture:** One `GET /api/v1/people/{user_id}/overview` endpoint returns a single, fully-populated response composed from existing tables. One frontend route renders that response as a longitudinal record. Details buttons on the superuser and club-level athlete/coach tables navigate to it with the focus club and profile kind.

**Tech Stack:** FastAPI, SQLModel, Alembic (no schema change), Pytest, React 19, TanStack Router/Query, TypeScript, Biome.

**Spec:** `docs/superpowers/specs/2026-10-27-person-overview-design.md`

## Global Constraints

- No new database tables or migrations. History is built from timestamps already stored (`created_at`, `updated_at`, `published_at`, `archived_at`, `started_at`, `ended_at`, `measurements_updated_at`).
- Never expose `hashed_password`, `token_version`, `must_change_password`, or stored object keys.
- Superusers may view any club. Club owners and `GYM_ADMIN` members may view only their own club. Coaches and athletes receive `403`.
- A person outside the focus club returns `404`.
- Archived athletes and inactive coach memberships remain viewable to authorized admins.
- Existing routes, filters, pagination, and permissions must not regress.
- Persian and English copy for every new label.
- All long histories stay in the response; no silent truncation.

## Review Focus

- A coach viewing another person's overview must be denied, while a club admin can view a coach and an athlete in their own club.
- A superuser opening an athlete from the global table has no active club; the page and downloads must still work using the row's `gym_id`.
- A person who is both coach and athlete shows the requested kind without losing the other stored data.
- A record with no programs, files, or assignments shows an explicit empty state, not a blank panel.
- Long program structures and histories render without hiding records or breaking the mobile layout.

---

### Task 1: Response models and overview service

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/people.py`
- Test: `backend/tests/api/routes/test_person_overview.py`

**Interfaces:**
- Consumes: `Gym`, `GymMembership`, `GymMembershipRole`, `AthleteProfile`, `CoachAssignment`, `WorkoutProgram`, `WorkoutProgramVersion`, `BodyAnalysisFile`, `User`; `get_membership_roles`; `version_detail`.
- Produces: `PersonOverview`, `PersonAccountPublic`, `PersonMembershipPublic`, `PersonRefPublic`, `PersonAssignmentPublic`, `PersonProgramPublic`, `PersonHistoryEvent`, `PersonStatsPublic`, `AthleteOverviewPublic`, `CoachOverviewPublic`; `build_person_overview(session, *, gym, user, kind, all_gyms) -> PersonOverview`.

- [ ] **Step 1: Write failing model/service tests** for field completeness, history ordering, and secret exclusion.
- [ ] **Step 2: Run tests, verify import failure** (`build_person_overview` missing).
- [ ] **Step 3: Add models and the service.**
- [ ] **Step 4: Run tests to verify they pass.**
- [ ] **Step 5: Commit.**

### Task 2: Overview endpoint and download endpoint

**Files:**
- Create: `backend/app/api/routes/people.py`
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/api/routes/test_person_overview.py`

**Interfaces:**
- Produces: `GET /api/v1/people/{user_id}/overview?gym_id=&kind=ATHLETE|COACH`; `GET /api/v1/people/{user_id}/body-files/{file_id}?gym_id=`.

- [ ] **Step 1: Write failing authorization and isolation tests.**
- [ ] **Step 2: Run tests, verify 404/405.**
- [ ] **Step 3: Implement the routes and register the router.**
- [ ] **Step 4: Run the focused tests.**
- [ ] **Step 5: Commit.**

### Task 3: Generated client

**Files:**
- Modify: `frontend/openapi.json`, `frontend/src/client/*`

- [ ] **Step 1: Export OpenAPI and run `bun run generate-client`.**
- [ ] **Step 2: Confirm `PeopleService` exists.**
- [ ] **Step 3: Commit.**

### Task 4: Overview page, route, styles, translations

**Files:**
- Create: `frontend/src/pages/PersonOverviewPage.tsx`
- Create: `frontend/src/routes/_app.people.$userId.tsx`
- Modify: `frontend/src/i18n.tsx`, `frontend/src/index.css`

- [ ] **Step 1: Write a Playwright test** that opens Details from a table and asserts identity, program, and history sections render, including an empty state.
- [ ] **Step 2: Implement route and page.**
- [ ] **Step 3: Run lint, TypeScript, and build.**
- [ ] **Step 4: Commit.**

### Task 5: Details buttons in tables

**Files:**
- Modify: `frontend/src/pages/SuperuserAthletesPage.tsx`
- Modify: `frontend/src/pages/SuperuserCoachesPage.tsx`
- Modify: `frontend/src/pages/AthletesPage.tsx`
- Modify: `frontend/src/pages/MembersPage.tsx`

- [ ] **Step 1: Add Details actions to table and card views.**
- [ ] **Step 2: Preserve list search state by returning through history.**
- [ ] **Step 3: Run lint, TypeScript, and build.**
- [ ] **Step 4: Commit.**

### Task 6: End-to-end verification

- [ ] **Step 1: Run the full backend suite.**
- [ ] **Step 2: Run Ruff and mypy.**
- [ ] **Step 3: Run frontend lint, TypeScript, build, and Playwright.**
- [ ] **Step 4: Review the diff for secrets and regressions.**
- [ ] **Step 5: Commit fixes.**
