from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


def paginate(
    session: Session,
    statement: Any,
    *,
    offset: int,
    limit: int,
) -> tuple[list[Any], int]:
    """Return one page of rows plus the total number of matching rows.

    The total is computed from the same statement (without ordering) so the
    page size, offset and explicit filters cannot make ``count`` disagree with
    the data the client can page through.
    """
    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = int(session.exec(count_statement).one())
    rows = list(session.exec(statement.offset(offset).limit(limit)).all())
    return rows, total
