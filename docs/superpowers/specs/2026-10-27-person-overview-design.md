# Person Overview Pages Design

## Intent

Superusers and club administrators need one place to see everything the database holds about an athlete or a coach, including a chronological history, without opening several tabs or dialogs. List tables expose a single Details action for fast access.

## Goals

- One read-only overview per person, opened from athlete and coach tables.
- Show every stored field relevant to the person, across all clubs for superusers and within the selected club for club admins.
- Show programs down to days, exercises, and sets, plus files, memberships, roles, assignments, and authored programs.
- Build a chronological timeline from timestamps already stored in the database.
- Preserve table filters, search, and page when returning.
- Keep existing role and tenant boundaries.

## Non-Goals

- No new audit table, event stream, or backfill of changes that were never stored.
- No editing from the overview page, except links to the existing edit and program screens.
- No bulk export.

## Anti-Goals

- Do not leak credentials, tokens, storage keys, or another club's records.
- Do not silently truncate history or program structures.

## Constraints

- The endpoint is admin-facing: superuser, owner, or `GYM_ADMIN`. Coaches and athletes are denied.
- The overview response is assembled on demand; no schema migration.
- The page must work for a superuser with no active club by passing the row's `gym_id`.
- Empty sections must say that no records exist, and the page must distinguish "no data" from "not recorded history".

## Approaches Considered

1. **Single composed endpoint and single page (chosen).** One request loads the complete record; the page renders sections and a timeline. Fast, predictable, simple to authorize and test.
2. **Reuse existing endpoints and merge in the browser.** Avoids backend work but needs many requests, duplicates authorization logic, and cannot assemble a coherent timeline.
3. **Add an audit/history subsystem.** Gives future change tracking but cannot reconstruct past edits and expands scope substantially. Rejected for this request.

## Decisions

- The overview endpoint is `GET /api/v1/people/{user_id}/overview?gym_id=&kind=ATHLETE|COACH`.
- Superusers receive memberships, assignments, and programs across all clubs; club admins receive only the focus club.
- History events are derived from stored timestamps and clearly labeled as a record timeline.
- The page uses an expandable program list so all versions and structures remain available without overwhelming the first view.

## Left to the Builder

- Exact visual grouping and responsive behavior.
- Whether to add more derived summary statistics.
- Future audit-table work, which is outside this design.
