from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, or_, select

from app.api.deps import CurrentUser, GymContextDep, GymStaffDep, SessionDep
from app.models import (
    Exercise,
    ExerciseCreate,
    ExercisePublic,
    ExercisesPublic,
    ExerciseUpdate,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=ExercisesPublic)
def list_exercises(
    *,
    session: SessionDep,
    ctx: GymStaffDep,
    q: str = Query(default="", max_length=255),
    muscle_group: str | None = Query(default=None, max_length=100),
) -> Any:
    statement = select(Exercise).where(
        or_(
            col(Exercise.is_custom).is_(False),
            Exercise.gym_id == ctx.gym.id,
        )
    )
    if muscle_group:
        statement = statement.where(Exercise.muscle_group == muscle_group)
    if q.strip():
        statement = statement.where(col(Exercise.name_fa).ilike(f"%{q.strip()}%"))
    exercises = session.exec(
        statement.order_by(
            col(Exercise.is_custom), col(Exercise.muscle_group), col(Exercise.name_fa)
        )
    ).all()
    data = [
        ExercisePublic(
            id=exercise.id,
            name_fa=exercise.name_fa,
            muscle_group=exercise.muscle_group,
            description=exercise.description,
            instructions=exercise.instructions,
            is_custom=exercise.is_custom,
            gym_id=exercise.gym_id,
        )
        for exercise in exercises
    ]
    return ExercisesPublic(data=data, count=len(data))


@router.post("", response_model=ExercisePublic)
def create_exercise(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: ExerciseCreate,
) -> Any:
    exercise = Exercise(
        name_fa=body.name_fa,
        muscle_group=body.muscle_group,
        description=body.description,
        instructions=body.instructions,
        is_custom=True,
        gym_id=ctx.gym.id,
        created_by_id=current_user.id,
    )
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return ExercisePublic(
        id=exercise.id,
        name_fa=exercise.name_fa,
        muscle_group=exercise.muscle_group,
        description=exercise.description,
        instructions=exercise.instructions,
        is_custom=True,
        gym_id=exercise.gym_id,
    )


@router.patch("/{exercise_id}", response_model=ExercisePublic)
def update_exercise(
    *,
    exercise_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: ExerciseUpdate,
) -> Any:
    exercise = session.get(Exercise, exercise_id)
    if not exercise or not exercise.is_custom or exercise.gym_id != ctx.gym.id:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    if not (ctx.is_admin or exercise.created_by_id == current_user.id):
        raise HTTPException(status_code=403, detail="exercise_edit_forbidden")
    exercise.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return ExercisePublic(
        id=exercise.id,
        name_fa=exercise.name_fa,
        muscle_group=exercise.muscle_group,
        description=exercise.description,
        instructions=exercise.instructions,
        is_custom=exercise.is_custom,
        gym_id=exercise.gym_id,
    )
