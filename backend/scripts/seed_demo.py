"""Idempotent local demo data for manual MVP acceptance testing.

Run after migrations and initial bootstrap:
    cd backend
    uv run python scripts/seed_demo.py

Demo accounts use a clearly fake shared password and are only for local testing.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models import (  # noqa: E402
    AthleteProfile,
    CoachAssignment,
    Exercise,
    ExerciseCategory,
    Gym,
    GymMembership,
    GymMembershipRole,
    ProgramTemplate,
    User,
    WorkoutProgram,
    WorkoutProgramVersion,
)
from app.services.programs import insert_structure  # noqa: E402

DEMO_PASSWORD = "DemoPass123!"
GYM_A = "باشگاه آرام"
GYM_B = "باشگاه پویا"
GYM_C = "باشگاه توان"


def ensure_user(session: Session, email: str, full_name: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        if not user.hashed_password:
            user.hashed_password = get_password_hash(DEMO_PASSWORD)
            session.add(user)
        return user
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        is_active=True,
        must_change_password=False,
    )
    session.add(user)
    session.flush()
    return user


def ensure_role(
    session: Session, user: User, gym: Gym, role: str | None = None
) -> GymMembership:
    membership = session.exec(
        select(GymMembership).where(
            GymMembership.gym_id == gym.id, GymMembership.user_id == user.id
        )
    ).first()
    if not membership:
        membership = GymMembership(gym_id=gym.id, user_id=user.id)
        session.add(membership)
        session.flush()
    if role:
        existing = session.exec(
            select(GymMembershipRole).where(
                GymMembershipRole.membership_id == membership.id,
                GymMembershipRole.role == role,
            )
        ).first()
        if not existing:
            session.add(GymMembershipRole(membership_id=membership.id, role=role))
    return membership


def ensure_gym(session: Session, name: str, owner: User) -> Gym:
    gym = session.exec(select(Gym).where(Gym.name == name)).first()
    if not gym:
        gym = Gym(
            name=name,
            description="باشگاه نمونه برای تست محلی",
            address="تهران، خیابان نمونه",
            phone="02100000000",
            owner_id=owner.id,
        )
        session.add(gym)
        session.flush()
    ensure_role(session, owner, gym)
    return gym


def ensure_athlete(
    session: Session,
    *,
    gym: Gym,
    user: User,
    coach: User,
    goal: str,
    height_cm: float,
    weight_kg: float,
) -> AthleteProfile:
    ensure_role(session, user, gym, "ATHLETE")
    profile = session.exec(
        select(AthleteProfile).where(
            AthleteProfile.gym_id == gym.id, AthleteProfile.user_id == user.id
        )
    ).first()
    if not profile:
        profile = AthleteProfile(
            gym_id=gym.id,
            user_id=user.id,
            phone="09120000000",
            height_cm=height_cm,
            weight_kg=weight_kg,
            chest_cm=100,
            waist_cm=82,
            hips_cm=98,
            arm_cm=36,
            thigh_cm=58,
            training_goal=goal,
            sports_history="دو سال تمرین باشگاهی",
            fitness_level="intermediate",
            limitations="حساسیت خفیف زانوی راست",
            training_days=["sat", "mon", "wed"],
            equipment="هالتر، دمبل، دستگاه سیم‌کش",
            internal_coach_note="PRIVATE-DEMO-NOTE — فقط برای مربی و مدیر",
        )
        session.add(profile)
        session.flush()
    assignment = session.exec(
        select(CoachAssignment).where(
            CoachAssignment.gym_id == gym.id,
            CoachAssignment.athlete_user_id == user.id,
            CoachAssignment.ended_at.is_(None),  # type: ignore[attr-defined]
        )
    ).first()
    if not assignment:
        session.add(
            CoachAssignment(
                gym_id=gym.id,
                athlete_user_id=user.id,
                coach_user_id=coach.id,
                assigned_by_id=coach.id,
            )
        )
    return profile


def exercise_snapshot(exercise: Exercise, sets: list[dict]) -> dict:
    return {
        "exercise_id": str(exercise.id),
        "exercise_name": exercise.name_fa,
        "muscle_group": exercise.muscle_group,
        "order_index": 0,
        "notes": "اجرای کنترل‌شده با تنفس منظم",
        "sets": sets,
    }


def build_days(session: Session, names: list[str]) -> list[dict]:
    exercises = {
        exercise.name_fa: exercise
        for exercise in session.exec(
            select(Exercise).where(Exercise.name_fa.in_(names))  # type: ignore[attr-defined]
        ).all()
    }
    selected = [exercises[name] for name in names if name in exercises]
    if not selected:
        return []
    days = [
        {
            "day_number": 1,
            "title": "روز اول — بالاتنه",
            "notes": "گرم‌کردن ۱۰ دقیقه‌ای فراموش نشود.",
            "exercises": [],
        },
        {
            "day_number": 2,
            "title": "روز دوم — پایین‌تنه",
            "notes": "بین ست‌ها استراحت کامل حفظ شود.",
            "exercises": [],
        },
    ]
    for index, exercise in enumerate(selected[:4]):
        target_day = days[0] if index < 2 else days[1]
        snapshot = exercise_snapshot(
            exercise,
            [
                {
                    "set_number": 1,
                    "reps_min": 8,
                    "reps_max": 10,
                    "weight_kg": 30 + index * 5,
                    "intensity": "RPE 7",
                    "rest_seconds": 60,
                    "duration_seconds": None,
                    "note": "ست گرم‌کردن",
                },
                {
                    "set_number": 2,
                    "reps_min": 6,
                    "reps_max": 8,
                    "weight_kg": 35 + index * 5,
                    "intensity": None,
                    "rest_seconds": 90,
                    "duration_seconds": None,
                    "note": None,
                },
            ],
        )
        snapshot["order_index"] = len(target_day["exercises"])
        target_day["exercises"].append(snapshot)
    return days


def ensure_program(
    session: Session,
    *,
    gym: Gym,
    athlete: User,
    coach: User,
    names: list[str],
) -> None:
    program = session.exec(
        select(WorkoutProgram).where(
            WorkoutProgram.gym_id == gym.id,
            WorkoutProgram.athlete_user_id == athlete.id,
        )
    ).first()
    if (
        program
        and session.exec(
            select(WorkoutProgramVersion).where(
                WorkoutProgramVersion.program_id == program.id
            )
        ).first()
    ):
        return
    if not program:
        program = WorkoutProgram(
            gym_id=gym.id,
            athlete_user_id=athlete.id,
            created_by_id=coach.id,
        )
        session.add(program)
        session.flush()
    structure = build_days(session, names)
    if not structure:
        return
    now = datetime.now(UTC)
    archived = WorkoutProgramVersion(
        program_id=program.id,
        version_number=1,
        status="ARCHIVED",
        title="برنامه آشنایی",
        goal="آماده‌سازی عمومی",
        notes="نسخه آغازین برای نمایش تاریخچه",
        coach_id=coach.id,
        coach_name=coach.full_name or coach.email,
        published_at=now,
        archived_at=now,
        created_at=now,
    )
    session.add(archived)
    session.flush()
    insert_structure(session, version_id=archived.id, structure=structure)

    active = WorkoutProgramVersion(
        program_id=program.id,
        version_number=2,
        status="ACTIVE",
        title="برنامه قدرتی ۸ هفته‌ای",
        goal="افزایش قدرت پایه و تکنیک",
        notes="تمرینات با وزنه کنترل‌شده؛ در صورت درد متوقف کنید.",
        coach_id=coach.id,
        coach_name=coach.full_name or coach.email,
        start_date=datetime.now(UTC).date(),
        created_at=now,
        published_at=now,
    )
    session.add(active)
    session.flush()
    insert_structure(session, version_id=active.id, structure=structure)


def ensure_template(
    session: Session, *, gym: Gym, coach: User, names: list[str]
) -> None:
    name = "قالب قدرت تمام‌بدن"
    existing = session.exec(
        select(ProgramTemplate).where(
            ProgramTemplate.gym_id == gym.id, ProgramTemplate.name == name
        )
    ).first()
    if existing:
        return
    structure = build_days(session, names)
    if not structure:
        return
    session.add(
        ProgramTemplate(
            gym_id=gym.id,
            created_by_id=coach.id,
            created_by_name=coach.full_name or coach.email,
            name=name,
            goal="قدرت و آمادگی عمومی",
            notes="قالب مستقل؛ ویرایش آن برنامه‌های قبلی را تغییر نمی‌دهد.",
            content={"days": structure},
        )
    )


def main() -> None:
    if settings.FASTAPI_ENV == "production":
        raise SystemExit("Refusing to seed demo data with FASTAPI_ENV=production")
    hosts = {host["host"] for host in settings.DATABASE_URL.hosts() if host.get("host")}
    if not hosts.issubset({"localhost", "127.0.0.1", "::1", "db"}):
        raise SystemExit(f"Refusing to seed a non-local database: {sorted(hosts)}")

    with Session(engine) as session:
        ali = ensure_user(session, "ali@example.com", "علی")
        bob = ensure_user(session, "bob@example.com", "بابک")
        omid = ensure_user(session, "omid@example.com", "امید")
        reza = ensure_user(session, "reza@example.com", "رضا مربی")
        sara = ensure_user(session, "sara@example.com", "سارا مربی")
        nima = ensure_user(session, "nima@example.com", "نیما ورزشکار")
        mina = ensure_user(session, "mina@example.com", "مینا ورزشکار")
        multi = ensure_user(session, "multi.athlete@example.com", "آرش چندباشگاهی")

        gym_a = ensure_gym(session, GYM_A, ali)
        gym_b = ensure_gym(session, GYM_B, bob)
        gym_c = ensure_gym(session, GYM_C, omid)

        ensure_role(session, ali, gym_a, "GYM_ADMIN")
        ensure_role(session, ali, gym_a, "COACH")
        ensure_role(session, ali, gym_b, "COACH")
        ensure_role(session, ali, gym_c, "GYM_ADMIN")
        ensure_role(session, reza, gym_a, "COACH")
        ensure_role(session, sara, gym_b, "COACH")

        custom = session.exec(
            select(Exercise).where(
                Exercise.name_fa == "پرس سینه با کش",
                Exercise.gym_id == gym_a.id,
            )
        ).first()
        if not custom:
            session.add(
                Exercise(
                    name_fa="پرس سینه با کش",
                    muscle_group="سینه",
                    category_id=session.exec(
                        select(ExerciseCategory).where(
                            ExerciseCategory.name == "سینه",
                            ExerciseCategory.gym_id.is_(None),
                        )
                    )
                    .one()
                    .id,
                    description="حرکت اختصاصی باشگاه آرام با کش مقاومتی.",
                    instructions="کش را از پشت بدن عبور دهید و کنترل‌شده جلو ببرید.",
                    is_custom=True,
                    gym_id=gym_a.id,
                    created_by_id=reza.id,
                )
            )

        ensure_athlete(
            session,
            gym=gym_a,
            user=nima,
            coach=reza,
            goal="افزایش قدرت و حجم عضلانی",
            height_cm=181,
            weight_kg=82,
        )
        ensure_athlete(
            session,
            gym=gym_b,
            user=mina,
            coach=sara,
            goal="استقامت و کاهش چربی",
            height_cm=166,
            weight_kg=61,
        )
        ensure_athlete(
            session,
            gym=gym_a,
            user=multi,
            coach=reza,
            goal="قدرت در باشگاه آرام",
            height_cm=175,
            weight_kg=72,
        )
        ensure_athlete(
            session,
            gym=gym_b,
            user=multi,
            coach=sara,
            goal="استقامت در باشگاه پویا",
            height_cm=175,
            weight_kg=72,
        )

        ensure_program(
            session,
            gym=gym_a,
            athlete=nima,
            coach=reza,
            names=["پرس سینه هالتر", "زیربغل سیم‌کش از بالا", "اسکوات هالتر", "پلانک"],
        )
        ensure_program(
            session,
            gym=gym_b,
            athlete=mina,
            coach=sara,
            names=["لگ پرس", "نشر جانبی دمبل", "کرانچ", "طناب زدن"],
        )
        ensure_template(
            session,
            gym=gym_a,
            coach=reza,
            names=["پرس سینه دمبل", "زیربغل قایقی", "اسکوات دستگاه", "پلانک"],
        )
        session.commit()

    print("Demo data is ready.")
    print("Gyms:", GYM_A, "|", GYM_B, "|", GYM_C)
    print("Sample accounts: ali@example.com, reza@example.com, sara@example.com,")
    print(
        "                 nima@example.com, mina@example.com, multi.athlete@example.com"
    )
    print(
        "Demo password is the local DEMO_PASSWORD value documented in docs/local-testing.md"
    )


if __name__ == "__main__":
    main()
