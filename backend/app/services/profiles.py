from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models import (
    AssignmentPublic,
    AthleteDetail,
    AthleteProfile,
    AthleteProfileSelf,
    AthleteSelfDetail,
    AthleteSummary,
    BodyAnalysisFile,
    BodyAnalysisFilePublic,
    CoachAssignment,
    CoachPublic,
    GymMembership,
    GymMembershipRole,
    User,
    WorkoutProgram,
    WorkoutProgramVersion,
)


def profile_self(profile: AthleteProfile, user: User) -> AthleteProfileSelf:
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


def body_file_public(file: BodyAnalysisFile) -> BodyAnalysisFilePublic:
    return BodyAnalysisFilePublic(
        id=file.id,
        original_name=file.original_name,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        created_at=file.created_at,
    )


def active_version_for(
    session: Session, gym_id: uuid.UUID, athlete_user_id: uuid.UUID
) -> WorkoutProgramVersion | None:
    return session.exec(
        select(WorkoutProgramVersion)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            WorkoutProgram.gym_id == gym_id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
            WorkoutProgramVersion.status == "ACTIVE",
        )
    ).first()


def athlete_summary(
    session: Session,
    *,
    profile: AthleteProfile,
    user: User,
    membership: GymMembership,
    assignment: CoachAssignment | None,
) -> AthleteSummary:
    coach = session.get(User, assignment.coach_user_id) if assignment else None
    active = active_version_for(session, profile.gym_id, profile.user_id)
    return AthleteSummary(
        user_id=user.id,
        gym_id=profile.gym_id,
        email=user.email,
        full_name=user.full_name,
        phone=profile.phone,
        is_active=membership.is_active,
        is_archived=profile.is_archived,
        coach_user_id=assignment.coach_user_id if assignment else None,
        coach_name=coach.full_name if coach else None,
        active_program_id=active.id if active else None,
        active_program_title=active.title if active else None,
        active_program_version=active.version_number if active else None,
        created_at=profile.created_at,
    )


def athlete_summaries_page(
    session: Session,
    *,
    gym_id: uuid.UUID,
    rows: Sequence[tuple[AthleteProfile, User, GymMembership]],
) -> list[AthleteSummary]:
    """Build summaries for one page of athletes with constant query count.

    Assignments, coach names and active program versions are fetched for the
    whole page at once instead of per row.
    """
    if not rows:
        return []

    athlete_ids = [user.id for _profile, user, _membership in rows]
    assignments = session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym_id,
            col(CoachAssignment.ended_at).is_(None),
            col(CoachAssignment.athlete_user_id).in_(athlete_ids),
        )
    ).all()
    assignment_map = {
        assignment.athlete_user_id: assignment for assignment in assignments
    }
    coach_ids = {assignment.coach_user_id for assignment in assignments}
    coaches = (
        session.exec(select(User).where(col(User.id).in_(coach_ids))).all()
        if coach_ids
        else []
    )
    coach_names = {coach.id: coach.full_name for coach in coaches}

    versions = session.exec(
        select(WorkoutProgramVersion, WorkoutProgram)
        .join(
            WorkoutProgram,
            col(WorkoutProgram.id) == col(WorkoutProgramVersion.program_id),
        )
        .where(
            WorkoutProgram.gym_id == gym_id,
            col(WorkoutProgram.athlete_user_id).in_(athlete_ids),
            WorkoutProgramVersion.status == "ACTIVE",
        )
    ).all()
    active_versions: dict[uuid.UUID, WorkoutProgramVersion] = {}
    for version, program in versions:
        active_versions.setdefault(program.athlete_user_id, version)

    summaries: list[AthleteSummary] = []
    for profile, user, membership in rows:
        assignment = assignment_map.get(user.id)
        active = active_versions.get(user.id)
        summaries.append(
            AthleteSummary(
                user_id=user.id,
                gym_id=profile.gym_id,
                email=user.email,
                full_name=user.full_name,
                phone=profile.phone,
                is_active=membership.is_active,
                is_archived=profile.is_archived,
                coach_user_id=(
                    assignment.coach_user_id if assignment else None
                ),
                coach_name=(
                    coach_names.get(assignment.coach_user_id)
                    if assignment
                    else None
                ),
                active_program_id=active.id if active else None,
                active_program_title=active.title if active else None,
                active_program_version=(
                    active.version_number if active else None
                ),
                created_at=profile.created_at,
            )
        )
    return summaries


def assignments_public(
    session: Session,
    *,
    gym_id: uuid.UUID,
    athlete_user_id: uuid.UUID,
) -> list[AssignmentPublic]:
    rows = session.exec(
        select(CoachAssignment)
        .where(
            CoachAssignment.gym_id == gym_id,
            CoachAssignment.athlete_user_id == athlete_user_id,
        )
        .order_by(col(CoachAssignment.started_at).desc())
    ).all()
    out: list[AssignmentPublic] = []
    for row in rows:
        coach = session.get(User, row.coach_user_id)
        out.append(
            AssignmentPublic(
                id=row.id,
                coach_user_id=row.coach_user_id,
                coach_name=coach.full_name if coach else None,
                started_at=row.started_at,
                ended_at=row.ended_at,
            )
        )
    return out


def body_files_for(
    session: Session, *, gym_id: uuid.UUID, athlete_user_id: uuid.UUID
) -> list[BodyAnalysisFilePublic]:
    rows = session.exec(
        select(BodyAnalysisFile)
        .where(
            BodyAnalysisFile.gym_id == gym_id,
            BodyAnalysisFile.athlete_user_id == athlete_user_id,
        )
        .order_by(col(BodyAnalysisFile.created_at).desc())
    ).all()
    return [body_file_public(row) for row in rows]


def staff_detail(
    session: Session,
    *,
    profile: AthleteProfile,
    user: User,
    assignment: CoachAssignment | None,
) -> AthleteDetail:
    coach = session.get(User, assignment.coach_user_id) if assignment else None
    return AthleteDetail(
        profile=profile_self(profile, user),
        coach_user_id=coach.id if coach else None,
        coach_name=coach.full_name if coach else None,
        coach_email=coach.email if coach else None,
        assignments=assignments_public(
            session, gym_id=profile.gym_id, athlete_user_id=profile.user_id
        ),
        body_files=body_files_for(
            session, gym_id=profile.gym_id, athlete_user_id=profile.user_id
        ),
        internal_coach_note=profile.internal_coach_note,
    )


def self_detail(
    session: Session,
    *,
    profile: AthleteProfile,
    user: User,
    assignment: CoachAssignment | None,
) -> AthleteSelfDetail:
    coach = session.get(User, assignment.coach_user_id) if assignment else None
    return AthleteSelfDetail(
        profile=profile_self(profile, user),
        coach_user_id=coach.id if coach else None,
        coach_name=coach.full_name if coach else None,
        coach_email=coach.email if coach else None,
        body_files=body_files_for(
            session, gym_id=profile.gym_id, athlete_user_id=profile.user_id
        ),
    )


def coach_members(session: Session, gym_id: uuid.UUID) -> list[CoachPublic]:
    rows = session.exec(
        select(User, GymMembership)
        .join(GymMembership, col(GymMembership.user_id) == col(User.id))
        .join(
            GymMembershipRole,
            col(GymMembershipRole.membership_id) == col(GymMembership.id),
        )
        .where(
            GymMembership.gym_id == gym_id,
            col(GymMembership.is_active).is_(True),
            GymMembershipRole.role == "COACH",
            col(User.is_active).is_(True),
        )
    ).all()
    return [
        CoachPublic(user_id=user.id, email=user.email, full_name=user.full_name)
        for user, _membership in rows
    ]
