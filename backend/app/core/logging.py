from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

_STANDARD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _STANDARD_ATTRIBUTES and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """One JSON object per line; safe for log shipping."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extras(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class KeyValueFormatter(logging.Formatter):
    """Human-readable equivalent used outside staging/production."""

    def format(self, record: logging.LogRecord) -> str:
        message = f"{record.levelname} {record.name} {record.getMessage()}"
        extras = _extras(record)
        if extras:
            message += " " + " ".join(
                f"{key}={value}" for key, value in sorted(extras.items())
            )
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
        return message


class _AppStreamHandler(logging.StreamHandler[Any]):
    _gym_handler = True


def configure_logging() -> None:
    """Configure the ``app`` logger once, without touching uvicorn handlers."""
    logger = logging.getLogger("app")
    if any(getattr(handler, "_gym_handler", False) for handler in logger.handlers):
        return
    handler = _AppStreamHandler()
    handler.setFormatter(JsonFormatter() if settings.LOG_JSON else KeyValueFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
