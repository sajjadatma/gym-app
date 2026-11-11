from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workout_session"
    __table_args__ = (
        UniqueConstraint(
            "gym_id",
            "athlete_user_id",
            "idempotency_key",
            name="uq_workout_session_retry",
        ),
        CheckConstraint(
            "effort IS NULL OR (effort >= 1 AND effort <= 10)",
            name="ck_workout_session_effort",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    athlete_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", index=True
    )
    version_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workout_program_version.id",
        ondelete="SET NULL",
        index=True,
    )
    day_id: uuid.UUID | None = Field(
        default=None, foreign_key="workout_day.id", ondelete="SET NULL"
    )
    program_title: str = Field(max_length=255)
    day_title: str = Field(max_length=255)
    performed_on: date = Field(index=True)
    completed: bool = True
    effort: int | None = None
    note: str | None = Field(default=None, max_length=2000)
    sets: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    idempotency_key: uuid.UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkoutSetActual(SQLModel):
    set_id: uuid.UUID
    completed: bool = False
    reps: int | None = Field(default=None, ge=0, le=1000)
    weight_kg: float | None = Field(default=None, ge=0, le=2000)


class WorkoutSessionCreate(SQLModel):
    version_id: uuid.UUID
    day_id: uuid.UUID
    performed_on: date
    completed: bool = True
    effort: int | None = Field(default=None, ge=1, le=10)
    note: str | None = Field(default=None, max_length=2000)
    sets: list[WorkoutSetActual] = Field(default_factory=list, max_length=200)
    idempotency_key: uuid.UUID


class WorkoutSessionPublic(SQLModel):
    id: uuid.UUID
    version_id: uuid.UUID | None
    day_id: uuid.UUID | None
    program_title: str
    day_title: str
    performed_on: date
    completed: bool
    effort: int | None
    note: str | None
    sets: list[dict[str, Any]]
    created_at: datetime
