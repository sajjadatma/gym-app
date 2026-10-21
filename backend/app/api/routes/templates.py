from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, select

from app.api.deps import (
    CurrentUser,
    GymContext,
    GymStaffDep,
    SessionDep,
    get_athlete_access,
)
from app.models import (
    ApplyTemplate,
    ProgramTemplate,
    ProgramTemplateCreate,
    ProgramTemplateDetail,
    ProgramTemplatesPublic,
    ProgramTemplateSummary,
    ProgramTemplateUpdate,
    ProgramVersionDetail,
    WorkoutProgramVersion,
)
from app.services.programs import (
    get_or_create_program,
    insert_structure,
    next_version_number,
    normalize_days,
    template_days_input,
    template_detail_model,
    template_summary,
    version_detail,
)

router = APIRouter(prefix="/templates", tags=["templates"])


def _template_access(
    session: Session,
    ctx: GymContext,
    current_user: CurrentUser,
    template_id: uuid.UUID,
) -> ProgramTemplate:
    template = session.get(ProgramTemplate, template_id)
    if not template or template.gym_id != ctx.gym.id:
        raise HTTPException(status_code=404, detail="template_not_found")
    if not ctx.is_admin and template.created_by_id != current_user.id:
        raise HTTPException(status_code=404, detail="template_not_found")
    return template


@router.get("", response_model=ProgramTemplatesPublic)
def list_templates(
    *, session: SessionDep, current_user: CurrentUser, ctx: GymStaffDep
) -> Any:
    statement = select(ProgramTemplate).where(ProgramTemplate.gym_id == ctx.gym.id)
    if not ctx.is_admin:
        statement = statement.where(ProgramTemplate.created_by_id == current_user.id)
    templates = session.exec(
        statement.order_by(col(ProgramTemplate.updated_at).desc())
    ).all()
    data: list[ProgramTemplateSummary] = [
        template_summary(template) for template in templates
    ]
    return ProgramTemplatesPublic(data=data, count=len(data))


@router.post("", response_model=ProgramTemplateDetail)
def create_template(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: ProgramTemplateCreate,
) -> Any:
    structure = normalize_days(session, gym_id=ctx.gym.id, days=body.days)
    template = ProgramTemplate(
        gym_id=ctx.gym.id,
        created_by_id=current_user.id,
        created_by_name=current_user.full_name or current_user.email,
        name=body.name,
        goal=body.goal,
        notes=body.notes,
        content={"days": structure},
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template_detail_model(template)


@router.get("/{template_id}", response_model=ProgramTemplateDetail)
def read_template(
    *,
    template_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
) -> Any:
    template = _template_access(session, ctx, current_user, template_id)
    return template_detail_model(template)


@router.put("/{template_id}", response_model=ProgramTemplateDetail)
def update_template(
    *,
    template_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: ProgramTemplateUpdate,
) -> Any:
    template = _template_access(session, ctx, current_user, template_id)
    structure = normalize_days(session, gym_id=ctx.gym.id, days=body.days)
    template.sqlmodel_update(
        {
            "name": body.name,
            "goal": body.goal,
            "notes": body.notes,
            "content": {"days": structure},
            "updated_at": datetime.now(UTC),
        }
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template_detail_model(template)


@router.post("/{template_id}/apply", response_model=ProgramVersionDetail)
def apply_template(
    *,
    template_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymStaffDep,
    body: ApplyTemplate,
) -> Any:
    template = _template_access(session, ctx, current_user, template_id)
    access = get_athlete_access(
        session, ctx, current_user, body.athlete_user_id, allow_archived=True
    )
    if not access.can_edit_staff_fields:
        raise HTTPException(status_code=403, detail="program_edit_forbidden")
    program = get_or_create_program(
        session,
        gym_id=ctx.gym.id,
        athlete_user_id=body.athlete_user_id,
        created_by_id=current_user.id,
    )
    version = WorkoutProgramVersion(
        program_id=program.id,
        version_number=next_version_number(session, program.id),
        status="DRAFT",
        title=template.name,
        goal=template.goal,
        notes=template.notes,
        coach_id=current_user.id,
        coach_name=current_user.full_name or current_user.email,
    )
    session.add(version)
    session.flush()
    structure = normalize_days(
        session, gym_id=ctx.gym.id, days=template_days_input(template)
    )
    insert_structure(session, version_id=version.id, structure=structure)
    session.commit()
    session.refresh(version)
    return version_detail(session, version, program)
