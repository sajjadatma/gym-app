from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, KeyValueFormatter


def _record() -> logging.LogRecord:
    record = logging.LogRecord(
        "app.request", logging.INFO, "", 0, "request", (), None
    )
    record.request_id = "abc123"
    record.status = 200
    record.duration_ms = 4.2
    return record


def test_json_formatter_emits_structured_extras() -> None:
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["message"] == "request"
    assert payload["logger"] == "app.request"
    assert payload["request_id"] == "abc123"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 4.2


def test_key_value_formatter_keeps_extras_readable() -> None:
    output = KeyValueFormatter().format(_record())
    assert "request_id=abc123" in output
    assert "status=200" in output
