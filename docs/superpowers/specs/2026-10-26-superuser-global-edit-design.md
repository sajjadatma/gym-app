# Superuser Global Coach and Athlete Editing

## Intent

Let superusers edit coaches and athletes directly from the global coach and athlete lists, while making account-wide versus gym-scoped changes clear and enforcing gym boundaries in the API.

## Goals

- Add Edit actions to the superuser coach and athlete lists.
- Coach edits update shared account name and phone; email/login identity is not editable.
- Athlete edits update shared account name and that gym's athlete phone, and allow reassignment to an active coach in the same gym.
- Restrict mutations to superusers, validate referenced memberships/profiles in the specified gym, refresh affected list/detail caches, and audit administrative changes.

## Non-goals and safeguards

- Gym editing remains on the existing gym detail page.
- Do not change email, password, roles, membership state, archive/delete behavior, or cross-gym memberships through these forms.
- Do not allow a coach from another gym or an archived/ineligible coach to be assigned.
- Keep existing gym-scoped athlete editing and lifecycle flows intact.

## Approaches

1. **Global-list dialogs with dedicated superuser mutations (recommended and selected):** edit in place where the superuser already manages global records; pass the row's gym/membership scope to the API and validate it server-side.
2. **Navigate to gym-scoped pages:** reuse existing gym workflows, but interrupts global management and does not provide a consistent coach editing experience.

The user selected the recommended global-list flow and confirmed coach reassignment should be included for athletes.

## Constraints and implementation choices

- Coach rows represent a user membership in a particular gym; editing name/phone changes the shared user account.
- Athlete rows represent a shared user account plus an `AthleteProfile` in a particular gym; profile phone and assignment remain gym-scoped.
- Reuse existing list/dialog conventions, translations, API client generation, and audit patterns.
- Backend authorization and gym validation are authoritative; frontend filtering is not a security boundary.

## Implementation details

- Keep the edit forms focused on identity/contact and assignment: coach full name/phone; athlete full name/profile phone/coach assignment. Do not expose sensitive training, health, or measurement fields in this global edit flow.
- Preserve existing behavior for archived rows: follow existing update restrictions unless a safe, explicit requirement dictates otherwise.
