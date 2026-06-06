"""Structured logging with run_id context injection.

Uses logging.setLogRecordFactory to inject the current run_id into
every log record during an agent run, plus an optional JSON-line formatter
for machine-readable structured logs.

Usage inside AgentRunner.run()::

    from teaagent.run_logging import setup_run_logging, teardown_run_logging

    setup_run_logging(current_run_id, json_format=False)
    try:
        logger.info("some message")
    finally:
        teardown_run_logging()
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

# Module-level state
_active_run_id: Optional[str] = None
_original_factory: Any = None
_json_format_active: bool = False
_saved_formatters: dict[int, logging.Formatter] = {}


def _inject_run_id_factory(
    name: str,
    level: int,
    fn: str,
    lno: int,
    msg: object,
    args: Any,
    exc_info: Any,
    func: Optional[str] = None,
    sinfo: Optional[str] = None,
) -> logging.LogRecord:
    record = _original_factory(
        name, level, fn, lno, msg, args, exc_info, func=func, sinfo=sinfo
    )
    record.__dict__['run_id'] = _active_run_id
    return record


# JSON formatter

_LOG_RECORD_BUILTINS = frozenset(
    {
        'args',
        'created',
        'exc_info',
        'exc_text',
        'filename',
        'funcName',
        'levelname',
        'levelno',
        'lineno',
        'module',
        'msecs',
        'msg',
        'name',
        'pathname',
        'process',
        'processName',
        'relativeCreated',
        'stack_info',
        'thread',
        'threadName',
    }
)

_JSON_FORMAT_TOP_KEYS = frozenset(
    {
        'timestamp',
        'level',
        'logger',
        'message',
        'run_id',
    }
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'run_id': record.__dict__.get('run_id'),
        }
        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_BUILTINS or key in _JSON_FORMAT_TOP_KEYS:
                continue
            if key.startswith('_'):
                continue
            data[key] = _safe_serialize(value)
        return json.dumps(data, default=repr, ensure_ascii=False)


def _safe_serialize(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def _all_handlers() -> Iterator[logging.Handler]:
    for handler in logging.root.handlers:
        yield handler
    for logger in logging.root.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            for handler in logger.handlers:
                yield handler


# Public API


def setup_run_logging(
    run_id: str,
    *,
    json_format: bool = False,
) -> None:
    global _active_run_id, _original_factory, _json_format_active, _saved_formatters
    if _original_factory is not None:
        teardown_run_logging()
    _active_run_id = run_id
    _original_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(_inject_run_id_factory)
    if json_format:
        _json_format_active = True
        _saved_formatters.clear()
        json_fmt = JsonLogFormatter()
        for handler in _all_handlers():
            _saved_formatters[id(handler)] = handler.formatter
            handler.setFormatter(json_fmt)


def teardown_run_logging() -> None:
    global _active_run_id, _original_factory, _json_format_active, _saved_formatters
    _active_run_id = None
    if _original_factory is not None:
        logging.setLogRecordFactory(_original_factory)
        _original_factory = None
    if _json_format_active:
        _json_format_active = False
        if _saved_formatters:
            fmt_by_id = _saved_formatters
            _saved_formatters = {}
            for handler in _all_handlers():
                orig = fmt_by_id.get(id(handler))
                if orig is not None:
                    handler.setFormatter(orig)
