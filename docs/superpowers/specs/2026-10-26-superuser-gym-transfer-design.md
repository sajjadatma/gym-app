# Superuser Gym Transfer for Coaches and Athletes

## Intent

Let superusers move an existing coach or athlete membership from one gym to another without losing identity, training history, or access. Transfers are consequential, so they get a dedicated action and dialog rather than a destination field in the existing Edit forms.

## Goals

- Add a Transfer action to the global coach and athlete lists.
- Move the selected membership to a destination gym and remove access to the source gym.
- Athletes move their profile, programs (versions/days), body-analysis files, and current assignment; the destination requires an active coach in the destination gym.
- Coaches transfer only when they have no current athlete assignments in the source gym, are not the gym owner, and would not retain source-gym credentials.
- Validate everything server-side and audit each transfer.

## Non-goals and safeguards

- No data merging: if the person already has a membership or profile in the destination gym, reject the transfer.
- No cross-gym coach assignment: the destination coach must be active and hold `COACH` in the destination gym.
- Do not transfer archived coaches or archived athletes through this action.
- Do not move gym-scoped content that belongs to the gym rather than the person, such as program templates and exercises.
- Do not change email, password, shared identity, or roles as part of the transfer.
- Keep Edit, archive/restore, delete, and gym-scoped workflows unchanged.

## Approaches

1. **Dedicated transfer endpoints and dialogs (selected):** `POST /superuser/coaches/{membership_id}/transfer` and `POST /superuser/athletes/{gym_id}/{athlete_user_id}/transfer`. Transfer is visibly different from editing and can carry destination-specific choices.
2. **Gym dropdown inside Edit:** fewer screens, but hides the consequences of losing source-gym access and moving training data.
3. **Archive plus recreate:** loses history and identity continuity; rejected.

## Decisions

- Coach transfers move the `GymMembership` row, preserving its roles and ID. Blocked when roles are not exactly `COACH`, when the person owns the source gym, when any current assignment exists in the source gym, when an athlete profile exists there, when the membership is archived, or when a destination membership exists.
- Athlete transfers move `AthleteProfile`, `WorkoutProgram`, and `BodyAnalysisFile` rows to the destination gym. The current assignment in the source gym is ended and replaced with a new assignment to the chosen destination coach. Source membership is removed when it only carries `ATHLETE`; the destination membership is created with `ATHLETE`.
- Transferring an athlete whose source membership carries staff roles is rejected to avoid silently moving staff privileges, and a gym owner cannot be transferred as an athlete.
- Destination membership/profile/program collisions return `409`; invalid destinations or coaches return `400`/`404`; non-superusers get `403`.
- Everything is validated before mutation so failures leave both gyms unchanged.

## Data moved

| Record | Coach transfer | Athlete transfer |
|---|---|---|
| `GymMembership` / roles | changed `gym_id`, roles kept | source removed, destination created with `ATHLETE` |
| `AthleteProfile` | n/a | `gym_id` changed |
| `WorkoutProgram` (+ versions/days) | n/a | `gym_id` changed |
| `BodyAnalysisFile` | n/a | `gym_id` changed |
| `CoachAssignment` | must be none current in source | source current ended, destination current created |

## UI

- A "Transfer gym" action next to Edit in both global tables and cards.
- Coach dialog: destination gym; explanatory text about removed access.
- Athlete dialog: destination gym, then an active coach loaded from that gym; explanatory text about moved profile, programs, and files.
- Submit disabled until required choices exist; server errors shown inline; success refreshes global lists and affected gym/member/athlete/program caches.

## Out of scope

- Bulk transfers.
- Transferring gym ownership (existing ownership-transfer flow remains).
- Moving shared identity or login credentials.
