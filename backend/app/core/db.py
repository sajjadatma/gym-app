from __future__ import annotations

from sqlmodel import Session, col, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Exercise, User
from app.seed_data import GLOBAL_EXERCISES
from app.services.exercises import ensure_global_categories

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


def init_db(session: Session) -> None:
    """Idempotent bootstrap: global super admin and global exercise library."""
    superuser = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not superuser:
        superuser = User(
            email=settings.FIRST_SUPERUSER,
            full_name="Sajjad Naseri",
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            is_superuser=True,
            is_active=True,
            must_change_password=False,
        )
        session.add(superuser)
    else:
        changed = False
        if not superuser.is_superuser:
            superuser.is_superuser = True
            changed = True
        if not superuser.full_name:
            superuser.full_name = "Sajjad Naseri"
            changed = True
        if not superuser.hashed_password:
            superuser.hashed_password = get_password_hash(
                settings.FIRST_SUPERUSER_PASSWORD
            )
            changed = True
        if changed:
            session.add(superuser)

    categories = ensure_global_categories(
        session, {row["muscle_group"] for row in GLOBAL_EXERCISES}
    )
    existing_names = {
        row.name_fa
        for row in session.exec(
            select(Exercise).where(col(Exercise.is_custom).is_(False))
        ).all()
    }
    for data in GLOBAL_EXERCISES:
        if data["name_fa"] not in existing_names:
            session.add(
                Exercise(
                    name_fa=data["name_fa"],
                    muscle_group=data["muscle_group"],
                    category_id=categories[data["muscle_group"]].id,
                    description=data.get("description"),
                    is_custom=False,
                )
            )
    session.commit()
