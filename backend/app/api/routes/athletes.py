from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.api.deps import (
    CurrentUser,
    GymContextDep,
    GymStaffDep,
    SessionDep,
    get_athlete_access,
    get_current_assignment,
)
from app.models import (
    AthleteCreate,
    AthleteCreated,
    AthleteDetail,
    AthleteProfile,
    AthleteProfileUpdate,
    AthleteSelfDetail,
    AthleteSelfUpdate,
    AthletesPublic,
    AthleteSummary,
    BodyAnalysisFile,
    BodyAnalysisFilePublic,
    CoachAssignment,
    GymMembership,
    GymMembershipRole,
    Message,
    ReassignCoach,
    User,
)
from app.services.access import get_membership_roles
from app.services.membership import activate_user, ensure_membership
from app.services.profiles import (
    athlete_summary,
    body_file_public,
    self_detail,
    staff_detail,
)
from app.services.storage import save_body_analysis_upload, stored_file_path

router = APIRouter(prefix="/athletes", tags=["athletes"])


def _validate_coach(
    session: Session, *, gym_id: uuid.UUID, coach_user_id: uuid.UUID
) -> User:
    coach = session.get(User, coach_user_id)
    if not coach or not coach.is_active:
        raise HTTPException(status_code=400, detail="invalid_coach")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == coach_user_id,
            col(GymMembership.is_active).is_(True),
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=400, detail="invalid_coach")
    if "COACH" not in get_membership_roles(session, membership.id):
        raise HTTPException(status_code=400, detail="invalid_coach")
    return coach


def _athlete_membership(
    session: Session, *, gym_id: uuid.UUID, user_id: uuid.UUID
) -> GymMembership:
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym_id,
            GymMembership.user_id == user_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="athlete_not_found")
    return membership


@router.get("", response_model=AthletesPublic)
def list_athletes(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    q: str = Query(default="", max_length=255),
    include_archived: bool = False,
) -> Any:
    if include_archived and not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    profiles = session.exec(
        select(AthleteProfile)
        .where(AthleteProfile.gym_id == ctx.gym.id)
        .order_by(col(AthleteProfile.created_at).desc())
    ).all()

    assigned_ids: set[uuid.UUID] | None = None
    if not ctx.is_admin:
        assignments = session.exec(
            select(CoachAssignment).where(
                CoachAssignment.gym_id == ctx.gym.id,
                CoachAssignment.coach_user_id == current_user.id,
                col(CoachAssignment.ended_at).is_(None),
            )
        ).all()
        assigned_ids = {row.athlete_user_id for row in assignments}

    needle = q.strip().lower()
    summaries: list[AthleteSummary] = []
    for profile in profiles:
        if assigned_ids is not None and profile.user_id not in assigned_ids:
            continue
        if profile.is_archived and not include_archived:
            continue
        user = session.get(User, profile.user_id)
        if not user:
            continue
        if needle:
            haystack = " ".join(
                filter(
                    None,
                    [user.full_name or "", user.email, profile.phone or ""],
                )
            ).lower()
            if needle not in haystack:
                continue
        membership = _athlete_membership(
            session, gym_id=ctx.gym.id, user_id=profile.user_id
        )
        if not membership.is_active:
            continue
        assignment = get_current_assignment(session, ctx.gym.id, profile.user_id)
        summaries.append(
            athlete_summary(
                session,
                profile=profile,
                user=user,
                membership=membership,
                assignment=assignment,
            )
        )
    return AthletesPublic(data=summaries, count=len(summaries))


@router.get("/me", response_model=AthleteSelfDetail)
def read_my_athlete_profile(
    *, session: SessionDep, current_user: CurrentUser, ctx: GymContextDep
) -> Any:
    access = get_athlete_access(session, ctx, current_user, current_user.id)
    return self_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=access.assignment,
    )


@router.patch("/me", response_model=AthleteSelfDetail)
def update_my_athlete_profile(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: AthleteSelfUpdate,
) -> Any:
    access = get_athlete_access(session, ctx, current_user, current_user.id)
    data = body.model_dump(exclude_unset=True)
    if any(
        key
        in {
            "height_cm",
            "weight_kg",
            "chest_cm",
            "waist_cm",
            "hips_cm",
            "arm_cm",
            "thigh_cm",
        }
        for key in data
    ):
        access.profile.measurements_updated_at = datetime.now(UTC)
    access.profile.sqlmodel_update(data)
    access.profile.updated_at = datetime.now(UTC)
    session.add(access.profile)
    session.commit()
    session.refresh(access.profile)
    access.assignment = get_current_assignment(session, ctx.gym.id, current_user.id)
    return self_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=access.assignment,
    )


@router.post("", response_model=AthleteCreated)
def create_athlete(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: AthleteCreate,
) -> Any:
    coach_id = body.coach_user_id
    if not ctx.is_admin:
        coach_id = current_user.id
    if not coach_id:
        coach_id = current_user.id if "COACH" in ctx.roles else None
    if not coach_id:
        raise HTTPException(status_code=400, detail="coach_required")
    coach = _validate_coach(session, gym_id=ctx.gym.id, coach_user_id=coach_id)

    existing_user = session.exec(select(User).where(User.email == body.email)).first()
    if existing_user:
        existing_profile = session.exec(
            select(AthleteProfile).where(
                AthleteProfile.gym_id == ctx.gym.id,
                AthleteProfile.user_id == existing_user.id,
            )
        ).first()
        if existing_profile:
            raise HTTPException(status_code=409, detail="athlete_already_exists")

    activation = activate_user(
        session,
        email=body.email,
        full_name=body.full_name,
        gym=ctx.gym,
        method=body.activation_method,
        initial_password=body.initial_password,
    )
    membership = ensure_membership(
        session, gym_id=ctx.gym.id, user_id=activation.user.id
    )
    session.flush()
    roles = get_membership_roles(session, membership.id)
    if "ATHLETE" not in roles:
        session.add(GymMembershipRole(membership_id=membership.id, role="ATHLETE"))
    if not activation.user.full_name and body.full_name:
        activation.user.full_name = body.full_name
        session.add(activation.user)

    profile = AthleteProfile(
        gym_id=ctx.gym.id,
        user_id=activation.user.id,
        phone=body.phone,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        training_goal=body.training_goal,
        training_days=[],
    )
    session.add(profile)
    session.flush()
    assignment = CoachAssignment(
        gym_id=ctx.gym.id,
        athlete_user_id=activation.user.id,
        coach_user_id=coach.id,
        assigned_by_id=current_user.id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(profile)
    session.refresh(assignment)
    detail = staff_detail(
        session,
        profile=profile,
        user=activation.user,
        assignment=assignment,
    )
    return AthleteCreated(
        athlete=detail,
        initial_password=activation.initial_password,
        invitation_sent=activation.invitation_sent,
    )


@router.get("/{athlete_user_id}", response_model=AthleteDetail)
def read_athlete(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    if not (ctx.is_admin or access.is_current_coach):
        raise HTTPException(status_code=403, detail="athlete_staff_access_required")
    return staff_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=access.assignment,
    )


@router.patch("/{athlete_user_id}", response_model=AthleteDetail)
def update_athlete(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: AthleteProfileUpdate,
) -> Any:
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    if not access.can_edit_staff_fields:
        raise HTTPException(status_code=403, detail="athlete_staff_access_required")
    data = body.model_dump(exclude_unset=True)
    full_name = data.pop("full_name", None)
    if full_name is not None:
        access.user.full_name = full_name
        session.add(access.user)
    if any(
        key
        in {
            "height_cm",
            "weight_kg",
            "chest_cm",
            "waist_cm",
            "hips_cm",
            "arm_cm",
            "thigh_cm",
        }
        for key in data
    ):
        access.profile.measurements_updated_at = datetime.now(UTC)
    access.profile.sqlmodel_update(data)
    access.profile.updated_at = datetime.now(UTC)
    session.add(access.profile)
    session.commit()
    session.refresh(access.profile)
    access.assignment = get_current_assignment(session, ctx.gym.id, athlete_user_id)
    return staff_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=access.assignment,
    )


@router.post("/{athlete_user_id}/reassign-coach", response_model=AthleteDetail)
def reassign_coach(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: ReassignCoach,
) -> Any:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    access = get_athlete_access(session, ctx, current_user, athlete_user_id)
    coach = _validate_coach(
        session, gym_id=ctx.gym.id, coach_user_id=body.coach_user_id
    )
    current_assignment = get_current_assignment(session, ctx.gym.id, athlete_user_id)
    if current_assignment and current_assignment.coach_user_id == coach.id:
        raise HTTPException(status_code=400, detail="coach_unchanged")
    if current_assignment:
        current_assignment.ended_at = datetime.now(UTC)
        session.add(current_assignment)
        session.flush()
    assignment = CoachAssignment(
        gym_id=ctx.gym.id,
        athlete_user_id=athlete_user_id,
        coach_user_id=coach.id,
        assigned_by_id=current_user.id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return staff_detail(
        session,
        profile=access.profile,
        user=access.user,
        assignment=assignment,
    )


@router.post("/{athlete_user_id}/archive", response_model=Message)
def archive_athlete(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    now = datetime.now(UTC)
    access.profile.is_archived = True
    access.profile.updated_at = now
    assignment = get_current_assignment(session, ctx.gym.id, athlete_user_id)
    if assignment:
        assignment.ended_at = now
        session.add(assignment)
    roles = get_membership_roles(session, access.membership.id)
    if roles <= {"ATHLETE"}:
        access.membership.is_active = False
        session.add(access.membership)
    session.add(access.profile)
    session.commit()
    return Message(message="athlete_archived")


@router.get(
    "/{athlete_user_id}/body-files", response_model=list[BodyAnalysisFilePublic]
)
def list_body_files(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    get_athlete_access(session, ctx, current_user, athlete_user_id, allow_archived=True)
    return [
        body_file_public(row)
        for row in session.exec(
            select(BodyAnalysisFile)
            .where(
                BodyAnalysisFile.gym_id == ctx.gym.id,
                BodyAnalysisFile.athlete_user_id == athlete_user_id,
            )
            .order_by(col(BodyAnalysisFile.created_at).desc())
        ).all()
    ]


@router.post("/{athlete_user_id}/body-files", response_model=BodyAnalysisFilePublic)
async def upload_body_file(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    file: UploadFile = File(...),
) -> Any:
    get_athlete_access(session, ctx, current_user, athlete_user_id)
    original_name, stored_name, size = await save_body_analysis_upload(file)
    record = BodyAnalysisFile(
        gym_id=ctx.gym.id,
        athlete_user_id=athlete_user_id,
        uploaded_by_id=current_user.id,
        original_name=original_name,
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return body_file_public(record)


@router.get("/{athlete_user_id}/body-files/{file_id}/download")
def download_body_file(
    *,
    athlete_user_id: uuid.UUID,
    file_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    get_athlete_access(session, ctx, current_user, athlete_user_id, allow_archived=True)
    record = session.get(BodyAnalysisFile, file_id)
    if (
        not record
        or record.gym_id != ctx.gym.id
        or record.athlete_user_id != athlete_user_id
    ):
        raise HTTPException(status_code=404, detail="file_not_found")
    path = stored_file_path(record.stored_name)
    return FileResponse(
        path,
        media_type=record.content_type,
        filename=Path(record.original_name).name,
        content_disposition_type="attachment",
    )
