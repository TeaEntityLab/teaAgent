"""Structured logging helpers for TeaAgent modules."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator


class StructuredFormatter(logging.Formatter):
    """Emit JSON log lines with standard TeaAgent keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'event': record.getMessage(),
            'level': record.levelname,
            'module': record.module,
            'logger': record.name,
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        for key in ('run_id', 'error_code', 'duration_ms', 'tool_name'):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        extra = getattr(record, 'structured_extra', None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_structured_logging(
    *,
    level: int = logging.INFO,
    json_output: bool = False,
) -> None:
    """Configure root logging with optional JSON formatting."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    root.addHandler(handler)
    root.setLevel(level)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Log a structured event with optional metadata fields."""
    record = logger.makeRecord(
        logger.name,
        level,
        '(structured)',
        0,
        event,
        (),
        None,
    )
    record.structured_extra = fields
    logger.handle(record)


@contextmanager
def log_duration(
    logger: logging.Logger,
    event: str,
    **fields: Any,
) -> Iterator[None]:
    """Log ``event`` with ``duration_ms`` after the block completes."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        log_event(logger, event, duration_ms=round(duration_ms, 2), **fields)
