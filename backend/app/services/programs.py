from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.api.deps import AthleteAccess, GymContext, get_athlete_access
from app.models import (
    DayInput,
    DayPublic,
    Exercise,
    ProgramStatus,
    ProgramTemplate,
    ProgramTemplateDetail,
    ProgramTemplateSummary,
    ProgramVersionDetail,
    ProgramVersionSummary,
    User,
    WorkoutDay,
    WorkoutExercise,
    WorkoutProgram,
    WorkoutProgramVersion,
    WorkoutSet,
)


def get_exercise_or_400(
    session: Session, *, gym_id: uuid.UUID, exercise_id: uuid.UUID
) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=400, detail="invalid_exercise")
    if exercise.is_custom and exercise.gym_id != gym_id:
        raise HTTPException(status_code=400, detail="invalid_exercise")
    return exercise


def normalize_days(
    session: Session, *, gym_id: uuid.UUID, days: list[DayInput]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for day_index, day in enumerate(days):
        exercises: list[dict[str, Any]] = []
        for exercise_index, item in enumerate(day.exercises):
            exercise = get_exercise_or_400(
                session, gym_id=gym_id, exercise_id=item.exercise_id
            )
            sets: list[dict[str, Any]] = []
            for set_index, workout_set in enumerate(
                sorted(item.sets, key=lambda value: value.set_number)
            ):
                data = workout_set.model_dump(mode="json")
                data["set_number"] = set_index + 1
                sets.append(data)
            exercises.append(
                {
                    "exercise_id": str(exercise.id),
                    "exercise_name": exercise.name_fa,
                    "muscle_group": exercise.muscle_group,
                    "order_index": exercise_index,
                    "notes": item.notes,
                    "sets": sets,
                }
            )
        result.append(
            {
                "day_number": day_index + 1,
                "title": day.title,
                "notes": day.notes,
                "exercises": exercises,
            }
        )
    return result


def insert_structure(
    session: Session,
    *,
    version_id: uuid.UUID,
    structure: list[dict[str, Any]],
) -> None:
    for day_data in structure:
        day = WorkoutDay(
            version_id=version_id,
            day_number=day_data["day_number"],
            title=day_data["title"],
            notes=day_data.get("notes"),
        )
        session.add(day)
        session.flush()
        for exercise_data in day_data.get("exercises", []):
            exercise_id = uuid.UUID(str(exercise_data["exercise_id"]))
            workout_exercise = WorkoutExercise(
                day_id=day.id,
                exercise_id=exercise_id,
                exercise_name=exercise_data["exercise_name"],
                muscle_group=exercise_data["muscle_group"],
                order_index=exercise_data["order_index"],
                notes=exercise_data.get("notes"),
            )
            session.add(workout_exercise)
            session.flush()
            for set_data in exercise_data.get("sets", []):
                session.add(
                    WorkoutSet(
                        workout_exercise_id=workout_exercise.id,
                        set_number=set_data["set_number"],
                        reps_min=set_data.get("reps_min"),
                        reps_max=set_data.get("reps_max"),
                        weight_kg=set_data.get("weight_kg"),
                        intensity=set_data.get("intensity"),
                        rest_seconds=set_data.get("rest_seconds"),
                        duration_seconds=set_data.get("duration_seconds"),
                        note=set_data.get("note"),
                    )
                )
    session.flush()


def replace_version_days(
    session: Session,
    *,
    version: WorkoutProgramVersion,
    days: list[DayInput],
    gym_id: uuid.UUID,
) -> None:
    structure = normalize_days(session, gym_id=gym_id, days=days)
    existing_days = session.exec(
        select(WorkoutDay).where(WorkoutDay.version_id == version.id)
    ).all()
    for day in existing_days:
        session.delete(day)
    session.flush()
    insert_structure(session, version_id=version.id, structure=structure)


def structure_from_version(
    session: Session, version: WorkoutProgramVersion
) -> list[dict[str, Any]]:
    days = session.exec(
        select(WorkoutDay)
        .where(WorkoutDay.version_id == version.id)
        .order_by(col(WorkoutDay.day_number))
    ).all()
    result: list[dict[str, Any]] = []
    for day in days:
        exercises = session.exec(
            select(WorkoutExercise)
            .where(WorkoutExercise.day_id == day.id)
            .order_by(col(WorkoutExercise.order_index))
        ).all()
        exercise_list: list[dict[str, Any]] = []
        for exercise in exercises:
            sets = session.exec(
                select(WorkoutSet)
                .where(WorkoutSet.workout_exercise_id == exercise.id)
                .order_by(col(WorkoutSet.set_number))
            ).all()
            exercise_list.append(
                {
                    "exercise_id": str(exercise.exercise_id),
                    "exercise_name": exercise.exercise_name,
                    "muscle_group": exercise.muscle_group,
                    "order_index": exercise.order_index,
                    "notes": exercise.notes,
                    "sets": [
                        {
                            "set_number": workout_set.set_number,
                            "reps_min": workout_set.reps_min,
                            "reps_max": workout_set.reps_max,
                            "weight_kg": workout_set.weight_kg,
                            "intensity": workout_set.intensity,
                            "rest_seconds": workout_set.rest_seconds,
                            "duration_seconds": workout_set.duration_seconds,
                            "note": workout_set.note,
                        }
                        for workout_set in sets
                    ],
                }
            )
        result.append(
            {
                "day_number": day.day_number,
                "title": day.title,
                "notes": day.notes,
                "exercises": exercise_list,
            }
        )
    return result


def days_public(structure: list[dict[str, Any]]) -> list[DayPublic]:
    return [DayPublic.model_validate(day) for day in structure]


def day_count(session: Session, version_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count(col(WorkoutDay.id))).where(
            WorkoutDay.version_id == version_id
        )
    ).one()


def version_summary(
    session: Session,
    version: WorkoutProgramVersion,
    program: WorkoutProgram,
    athlete: User | None,
) -> ProgramVersionSummary:
    return ProgramVersionSummary(
        id=version.id,
        program_id=program.id,
        athlete_user_id=program.athlete_user_id,
        athlete_name=athlete.full_name if athlete else None,
        title=version.title,
        goal=version.goal,
        version_number=version.version_number,
        status=cast(ProgramStatus, version.status),
        coach_id=version.coach_id,
        coach_name=version.coach_name,
        start_date=version.start_date,
        end_date=version.end_date,
        created_at=version.created_at,
        published_at=version.published_at,
        archived_at=version.archived_at,
        day_count=day_count(session, version.id),
    )


def version_detail(
    session: Session, version: WorkoutProgramVersion, program: WorkoutProgram
) -> ProgramVersionDetail:
    athlete = session.get(User, program.athlete_user_id)
    summary = version_summary(session, version, program, athlete)
    return ProgramVersionDetail(
        **summary.model_dump(),
        notes=version.notes,
        days=days_public(structure_from_version(session, version)),
    )


def load_version_context(
    session: Session,
    *,
    ctx: GymContext,
    current_user: User,
    version_id: uuid.UUID,
) -> tuple[WorkoutProgramVersion, WorkoutProgram, AthleteAccess]:
    version = session.get(WorkoutProgramVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="program_version_not_found")
    program = session.get(WorkoutProgram, version.program_id)
    if not program or program.gym_id != ctx.gym.id:
        raise HTTPException(status_code=404, detail="program_version_not_found")
    access = get_athlete_access(
        session, ctx, current_user, program.athlete_user_id, allow_archived=True
    )
    if access.is_self and version.status == "DRAFT" and not ctx.is_admin:
        raise HTTPException(status_code=404, detail="program_version_not_found")
    return version, program, access


def ensure_staff_write(access: AthleteAccess) -> None:
    if not access.can_edit_staff_fields:
        raise HTTPException(status_code=403, detail="program_edit_forbidden")


def ensure_publishable(structure: list[dict[str, Any]]) -> None:
    if not structure:
        raise HTTPException(status_code=400, detail="program_is_empty")
    for day in structure:
        if not day.get("exercises"):
            raise HTTPException(status_code=400, detail="program_day_is_empty")
        for exercise in day["exercises"]:
            if not exercise.get("sets"):
                raise HTTPException(
                    status_code=400, detail="program_exercise_has_no_sets"
                )


def get_or_create_program(
    session: Session,
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
    created_by_id: uuid.UUID,
) -> WorkoutProgram:
    program = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == gym_id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
        )
    ).first()
    if program:
        return program
    program = WorkoutProgram(
        gym_id=gym_id,
        athlete_user_id=athlete_user_id,
        created_by_id=created_by_id,
    )
    session.add(program)
    session.flush()
    return program


def next_version_number(session: Session, program_id: uuid.UUID) -> int:
    current = session.exec(
        select(func.max(WorkoutProgramVersion.version_number)).where(
            WorkoutProgramVersion.program_id == program_id
        )
    ).one()
    return int(current or 0) + 1


def template_days_public(template: ProgramTemplate) -> list[DayPublic]:
    raw_days = template.content.get("days", []) if template.content else []
    return [DayPublic.model_validate(day) for day in raw_days]


def template_summary(template: ProgramTemplate) -> ProgramTemplateSummary:
    return ProgramTemplateSummary(
        id=template.id,
        name=template.name,
        goal=template.goal,
        notes=template.notes,
        created_by_id=template.created_by_id,
        created_by_name=template.created_by_name,
        created_at=template.created_at,
        updated_at=template.updated_at,
        day_count=len(template.content.get("days", [])) if template.content else 0,
    )


def template_detail_model(template: ProgramTemplate) -> ProgramTemplateDetail:
    return ProgramTemplateDetail(
        **template_summary(template).model_dump(),
        days=template_days_public(template),
    )


def template_structure(template: ProgramTemplate) -> list[dict[str, Any]]:
    return template.content.get("days", []) if template.content else []


def template_days_input(template: ProgramTemplate) -> list[DayInput]:
    return [DayInput.model_validate(day) for day in template_structure(template)]
