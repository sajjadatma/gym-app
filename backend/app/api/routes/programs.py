from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.deps import (
    AthleteAccess,
    CurrentUser,
    GymContextDep,
    SessionDep,
    get_athlete_access,
)
from app.core.audit import audit
from app.models import (
    Message,
    ProgramTemplate,
    ProgramTemplateDetail,
    ProgramVersionCreate,
    ProgramVersionDetail,
    ProgramVersionsPublic,
    ProgramVersionSummary,
    ProgramVersionUpdate,
    SaveAsTemplate,
    User,
    WorkoutProgram,
    WorkoutProgramVersion,
)
from app.services.programs import (
    bump_version_revision,
    create_version_with_allocated_number,
    ensure_publishable,
    ensure_staff_write,
    get_or_create_program,
    insert_structure,
    load_version_context,
    normalize_days,
    replace_version_days,
    structure_from_version,
    template_days_input,
    version_detail,
    version_summary,
)

router = APIRouter(tags=["programs"])


def _staff_access(
    *,
    session: Session,
    ctx: GymContextDep,
    current_user: CurrentUser,
    athlete_user_id: uuid.UUID,
) -> AthleteAccess:
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    if not access.can_edit_staff_fields:
        raise HTTPException(status_code=403, detail="program_edit_forbidden")
    if access.profile.is_archived:
        raise HTTPException(status_code=409, detail="athlete_archived")
    return access


@router.get(
    "/athletes/{athlete_user_id}/programs",
    response_model=ProgramVersionsPublic,
)
def list_programs(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    access = get_athlete_access(
        session, ctx, current_user, athlete_user_id, allow_archived=True
    )
    program = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == ctx.gym.id,
            WorkoutProgram.athlete_user_id == athlete_user_id,
        )
    ).first()
    if not program:
        return ProgramVersionsPublic(data=[], count=0)
    versions = session.exec(
        select(WorkoutProgramVersion)
        .where(WorkoutProgramVersion.program_id == program.id)
        .order_by(col(WorkoutProgramVersion.version_number).desc())
    ).all()
    show_drafts = ctx.is_admin or access.is_current_coach
    athlete = session.get(User, athlete_user_id)
    data: list[ProgramVersionSummary] = []
    for version in versions:
        if version.status == "DRAFT" and not show_drafts:
            continue
        data.append(version_summary(session, version, program, athlete))
    return ProgramVersionsPublic(data=data, count=len(data))


@router.post(
    "/athletes/{athlete_user_id}/programs",
    response_model=ProgramVersionDetail,
)
def create_program(
    *,
    athlete_user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: ProgramVersionCreate,
) -> Any:
    _staff_access(
        session=session,
        ctx=ctx,
        current_user=current_user,
        athlete_user_id=athlete_user_id,
    )
    program = get_or_create_program(
        session,
        gym_id=ctx.gym.id,
        athlete_user_id=athlete_user_id,
        created_by_id=current_user.id,
    )
    version = create_version_with_allocated_number(
        session,
        program_id=program.id,
        title=body.title,
        goal=body.goal,
        notes=body.notes,
        start_date=body.start_date,
        end_date=body.end_date,
        coach_id=current_user.id,
        coach_name=current_user.full_name or current_user.email,
    )

    if body.template_id:
        template = session.get(ProgramTemplate, body.template_id)
        if not template or template.gym_id != ctx.gym.id:
            raise HTTPException(status_code=404, detail="template_not_found")
        if not ctx.is_admin and template.created_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="template_access_forbidden")
        structure = normalize_days(
            session,
            gym_id=ctx.gym.id,
            days=template_days_input(template),
        )
        insert_structure(session, version_id=version.id, structure=structure)

    session.commit()
    session.refresh(version)
    return version_detail(session, version, program)


@router.get(
    "/program-versions/{version_id}",
    response_model=ProgramVersionDetail,
)
def read_program_version(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    version, program, _access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    return version_detail(session, version, program)


@router.put(
    "/program-versions/{version_id}",
    response_model=ProgramVersionDetail,
)
def update_program_version(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: ProgramVersionUpdate,
) -> Any:
    version, program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    if version.status == "ARCHIVED":
        raise HTTPException(status_code=400, detail="archived_program_is_read_only")
    bump_version_revision(
        session, version=version, expected_revision=body.expected_revision
    )
    version.sqlmodel_update(
        {
            "title": body.title,
            "goal": body.goal,
            "notes": body.notes,
            "start_date": body.start_date,
            "end_date": body.end_date,
        }
    )
    session.add(version)
    replace_version_days(
        session,
        version=version,
        days=body.days,
        gym_id=ctx.gym.id,
        athlete_user_id=program.athlete_user_id,
    )
    session.commit()
    session.refresh(version)
    return version_detail(session, version, program)


@router.delete(
    "/program-versions/{version_id}",
    response_model=Message,
)
def delete_program_version(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    version, _program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    session.delete(version)
    session.commit()
    audit(
        "program_version.deleted",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=version_id,
    )
    return Message(message="program_version_deleted")


@router.post(
    "/program-versions/{version_id}/new-draft",
    response_model=ProgramVersionDetail,
)
def create_new_draft(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    source, program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    version = create_version_with_allocated_number(
        session,
        program_id=program.id,
        title=source.title,
        goal=source.goal,
        notes=source.notes,
        start_date=source.start_date,
        end_date=source.end_date,
        coach_id=current_user.id,
        coach_name=current_user.full_name or current_user.email,
    )
    insert_structure(
        session,
        version_id=version.id,
        structure=structure_from_version(session, source),
    )
    session.commit()
    session.refresh(version)
    return version_detail(session, version, program)


@router.post(
    "/program-versions/{version_id}/publish",
    response_model=ProgramVersionDetail,
)
def publish_program_version(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    version, program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    if version.status != "DRAFT":
        raise HTTPException(status_code=400, detail="only_drafts_can_be_published")
    structure = structure_from_version(session, version)
    ensure_publishable(structure)
    active = session.exec(
        select(WorkoutProgramVersion).where(
            WorkoutProgramVersion.program_id == program.id,
            WorkoutProgramVersion.status == "ACTIVE",
        )
    ).all()
    now = datetime.now(UTC)
    for old in active:
        old.status = "ARCHIVED"
        old.archived_at = now
        session.add(old)
    session.flush()
    version.status = "ACTIVE"
    version.published_at = now
    version.archived_at = None
    session.add(version)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="active_program_conflict") from exc
    session.refresh(version)
    audit(
        "program_version.published",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=version_id,
    )
    return version_detail(session, version, program)


@router.post(
    "/program-versions/{version_id}/archive",
    response_model=ProgramVersionDetail,
)
def archive_program_version(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
) -> Any:
    version, program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    if version.status == "ARCHIVED":
        raise HTTPException(status_code=400, detail="already_archived")
    version.status = "ARCHIVED"
    version.archived_at = datetime.now(UTC)
    session.add(version)
    session.commit()
    audit(
        "program_version.archived",
        actor_id=current_user.id,
        gym_id=ctx.gym.id,
        target_id=version_id,
    )
    session.refresh(version)
    return version_detail(session, version, program)


@router.post(
    "/program-versions/{version_id}/save-as-template",
    response_model=ProgramTemplateDetail,
)
def save_as_template(
    *,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    body: SaveAsTemplate,
) -> Any:
    version, _program, access = load_version_context(
        session,
        ctx=ctx,
        current_user=current_user,
        version_id=version_id,
    )
    ensure_staff_write(access)
    template = ProgramTemplate(
        gym_id=ctx.gym.id,
        created_by_id=current_user.id,
        created_by_name=current_user.full_name or current_user.email,
        name=body.name,
        goal=body.goal or version.goal,
        notes=body.notes or version.notes,
        content={"days": structure_from_version(session, version)},
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    from app.services.programs import template_detail_model

    return template_detail_model(template)
