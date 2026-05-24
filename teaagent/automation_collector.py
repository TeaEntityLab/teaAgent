"""Deterministic collector step for script-first automations."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from importlib.util import find_spec
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
_BLOCKED_EXECUTABLES = frozenset(
    {
        'bash',
        'curl',
        'fish',
        'nc',
        'netcat',
        'osascript',
        'scp',
        'sh',
        'ssh',
        'wget',
        'zsh',
    }
)
_BLOCKED_INLINE_FLAGS = frozenset({'-c', '/c'})


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


def validate_collector_command(command: str) -> list[str]:
    """Validate deterministic collector commands before durable scheduling."""
    text = command.strip()
    if not text:
        return []
    try:
        argv = shlex.split(text)
    except ValueError as exc:
        return [f'collector_command is not parseable: {exc}']
    if not argv:
        return ['collector_command cannot be empty']
    executable = Path(argv[0]).name.lower()
    if executable in _BLOCKED_EXECUTABLES:
        return [
            f'collector_command executable {executable!r} is blocked; use a local deterministic script'
        ]
    if (
        executable.startswith('python')
        and len(argv) > 1
        and argv[1] in _BLOCKED_INLINE_FLAGS
    ):
        return ['collector_command must run a script file; inline python -c is blocked']
    if (
        executable in {'node', 'ruby', 'perl', 'php'}
        and len(argv) > 1
        and argv[1] in _BLOCKED_INLINE_FLAGS
    ):
        return [
            f'collector_command must run a script file; inline {executable} is blocked'
        ]
    if any('://' in item for item in argv):
        return [
            'collector_command must not embed remote URLs; fetch data in a reviewed local script'
        ]
    return []


def compute_collector_command_digest(
    command: str,
    *,
    root: str | Path,
) -> tuple[str, list[str]]:
    """Return a stable digest for the local script/module executed by a collector."""
    errors = validate_collector_command(command)
    text = command.strip()
    if errors or not text:
        return '', errors
    try:
        argv = shlex.split(text)
    except ValueError as exc:
        return '', [f'collector_command is not parseable: {exc}']
    target, target_errors = _collector_digest_target(argv, root=Path(root).resolve())
    if target_errors:
        return '', target_errors
    if target is None:
        return '', []
    if not target.is_file():
        return '', [f'collector_command script not found: {target}']
    digest = sha256(target.read_bytes()).hexdigest()
    return f'sha256:{digest}', []


def _collector_digest_target(
    argv: list[str], *, root: Path
) -> tuple[Optional[Path], list[str]]:
    if not argv:
        return None, []
    executable = Path(argv[0]).name.lower()
    if executable.startswith('python'):
        return _python_digest_target(argv, root=root)
    first = Path(argv[0])
    if first.is_absolute() or '/' in argv[0]:
        return _resolve_local_path(first, root=root), []
    return None, []


def _python_digest_target(
    argv: list[str], *, root: Path
) -> tuple[Optional[Path], list[str]]:
    if len(argv) < 2:
        return None, []
    target = argv[1]
    if target == '-m':
        if len(argv) < 3 or not argv[2].strip():
            return None, ['collector_command python -m requires a module name']
        try:
            spec = find_spec(argv[2])
        except (ImportError, AttributeError, ValueError) as exc:
            return None, [
                f'collector_command module {argv[2]!r} cannot be resolved: {exc}'
            ]
        if spec is None or not spec.origin:
            return None, [f'collector_command module {argv[2]!r} cannot be resolved']
        if spec.origin in {'built-in', 'namespace'}:
            return None, []
        return Path(spec.origin).resolve(), []
    if target.startswith('-'):
        return None, []
    return _resolve_local_path(Path(target), root=root), []


def _resolve_local_path(path: Path, *, root: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


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
