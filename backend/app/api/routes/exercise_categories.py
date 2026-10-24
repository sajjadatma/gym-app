from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, or_, select

from app.api.deps import CurrentUser, GymStaffDep, SessionDep
from app.models import (
    ExerciseCategoriesPublic,
    ExerciseCategory,
    ExerciseCategoryCreate,
    ExerciseCategoryPublic,
)

router = APIRouter(prefix="/exercise-categories", tags=["exercise_categories"])


@router.get("", response_model=ExerciseCategoriesPublic)
def list_exercise_categories(*, session: SessionDep, ctx: GymStaffDep) -> Any:
    categories = session.exec(
        select(ExerciseCategory)
        .where(
            or_(
                col(ExerciseCategory.gym_id).is_(None),
                ExerciseCategory.gym_id == ctx.gym.id,
            )
        )
        .order_by(col(ExerciseCategory.name))
    ).all()
    return ExerciseCategoriesPublic(
        data=[
            ExerciseCategoryPublic.model_validate(row, from_attributes=True)
            for row in categories
        ],
        count=len(categories),
    )


@router.post("", response_model=ExerciseCategoryPublic)
def create_exercise_category(
    *,
    session: SessionDep,
    ctx: GymStaffDep,
    current_user: CurrentUser,
    body: ExerciseCategoryCreate,
) -> Any:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    key = body.name.casefold()
    existing = session.exec(
        select(ExerciseCategory).where(
            ExerciseCategory.name_key == key,
            or_(
                col(ExerciseCategory.gym_id).is_(None),
                ExerciseCategory.gym_id == ctx.gym.id,
            ),
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="exercise_category_already_exists")
    category = ExerciseCategory(
        name=body.name,
        name_key=key,
        gym_id=ctx.gym.id,
        created_by_id=current_user.id,
    )
    session.add(category)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="exercise_category_already_exists"
        ) from exc
    session.refresh(category)
    return category
