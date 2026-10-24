from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, or_, select

from app.api.deps import CurrentUser, GymStaffDep, SessionDep
from app.models import (
    Exercise,
    ExerciseCreate,
    ExercisePublic,
    ExercisesPublic,
    ExerciseUpdate,
)
from app.services.exercises import exercise_public, get_category

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=ExercisesPublic)
def list_exercises(
    *,
    session: SessionDep,
    ctx: GymStaffDep,
    q: str = Query(default="", max_length=255),
    muscle_group: str | None = Query(default=None, max_length=100),
    category_id: uuid.UUID | None = None,
) -> Any:
    statement = select(Exercise).where(
        or_(
            col(Exercise.is_custom).is_(False),
            Exercise.gym_id == ctx.gym.id,
        )
    )
    if category_id:
        get_category(session, gym_id=ctx.gym.id, category_id=category_id)
        statement = statement.where(Exercise.category_id == category_id)
    if muscle_group:
        statement = statement.where(Exercise.muscle_group == muscle_group)
    if q.strip():
        statement = statement.where(col(Exercise.name_fa).ilike(f"%{q.strip()}%"))
    exercises = session.exec(
        statement.order_by(
            col(Exercise.is_custom), col(Exercise.muscle_group), col(Exercise.name_fa)
        )
    ).all()
    data = [exercise_public(exercise) for exercise in exercises]
    return ExercisesPublic(data=data, count=len(data))


@router.post("", response_model=ExercisePublic)
def create_exercise(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: ExerciseCreate,
) -> Any:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    category = get_category(session, gym_id=ctx.gym.id, category_id=body.category_id)
    exercise = Exercise(
        name_fa=body.name_fa,
        muscle_group=category.name,
        category_id=category.id,
        description=body.description,
        instructions=body.instructions,
        is_custom=True,
        gym_id=ctx.gym.id,
        created_by_id=current_user.id,
    )
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return exercise_public(exercise)


@router.patch("/{exercise_id}", response_model=ExercisePublic)
def update_exercise(
    *,
    exercise_id: uuid.UUID,
    session: SessionDep,
    ctx: GymStaffDep,
    body: ExerciseUpdate,
) -> Any:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    exercise = session.get(Exercise, exercise_id)
    if not exercise or not exercise.is_custom or exercise.gym_id != ctx.gym.id:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    data = body.model_dump(exclude_unset=True)
    if "category_id" in data:
        if body.category_id is None:
            raise HTTPException(status_code=400, detail="invalid_exercise_category")
        category = get_category(
            session, gym_id=ctx.gym.id, category_id=body.category_id
        )
        data["muscle_group"] = category.name
    exercise.sqlmodel_update(data)
    session.add(exercise)
    session.commit()
    session.refresh(exercise)
    return exercise_public(exercise)
