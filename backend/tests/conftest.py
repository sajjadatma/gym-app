from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.api.deps import get_db
from app.core.config import settings
from app.core.rate_limit import reset_rate_limits
from app.core.security import get_password_hash
from app.main import app
from app.models import Exercise, SQLModel, User
from app.seed_data import GLOBAL_EXERCISES
from app.services.exercises import ensure_global_categories
from tests.utils.helpers import TEST_SUPERUSER_PASSWORD

if not settings.TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL must be configured for tests")
# Keep normal regression fixtures independent of request volume; the dedicated
# abuse tests enable the limiter explicitly.
settings.RATE_LIMIT_ENABLED = False
if not str(settings.TEST_DATABASE_URL).rstrip("/").endswith("_test"):
    raise RuntimeError("Refusing to run tests against a non-test database")

test_engine = create_engine(str(settings.TEST_DATABASE_URL), pool_pre_ping=True)


def _seed_global_data(session: Session) -> None:
    categories = ensure_global_categories(
        session, {row["muscle_group"] for row in GLOBAL_EXERCISES}
    )
    existing = {
        row.name_fa
        for row in session.exec(
            select(Exercise).where(Exercise.is_custom.is_(False))  # type: ignore[attr-defined]
        ).all()
    }
    for data in GLOBAL_EXERCISES:
        if data["name_fa"] not in existing:
            session.add(
                Exercise(
                    name_fa=data["name_fa"],
                    muscle_group=data["muscle_group"],
                    category_id=categories[data["muscle_group"]].id,
                    description=data.get("description"),
                    is_custom=False,
                )
            )
    superuser = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not superuser:
        session.add(
            User(
                email=settings.FIRST_SUPERUSER,
                full_name="Test Superuser",
                hashed_password=get_password_hash(TEST_SUPERUSER_PASSWORD),
                is_superuser=True,
                is_active=True,
                must_change_password=False,
            )
        )
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def prepare_database(tmp_path_factory: pytest.TempPathFactory) -> Generator[None]:
    settings.BODY_ANALYSIS_DIR = tmp_path_factory.mktemp("body-analysis")
    # Tests must never write to external object storage, even when a developer
    # .env is configured for Neon.
    settings.BODY_ANALYSIS_BUCKET = None
    settings.AWS_ENDPOINT_URL_S3 = None
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        _seed_global_data(session)
    yield


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None]:
    reset_rate_limits()
    tables = [
        table.name
        for table in SQLModel.metadata.sorted_tables
        if table.name != "exercise"
    ]
    quoted = ", ".join(f'"{name}"' for name in tables)
    with test_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    with Session(test_engine) as session:
        _seed_global_data(session)
    yield


def override_get_db() -> Generator[Session]:
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session() -> Generator[Session]:
    with Session(test_engine) as session:
        yield session


@pytest.fixture()
def superuser_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": TEST_SUPERUSER_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def email_outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    outbox: list[dict[str, Any]] = []

    def fake_send_email(
        *, email_to: str, subject: str = "", html_content: str = ""
    ) -> None:
        outbox.append(
            {"email_to": email_to, "subject": subject, "html_content": html_content}
        )

    monkeypatch.setattr("app.services.membership.send_email", fake_send_email)
    return outbox


def invitation_token_from(outbox: list[dict[str, Any]]) -> str:
    assert outbox, "expected an invitation email"
    match = re.search(
        r"accept-invitation\?token=([^\"&<]+)", outbox[-1]["html_content"]
    )
    assert match, "invitation token not found"
    return match.group(1)
