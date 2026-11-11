from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app.api.deps import (
    CurrentSuperuser,
    CurrentUser,
    GymContextDep,
    SessionDep,
    get_current_assignment,
)
from app.finance_models import (
    FinanceAuditPublic,
    FinanceCoachContractCreate,
    FinanceCoachContractPublic,
    FinanceCoachContractUpdate,
    FinanceCoachOptionPublic,
    FinanceCoachPlan,
    FinanceCoachPlanCreate,
    FinanceCoachPlanPublic,
    FinanceCoachPlanUpdate,
    FinancePaymentPublic,
    FinancePaymentSimulate,
    FinancePlanPurchaseCreate,
    FinancePlanPurchasePublic,
    FinancePlatformContractCreate,
    FinancePlatformContractPublic,
    FinancePlatformContractUpdate,
    FinancePlatformPolicyPublic,
    FinanceProgramRequestPublic,
    FinanceRefundCreate,
    FinanceRefundPublic,
    FinanceReportPublic,
    FinanceSaleCreate,
    FinanceSalePreviewPublic,
    FinanceSalePreviewRequest,
    FinanceSalePublic,
    FinanceSettlementCreate,
    FinanceSettlementPublic,
    FinanceTaxCreate,
    FinanceTaxPublic,
    FinanceTaxUpdate,
    FinanceTrainingOfferPublic,
)
from app.services import finance as finance_service

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get(
    "/platform-contracts",
    response_model=list[FinancePlatformContractPublic],
)
def list_platform_contracts(
    *,
    session: SessionDep,
    _current_user: CurrentSuperuser,
    scope: str | None = None,
    gym_id: uuid.UUID | None = None,
) -> Any:
    return finance_service.list_platform_contracts(session, scope=scope, gym_id=gym_id)


@router.post(
    "/platform-contracts",
    response_model=FinancePlatformContractPublic,
)
def create_platform_contract(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: FinancePlatformContractCreate,
) -> Any:
    return finance_service.create_platform_contract(
        session,
        actor=current_user,
        name=body.name,
        scope=body.scope,
        gym_id=body.gym_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        rates=[rate.model_dump() for rate in body.rates],
    )


@router.put(
    "/platform-contracts/{contract_id}",
    response_model=FinancePlatformContractPublic,
)
def update_platform_contract(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    contract_id: uuid.UUID,
    body: FinancePlatformContractUpdate,
) -> Any:
    return finance_service.update_platform_contract(
        session,
        actor=current_user,
        contract_id=contract_id,
        name=body.name,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        rates=[rate.model_dump() for rate in body.rates],
    )


@router.post(
    "/platform-contracts/{contract_id}/activate",
    response_model=FinancePlatformContractPublic,
)
def activate_platform_contract(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    contract_id: uuid.UUID,
) -> Any:
    return finance_service.activate_platform_contract(
        session, actor=current_user, contract_id=contract_id
    )


@router.post(
    "/platform-contracts/{contract_id}/archive",
    response_model=FinancePlatformContractPublic,
)
def archive_platform_contract(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    contract_id: uuid.UUID,
) -> Any:
    return finance_service.archive_platform_contract(
        session, actor=current_user, contract_id=contract_id
    )


@router.get("/platform-policy", response_model=FinancePlatformPolicyPublic)
def read_platform_policy(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    category: str,
    on_date: date | None = None,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.resolve_platform_policy(
        session,
        gym_id=gym_id,
        category=category,
        on_date=on_date or finance_service.finance_today(),
    )


@router.get("/taxes", response_model=list[FinanceTaxPublic])
def list_taxes(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    include_inactive: bool = False,
) -> Any:
    finance_service.require_any_finance_admin(session, current_user)
    return finance_service.list_taxes(
        session, include_inactive=include_inactive and current_user.is_superuser
    )


@router.post("/taxes", response_model=FinanceTaxPublic)
def create_tax(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    body: FinanceTaxCreate,
) -> Any:
    return finance_service.create_tax(
        session,
        actor=current_user,
        name=body.name,
        calculation=body.calculation,
        percent_bp=body.percent_bp,
        fixed_amount_irr=body.fixed_amount_irr,
        is_active=body.is_active,
        is_default_vat=body.is_default_vat,
    )


@router.patch("/taxes/{tax_id}", response_model=FinanceTaxPublic)
def update_tax(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    tax_id: uuid.UUID,
    body: FinanceTaxUpdate,
) -> Any:
    return finance_service.update_tax(
        session,
        actor=current_user,
        tax_id=tax_id,
        name=body.name,
        calculation=body.calculation,
        percent_bp=body.percent_bp,
        fixed_amount_irr=body.fixed_amount_irr,
        percent_provided="percent_bp" in body.model_fields_set,
        fixed_provided="fixed_amount_irr" in body.model_fields_set,
        is_active=body.is_active,
        is_default_vat=body.is_default_vat,
    )


@router.get("/overview", response_model=FinanceReportPublic)
def finance_overview(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    from_date: date,
    to_date: date,
    gym_id: uuid.UUID | None = None,
    category: str | None = None,
) -> Any:
    if not current_user.is_superuser:
        if gym_id is None:
            raise HTTPException(status_code=400, detail="gym_context_required")
        finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.finance_report(
        session,
        gym_id=gym_id,
        from_date=from_date,
        to_date=to_date,
        category=category,
    )


@router.get("/reports", response_model=FinanceReportPublic)
def finance_reports(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    from_date: date,
    to_date: date,
    gym_id: uuid.UUID | None = None,
    category: str | None = None,
) -> Any:
    if not current_user.is_superuser:
        if gym_id is None:
            raise HTTPException(status_code=400, detail="gym_context_required")
        finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.finance_report(
        session,
        gym_id=gym_id,
        from_date=from_date,
        to_date=to_date,
        category=category,
    )


@router.get("/reports/export")
def export_finance_report(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    from_date: date,
    to_date: date,
    gym_id: uuid.UUID | None = None,
    category: str | None = None,
) -> Any:
    if not current_user.is_superuser:
        if gym_id is None:
            raise HTTPException(status_code=400, detail="gym_context_required")
        finance_service.require_gym_finance_admin(session, current_user, gym_id)
    report = finance_service.finance_report(
        session,
        gym_id=gym_id,
        from_date=from_date,
        to_date=to_date,
        category=category,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in finance_service.report_csv_rows(report):
        writer.writerow(row)
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="finance-report.csv"'},
    )


@router.get(
    "/gyms/{gym_id}/coach-contracts",
    response_model=list[FinanceCoachContractPublic],
)
def list_coach_contracts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_coach_contracts(session, gym_id=gym_id)


@router.post(
    "/gyms/{gym_id}/coach-contracts",
    response_model=FinanceCoachContractPublic,
)
def create_coach_contract(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    body: FinanceCoachContractCreate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.create_coach_contract(
        session,
        actor=current_user,
        gym_id=gym_id,
        coach_user_id=body.coach_user_id,
        category=body.category,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        platform_bp=body.platform_bp,
        gym_bp=body.gym_bp,
        coach_bp=body.coach_bp,
    )


@router.put(
    "/gyms/{gym_id}/coach-contracts/{contract_id}",
    response_model=FinanceCoachContractPublic,
)
def update_coach_contract(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    contract_id: uuid.UUID,
    body: FinanceCoachContractUpdate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.update_coach_contract(
        session,
        actor=current_user,
        gym_id=gym_id,
        contract_id=contract_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        platform_bp=body.platform_bp,
        gym_bp=body.gym_bp,
        coach_bp=body.coach_bp,
    )


@router.post(
    "/gyms/{gym_id}/coach-contracts/{contract_id}/activate",
    response_model=FinanceCoachContractPublic,
)
def activate_coach_contract(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    contract_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.activate_coach_contract(
        session, actor=current_user, gym_id=gym_id, contract_id=contract_id
    )


@router.post(
    "/gyms/{gym_id}/coach-contracts/{contract_id}/archive",
    response_model=FinanceCoachContractPublic,
)
def archive_coach_contract(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    contract_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.archive_coach_contract(
        session, actor=current_user, gym_id=gym_id, contract_id=contract_id
    )


@router.get(
    "/gyms/{gym_id}/coach-plans",
    response_model=list[FinanceCoachPlanPublic],
)
def list_coach_plans(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    coach_user_id: uuid.UUID | None = None,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    if not ctx.is_admin:
        if coach_user_id is not None and coach_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="gym_admin_required")
        coach_user_id = current_user.id
    return finance_service.list_coach_plans(
        session, gym_id=gym_id, coach_user_id=coach_user_id
    )


@router.post(
    "/gyms/{gym_id}/coach-plans",
    response_model=FinanceCoachPlanPublic,
)
def create_coach_plan(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    body: FinanceCoachPlanCreate,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    coach_user_id = body.coach_user_id or current_user.id
    if not ctx.is_admin and coach_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    return finance_service.create_coach_plan(
        session,
        actor=current_user,
        gym_id=gym_id,
        coach_user_id=coach_user_id,
        title=body.title,
        description=body.description,
        base_price_irr=body.base_price_irr,
        is_active=body.is_active,
    )


@router.put(
    "/gyms/{gym_id}/coach-plans/{plan_id}",
    response_model=FinanceCoachPlanPublic,
)
def update_coach_plan(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: FinanceCoachPlanUpdate,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    plan = session.get(FinanceCoachPlan, plan_id)
    if plan is None or plan.gym_id != gym_id:
        raise HTTPException(status_code=404, detail="coach_plan_not_found")
    if not ctx.is_admin and plan.coach_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="gym_admin_required")
    return finance_service.update_coach_plan(
        session,
        actor=current_user,
        gym_id=gym_id,
        plan_id=plan_id,
        title=body.title,
        description=body.description,
        base_price_irr=body.base_price_irr,
        is_active=body.is_active,
    )


@router.get(
    "/gyms/{gym_id}/athlete/training-offer",
    response_model=FinanceTrainingOfferPublic | None,
)
def read_athlete_training_offer(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_athlete:
        raise HTTPException(status_code=403, detail="athlete_access_required")
    assignment = get_current_assignment(session, gym_id, current_user.id)
    if assignment is None:
        return None
    return finance_service.training_plan_offer(
        session, gym_id=gym_id, coach_user_id=assignment.coach_user_id
    )


@router.post(
    "/gyms/{gym_id}/athlete/training-purchases",
    response_model=FinancePlanPurchasePublic,
)
def purchase_athlete_training_plan(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
    body: FinancePlanPurchaseCreate,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_athlete:
        raise HTTPException(status_code=403, detail="athlete_access_required")
    assignment = get_current_assignment(session, gym_id, current_user.id)
    if assignment is None:
        raise HTTPException(status_code=400, detail="current_coach_required")
    return finance_service.purchase_training_plan(
        session,
        actor=current_user,
        gym_id=gym_id,
        athlete_user_id=current_user.id,
        coach_user_id=assignment.coach_user_id,
        plan_id=body.plan_id,
        note=body.note,
        idempotency_key=body.idempotency_key,
        outcome=body.outcome,
        quote_token=body.quote_token,
    )


@router.get(
    "/gyms/{gym_id}/athlete/program-requests",
    response_model=list[FinanceProgramRequestPublic],
)
def list_athlete_program_requests(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_athlete:
        raise HTTPException(status_code=403, detail="athlete_access_required")
    return finance_service.list_program_requests(
        session, gym_id=gym_id, athlete_user_id=current_user.id
    )


@router.get(
    "/gyms/{gym_id}/program-requests",
    response_model=list[FinanceProgramRequestPublic],
)
def list_gym_program_requests(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    ctx: GymContextDep,
    gym_id: uuid.UUID,
) -> Any:
    if ctx.gym.id != gym_id or not ctx.is_staff:
        raise HTTPException(status_code=403, detail="gym_staff_required")
    coach_user_id = None if ctx.is_admin else current_user.id
    return finance_service.list_program_requests(
        session, gym_id=gym_id, coach_user_id=coach_user_id
    )


@router.get(
    "/gyms/{gym_id}/coaches",
    response_model=list[FinanceCoachOptionPublic],
)
def list_gym_coaches(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    with_balance: bool = False,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_gym_coaches(
        session, gym_id=gym_id, with_balance=with_balance
    )


@router.get(
    "/gyms/{gym_id}/sales",
    response_model=list[FinanceSalePublic],
)
def list_sales(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    category: str | None = None,
    status: str | None = None,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_sales(
        session,
        gym_id=gym_id,
        from_date=from_date,
        to_date=to_date,
        category=category,
        status=status,
    )


@router.post(
    "/gyms/{gym_id}/sales/preview",
    response_model=FinanceSalePreviewPublic,
)
def preview_sale(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    body: FinanceSalePreviewRequest,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.preview_sale(
        session,
        gym_id=gym_id,
        category=body.category,
        base_amount_irr=body.base_amount_irr,
        tax_ids=body.tax_ids,
        coach_user_id=body.coach_user_id,
        sold_on=body.sold_on,
    )


@router.post(
    "/gyms/{gym_id}/sales",
    response_model=FinanceSalePublic,
)
def create_sale(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    body: FinanceSaleCreate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    sale = finance_service.create_sale(
        session,
        actor=current_user,
        gym_id=gym_id,
        category=body.category,
        description=body.description,
        base_amount_irr=body.base_amount_irr,
        tax_ids=body.tax_ids,
        coach_user_id=body.coach_user_id,
        sold_on=body.sold_on,
    )
    return finance_service.sale_public(session, sale)


@router.get(
    "/gyms/{gym_id}/sales/{sale_id}",
    response_model=FinanceSalePublic,
)
def read_sale(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    sale_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.sale_public(
        session,
        finance_service.get_sale(session, gym_id=gym_id, sale_id=sale_id),
    )


@router.post(
    "/gyms/{gym_id}/sales/{sale_id}/payments",
    response_model=FinancePaymentPublic,
)
def simulate_payment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    sale_id: uuid.UUID,
    body: FinancePaymentSimulate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.simulate_payment(
        session,
        actor=current_user,
        gym_id=gym_id,
        sale_id=sale_id,
        outcome=body.outcome,
        idempotency_key=body.idempotency_key,
        note=body.note,
    )


@router.get(
    "/gyms/{gym_id}/payments",
    response_model=list[FinancePaymentPublic],
)
def list_payments(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_payments(session, gym_id=gym_id)


@router.post(
    "/gyms/{gym_id}/payments/{payment_id}/refunds",
    response_model=FinanceRefundPublic,
)
def create_refund(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: FinanceRefundCreate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.create_refund(
        session,
        actor=current_user,
        gym_id=gym_id,
        payment_id=payment_id,
        amount_irr=body.amount_irr,
        idempotency_key=body.idempotency_key,
        reason=body.reason,
    )


@router.get(
    "/gyms/{gym_id}/settlements",
    response_model=list[FinanceSettlementPublic],
)
def list_settlements(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_settlements(session, gym_id=gym_id)


@router.post(
    "/gyms/{gym_id}/settlements",
    response_model=FinanceSettlementPublic,
)
def create_settlement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    body: FinanceSettlementCreate,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.create_settlement(
        session,
        actor=current_user,
        gym_id=gym_id,
        party=body.party,
        party_user_id=body.party_user_id,
        amount_irr=body.amount_irr,
        idempotency_key=body.idempotency_key,
    )


@router.post(
    "/gyms/{gym_id}/settlements/{settlement_id}/complete",
    response_model=FinanceSettlementPublic,
)
def complete_settlement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    settlement_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.complete_settlement(
        session, actor=current_user, gym_id=gym_id, settlement_id=settlement_id
    )


@router.post(
    "/gyms/{gym_id}/settlements/{settlement_id}/cancel",
    response_model=FinanceSettlementPublic,
)
def cancel_settlement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
    settlement_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.cancel_settlement(
        session, actor=current_user, gym_id=gym_id, settlement_id=settlement_id
    )


@router.post(
    "/gyms/{gym_id}/settlements/auto",
    response_model=list[FinanceSettlementPublic],
)
def auto_settle(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.auto_settle(session, actor=current_user, gym_id=gym_id)


@router.get(
    "/gyms/{gym_id}/audit",
    response_model=list[FinanceAuditPublic],
)
def list_audit(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    gym_id: uuid.UUID,
) -> Any:
    finance_service.require_gym_finance_admin(session, current_user, gym_id)
    return finance_service.list_audit(session, gym_id=gym_id)
