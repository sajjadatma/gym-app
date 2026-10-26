# Superuser Global Coach and Athlete Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add superuser-only Edit dialogs to the global coach and athlete lists, with gym-scoped athlete profile edits and coach reassignment.

**Architecture:** Add dedicated superuser PATCH endpoints and request schemas rather than widening gym-scoped mutations. The coach endpoint receives a membership ID and changes shared name/phone; the athlete endpoint receives gym and athlete IDs and changes shared name, that gym's phone, and assignment only to an eligible coach in that gym. Frontend dialogs call generated API methods and invalidate relevant global and gym-scoped queries.

**Tech Stack:** FastAPI, SQLModel, pytest, React, TanStack Query, generated OpenAPI TypeScript client, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-superuser-global-edit-design.md`

## Global Constraints

- Coach edits affect shared user name and phone; email/login identity is not editable.
- Athlete edits affect shared account name, the selected gym's athlete phone, and coach assignment within that gym.
- Mutations require superuser authorization and server-side validation of row/gym/profile/membership relationships.
- Do not change email, password, roles, membership state, archive/delete behavior, or cross-gym memberships through these forms.
- Do not expose sensitive training, health, or measurement fields in this global edit flow.
- Keep existing gym-scoped edit and lifecycle flows intact.

## Review Focus

- A forged gym/row combination must not edit a different gym's athlete profile; test mismatch returns 404 and leaves both records unchanged (Task 1).
- A reassignment target outside the athlete's gym, inactive, or not an eligible coach must be rejected without ending the current assignment (Task 1).
- Non-superusers must not call either mutation, even with valid IDs (Task 1).
- Blank coach phone and null coach assignment must be rejected without partially applying other submitted fields (Task 1).
- Editing a shared name through one gym's coach or athlete row must update the shared account identity, while profile phone/assignment remains gym-specific (Task 1 and Task 2).

---

### Task 1: Superuser edit mutation APIs and backend tests

**Files:**
- Modify: `backend/app/models.py` — add focused coach and athlete edit request schemas.
- Modify: `backend/app/api/routes/superuser_coaches.py` — add membership-scoped PATCH endpoint and audit event.
- Modify: `backend/app/api/routes/superuser_athletes.py` — add gym/profile-scoped PATCH endpoint, validate coach eligibility in the same gym, update assignment through existing assignment services, and audit the change.
- Test: `backend/tests/api/routes/test_superuser_coaches.py`
- Test: `backend/tests/api/routes/test_superuser_athletes.py`

**Interfaces:**
- Produces `SuperuserCoachUpdate(full_name: str | None, phone: str | None)` and `SuperuserAthleteUpdate(full_name: str | None, phone: str | None, coach_user_id: uuid.UUID | None)`; apply only supplied fields.
- Produces `PATCH /api/v1/superuser/coaches/{membership_id}` returning `SuperuserCoachRow`.
- Produces `PATCH /api/v1/superuser/athletes/{gym_id}/{athlete_user_id}` returning `SuperuserAthleteRow`.

- [x] **Step 1: Write failing API tests** for coach name/phone update, athlete name/profile-phone/reassignment, superuser authorization, coach membership scope, athlete gym/profile mismatch, and invalid/out-of-gym/inactive coach targets. Assert failed requests leave DB state and active assignment unchanged.
- [x] **Step 2: Run the focused tests** with `cd backend && uv run pytest tests/api/routes/test_superuser_coaches.py tests/api/routes/test_superuser_athletes.py -q`; confirmed new cases failed before implementation.
- [x] **Step 3: Add the request schemas and endpoints** with the interfaces above. Reuse existing membership/assignment validation and assignment lifecycle services; never trust a client gym ID without loading and validating the matching records.
- [x] **Step 4: Run focused tests and backend quality checks**: the two pytest modules, `uv run ruff check app tests`, and `uv run mypy app`; all passed.

### Task 2: Global-list edit dialogs and regression coverage

**Files:**
- Modify: `frontend/src/pages/SuperuserCoachesPage.tsx` — add Edit action, initialize/save coach edit form, refresh caches.
- Modify: `frontend/src/pages/SuperuserAthletesPage.tsx` — add Edit action, initialize/save athlete form, load active coaches for the selected gym, refresh caches.
- Modify: `frontend/src/i18n.tsx` — add Persian and English labels, validation/feedback copy.
- Regenerate: `frontend/src/client/*` using the repository OpenAPI client generation command.
- Test: add/update `frontend/tests/superuser-context.spec.ts` for edit actions, saved values, assignment scope and unchanged lifecycle actions.

**Interfaces:**
- Consumes Task 1 PATCH endpoints through generated `SuperuserCoachesService` and `SuperuserAthletesService` methods.
- Coach dialog edits only full name and phone; athlete dialog edits full name, gym-specific phone, and active coach assignment from the row's gym.

- [x] **Step 1: Write failing Playwright coverage** that edits a coach from the global list and an athlete from the global list, verifies values persist, verifies athlete coach options are gym-scoped, and verifies archive/restore actions remain available as before.
- [x] **Step 2: Run the focused Playwright test**; confirmed the edit action failed before implementation, then passed after implementation.
- [x] **Step 3: Generate the TypeScript client** from the updated OpenAPI schema using the existing frontend generator.
- [x] **Step 4: Implement both dialogs** following existing list/dialog and error/snackbar patterns. Disable edits during stale list data or save, show server validation errors, invalidate superuser list plus affected gym/member/athlete/profile/assignment queries after success.
- [x] **Step 5: Run verification**: focused and full Playwright coverage, frontend lint, TypeScript check, and production build; all passed.
