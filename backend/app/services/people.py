from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models import (
    AthleteOverviewPublic,
    AthleteProfile,
    AthleteProfileSelf,
    BodyAnalysisFile,
    CoachAssignment,
    CoachOverviewPublic,
    Gym,
    GymMembership,
    GymRole,
    PersonAccountPublic,
    PersonAssignmentPublic,
    PersonBodyFilePublic,
    PersonHistoryEvent,
    PersonMembershipPublic,
    PersonOverview,
    PersonProgramPublic,
    PersonRefPublic,
    PersonStatsPublic,
    ProgramStatus,
    ProgramVersionDetail,
    User,
    WorkoutDay,
    WorkoutExercise,
    WorkoutProgram,
    WorkoutProgramVersion,
    WorkoutSet,
)
from app.services.access import get_membership_roles
from app.services.programs import days_public

PersonKind = Literal["ATHLETE", "COACH"]


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    return user.full_name or user.email


def _load_users(
    session: Session, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, User]:
    if not user_ids:
        return {}
    rows = session.exec(select(User).where(col(User.id).in_(user_ids))).all()
    return {row.id: row for row in rows}


def _load_gyms(session: Session, gym_ids: set[uuid.UUID]) -> dict[uuid.UUID, Gym]:
    if not gym_ids:
        return {}
    rows = session.exec(select(Gym).where(col(Gym.id).in_(gym_ids))).all()
    return {row.id: row for row in rows}


def _profile_self(profile: AthleteProfile, user: User) -> AthleteProfileSelf:
    return AthleteProfileSelf(
        user_id=user.id,
        gym_id=profile.gym_id,
        email=user.email,
        full_name=user.full_name,
        phone=profile.phone,
        birth_date=profile.birth_date,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        chest_cm=profile.chest_cm,
        waist_cm=profile.waist_cm,
        hips_cm=profile.hips_cm,
        arm_cm=profile.arm_cm,
        thigh_cm=profile.thigh_cm,
        training_goal=profile.training_goal,
        sports_history=profile.sports_history,
        fitness_level=profile.fitness_level,
        limitations=profile.limitations,
        training_days=profile.training_days or [],
        training_days_count=profile.training_days_count,
        equipment=profile.equipment,
        is_archived=profile.is_archived,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _program_details(
    session: Session,
    program_rows: Sequence[tuple[WorkoutProgramVersion, WorkoutProgram]],
    athlete_names: dict[uuid.UUID, str | None],
) -> list[PersonProgramPublic]:
    """Load every version structure with three bulk queries per relation."""
    if not program_rows:
        return []
    version_ids = [version.id for version, _program in program_rows]
    day_rows = session.exec(
        select(WorkoutDay)
        .where(col(WorkoutDay.version_id).in_(version_ids))
        .order_by(col(WorkoutDay.day_number))
    ).all()
    day_ids = [day.id for day in day_rows]
    exercise_rows = (
        session.exec(
            select(WorkoutExercise)
            .where(col(WorkoutExercise.day_id).in_(day_ids))
            .order_by(col(WorkoutExercise.order_index))
        ).all()
        if day_ids
        else []
    )
    exercise_ids = [exercise.id for exercise in exercise_rows]
    set_rows = (
        session.exec(
            select(WorkoutSet)
            .where(col(WorkoutSet.workout_exercise_id).in_(exercise_ids))
            .order_by(col(WorkoutSet.set_number))
        ).all()
        if exercise_ids
        else []
    )

    sets_by_exercise: dict[uuid.UUID, list[WorkoutSet]] = {}
    for workout_set in set_rows:
        sets_by_exercise.setdefault(
            workout_set.workout_exercise_id, []
        ).append(workout_set)
    exercises_by_day: dict[uuid.UUID, list[WorkoutExercise]] = {}
    for exercise in exercise_rows:
        exercises_by_day.setdefault(exercise.day_id, []).append(exercise)
    days_by_version: dict[uuid.UUID, list[WorkoutDay]] = {}
    for day in day_rows:
        days_by_version.setdefault(day.version_id, []).append(day)

    def day_public(day: WorkoutDay) -> dict[str, Any]:
        return {
            "id": day.id,
            "day_number": day.day_number,
            "weekday": day.weekday,
            "category_id": day.category_id,
            "category_name": day.category_name,
            "category_ids": day.category_ids,
            "category_names": day.category_names,
            "title": day.title,
            "notes": day.notes,
            "exercises": [
                {
                    "id": exercise.id,
                    "exercise_id": exercise.exercise_id,
                    "exercise_name": exercise.exercise_name,
                    "muscle_group": exercise.muscle_group,
                    "order_index": exercise.order_index,
                    "notes": exercise.notes,
                    "sets": [
                        {
                            "id": workout_set.id,
                            "set_number": workout_set.set_number,
                            "reps_min": workout_set.reps_min,
                            "reps_max": workout_set.reps_max,
                            "weight_kg": workout_set.weight_kg,
                            "intensity": workout_set.intensity,
                            "rest_seconds": workout_set.rest_seconds,
                            "duration_seconds": workout_set.duration_seconds,
                            "note": workout_set.note,
                        }
                        for workout_set in sets_by_exercise.get(
                            exercise.id, []
                        )
                    ],
                }
                for exercise in exercises_by_day.get(day.id, [])
            ],
        }

    gyms = _load_gyms(
        session, {program.gym_id for _version, program in program_rows}
    )
    details: list[PersonProgramPublic] = []
    for version, program in program_rows:
        program_gym = gyms.get(program.gym_id)
        version_days = days_by_version.get(version.id, [])
        detail = ProgramVersionDetail(
            id=version.id,
            program_id=program.id,
            athlete_user_id=program.athlete_user_id,
            athlete_name=athlete_names.get(program.athlete_user_id),
            title=version.title,
            goal=version.goal,
            version_number=version.version_number,
            revision=version.revision,
            status=cast(ProgramStatus, version.status),
            coach_id=version.coach_id,
            coach_name=version.coach_name,
            start_date=version.start_date,
            end_date=version.end_date,
            created_at=version.created_at,
            published_at=version.published_at,
            archived_at=version.archived_at,
            day_count=len(version_days),
            notes=version.notes,
            days=days_public(
                [day_public(day) for day in version_days]
            ),
        )
        details.append(
            PersonProgramPublic(
                **detail.model_dump(),
                gym_id=program.gym_id,
                gym_name=program_gym.name if program_gym else "",
            )
        )
    return details


def _event_timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def _seconds_between(first: datetime, second: datetime) -> float:
    return abs(_event_timestamp(first) - _event_timestamp(second))


def build_person_overview(
    session: Session,
    *,
    gym: Gym,
    user: User,
    kind: PersonKind,
    all_gyms: bool,
) -> PersonOverview:
    """Assemble every stored record we hold for one athlete or coach."""
    membership_statement = (
        select(GymMembership, Gym)
        .join(Gym, col(Gym.id) == col(GymMembership.gym_id))
        .where(GymMembership.user_id == user.id)
    )
    profile_statement = select(AthleteProfile).where(
        AthleteProfile.user_id == user.id
    )
    if not all_gyms:
        membership_statement = membership_statement.where(
            GymMembership.gym_id == gym.id
        )
        profile_statement = profile_statement.where(
            AthleteProfile.gym_id == gym.id
        )

    membership_rows = session.exec(
        membership_statement.order_by(col(GymMembership.created_at))
    ).all()
    profiles = session.exec(profile_statement).all()

    focus_membership = next(
        (row for row in membership_rows if row[0].gym_id == gym.id), None
    )
    focus_profile = next(
        (row for row in profiles if row.gym_id == gym.id), None
    )
    if not focus_membership and not focus_profile:
        raise HTTPException(status_code=404, detail="person_not_found")

    roles_by_membership = {
        membership.id: get_membership_roles(session, membership.id)
        for membership, _membership_gym in membership_rows
    }
    focus_roles = (
        roles_by_membership.get(focus_membership[0].id, set())
        if focus_membership
        else set()
    )
    if kind == "ATHLETE" and not focus_profile:
        raise HTTPException(status_code=404, detail="athlete_not_found")
    if kind == "COACH" and (
        not focus_membership or "COACH" not in focus_roles
    ):
        raise HTTPException(status_code=404, detail="coach_not_found")

    gym_ids = {row[1].id for row in membership_rows}
    gym_ids.update(profile.gym_id for profile in profiles)

    assignment_statement = select(CoachAssignment).where(
        or_(
            col(CoachAssignment.athlete_user_id) == user.id,
            col(CoachAssignment.coach_user_id) == user.id,
        )
    )
    if not all_gyms:
        assignment_statement = assignment_statement.where(
            CoachAssignment.gym_id == gym.id
        )
    assignments = session.exec(
        assignment_statement.order_by(col(CoachAssignment.started_at))
    ).all()
    gym_ids.update(assignment.gym_id for assignment in assignments)

    program_statement = (
        select(WorkoutProgramVersion, WorkoutProgram)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            or_(
                col(WorkoutProgram.athlete_user_id) == user.id,
                col(WorkoutProgramVersion.coach_id) == user.id,
            )
        )
    )
    if not all_gyms:
        program_statement = program_statement.where(
            WorkoutProgram.gym_id == gym.id
        )
    program_rows = session.exec(
        program_statement.order_by(col(WorkoutProgramVersion.created_at))
    ).all()
    gym_ids.update(program.gym_id for _version, program in program_rows)

    file_statement = select(BodyAnalysisFile).where(
        BodyAnalysisFile.athlete_user_id == user.id
    )
    if not all_gyms:
        file_statement = file_statement.where(
            BodyAnalysisFile.gym_id == gym.id
        )
    body_files = session.exec(
        file_statement.order_by(col(BodyAnalysisFile.created_at))
    ).all()
    gym_ids.update(body_file.gym_id for body_file in body_files)

    gyms = _load_gyms(session, gym_ids)
    user_ids = {user.id}
    for assignment in assignments:
        user_ids.add(assignment.athlete_user_id)
        user_ids.add(assignment.coach_user_id)
        if assignment.assigned_by_id:
            user_ids.add(assignment.assigned_by_id)
    for _version, program in program_rows:
        user_ids.add(program.athlete_user_id)
    for body_file in body_files:
        if body_file.uploaded_by_id:
            user_ids.add(body_file.uploaded_by_id)
    users = _load_users(session, user_ids)

    def gym_of(gym_id: uuid.UUID) -> Gym | None:
        return gyms.get(gym_id)

    def assignment_public(
        assignment: CoachAssignment,
    ) -> PersonAssignmentPublic:
        assignment_gym = gym_of(assignment.gym_id)
        return PersonAssignmentPublic(
            id=assignment.id,
            gym_id=assignment.gym_id,
            gym_name=assignment_gym.name if assignment_gym else "",
            athlete_user_id=assignment.athlete_user_id,
            athlete_name=_display_name(
                users.get(assignment.athlete_user_id)
            ),
            coach_user_id=assignment.coach_user_id,
            coach_name=_display_name(users.get(assignment.coach_user_id)),
            assigned_by_id=assignment.assigned_by_id,
            assigned_by_name=_display_name(
                users.get(assignment.assigned_by_id)
                if assignment.assigned_by_id
                else None
            ),
            started_at=assignment.started_at,
            ended_at=assignment.ended_at,
        )

    athlete_assignments = [
        assignment_public(row)
        for row in assignments
        if row.athlete_user_id == user.id
    ]
    coach_assignments = [
        assignment_public(row)
        for row in assignments
        if row.coach_user_id == user.id
    ]

    athlete_names = {
        athlete_id: _display_name(users.get(athlete_id))
        for athlete_id in {program.athlete_user_id for _v, program in program_rows}
    }
    programs = sorted(
        _program_details(session, program_rows, athlete_names),
        key=lambda item: _event_timestamp(item.created_at),
        reverse=True,
    )
    athlete_programs = [
        program for program in programs if program.athlete_user_id == user.id
    ]
    authored_programs = [
        program
        for program in programs
        if program.coach_id == user.id
    ]

    body_file_public: list[PersonBodyFilePublic] = []
    for body_file in sorted(
        body_files,
        key=lambda item: _event_timestamp(item.created_at),
        reverse=True,
    ):
        file_gym = gym_of(body_file.gym_id)
        body_file_public.append(
            PersonBodyFilePublic(
                id=body_file.id,
                original_name=body_file.original_name,
                content_type=body_file.content_type,
                size_bytes=body_file.size_bytes,
                created_at=body_file.created_at,
                gym_id=body_file.gym_id,
                gym_name=file_gym.name if file_gym else "",
                uploaded_by_name=_display_name(
                    users.get(body_file.uploaded_by_id)
                    if body_file.uploaded_by_id
                    else None
                ),
            )
        )

    events: list[PersonHistoryEvent] = []

    def add_event(
        event: str,
        occurred_at: datetime | None,
        *,
        gym_id: uuid.UUID | None = None,
        actor_name: str | None = None,
        related_type: str | None = None,
        related_id: uuid.UUID | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if occurred_at is None:
            return
        event_gym = gym_of(gym_id) if gym_id else None
        events.append(
            PersonHistoryEvent(
                event=event,
                occurred_at=occurred_at,
                gym_id=gym_id,
                gym_name=event_gym.name if event_gym else None,
                actor_name=actor_name,
                related_type=related_type,
                related_id=related_id,
                data=data or {},
            )
        )

    add_event(
        "account.created",
        user.created_at,
        data={"email": user.email},
    )

    for membership, membership_gym in membership_rows:
        roles = roles_by_membership.get(membership.id, set())
        add_event(
            "membership.joined",
            membership.created_at,
            gym_id=membership_gym.id,
            related_type="membership",
            related_id=membership.id,
            data={
                "roles": sorted(roles),
                "is_active": membership.is_active,
                "is_owner": membership_gym.owner_id == user.id,
            },
        )

    for profile in profiles:
        add_event(
            "athlete.profile_created",
            profile.created_at,
            gym_id=profile.gym_id,
            related_type="profile",
            related_id=profile.id,
            data={"archived": profile.is_archived},
        )
        if _seconds_between(profile.updated_at, profile.created_at) > 1:
            add_event(
                "athlete.profile_updated",
                profile.updated_at,
                gym_id=profile.gym_id,
                related_type="profile",
                related_id=profile.id,
            )
        if (
            profile.measurements_updated_at
            and _seconds_between(
                profile.measurements_updated_at, profile.updated_at
            )
            > 1
        ):
            add_event(
                "athlete.measurements_updated",
                profile.measurements_updated_at,
                gym_id=profile.gym_id,
                related_type="profile",
                related_id=profile.id,
            )

    for assignment in assignments:
        athlete = users.get(assignment.athlete_user_id)
        coach = users.get(assignment.coach_user_id)
        assigned_by = (
            users.get(assignment.assigned_by_id)
            if assignment.assigned_by_id
            else None
        )
        assignment_payload = {
            "athlete": _display_name(athlete),
            "coach": _display_name(coach),
        }
        add_event(
            "assignment.started",
            assignment.started_at,
            gym_id=assignment.gym_id,
            actor_name=_display_name(assigned_by),
            related_type="assignment",
            related_id=assignment.id,
            data=assignment_payload,
        )
        add_event(
            "assignment.ended",
            assignment.ended_at,
            gym_id=assignment.gym_id,
            related_type="assignment",
            related_id=assignment.id,
            data=assignment_payload,
        )

    for program_item in programs:
        payload: dict[str, Any] = {
            "title": program_item.title,
            "version": program_item.version_number,
            "status": program_item.status,
            "athlete": program_item.athlete_name,
            "coach": program_item.coach_name,
        }
        add_event(
            "program.version_created",
            program_item.created_at,
            gym_id=program_item.gym_id,
            actor_name=program_item.coach_name,
            related_type="program_version",
            related_id=program_item.id,
            data=payload,
        )
        add_event(
            "program.version_published",
            program_item.published_at,
            gym_id=program_item.gym_id,
            actor_name=program_item.coach_name,
            related_type="program_version",
            related_id=program_item.id,
            data=payload,
        )
        add_event(
            "program.version_archived",
            program_item.archived_at,
            gym_id=program_item.gym_id,
            actor_name=program_item.coach_name,
            related_type="program_version",
            related_id=program_item.id,
            data=payload,
        )

    for file_item in body_file_public:
        add_event(
            "athlete.body_file_uploaded",
            file_item.created_at,
            gym_id=file_item.gym_id,
            actor_name=file_item.uploaded_by_name,
            related_type="body_file",
            related_id=file_item.id,
            data={
                "file": file_item.original_name,
                "size": file_item.size_bytes,
                "content_type": file_item.content_type,
            },
        )

    deduped: dict[tuple[str, uuid.UUID | None, float], PersonHistoryEvent] = {}
    for event in events:
        deduped[
            (event.event, event.related_id, _event_timestamp(event.occurred_at))
        ] = event
    history = sorted(
        deduped.values(),
        key=lambda event: _event_timestamp(event.occurred_at),
        reverse=True,
    )

    current_coach = None
    if focus_profile:
        current = next(
            (
                row
                for row in assignments
                if row.gym_id == gym.id
                and row.athlete_user_id == user.id
                and row.ended_at is None
            ),
            None,
        )
        if current:
            coach_user = users.get(current.coach_user_id)
            if coach_user:
                current_coach = PersonRefPublic(
                    user_id=coach_user.id,
                    full_name=coach_user.full_name,
                    email=coach_user.email,
                )

    athlete_section = None
    if focus_profile:
        athlete_section = AthleteOverviewPublic(
            profile=_profile_self(focus_profile, user),
            measurements_updated_at=focus_profile.measurements_updated_at,
            internal_coach_note=focus_profile.internal_coach_note,
            current_coach=current_coach,
            assignments=athlete_assignments,
            programs=athlete_programs,
            body_files=body_file_public,
        )

    coach_section = None
    if focus_membership and "COACH" in focus_roles:
        coach_section = CoachOverviewPublic(
            roles=cast(list[GymRole], sorted(focus_roles)),
            is_active=focus_membership[0].is_active,
            is_owner=gym.owner_id == user.id,
            assignments=coach_assignments,
            authored_programs=authored_programs,
        )

    active_assignments = sum(
        1
        for assignment in (
            athlete_assignments if kind == "ATHLETE" else coach_assignments
        )
        if assignment.ended_at is None
    )
    overview_assignments = (
        athlete_assignments if kind == "ATHLETE" else coach_assignments
    )
    stats = PersonStatsPublic(
        memberships=len(membership_rows),
        assignments=len(overview_assignments),
        active_assignments=active_assignments,
        program_versions=len(programs),
        active_program_versions=sum(
            1 for program in programs if program.status == "ACTIVE"
        ),
        body_files=len(body_file_public),
    )

    return PersonOverview(
        kind=kind,
        focus_gym_id=gym.id,
        focus_gym_name=gym.name,
        account=PersonAccountPublic(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=(
                focus_profile.phone
                if focus_profile and focus_profile.phone
                else user.phone
            ),
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        memberships=[
            PersonMembershipPublic(
                membership_id=membership.id,
                gym_id=membership_gym.id,
                gym_name=membership_gym.name,
                roles=cast(
                    list[GymRole],
                    sorted(roles_by_membership.get(membership.id, set())),
                ),
                is_active=membership.is_active,
                is_owner=membership_gym.owner_id == user.id,
                created_at=membership.created_at,
            )
            for membership, membership_gym in membership_rows
        ],
        athlete=athlete_section,
        coach=coach_section,
        stats=stats,
        history=history,
        generated_at=datetime.now(UTC),
    )
