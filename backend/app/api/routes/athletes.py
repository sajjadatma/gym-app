from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import exists, or_
from sqlmodel import col, select

from app.api.deps import (
    CurrentUser,
    GymAdminDep,
    GymContextDep,
    GymStaffDep,
    SessionDep,
    get_athlete_access,
    get_current_assignment,
)
from app.models import (
    ActivationMethod,
    AthleteCreate,
    AthleteCreated,
    AthleteDetail,
    AthleteImportPreview,
    AthleteImportResult,
    AthleteProfile,
    AthleteProfileUpdate,
    AthleteRestore,
    AthleteSelfDetail,
    AthleteSelfUpdate,
    AthletesPublic,
    BodyAnalysisFile,
    BodyAnalysisFilePublic,
    CoachAssignment,
    GymMembership,
    Message,
    ReassignCoach,
    User,
)
from app.services.athlete_import import (
    MAX_IMPORT_BYTES,
    build_template_csv,
    build_template_xlsx,
)
from app.services.athlete_import import (
    import_athletes as import_athletes_service,
)
from app.services.athlete_import import (
    preview_athlete_import as preview_athlete_import_service,
)
from app.services.athlete_lifecycle import (
    archive_athlete_record,
    create_athlete_record,
    delete_athlete_record,
    restore_athlete_record,
)
from app.services.athlete_lifecycle import (
    validate_coach as _validate_coach,
)
from app.services.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    paginate,
)
from app.services.profiles import (
    athlete_summaries_page,
    body_file_public,
    self_detail,
    staff_detail,
)
from app.services.storage import (
    delete_stored_files,
    save_body_analysis_upload,
    stored_file_path,
)

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.get("", response_model=AthletesPublic)
def list_athletes(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    q: str = Query(default="", max_length=255),
    include_archived: bool = False,
    is_archived: bool | None = None,
    assigned_to_me: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Any:
    archived_scope = is_archived is True or (
        is_archived is None and include_archived
    )
    if archived_scope and not ctx.is_admin:
        raise HTTPException(status_code=403, detail="gym_admin_required")

    statement = (
        select(AthleteProfile, User, GymMembership)
        .join(User, col(User.id) == col(AthleteProfile.user_id))
        .join(
            GymMembership,
            (col(GymMembership.gym_id) == col(AthleteProfile.gym_id))
            & (col(GymMembership.user_id) == col(AthleteProfile.user_id)),
        )
        .where(AthleteProfile.gym_id == ctx.gym.id)
    )

    if is_archived is not None:
        statement = statement.where(
            col(AthleteProfile.is_archived).is_(is_archived)
        )
    elif not include_archived:
        statement = statement.where(
            col(AthleteProfile.is_archived).is_(False)
        )

    if is_archived is not True:
        if is_archived is None and include_archived:
            statement = statement.where(
                or_(
                    col(GymMembership.is_active).is_(True),
                    col(AthleteProfile.is_archived).is_(True),
                )
            )
        else:
            statement = statement.where(
                col(GymMembership.is_active).is_(True)
            )

    if assigned_to_me or not ctx.is_admin:
        statement = statement.where(
            exists(
                select(CoachAssignment.id).where(
                    CoachAssignment.gym_id == ctx.gym.id,
                    CoachAssignment.coach_user_id == current_user.id,
                    CoachAssignment.athlete_user_id
                    == AthleteProfile.user_id,
                    col(CoachAssignment.ended_at).is_(None),
                )
            )
        )

    term = q.strip()
    if term:
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                col(User.email).ilike(pattern),
                col(User.full_name).ilike(pattern),
                col(AthleteProfile.phone).ilike(pattern),
            )
        )

    statement = statement.order_by(
        col(AthleteProfile.created_at).desc(),
        col(AthleteProfile.user_id),
    )
    rows, total = paginate(
        session, statement, offset=offset, limit=limit
    )
    summaries = athlete_summaries_page(
        session, gym_id=ctx.gym.id, rows=rows
    )
    return AthletesPublic(data=summaries, count=total)


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
    return create_athlete_record(
        session=session, current_user=current_user, ctx=ctx, body=body
    )


async def _read_import_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="import_file_too_large")
    return content


@router.get("/import/template")
def download_athlete_import_template(
    *,
    session: SessionDep,
    ctx: GymAdminDep,
    file_format: Literal["csv", "xlsx"] = Query("csv"),
) -> Response:
    if file_format == "xlsx":
        content = build_template_xlsx(session, ctx.gym.id)
        filename = "athlete-import-template.xlsx"
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        content = build_template_csv()
        filename = "athlete-import-template.csv"
        media_type = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/preview", response_model=AthleteImportPreview)
async def preview_athlete_import(
    *,
    session: SessionDep,
    ctx: GymAdminDep,
    file: UploadFile = File(...),
    default_coach_user_id: uuid.UUID | None = Form(None),
) -> Any:
    return preview_athlete_import_service(
        session,
        gym_id=ctx.gym.id,
        filename=file.filename or "",
        content=await _read_import_upload(file),
        default_coach_user_id=default_coach_user_id,
    )


@router.post("/import", response_model=AthleteImportResult)
async def bulk_import_athletes(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymAdminDep,
    file: UploadFile = File(...),
    default_coach_user_id: uuid.UUID | None = Form(None),
    activation_method: ActivationMethod = Form("invite"),
    initial_password: str | None = Form(None),
) -> Any:
    return import_athletes_service(
        session,
        gym=ctx.gym,
        current_user=current_user,
        filename=file.filename or "",
        content=await _read_import_upload(file),
        default_coach_user_id=default_coach_user_id,
        activation_method=activation_method,
        initial_password=initial_password,
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
    if access.profile.is_archived:
        raise HTTPException(status_code=409, detail="athlete_archived")
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
    return archive_athlete_record(
        session=session,
        current_user=current_user,
        ctx=ctx,
        athlete_user_id=athlete_user_id,
    )



@router.post("/{athlete_user_id}/restore", response_model=AthleteDetail)
def restore_athlete(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: AthleteRestore | None = None,
) -> Any:
    return restore_athlete_record(
        session=session,
        current_user=current_user,
        ctx=ctx,
        athlete_user_id=athlete_user_id,
        body=body,
    )


@router.delete("/{athlete_user_id}", response_model=Message)
def delete_athlete(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    return delete_athlete_record(
        session=session,
        current_user=current_user,
        ctx=ctx,
        athlete_user_id=athlete_user_id,
    )


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
    try:
        session.commit()
    except Exception:
        # The file was written before the row. If the row cannot be committed,
        # remove the file so repeated failures do not accumulate orphans.
        session.rollback()
        delete_stored_files([stored_name])
        raise
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
