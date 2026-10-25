from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import EmailStr, field_validator, model_validator
from sqlalchemy import CheckConstraint, Column, Index, Text, UniqueConstraint, text
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

GymRole = Literal["GYM_ADMIN", "COACH", "ATHLETE"]
ProgramStatus = Literal["DRAFT", "ACTIVE", "ARCHIVED"]
ActivationMethod = Literal["invite", "password"]


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class User(UserBase, table=True):
    __tablename__ = "user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    phone: str | None = Field(default=None, max_length=50)
    hashed_password: str | None = Field(default=None, max_length=255)
    must_change_password: bool = Field(default=False)
    token_version: int = Field(default=0)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserPublic(UserBase):
    id: uuid.UUID
    must_change_password: bool = False
    created_at: datetime | None = None


class GymAccessPublic(SQLModel):
    gym_id: uuid.UUID
    gym_name: str
    roles: list[GymRole]
    is_owner: bool


class UserMePublic(UserPublic):
    phone: str | None = None
    gyms: list[GymAccessPublic]


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class AcceptInvitation(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None
    purpose: str | None = None
    token_version: int = 0


class Message(SQLModel):
    message: str


# ---------------------------------------------------------------------------
# Gyms and memberships
# ---------------------------------------------------------------------------


class Gym(SQLModel, table=True):
    __tablename__ = "gym"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(min_length=1, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    owner_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT", index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class GymCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    owner_email: EmailStr
    owner_full_name: str | None = Field(default=None, max_length=255)
    activation_method: ActivationMethod = "invite"
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)


class GymUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class GymStaffCounts(SQLModel):
    coaches: int = 0
    admins: int = 0
    athletes: int = 0
    active_programs: int = 0
    draft_programs: int = 0
    archived_programs: int = 0


class GymPublic(SQLModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    address: str | None = None
    phone: str | None = None
    owner_id: uuid.UUID
    owner_name: str | None = None
    is_active: bool
    created_at: datetime
    is_owner: bool = False
    my_roles: list[GymRole]
    stats: GymStaffCounts | None = None


class GymsPublic(SQLModel):
    data: list[GymPublic]
    count: int


class GymCreated(SQLModel):
    gym: GymPublic
    initial_password: str | None = None
    invitation_sent: bool = False


class OwnershipTransferred(SQLModel):
    gym: GymPublic
    initial_password: str | None = None
    invitation_sent: bool = False


class OwnershipTransfer(SQLModel):
    new_owner_email: EmailStr
    new_owner_full_name: str | None = Field(default=None, max_length=255)
    activation_method: ActivationMethod = "invite"
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)


class GymMembership(SQLModel, table=True):
    __tablename__ = "gym_membership"
    __table_args__ = (
        UniqueConstraint("user_id", "gym_id", name="uq_gym_membership_user_gym"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class GymMembershipRole(SQLModel, table=True):
    __tablename__ = "gym_membership_role"
    __table_args__ = (
        UniqueConstraint("membership_id", "role", name="uq_membership_role"),
        CheckConstraint(
            "role IN ('GYM_ADMIN', 'COACH', 'ATHLETE')",
            name="ck_membership_role",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    membership_id: uuid.UUID = Field(
        foreign_key="gym_membership.id", ondelete="CASCADE", index=True
    )
    role: str = Field(max_length=20)


class MemberCreate(SQLModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    roles: list[GymRole]
    activation_method: ActivationMethod = "invite"
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[GymRole]) -> list[GymRole]:
        if not value:
            raise ValueError("at least one role is required")
        if "ATHLETE" in value:
            raise ValueError("athletes are created through the athletes flow")
        return sorted(set(value))


class MemberUpdate(SQLModel):
    roles: list[GymRole] | None = None
    is_active: bool | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[GymRole] | None) -> list[GymRole] | None:
        if value is None:
            return None
        if "ATHLETE" in value:
            raise ValueError("athlete membership is managed from the athlete record")
        return sorted(set(value))


class MemberPublic(SQLModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    roles: list[GymRole]
    is_active: bool
    is_owner: bool
    created_at: datetime


class MembersPublic(SQLModel):
    data: list[MemberPublic]
    count: int


class MemberCreated(SQLModel):
    member: MemberPublic
    initial_password: str | None = None
    invitation_sent: bool = False

class SuperuserCoachRow(SQLModel):
    membership_id: uuid.UUID
    gym_id: uuid.UUID
    gym_name: str
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    roles: list[GymRole]
    is_active: bool
    can_archive: bool
    created_at: datetime


class SuperuserCoachesPublic(SQLModel):
    data: list[SuperuserCoachRow]
    count: int


class SuperuserCoachCreate(SQLModel):
    gym_id: uuid.UUID
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    activation_method: ActivationMethod = "invite"
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)


class SuperuserCoachCreated(SQLModel):
    coach: SuperuserCoachRow
    initial_password: str | None = None
    invitation_sent: bool = False


# ---------------------------------------------------------------------------
# Athlete profiles and coach assignment
# ---------------------------------------------------------------------------


class CoachAssignment(SQLModel, table=True):
    __tablename__ = "coach_assignment"
    __table_args__ = (
        Index(
            "uq_coach_assignment_current",
            "gym_id",
            "athlete_user_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    athlete_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", index=True
    )
    coach_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", index=True
    )
    assigned_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    started_at: datetime = Field(default_factory=get_datetime_utc)
    ended_at: datetime | None = Field(default=None)


class AthleteProfile(SQLModel, table=True):
    __tablename__ = "athlete_profile"
    __table_args__ = (
        UniqueConstraint("gym_id", "user_id", name="uq_athlete_profile_gym_user"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    phone: str | None = Field(default=None, max_length=50)
    birth_date: date | None = Field(default=None)
    height_cm: float | None = Field(default=None)
    weight_kg: float | None = Field(default=None)
    chest_cm: float | None = Field(default=None)
    waist_cm: float | None = Field(default=None)
    hips_cm: float | None = Field(default=None)
    arm_cm: float | None = Field(default=None)
    thigh_cm: float | None = Field(default=None)
    training_goal: str | None = Field(default=None, max_length=1000)
    sports_history: str | None = Field(default=None, max_length=2000)
    fitness_level: str | None = Field(default=None, max_length=100)
    limitations: str | None = Field(default=None, max_length=2000)
    training_days: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    training_days_count: int | None = Field(default=None, ge=1, le=7)
    equipment: str | None = Field(default=None, max_length=1000)
    measurements_updated_at: datetime | None = Field(default=None)
    internal_coach_note: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    is_archived: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    updated_at: datetime = Field(default_factory=get_datetime_utc)

    @field_validator(
        "height_cm",
        "weight_kg",
        "chest_cm",
        "waist_cm",
        "hips_cm",
        "arm_cm",
        "thigh_cm",
    )
    @classmethod
    def validate_measurement(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("measurement must be positive")
        return value


class AthleteProfileUpdate(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    birth_date: date | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    arm_cm: float | None = None
    thigh_cm: float | None = None
    training_goal: str | None = Field(default=None, max_length=1000)
    sports_history: str | None = Field(default=None, max_length=2000)
    fitness_level: str | None = Field(default=None, max_length=100)
    limitations: str | None = Field(default=None, max_length=2000)
    training_days: list[str] | None = None
    training_days_count: int | None = Field(default=None, ge=1, le=7)
    equipment: str | None = Field(default=None, max_length=1000)
    internal_coach_note: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "height_cm",
        "weight_kg",
        "chest_cm",
        "waist_cm",
        "hips_cm",
        "arm_cm",
        "thigh_cm",
    )
    @classmethod
    def validate_measurement(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("measurement must be positive")
        return value


class AthleteSelfUpdate(SQLModel):
    phone: str | None = Field(default=None, max_length=50)
    birth_date: date | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    arm_cm: float | None = None
    thigh_cm: float | None = None
    training_goal: str | None = Field(default=None, max_length=1000)
    sports_history: str | None = Field(default=None, max_length=2000)
    fitness_level: str | None = Field(default=None, max_length=100)
    limitations: str | None = Field(default=None, max_length=2000)
    training_days: list[str] | None = None
    training_days_count: int | None = Field(default=None, ge=1, le=7)
    equipment: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "height_cm",
        "weight_kg",
        "chest_cm",
        "waist_cm",
        "hips_cm",
        "arm_cm",
        "thigh_cm",
    )
    @classmethod
    def validate_measurement(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("measurement must be positive")
        return value


class AthleteCreate(SQLModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    coach_user_id: uuid.UUID | None = None
    activation_method: ActivationMethod = "invite"
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)
    height_cm: float | None = None
    weight_kg: float | None = None
    training_goal: str | None = Field(default=None, max_length=1000)
    training_days_count: int | None = Field(default=None, ge=1, le=7)


class AthleteRestore(SQLModel):
    coach_user_id: uuid.UUID | None = None

class SuperuserAthleteRow(SQLModel):
    user_id: uuid.UUID
    gym_id: uuid.UUID
    gym_name: str
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    is_archived: bool
    coach_user_id: uuid.UUID | None = None
    coach_name: str | None = None
    created_at: datetime


class SuperuserAthletesPublic(SQLModel):
    data: list[SuperuserAthleteRow]
    count: int


class SuperuserAthleteCreate(AthleteCreate):
    gym_id: uuid.UUID


class AthleteImportPreviewRow(SQLModel):
    row_number: int
    email: str
    full_name: str | None = None
    coach_email: str | None = None
    coach_name: str | None = None
    status: Literal["valid", "skip", "error"]
    messages: list[str] = Field(default_factory=list)


class AthleteImportPreview(SQLModel):
    rows: list[AthleteImportPreviewRow]
    total: int
    valid: int
    skipped: int
    errors: int


class AthleteImportFailure(SQLModel):
    row_number: int
    email: str
    messages: list[str] = Field(default_factory=list)


class AthleteImportResult(SQLModel):
    total: int
    created: int
    skipped: int
    failed: list[AthleteImportFailure] = Field(default_factory=list)


class ReassignCoach(SQLModel):
    coach_user_id: uuid.UUID


class AssignmentPublic(SQLModel):
    id: uuid.UUID
    coach_user_id: uuid.UUID
    coach_name: str | None = None
    started_at: datetime
    ended_at: datetime | None = None


class AthleteSummary(SQLModel):
    user_id: uuid.UUID
    gym_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    is_active: bool
    is_archived: bool
    coach_user_id: uuid.UUID | None = None
    coach_name: str | None = None
    active_program_id: uuid.UUID | None = None
    active_program_title: str | None = None
    active_program_version: int | None = None
    created_at: datetime


class AthletesPublic(SQLModel):
    data: list[AthleteSummary]
    count: int


class CoachPublic(SQLModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None


class CoachesPublic(SQLModel):
    data: list[CoachPublic]
    count: int


class BodyAnalysisFile(SQLModel, table=True):
    __tablename__ = "body_analysis_file"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    athlete_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", index=True
    )
    uploaded_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    original_name: str = Field(max_length=255)
    stored_name: str = Field(unique=True, max_length=255)
    content_type: str = Field(max_length=100)
    size_bytes: int
    created_at: datetime = Field(default_factory=get_datetime_utc)


class BodyAnalysisFilePublic(SQLModel):
    id: uuid.UUID
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class AthleteDetail(SQLModel):
    profile: AthleteProfileSelf
    coach_user_id: uuid.UUID | None = None
    coach_name: str | None = None
    coach_email: EmailStr | None = None
    assignments: list[AssignmentPublic]
    body_files: list[BodyAnalysisFilePublic]
    internal_coach_note: str | None = None


class AthleteSelfDetail(SQLModel):
    profile: AthleteProfileSelf
    coach_user_id: uuid.UUID | None = None
    coach_name: str | None = None
    coach_email: EmailStr | None = None
    body_files: list[BodyAnalysisFilePublic]


class AthleteCreated(SQLModel):
    athlete: AthleteDetail
    initial_password: str | None = None
    invitation_sent: bool = False


class AthleteProfileSelf(SQLModel):
    user_id: uuid.UUID
    gym_id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    arm_cm: float | None = None
    thigh_cm: float | None = None
    training_goal: str | None = None
    sports_history: str | None = None
    fitness_level: str | None = None
    limitations: str | None = None
    training_days: list[str]
    training_days_count: int | None = None
    equipment: str | None = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Exercise library
# ---------------------------------------------------------------------------


class ExerciseCategory(SQLModel, table=True):
    __tablename__ = "exercise_category"
    __table_args__ = (
        Index(
            "uq_exercise_category_global",
            "name_key",
            unique=True,
            postgresql_where=text("gym_id IS NULL"),
        ),
        UniqueConstraint("gym_id", "name_key", name="uq_exercise_category_gym_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(min_length=1, max_length=100)
    name_key: str = Field(max_length=100)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class ExerciseCategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("category name cannot be blank")
        return value


class ExerciseCategoryPublic(SQLModel):
    id: uuid.UUID
    name: str
    gym_id: uuid.UUID | None = None


class ExerciseCategoriesPublic(SQLModel):
    data: list[ExerciseCategoryPublic]
    count: int


class Exercise(SQLModel, table=True):
    __tablename__ = "exercise"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name_fa: str = Field(min_length=1, max_length=255, index=True)
    muscle_group: str = Field(min_length=1, max_length=100, index=True)
    category_id: uuid.UUID = Field(
        foreign_key="exercise_category.id", ondelete="RESTRICT", index=True
    )
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)
    is_custom: bool = Field(default=False, index=True)
    gym_id: uuid.UUID | None = Field(
        default=None, foreign_key="gym.id", ondelete="CASCADE", index=True
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class ExerciseCreate(SQLModel):
    name_fa: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)


class ExerciseUpdate(SQLModel):
    name_fa: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)


class ExercisePublic(SQLModel):
    id: uuid.UUID
    name_fa: str
    muscle_group: str
    category_id: uuid.UUID
    description: str | None = None
    instructions: str | None = None
    is_custom: bool
    gym_id: uuid.UUID | None = None


class ExercisesPublic(SQLModel):
    data: list[ExercisePublic]
    count: int


# ---------------------------------------------------------------------------
# Workout programs and versions
# ---------------------------------------------------------------------------


class WorkoutProgram(SQLModel, table=True):
    __tablename__ = "workout_program"
    __table_args__ = (
        UniqueConstraint(
            "gym_id", "athlete_user_id", name="uq_workout_program_gym_athlete"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    athlete_user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", index=True
    )
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)


class WorkoutProgramVersion(SQLModel, table=True):
    __tablename__ = "workout_program_version"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "version_number", name="uq_program_version_number"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')",
            name="ck_program_version_status",
        ),
        Index(
            "uq_program_version_active",
            "program_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    program_id: uuid.UUID = Field(
        foreign_key="workout_program.id", ondelete="CASCADE", index=True
    )
    version_number: int
    revision: int = Field(default=0)
    status: str = Field(default="DRAFT", max_length=20)
    title: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)
    coach_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    coach_name: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    published_at: datetime | None = Field(default=None)
    archived_at: datetime | None = Field(default=None)


class WorkoutDay(SQLModel, table=True):
    __tablename__ = "workout_day"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version_id: uuid.UUID = Field(
        foreign_key="workout_program_version.id", ondelete="CASCADE", index=True
    )
    day_number: int
    weekday: str | None = Field(default=None, max_length=16)
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    category_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="exercise_category.id",
        ondelete="RESTRICT",
        index=True,
    )
    category_name: str | None = Field(default=None, max_length=100)
    category_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    category_names: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class WorkoutExercise(SQLModel, table=True):
    __tablename__ = "workout_exercise"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    day_id: uuid.UUID = Field(
        foreign_key="workout_day.id", ondelete="CASCADE", index=True
    )
    exercise_id: uuid.UUID = Field(
        foreign_key="exercise.id", ondelete="RESTRICT", index=True
    )
    exercise_name: str = Field(max_length=255)
    muscle_group: str = Field(max_length=100)
    order_index: int
    notes: str | None = Field(default=None, max_length=2000)


class WorkoutSet(SQLModel, table=True):
    __tablename__ = "workout_set"
    __table_args__ = (
        UniqueConstraint(
            "workout_exercise_id", "set_number", name="uq_workout_set_number"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workout_exercise_id: uuid.UUID = Field(
        foreign_key="workout_exercise.id", ondelete="CASCADE", index=True
    )
    set_number: int
    reps_min: int | None = Field(default=None)
    reps_max: int | None = Field(default=None)
    weight_kg: float | None = Field(default=None)
    intensity: str | None = Field(default=None, max_length=100)
    rest_seconds: int | None = Field(default=None)
    duration_seconds: int | None = Field(default=None)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_set(self) -> WorkoutSet:
        if self.reps_min is not None and self.reps_min < 0:
            raise ValueError("reps_min must be non-negative")
        if self.reps_max is not None and self.reps_max < 0:
            raise ValueError("reps_max must be non-negative")
        if (
            self.reps_min is not None
            and self.reps_max is not None
            and self.reps_min > self.reps_max
        ):
            raise ValueError("reps_min cannot be greater than reps_max")
        if self.weight_kg is not None and self.weight_kg < 0:
            raise ValueError("weight_kg must be non-negative")
        if self.rest_seconds is not None and self.rest_seconds < 0:
            raise ValueError("rest_seconds must be non-negative")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        return self


class SetInput(SQLModel):
    set_number: int = Field(ge=1)
    reps_min: int | None = Field(default=None, ge=0)
    reps_max: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    intensity: str | None = Field(default=None, max_length=100)
    rest_seconds: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_reps(self) -> SetInput:
        if (
            self.reps_min is not None
            and self.reps_max is not None
            and self.reps_min > self.reps_max
        ):
            raise ValueError("reps_min cannot be greater than reps_max")
        return self


class SetPublic(SetInput):
    id: uuid.UUID | None = None


class ExerciseInput(SQLModel):
    exercise_id: uuid.UUID
    order_index: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=2000)
    sets: list[SetInput]


class ExercisePublicProgram(ExerciseInput):
    id: uuid.UUID | None = None
    exercise_name: str
    muscle_group: str
    sets: list[SetPublic]  # type: ignore[assignment]


class DayInput(SQLModel):
    day_number: int = Field(ge=1)
    weekday: str | None = Field(default=None, max_length=16)
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    category_id: uuid.UUID | None = None
    category_ids: list[uuid.UUID] = Field(default_factory=list)
    exercises: list[ExerciseInput]


class DayPublic(DayInput):
    category_names: list[str] = Field(default_factory=list)
    id: uuid.UUID | None = None
    category_name: str | None = None
    exercises: list[ExercisePublicProgram]  # type: ignore[assignment]


class ProgramVersionCreate(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    start_date: date | None = None
    end_date: date | None = None
    template_id: uuid.UUID | None = None


class ProgramVersionUpdate(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    start_date: date | None = None
    end_date: date | None = None
    days: list[DayInput]
    expected_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_dates(self) -> ProgramVersionUpdate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ProgramVersionSummary(SQLModel):
    id: uuid.UUID
    program_id: uuid.UUID
    athlete_user_id: uuid.UUID
    athlete_name: str | None = None
    title: str
    goal: str | None = None
    version_number: int
    revision: int
    status: ProgramStatus
    coach_id: uuid.UUID | None = None
    coach_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime
    published_at: datetime | None = None
    archived_at: datetime | None = None
    day_count: int = 0


class ProgramVersionDetail(ProgramVersionSummary):
    notes: str | None = None
    days: list[DayPublic]


class ProgramVersionsPublic(SQLModel):
    data: list[ProgramVersionSummary]
    count: int


class ProgramTemplate(SQLModel, table=True):
    __tablename__ = "program_template"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    gym_id: uuid.UUID = Field(foreign_key="gym.id", ondelete="CASCADE", index=True)
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    created_by_name: str | None = Field(default=None, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    content: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=get_datetime_utc)
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class ProgramTemplateCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    days: list[DayInput]


class ProgramTemplateUpdate(ProgramTemplateCreate):
    pass


class ProgramTemplateSummary(SQLModel):
    id: uuid.UUID
    name: str
    goal: str | None = None
    notes: str | None = None
    created_by_id: uuid.UUID | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    day_count: int = 0


class ProgramTemplateDetail(ProgramTemplateSummary):
    days: list[DayPublic]


class ProgramTemplatesPublic(SQLModel):
    data: list[ProgramTemplateSummary]
    count: int


class ApplyTemplate(SQLModel):
    athlete_user_id: uuid.UUID


class SaveAsTemplate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


# Resolve forward references used by athlete response models.
for _model in (AthleteDetail, AthleteSelfDetail, AthleteCreated):
    _model.model_rebuild()
