"""Deterministic collector step for script-first automations."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Optional

_DEFAULT_MAX_OUTPUT_BYTES = 16_384
_SECRET_PATTERNS = (
    re.compile(
        r'(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*["\']?[^"\'\s,;]+'
    ),
    re.compile(r'\b(sk-[A-Za-z0-9_-]{12,})\b'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b'),
)


@dataclass(frozen=True)
class CollectorResult:
    exit_code: int
    stdout: str
    stderr: str
    wake_agent: bool
    summary: str
    parse_error: Optional[str] = None
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'wake_agent': self.wake_agent,
            'summary': self.summary,
            'parse_error': self.parse_error,
            'timed_out': self.timed_out,
            'stdout_truncated': self.stdout_truncated,
            'stderr_truncated': self.stderr_truncated,
            'duration_seconds': round(self.duration_seconds, 3),
        }


def redact_collector_output(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub('[REDACTED]', redacted)
    return redacted


def _text_from_timeout(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def cap_collector_output(text: str, *, max_bytes: int) -> tuple[str, bool]:
    if max_bytes < 0:
        raise ValueError('max_bytes must be >= 0')
    raw = text.encode('utf-8')
    if len(raw) <= max_bytes:
        return text, False
    capped = raw[:max_bytes].decode('utf-8', errors='replace')
    return capped, True


def parse_collector_payload(stdout: str) -> tuple[bool, str, Optional[str]]:
    text = stdout.strip()
    if not text:
        return True, '', None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return True, text[:500], str(exc)
    if not isinstance(payload, dict):
        return True, text[:500], 'collector output must be a JSON object'
    wake_agent = bool(payload.get('wake_agent', True))
    summary = payload.get('summary', payload.get('message', ''))
    return wake_agent, str(summary).strip(), None


def run_collector_command(
    command: str,
    *,
    root: str | Path,
    timeout_seconds: float = 120.0,
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
) -> CollectorResult:
    argv = shlex.split(command.strip())
    if not argv:
        raise ValueError('collector_command cannot be empty')
    started = monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(Path(root).resolve()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = monotonic() - started
        stdout, stdout_truncated = cap_collector_output(
            redact_collector_output(completed.stdout),
            max_bytes=max_output_bytes,
        )
        stderr, stderr_truncated = cap_collector_output(
            redact_collector_output(completed.stderr),
            max_bytes=max_output_bytes,
        )
        wake_agent, summary, parse_error = parse_collector_payload(stdout)
        if summary:
            summary = redact_collector_output(summary)
    except subprocess.TimeoutExpired as exc:
        duration = monotonic() - started
        stdout = redact_collector_output(_text_from_timeout(exc.stdout))
        stderr = redact_collector_output(_text_from_timeout(exc.stderr))
        stdout, stdout_truncated = cap_collector_output(
            stdout,
            max_bytes=max_output_bytes,
        )
        stderr, stderr_truncated = cap_collector_output(
            stderr,
            max_bytes=max_output_bytes,
        )
        return CollectorResult(
            exit_code=124,
            stdout=stdout,
            stderr=stderr,
            wake_agent=False,
            summary=f'collector timed out after {timeout_seconds:g}s',
            parse_error='timeout',
            timed_out=True,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            duration_seconds=duration,
        )
    return CollectorResult(
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        wake_agent=wake_agent,
        summary=summary,
        parse_error=parse_error,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        duration_seconds=duration,
    )
