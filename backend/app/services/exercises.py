from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models import Exercise, ExerciseCategory, ExercisePublic


def get_category(
    session: Session, *, gym_id: uuid.UUID, category_id: uuid.UUID
) -> ExerciseCategory:
    category = session.get(ExerciseCategory, category_id)
    if not category or (category.gym_id is not None and category.gym_id != gym_id):
        raise HTTPException(status_code=400, detail="invalid_exercise_category")
    return category


def exercise_public(exercise: Exercise) -> ExercisePublic:
    return ExercisePublic.model_validate(exercise, from_attributes=True)


def ensure_global_categories(
    session: Session, names: set[str]
) -> dict[str, ExerciseCategory]:
    categories = {
        row.name: row
        for row in session.exec(
            select(ExerciseCategory).where(col(ExerciseCategory.gym_id).is_(None))
        ).all()
    }
    for name in sorted(names):
        if name not in categories:
            category = ExerciseCategory(name=name, name_key=name.casefold())
            session.add(category)
            categories[name] = category
    session.flush()
    return categories
