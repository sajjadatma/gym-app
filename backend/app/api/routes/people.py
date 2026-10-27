from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    BodyAnalysisFile,
    Gym,
    GymMembership,
    PersonOverview,
    User,
)
from app.services.access import get_membership_roles
from app.services.people import build_person_overview
from app.services.storage import (
    object_storage_enabled,
    read_stored_file,
    stored_file_path,
)

router = APIRouter(prefix="/people", tags=["people"])


def _authorized_gym(
    session: Session, current_user: User, gym_id: uuid.UUID
) -> Gym:
    gym = session.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="gym_not_found")
    if current_user.is_superuser:
        return gym
    if not gym.is_active:
        raise HTTPException(status_code=404, detail="gym_not_found")
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym.id,
            GymMembership.user_id == current_user.id,
        )
    ).first()
    if not membership or not membership.is_active:
        raise HTTPException(status_code=403, detail="not_a_gym_member")
    if (
        gym.owner_id != current_user.id
        and "GYM_ADMIN" not in get_membership_roles(session, membership.id)
    ):
        raise HTTPException(status_code=403, detail="gym_admin_required")
    return gym


@router.get("/{user_id}/overview", response_model=PersonOverview)
def read_person_overview(
    *,
    user_id: uuid.UUID,
    gym_id: uuid.UUID = Query(),
    kind: Literal["ATHLETE", "COACH"] = Query(),
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    gym = _authorized_gym(session, current_user, gym_id)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="person_not_found")
    return build_person_overview(
        session,
        gym=gym,
        user=user,
        kind=kind,
        all_gyms=current_user.is_superuser,
    )


@router.get("/{user_id}/body-files/{file_id}")
def download_person_body_file(
    *,
    user_id: uuid.UUID,
    file_id: uuid.UUID,
    gym_id: uuid.UUID = Query(),
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    gym = _authorized_gym(session, current_user, gym_id)
    record = session.get(BodyAnalysisFile, file_id)
    if (
        not record
        or record.gym_id != gym.id
        or record.athlete_user_id != user_id
    ):
        raise HTTPException(status_code=404, detail="file_not_found")
    if object_storage_enabled():
        filename = Path(record.original_name).name
        return Response(
            content=read_stored_file(record.stored_name),
            media_type=record.content_type,
            headers={
                "Content-Disposition": (
                    "attachment; filename*=UTF-8''" + quote(filename)
                )
            },
        )
    path = stored_file_path(record.stored_name)
    return FileResponse(
        path,
        media_type=record.content_type,
        filename=Path(record.original_name).name,
        content_disposition_type="attachment",
    )
