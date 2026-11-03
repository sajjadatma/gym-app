from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from app.api.deps import CurrentSuperuser, SessionDep
from app.platform_models import (
    PlatformAgreementCreate,
    PlatformAgreementPublic,
    PlatformAgreementsPublic,
    PlatformGroupCreate,
    PlatformGroupMemberInput,
    PlatformGroupPublic,
    PlatformGroupsPublic,
    PlatformInvoiceCancelCreate,
    PlatformInvoiceCreate,
    PlatformInvoicePublic,
    PlatformInvoicesPublic,
    PlatformPaymentCreate,
    PlatformPaymentPublic,
    PlatformPaymentsPublic,
    PlatformPlanCreate,
    PlatformPlanPublic,
    PlatformPlansPublic,
    PlatformPlanUsagePublic,
    PlatformPlanVersion,
    PlatformPlanVersionCreate,
    PlatformPlanVersionPublic,
    PlatformReceivablePublic,
    PlatformReceivablesPublic,
    PlatformRemindersPublic,
    PlatformStandingPublic,
    PlatformSubscriptionAccrual,
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


@router.get("/groups", response_model=PlatformGroupsPublic)
def read_platform_groups(
    *, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.list_groups(session)


@router.post("/groups", response_model=PlatformGroupPublic)
def create_platform_group(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformGroupCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.create_group(
        session,
        actor=current_user,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/groups/{group_id}/members",
    response_model=PlatformGroupPublic,
)
def update_platform_group_member(
    *,
    group_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformGroupMemberInput,
) -> Any:
    return platform_service.add_group_member(
        session,
        actor=current_user,
        group_id=group_id,
        gym_id=body.gym_id,
        allocation_bp=body.allocation_bp,
    )


@router.get("/agreements", response_model=PlatformAgreementsPublic)
def read_platform_agreements(
    *, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.list_agreements(session)


@router.post("/agreements", response_model=PlatformAgreementPublic)
def create_platform_agreement(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformAgreementCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.create_agreement(
        session,
        actor=current_user,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/agreements/{agreement_id}/activate",
    response_model=PlatformAgreementPublic,
)
def activate_platform_agreement(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.activate_agreement(
        session,
        actor=current_user,
        agreement_id=agreement_id,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/agreements/{agreement_id}/disable",
    response_model=PlatformAgreementPublic,
)
def disable_platform_agreement(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.disable_agreement(
        session,
        actor=current_user,
        agreement_id=agreement_id,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.get("/receivables", response_model=PlatformReceivablesPublic)
def read_platform_receivables(
    *,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    gym_id: uuid.UUID | None = None,
) -> Any:
    return platform_service.list_receivables(session, gym_id=gym_id)


@router.post(
    "/agreements/{agreement_id}/accrue-period",
    response_model=PlatformReceivablePublic,
)
def accrue_platform_subscription(
    *,
    agreement_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformSubscriptionAccrual,
    branch_gym_id: uuid.UUID | None = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.accrue_subscription_period(
        session,
        actor=current_user,
        agreement_id=agreement_id,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
        branch_gym_id=branch_gym_id,
    )


@router.get("/invoices", response_model=PlatformInvoicesPublic)
def read_platform_invoices(
    *, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.list_platform_invoices(session)


@router.post("/invoices", response_model=PlatformInvoicePublic)
def issue_platform_invoice(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformInvoiceCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.issue_platform_invoice(
        session,
        actor=current_user,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.get("/invoices/{invoice_id}", response_model=PlatformInvoicePublic)
def read_platform_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentSuperuser,
) -> Any:
    return platform_service.get_platform_invoice(session, invoice_id)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PlatformPaymentPublic,
)
def record_platform_invoice_payment(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformPaymentCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.record_platform_payment(
        session,
        actor=current_user,
        invoice_id=invoice_id,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=PlatformInvoicePublic,
)
def cancel_platform_invoice(
    *,
    invoice_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: PlatformInvoiceCancelCreate,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
) -> Any:
    return platform_service.cancel_platform_invoice(
        session,
        actor=current_user,
        invoice_id=invoice_id,
        body=body,
        operation_key=_idempotency_key(idempotency_key),
    )


@router.get("/payments", response_model=PlatformPaymentsPublic)
def read_platform_payments(
    *, session: SessionDep, _current_user: CurrentSuperuser
) -> Any:
    return platform_service.list_platform_payments(session)


@router.get("/dues", response_model=list[PlatformStandingPublic])
def read_platform_dues(
    *,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    as_of: date | None = None,
) -> Any:
    return platform_service.list_platform_dues(session, as_of=as_of)


@router.get("/dues/{gym_id}", response_model=PlatformStandingPublic)
def read_platform_gym_dues(
    *,
    gym_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    as_of: date | None = None,
) -> Any:
    return platform_service.platform_standing(session, gym_id=gym_id, as_of=as_of)


@router.get("/reminders", response_model=PlatformRemindersPublic)
def read_platform_reminders(
    *,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    as_of: date | None = None,
    within_days: int = 7,
) -> Any:
    return platform_service.list_platform_reminders(
        session, as_of=as_of, within_days=within_days
    )
