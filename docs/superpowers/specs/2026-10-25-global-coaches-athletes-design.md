# Global coaches and athletes pages — design

**Date:** 2026-10-25
**Status:** awaiting approval
**Scope:** superuser global mode only (no active club)

## Intent

A superuser currently manages coaches and athletes club by club. They need two global pages — one for every coach and one for every athlete across all clubs — showing which club each belongs to, contact details, and the existing management actions, plus the ability to create a coach or athlete directly from the global view.

## Decisions taken with the human partner

- Coach phone is **mandatory** when creating a coach.
- Coach **archive** and **delete** are membership-scoped; no separate active/deactivate control is exposed.
- Creating a coach/athlete asks for the club inside the dialog.
- Pages live at `/coaches` and `/athletes` and are visible only to a superuser in global mode.

## Data model

- Add `User.phone: str | None` (nullable, Alembic migration). Nullable is required so existing accounts are not broken; the **coach creation API requires it**, and a phone field is added to the profile editor so existing coaches can fill theirs. Rows without a phone show “—” until updated.
- A coach row is a `GymMembership` holding the `COACH` role. A person coaching two clubs appears twice, once per club.
- An athlete row is an `AthleteProfile` joined to its gym, coach assignment, and user account.

## Behavior

### Coaches page (`/coaches`)

Columns: name, email, phone, club, status (active/archived), created date. Search across name/email/phone, club filter, archived filter.

Actions per row:
- **Archive** — deactivate that gym membership, only when the membership’s only role is `COACH`, the user is not the gym owner, is not the acting superuser, and the membership has no athlete profile. Otherwise the Archive action is hidden and only Delete is offered, so admin/owner/athlete access is never deactivated. Archiving ends every active `CoachAssignment` where this user is the coach in that club, in the same transaction, so no athlete remains assigned to an inactive coach. Assignment rows are kept with `ended_at` set (history preserved). Athletes become unassigned and can be reassigned with the existing admin reassignment flow.
- **Restore** — reactivate an archived coach-only membership. Assignments are not recreated automatically; the coach must be reassigned to athletes.
- **Delete** — end the coach’s active assignments in that club, then remove the `COACH` role from that gym, in one transaction. Delete the membership row only if no roles remain, the user is not the owner, and there is no athlete profile. The user account, memberships in other clubs, athlete records, workout history, and ended assignment history are never deleted.

Create-coach dialog: club (required), full name, email (required), phone (required), activation (invite / initial password). The same phone requirement applies to the existing club “add member” flow whenever the `COACH` role is selected, so both paths enforce one rule. Existing coaches without a phone show “—” until they set it in their profile.

### Athletes page (`/athletes`)

Columns: name, email, phone, club, assigned coach, status. Same search/filter pattern.

Actions: archive, restore, delete — the existing athlete semantics, scoped to that athlete’s club.

Create-athlete dialog: club, assigned coach (loaded from the chosen club, required), full name, email, phone, activation (invite / initial password). If the club has no active coach, creation is disabled with a “create a coach first” message. Athlete phone remains the existing `AthleteProfile.phone`; `User.phone` is the account/coach phone and is not dual-written.

### Navigation and routing

- Global superuser nav (no active club): dashboard, clubs, **coaches**, **athletes**.
- Inside a club the two items disappear; `/coaches` redirects to that club’s team page and `/athletes` keeps its club redirect.
- Non-superusers never see the items; direct access falls back to the normal club behavior (no cross-club data is exposed).

## Backend

New superuser-only router (`/api/v1/superuser`, `CurrentSuperuser`), no `X-Gym-ID` requirement; every mutation names the club explicitly:

- `GET /superuser/coaches?q=&gym_id=&include_archived=`
- `POST /superuser/coaches` (club, email, name, **phone required**, activation)
- `POST /superuser/coaches/{membership_id}/archive`
- `POST /superuser/coaches/{membership_id}/restore`
- `DELETE /superuser/coaches/{membership_id}`
- `GET /superuser/athletes?q=&gym_id=&include_archived=` (phone from `AthleteProfile`)
- `POST /superuser/athletes` (club, coach, email, name, phone, activation)
- `POST /superuser/athletes/{gym_id}/{athlete_user_id}/archive`
- `POST /superuser/athletes/{gym_id}/{athlete_user_id}/restore`
- `DELETE /superuser/athletes/{gym_id}/{athlete_user_id}`

Reuse existing membership/athlete service functions; do not duplicate authorization logic. Owner protection, athlete-membership protection, and cross-gym checks follow the existing rules. Deletion of a coach’s last membership requires no account deletion.

The actions are transactional: assignment termination, role removal, optional membership deletion, and the audit-visible timestamps commit together. Existing uniqueness constraints (`gym_membership(user_id, gym_id)`, `gym_membership_role(membership_id, role)`, and the partial unique index for one current assignment per athlete) are relied on and unchanged.

### Multi-club account reuse

Coach creation reuses `activate_user` (identity by email, existing accounts are not duplicated) and `ensure_membership` (reactivates an existing membership instead of creating a second one). Adding a coach to another club never deletes or rewrites memberships or roles in their other clubs.

### Athlete creation requires a coach — preserved MVP rule

The existing API rejects athlete creation without a coach (`coach_required`) and every create path assigns one; this is approved MVP behavior, so the global page keeps it. The dialog requires an active coach and is disabled with a “create a coach first” message when the club has none.

### Phone ownership

- `User.phone` is the **account/coach phone**, added as nullable for migration safety; the coach creation paths require it. It is shown in the coach list and editable from the profile page.
- Athlete phone remains `AthleteProfile.phone` (club-scoped); it is shown in the athlete list and is not dual-written to `User.phone`.
- Attaching an existing account to a club as a coach **never overwrites an existing non-empty phone**; the provided phone fills the account phone only when it is empty. Existing accounts are otherwise reused as-is.

## Frontend

- Two pages using the existing M3 table/card patterns, search + club filter + archived filter, create dialogs with club pickers and a coach picker for athletes.
- Profile page gains an optional phone field (`User.phone`) so existing coaches can satisfy the requirement.
- Confirmation dialogs for archive/delete; snackbars on success; errors translated through the existing API error mapping.
- New i18n keys (fa/en).
- Reuse `m3-data-table` and dialog patterns from the athletes page.

## Out of scope

- Editing coach roles or contact details from the global list (profile editing covers phone).
- Deactivating owner/admin/athlete memberships through the coach action set.
- Bulk actions, pagination, CSV export, account deletion, invitation resend.

## Verification

- Backend: superuser-only enforcement (403 for others), cross-gym listing, phone required on coach creation, archive/restore/delete scoping, multi-gym coach deletion safety, owner-as-coach safety, athlete archive/delete through the global API.
- Playwright: nav visibility (global only), both lists show club/phone, create coach and athlete, archive/restore/delete, non-superuser cannot see or reach the pages.
- Full existing suites stay green.
