from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.storage import atomic_write_text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BackgroundRunRecord:
    background_id: str
    pid: int
    command: list[str]
    started_at: str
    log_path: str
    run_id: Optional[str] = None
    label: Optional[str] = None
    stopped_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BackgroundRunStore:
    """Detached agent runs persisted under ``.teaagent/background/``."""

    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self.dir = self.root / '.teaagent' / 'background'
        self.dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, background_id: str) -> Path:
        return self.dir / f'{background_id}.json'

    def start(
        self, command: list[str], *, label: Optional[str] = None
    ) -> BackgroundRunRecord:
        if not command:
            raise ValueError('background command must not be empty')
        background_id = uuid4().hex
        log_path = self.dir / f'{background_id}.log'
        record_path = self._record_path(background_id)
        log_handle = log_path.open('w', encoding='utf-8')
        try:
            proc = subprocess.Popen(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=self.root,
            )
        finally:
            log_handle.close()
        record = BackgroundRunRecord(
            background_id=background_id,
            pid=proc.pid,
            command=list(command),
            started_at=_utc_now(),
            log_path=str(log_path),
            label=label,
        )
        atomic_write_text(record_path, json.dumps(record.to_dict(), sort_keys=True))
        return record

    def get(self, background_id: str) -> dict[str, Any]:
        record_path = self._record_path(background_id)
        if not record_path.exists():
            raise FileNotFoundError(f"background run '{background_id}' not found")
        data = json.loads(record_path.read_text(encoding='utf-8'))
        data['alive'] = _is_alive(int(data['pid']))
        run_id = _run_id_from_log(Path(str(data['log_path'])))
        if run_id:
            data['run_id'] = run_id
        return data

    def update_run_id(self, background_id: str, run_id: str) -> None:
        record_path = self._record_path(background_id)
        if not record_path.exists():
            raise FileNotFoundError(f"background run '{background_id}' not found")
        data = json.loads(record_path.read_text(encoding='utf-8'))
        data['run_id'] = run_id
        atomic_write_text(record_path, json.dumps(data, sort_keys=True))

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(
            self.dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            data = json.loads(path.read_text(encoding='utf-8'))
            data['alive'] = _is_alive(int(data['pid']))
            log_path = Path(str(data.get('log_path', '')))
            if not data.get('run_id'):
                run_id = _run_id_from_log(log_path)
                if run_id:
                    data['run_id'] = run_id
            rows.append(data)
        return rows


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _run_id_from_log(log_path: Path) -> Optional[str]:
    if not log_path.is_file():
        return None
    for line in log_path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            run_id = payload.get('run_id')
            if isinstance(run_id, str) and run_id:
                return run_id
    return None


def build_agent_run_command(args: Any, task: str) -> list[str]:
    """Reconstruct a foreground ``agent run`` argv list for a background worker."""
    cmd = [
        sys.executable,
        '-m',
        'teaagent.cli',
        'agent',
        'run',
    ]
    if getattr(args, 'provider', None):
        cmd.append(args.provider)
    cmd.append(task)
    cmd.extend(['--root', str(args.root)])
    if getattr(args, 'model', None):
        cmd.extend(['--model', args.model])
    if getattr(args, 'route_model', False):
        cmd.append('--route-model')
    if getattr(args, 'max_iterations', None) not in (None, 10):
        cmd.extend(['--max-iterations', str(args.max_iterations)])
    if getattr(args, 'max_tool_calls', None) not in (None, 10):
        cmd.extend(['--max-tool-calls', str(args.max_tool_calls)])
    if getattr(args, 'clarify', False):
        cmd.append('--clarify')
    if getattr(args, 'allow_destructive', False):
        cmd.append('--allow-destructive')
    for call_id in getattr(args, 'approve_call_id', []) or []:
        cmd.extend(['--approve-call-id', call_id])
    if getattr(args, 'hitl_approval', False):
        cmd.append('--hitl-approval')
    if getattr(args, 'permission_mode', None):
        cmd.extend(['--permission-mode', args.permission_mode])
    if getattr(args, 'subagent', False):
        cmd.append('--subagent')
    if getattr(args, 'heartbeat', 0.0):
        cmd.extend(['--heartbeat', str(args.heartbeat)])
    if getattr(args, 'code_analysis', False):
        cmd.append('--code-analysis')
    if getattr(args, 'context_profile', None):
        cmd.extend(['--context-profile', args.context_profile])
    selected_skills = getattr(args, 'selected_skills', None)
    if selected_skills is not None:
        if not selected_skills:
            cmd.append('--no-auto-skills')
        else:
            for skill_name in selected_skills:
                cmd.extend(['--skill', skill_name])
    return cmd
