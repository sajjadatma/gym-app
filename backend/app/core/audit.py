from __future__ import annotations

import logging
import uuid

logger = logging.getLogger("app.audit")


def audit(
    event: str,
    *,
    actor_id: uuid.UUID | None = None,
    gym_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    detail: str | None = None,
) -> None:
    """Record a security-relevant mutation without logging PII or secrets."""
    logger.info(
        "audit",
        extra={
            "event": event,
            "actor_id": actor_id,
            "gym_id": gym_id,
            "target_id": target_id,
            "detail": detail,
        },
    )
