from __future__ import annotations

import pytest
from sqlmodel import Session

from app.core import rate_limit
from app.core.config import settings


def test_database_limiter_is_shared_and_resets(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "database")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)

    assert rate_limit._consume_database(db_session, "login:1:a", 2, 60) == (
        True,
        0,
    )
    assert rate_limit._consume_database(db_session, "login:1:a", 2, 60) == (
        True,
        0,
    )
    allowed, retry_after = rate_limit._consume_database(
        db_session, "login:1:a", 2, 60
    )
    assert allowed is False
    assert retry_after >= 1

    rate_limit.reset_rate_limit(db_session, "login:1:a")
    assert rate_limit._consume_database(db_session, "login:1:a", 2, 60) == (
        True,
        0,
    )


def test_database_limiter_separates_keys(db_session: Session) -> None:
    assert rate_limit._consume_database(db_session, "login:1:a", 1, 60) == (
        True,
        0,
    )
    assert rate_limit._consume_database(db_session, "login:1:b", 1, 60) == (
        True,
        0,
    )
