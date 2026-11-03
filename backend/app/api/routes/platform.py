from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from app.api.deps import CurrentSuperuser, SessionDep
from app.platform_models import (
    PlatformPlanCreate,
    PlatformPlanPublic,
    PlatformPlansPublic,
    PlatformPlanUsagePublic,
    PlatformPlanVersion,
    PlatformPlanVersionCreate,
    PlatformPlanVersionPublic,
)
from app.services import platform as platform_service

router = APIRouter(prefix="/platform", tags=["platform"])


def _idempotency_key(value: str | None) -> str:
    if not value:
        raise HTTPException(
            status_code=400, detail="idempotency_key_required"
        )
    return value


@router.get("/plans", response_model=PlatformPlansPublic)
def read_platform_plans(
    *, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.list_plans(session)


@router.post("/plans", response_model=PlatformPlanPublic)
def create_platform_plan(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformPlanCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.create_plan(
        session,
        actor=current_user,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.get("/plans/{plan_id}", response_model=PlatformPlanPublic)
def read_platform_plan(
    *, plan_id: uuid.UUID, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.get_plan(session, plan_id)


@router.post(
    "/plans/{plan_id}/versions",
    response_model=PlatformPlanVersionPublic,
)
def create_platform_plan_version(
    *,
    plan_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformPlanVersionCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.create_plan_version(
        session,
        actor=current_user,
        plan_id=plan_id,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/plans/{plan_id}/versions/{version_id}/activate",
    response_model=PlatformPlanVersionPublic,
)
def activate_platform_plan_version(
    *,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.activate_plan_version(
        session,
        actor=current_user,
        plan_id=plan_id,
        version_id=version_id,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/plans/{plan_id}/versions/{version_id}/retire",
    response_model=PlatformPlanVersionPublic,
)
def retire_platform_plan_version(
    *,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.retire_plan_version(
        session,
        actor=current_user,
        plan_id=plan_id,
        version_id=version_id,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.get(
    "/plans/{plan_id}/versions/{version_id}/usage",
    response_model=PlatformPlanUsagePublic,
)
def read_platform_plan_usage(
    *,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentSuperuser,
) -> Any:
    version = session.get(PlatformPlanVersion, version_id)
    if version is None or version.plan_id != plan_id:
        raise HTTPException(
            status_code=404, detail="platform_plan_version_not_found"
        )
    return platform_service.plan_usage(session, plan_version_id=version_id)
