# Superuser global context and club workspaces — design

**Date:** 2026-10-25
**Status:** awaiting approval
**Approach chosen:** hybrid (explicit club entry + real club URLs), with full URL-scoped context deferred

## Problem

A superuser logs in and is immediately bound to the first club: the top bar shows that club's name and a "management mode" chip, and the dashboard shows that club's stats and athletes. Nothing tells the superuser they are inside one club by accident, and there is no way back to a global view. Club owners, coaches and athletes should keep seeing their club; a superuser oversees all clubs and should only see a club context after deliberately entering that club's workspace.

## What the user decided

- Superuser enters a club's workspace completely when they choose it.
- Every club should have its own route and id (long-term direction).
- Chosen implementation: hybrid — ship the behavior now on real club routes, migrate the remaining inner pages later.

## Behavior

**Global superuser (no active club)**

- Fresh login lands on `/` with **no club name and no mode chip** in the top bar.
- `/` shows a global dashboard: welcome hero, "manage clubs" action, and one card per club (coach count, athlete count, active-program count), each with an "enter club" action.
- Nav: dashboard, clubs.
- The club switcher is not shown.

**Entering a club**

- Clicking a club card (global dashboard or clubs page) navigates to `/gyms/:gymId`, which renders the club workspace (the existing club dashboard) and sets that club active.
- Top bar shows the club name (switcher across clubs) and the mode chip, as it does today for club users.
- Nav becomes the club admin nav; navigating to athletes, exercises, etc. keeps the club context.
- The club workspace exposes a settings action to `/gyms/:gymId/settings`.

**Leaving a club**

- The club dropdown gains an "all clubs" item: clears the active club and returns to `/` (global view).
- Logging out and back in always returns a superuser to the global view.

**Club users (owner, coach, athlete) — unchanged**

- Same landing behavior, same header, same routes as today.

**URLs**

- `/gyms/:gymId` — club workspace (new; supersedes the current detail page at this path).
- `/gyms/:gymId/settings` — club detail/settings (today's `GymDetailPage`).
- `/gyms` — clubs list (unchanged).
- `/` — dashboard: club dashboard when a club is active, otherwise the superuser global dashboard.

**Known intermediate state (documented):** inner club pages remain at `/athletes`, `/exercises`, etc. and rely on the active-club state; moving them under `/gyms/:gymId/...` is the follow-up B step. Deep-linking such a page after login without first entering a club is not supported for superusers.

## Technical shape

- `frontend/src/auth.tsx`: auto-select the first club only for non-superusers; clear the stored club on login; allow clearing the active club (`setActiveGym(null)` / `clearActiveGym`).
- `frontend/src/routes/_app.gyms.$gymId.tsx`: becomes a layout that syncs the active club from the route param and renders an outlet.
- New `_app.gyms.$gymId.index.tsx` (club workspace) and `_app.gyms.$gymId.settings.tsx` (current `GymDetailPage`), reusing `DashboardPage`.
- `DashboardPage`: superuser with no active club renders the global dashboard (club cards + enter action); the in-club superuser view drops the cross-club card grid.
- `AppShell`: hide club/role context for a superuser with no active club; add the "all clubs" menu item for superusers.
- `GymsPage` / dashboard links: enter goes to `/gyms/:gymId`; "details" goes to `/gyms/:gymId/settings`.
- i18n: new Persian/English strings for "all clubs", "enter club".
- No backend or API changes.

## Test strategy

- New Playwright spec for the superuser journey, gated on `PLAYWRIGHT_SUPERUSER_EMAIL` / `PLAYWRIGHT_SUPERUSER_PASSWORD` (documented in README; skipped when absent, since the demo seed has no superuser):
  1. login lands global: no club name in the top bar, club cards visible;
  2. entering a club goes to `/gyms/:gymId`, shows the club name and club dashboard;
  3. settings route renders the club settings page;
  4. "all clubs" returns to `/` and hides the club name again;
  5. reload while inside a club keeps the club context.
- Existing non-superuser specs (`admin.spec.ts` and the rest) must keep passing unchanged — they are the regression guard for owners/coaches/athletes.

## Non-goals

- Moving every club page under `/gyms/:gymId/...` (follow-up B).
- Any backend/schema/permission change.
- Changing what a club user sees.

## Work size

Small-to-medium: one frontend change set, new routes, new tests, no migration.
