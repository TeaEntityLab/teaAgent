"""Observe-only recorder for a foreign harness command hook.

This is an opt-in instrument, not an enforcement boundary and not an
installed integration. It reads one JSON object from stdin, appends a
metadata-only audit event through :class:`teaagent.audit.AuditLogger`, and
exits 0 with ``{}``. If that log cannot be created, or ``record`` keeps the
event in memory after a disk error, it still exits 0 with ``{}`` and says
so on stderr. Tool arguments and tool results are not stored.

``--enforce`` is refused with exit code 2, including when the audit log
cannot be created. The refusal does not depend on recording succeeding.
Enforcement is not implemented; exit 0 or 1 under that flag is not a block
(a Claude Code command hook treats only exit 2 as blocking).

Nothing in this module edits host settings. ``--print-install`` prints the
observe-only snippet for another computer. It is a PostToolUse async hook,
not a PreToolUse gate. Wiring it in is an owner action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO, TextIO

_MAX_STDIN_BYTES = 1_048_576
_MAX_FIELD_CHARS = 256
_INSTALL_WARNING = (
    'teaagent foreign_hook: observe only. Paste this into the user settings '
    'on this computer. Do not commit it, and do not copy it to another '
    'machine. The command is this interpreter, shell-quoted, because a '
    'user-level hook runs in each project directory and does not activate '
    'a venv. TeaAgent must be installed in this interpreter. PostToolUse '
    'with async true is not on the allow path: a crash loses a log line and '
    'cannot allow a tool. Do not use PreToolUse for this recorder, and do '
    'not pass --enforce. Codex has no documented fail-closed switch for a '
    'crashed hook; do not put this command on Codex PreToolUse either.'
)
_METADATA_FIELDS = (
    'hook_event_name',
    'tool_name',
    'session_id',
    'permission_mode',
)


def _clip(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > _MAX_FIELD_CHARS:
        return text[:_MAX_FIELD_CHARS]
    return text


def _run_id(session_id: str | None) -> str:
    if session_id is None:
        return 'foreign-hook'
    if len(session_id) > 128:
        return 'foreign-hook'
    if all(ch.isalnum() or ch in '-_.' for ch in session_id):
        return session_id
    return 'foreign-hook'


def _read_bounded(stream: BinaryIO, limit: int) -> tuple[bytes, bool]:
    data = stream.read(limit + 1)
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('hook stdin must be binary')
    raw = bytes(data)
    if len(raw) > limit:
        return raw[:limit], True
    return raw, False


def build_observe_payload(
    raw: bytes,
    *,
    truncated: bool,
    enforce_refused: bool,
) -> tuple[str, dict[str, object]]:
    """Return ``(run_id, payload)`` with no tool-argument body."""
    digest = hashlib.sha256(raw).hexdigest()
    payload: dict[str, object] = {
        'source': 'foreign_hook',
        'mode': 'enforce_refused' if enforce_refused else 'observe',
        'input_sha256': digest,
        'input_bytes': len(raw),
        'truncated': truncated,
    }
    if truncated:
        payload['parse_error'] = True
        return 'foreign-hook', payload
    try:
        parsed = json.loads(raw.decode('utf-8')) if raw.strip() else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload['parse_error'] = True
        return 'foreign-hook', payload
    if not isinstance(parsed, dict):
        payload['parse_error'] = True
        return 'foreign-hook', payload
    for key in _METADATA_FIELDS:
        clipped = _clip(parsed.get(key))
        if clipped is not None:
            payload[key] = clipped
    session = payload.get('session_id')
    return _run_id(session if isinstance(session, str) else None), payload


def hook_command(executable: str | None = None) -> str:
    """Shell command bound to one absolute interpreter.

    A bare ``python`` is wrong for a user-level hook: the host runs it in
    the project directory, without the checkout's virtualenv.
    """
    raw = sys.executable if executable is None else executable
    # Do not resolve symlinks. A venv interpreter is often a symlink to a
    # system Python, and only the symlink path sees that venv's site-packages.
    interpreter = str(Path(raw).expanduser().absolute())
    return f'{shlex.quote(interpreter)} -m teaagent.foreign_hook'


def install_snippet(command: str | None = None) -> str:
    """Return the observe-only Claude Code snippet. Does not write a file."""
    payload = {
        'hooks': {
            'PostToolUse': [
                {
                    'matcher': '*',
                    'hooks': [
                        {
                            'type': 'command',
                            'command': (hook_command() if command is None else command),
                            'async': True,
                        }
                    ],
                }
            ]
        }
    }
    return json.dumps(payload, indent=2) + '\n'


def prove_install_command(command: str) -> str | None:
    """Run ``command`` from an unrelated directory. Return an error, or None.

    The host will not start the hook in the checkout, so a snippet that only
    works when the current directory is this repo must not be printed.
    """
    with tempfile.TemporaryDirectory(prefix='teaagent-hook-probe-') as tmp:
        probe = subprocess.run(
            ['/bin/bash', '-c', command],
            cwd=tmp,
            input=b'{"hook_event_name":"PostToolUse","tool_name":"Read"}',
            capture_output=True,
            check=False,
        )
        audit = Path(tmp) / '.teaagent' / 'foreign-hooks' / 'observe.jsonl'
        stderr = probe.stderr.decode('utf-8', errors='replace')
        # Exit 0 and a file are not enough. A swallowed disk error still
        # prints {} and can leave a partial file while the event stays in memory.
        if (
            probe.returncode != 0
            or probe.stdout.strip() != b'{}'
            or not audit.is_file()
            or 'was not recorded' in stderr
        ):
            detail = stderr.strip()
            return (
                detail or 'this interpreter cannot import teaagent outside the checkout'
            )
    return None


def record_observation(
    raw: bytes,
    *,
    audit_path: Path,
    truncated: bool,
    enforce_refused: bool,
) -> None:
    """Append one metadata audit event. Does not store ``raw``."""
    from teaagent.audit import AuditLogger

    run_id, payload = build_observe_payload(
        raw,
        truncated=truncated,
        enforce_refused=enforce_refused,
    )
    logger = AuditLogger(path=audit_path)
    logger.record('foreign_hook_observed', run_id, **payload)
    # compliance_mode raises on the first OSError. With it off, record()
    # stores the error and keeps the event in memory. That is still a miss:
    # the process is about to exit, so the memory copy is not a log.
    disk_error = logger.disk_error
    if disk_error is not None:
        raise disk_error


def _record_if_possible(
    raw_stream: BinaryIO,
    *,
    limit: int,
    audit_path: Path,
    enforce_refused: bool,
    err_stream: TextIO,
) -> None:
    """Append one observation. A recording failure must not escape."""
    try:
        raw, truncated = _read_bounded(raw_stream, limit)
        record_observation(
            raw,
            audit_path=audit_path,
            truncated=truncated,
            enforce_refused=enforce_refused,
        )
    except Exception as exc:
        print(
            'teaagent foreign_hook: observation was not recorded '
            f'({type(exc).__name__})',
            file=err_stream,
        )


def main(
    argv: list[str] | None = None,
    *,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one hook invocation. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog='python -m teaagent.foreign_hook',
        description=(
            'Record a foreign harness hook event without storing tool arguments. '
            'Observe-only. --enforce is refused.'
        ),
    )
    parser.add_argument(
        '--audit',
        type=Path,
        default=Path('.teaagent') / 'foreign-hooks' / 'observe.jsonl',
        help='Audit JSONL path (default: .teaagent/foreign-hooks/observe.jsonl)',
    )
    parser.add_argument(
        '--enforce',
        action='store_true',
        help='Refused. Enforcement is not implemented; exit 2 instead of pretending.',
    )
    parser.add_argument(
        '--print-install',
        action='store_true',
        help=(
            'Print the observe-only PostToolUse async snippet and exit. '
            'Does not read the caller stdin or write the caller audit log. '
            'Probes the command from a temporary directory first.'
        ),
    )
    parser.add_argument(
        '--max-bytes',
        type=int,
        default=_MAX_STDIN_BYTES,
        help=f'Maximum stdin bytes retained (default: {_MAX_STDIN_BYTES})',
    )
    args = parser.parse_args(argv)
    in_stream = stdin if stdin is not None else sys.stdin.buffer
    out_stream = stdout if stdout is not None else sys.stdout
    err_stream = stderr if stderr is not None else sys.stderr
    if args.print_install and args.enforce:
        print(
            'print-install cannot be combined with --enforce',
            file=err_stream,
        )
        return 2
    if args.print_install:
        command = hook_command()
        problem = prove_install_command(command)
        if problem is not None:
            print(
                'teaagent foreign_hook: not printing an install snippet '
                f'({problem}). Install teaagent into this interpreter and '
                'run --print-install again on this computer.',
                file=err_stream,
            )
            return 2
        print(_INSTALL_WARNING, file=err_stream)
        print(install_snippet(command), file=out_stream, end='')
        return 0

    if args.max_bytes < 1:
        print('max-bytes must be positive', file=err_stream)
        return 2

    if args.enforce:
        # Decide before any audit I/O. Claude Code treats every exit other
        # than 2 as non-blocking, including a traceback from AuditLogger.
        print(
            'teaagent foreign_hook: --enforce is not implemented; refusing to allow the call',
            file=err_stream,
        )
        _record_if_possible(
            in_stream,
            limit=args.max_bytes,
            audit_path=args.audit,
            enforce_refused=True,
            err_stream=err_stream,
        )
        return 2

    # An async post-tool hook is not on the allow path. A recording failure
    # loses the line and must not turn into a traceback or a non-zero exit.
    _record_if_possible(
        in_stream,
        limit=args.max_bytes,
        audit_path=args.audit,
        enforce_refused=False,
        err_stream=err_stream,
    )
    print('{}', file=out_stream)
    return 0


if __name__ == '__main__':
    sys.exit(main())
