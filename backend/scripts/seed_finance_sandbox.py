"""Idempotent demo finance data for the isolated sandbox.

Run only with ENV_FILE=.env.finance-sandbox after migrations.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.finance_models import (  # noqa: E402
    FinanceCoachContract,
    FinancePlatformContract,
    FinanceSale,
    FinanceTaxDefinition,
)
from app.models import Gym, User  # noqa: E402
from app.services import finance as finance_service  # noqa: E402


def main() -> None:
    if settings.FASTAPI_ENV == "production":
        raise SystemExit("Refusing to seed finance sandbox data in production")
    hosts = {host["host"] for host in settings.DATABASE_URL.hosts() if host.get("host")}
    if not hosts.issubset({"localhost", "127.0.0.1", "::1", "db"}):
        raise SystemExit(f"Refusing non-local database: {sorted(hosts)}")

    with Session(engine) as session:
        superuser = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        if superuser is None:
            raise SystemExit("Run app.initial_data before seeding finance data")
        owner = session.exec(
            select(User).where(User.email == "ali@example.com")
        ).first()
        coach = session.exec(
            select(User).where(User.email == "reza@example.com")
        ).first()
        gym = session.exec(
            select(Gym).where(Gym.name == "باشگاه آرام")
        ).first()
        if owner is None or coach is None or gym is None:
            raise SystemExit("Run scripts/seed_demo.py before finance seed")

        vat = session.exec(
            select(FinanceTaxDefinition).where(
                FinanceTaxDefinition.is_default_vat.is_(True)  # type: ignore[attr-defined]
            )
        ).first()
        if vat is None:
            session.add(
                FinanceTaxDefinition(
                    name="Value-added tax",
                    calculation="PERCENT",
                    percent_bp=1000,
                    is_active=True,
                    is_default_vat=True,
                    created_by_id=superuser.id,
                )
            )
            session.commit()

        default = session.exec(
            select(FinancePlatformContract).where(
                FinancePlatformContract.scope == "DEFAULT",
                FinancePlatformContract.status == "ACTIVE",
            )
        ).first()
        if default is None:
            draft = finance_service.create_platform_contract(
                session,
                actor=superuser,
                name="قرارداد پیش‌فرض پلتفرم",
                scope="DEFAULT",
                gym_id=None,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                rates=[
                    {"category": "MEMBERSHIP", "percent_bp": 1000},
                    {"category": "NUTRITION", "percent_bp": 1200},
                    {"category": "TRAINING", "percent_bp": 1500},
                ],
            )
            finance_service.activate_platform_contract(
                session, actor=superuser, contract_id=draft["id"]
            )

        contract = session.exec(
            select(FinanceCoachContract).where(
                FinanceCoachContract.gym_id == gym.id,
                FinanceCoachContract.coach_user_id == coach.id,
                FinanceCoachContract.category == "MEMBERSHIP",
                FinanceCoachContract.status == "ACTIVE",
            )
        ).first()
        if contract is None:
            draft = finance_service.create_coach_contract(
                session,
                actor=owner,
                gym_id=gym.id,
                coach_user_id=coach.id,
                category="MEMBERSHIP",
                effective_from=date(2026, 1, 1),
                effective_to=None,
                platform_bp=1000,
                gym_bp=4000,
                coach_bp=5000,
            )
            finance_service.activate_coach_contract(
                session,
                actor=owner,
                gym_id=gym.id,
                contract_id=draft["id"],
            )

        existing_sale = session.exec(
            select(FinanceSale).where(
                FinanceSale.gym_id == gym.id,
                FinanceSale.description == "فروش نمونه عضویت با مالیات",
            )
        ).first()
        if existing_sale is None:
            vat = session.exec(
                select(FinanceTaxDefinition).where(
                    FinanceTaxDefinition.is_default_vat.is_(True)  # type: ignore[attr-defined]
                )
            ).one()
            sale = finance_service.create_sale(
                session,
                actor=owner,
                gym_id=gym.id,
                category="MEMBERSHIP",
                description="فروش نمونه عضویت با مالیات",
                base_amount_irr=10_000_000,
                tax_ids=[vat.id],
                coach_user_id=coach.id,
                sold_on=finance_service.finance_today(),
            )
            finance_service.simulate_payment(
                session,
                actor=owner,
                gym_id=gym.id,
                sale_id=sale.id,
                outcome="SUCCESS",
                idempotency_key="seed-finance-sale-1",
            )

    print("Finance sandbox seed ready.")


if __name__ == "__main__":
    main()
