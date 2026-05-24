"""Deterministic collector step for script-first automations."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class CollectorResult:
    exit_code: int
    stdout: str
    stderr: str
    wake_agent: bool
    summary: str
    parse_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'wake_agent': self.wake_agent,
            'summary': self.summary,
            'parse_error': self.parse_error,
        }


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
) -> CollectorResult:
    argv = shlex.split(command.strip())
    if not argv:
        raise ValueError('collector_command cannot be empty')
    completed = subprocess.run(
        argv,
        cwd=str(Path(root).resolve()),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    wake_agent, summary, parse_error = parse_collector_payload(completed.stdout)
    return CollectorResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        wake_agent=wake_agent,
        summary=summary,
        parse_error=parse_error,
    )
