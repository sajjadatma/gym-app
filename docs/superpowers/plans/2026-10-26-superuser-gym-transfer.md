# Superuser Gym Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add superuser coach and athlete gym transfers with data movement, destination validation, and dedicated transfer dialogs.

**Architecture:** Add two superuser-only `POST .../transfer` endpoints. The coach endpoint moves a `GymMembership` after eligibility checks. The athlete endpoint moves gym-bound profile/program/body-file rows, replaces the source membership and assignment, and validates the destination coach in the same transaction. Frontend dialogs use the regenerated client and invalidate affected caches.

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, pytest, React, TanStack Query, generated OpenAPI client, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-superuser-gym-transfer-design.md`

## Global Constraints

- Transfer requires superuser authorization.
- Never trust client gym IDs; load and validate source/destination relationships.
- Reject collisions instead of merging memberships or profiles.
- Validate all guards before mutating; failed transfers leave both gyms unchanged.
- Do not move shared identity, roles (coach), templates, exercises, or ownership.

---

### Task 1: Backend transfer endpoints and tests

**Files:**
- Modify: `backend/app/models.py` — add `SuperuserCoachTransfer` and `SuperuserAthleteTransfer`.
- Modify: `backend/app/api/routes/superuser_coaches.py` — transfer endpoint.
- Modify: `backend/app/api/routes/superuser_athletes.py` — transfer endpoint.
- Test: `backend/tests/api/routes/test_superuser_coaches.py`
- Test: `backend/tests/api/routes/test_superuser_athletes.py`

**Interfaces:**
- `POST /api/v1/superuser/coaches/{membership_id}/transfer` with `{gym_id}` → `SuperuserCoachRow` for the destination gym.
- `POST /api/v1/superuser/athletes/{gym_id}/{athlete_user_id}/transfer` with `{gym_id, coach_user_id}` → `SuperuserAthleteRow` for the destination gym.

- [x] **Step 1: Write failing tests** for successful coach/athlete transfers and every guard: assignments, ownership, archived membership, staff roles, collisions, same gym, invalid/destination coach, non-superuser, state unchanged on failure; verify profile, programs (versions/days), files, membership, and assignments move.
- [x] **Step 2: Run focused tests** and confirm the new cases fail for missing endpoints.
- [x] **Step 3: Implement schemas and endpoints** with validation-before-mutation and audit events.
- [x] **Step 4: Verify** focused modules (30 passed), full backend suite (140 passed), Ruff, and mypy.

### Task 2: Transfer dialogs and end-to-end coverage

**Files:**
- Modify: `frontend/src/pages/SuperuserCoachesPage.tsx`
- Modify: `frontend/src/pages/SuperuserAthletesPage.tsx`
- Modify: `frontend/src/i18n.tsx`
- Regenerate: `frontend/src/client/*`
- Test: `frontend/tests/superuser-context.spec.ts`

- [x] **Step 1: Add Playwright coverage** for transferring a coach and an athlete between seeded gyms, including destination-gym coach selection and blocked transfer feedback.
- [x] **Step 2: Regenerate the client** and implement dialogs/actions following existing patterns.
- [x] **Step 3: Verify** focused and full Playwright suites (70 passed, 1 skipped), lint, TypeScript, and production build.
