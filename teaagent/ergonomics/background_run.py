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
    exit_code: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BackgroundRunStore:
    """Detached agent runs persisted under ``.teaagent/background/``."""

    def __init__(self, root: str | Path = '.', *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.readonly = readonly
        self.dir = self.root / '.teaagent' / 'background'
        if not readonly:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, background_id: str) -> Path:
        return self.dir / f'{background_id}.json'

    def start(
        self, command: list[str], *, label: Optional[str] = None
    ) -> BackgroundRunRecord:
        if self.readonly:
            raise IOError('Cannot start background run: BackgroundRunStore is in readonly mode')
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
        data = _refresh_process_state(data, record_path, persist=not self.readonly)
        run_id = _run_id_from_log(Path(str(data['log_path'])))
        if run_id:
            previous_run_id = data.get('run_id')
            data['run_id'] = run_id
            if previous_run_id != run_id and not self.readonly:
                _persist_record_state(record_path, data)
        return data

    def update_run_id(self, background_id: str, run_id: str) -> None:
        if self.readonly:
            raise IOError('Cannot update run_id: BackgroundRunStore is in readonly mode')
        record_path = self._record_path(background_id)
        if not record_path.exists():
            raise FileNotFoundError(f"background run '{background_id}' not found")
        data = json.loads(record_path.read_text(encoding='utf-8'))
        data['run_id'] = run_id
        atomic_write_text(record_path, json.dumps(data, sort_keys=True))

    def list(self) -> list[dict[str, Any]]:
        if not self.dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(
            self.dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            data = json.loads(path.read_text(encoding='utf-8'))
            data = _refresh_process_state(data, path, persist=not self.readonly)
            log_path = Path(str(data.get('log_path', '')))
            if not data.get('run_id'):
                run_id = _run_id_from_log(log_path)
                if run_id:
                    data['run_id'] = run_id
                    if not self.readonly:
                        _persist_record_state(path, data)
            rows.append(data)
        return rows


def _persist_record_state(path: Path, data: dict[str, Any]) -> None:
    persisted = {k: v for k, v in data.items() if k != 'alive'}
    atomic_write_text(path, json.dumps(persisted, sort_keys=True))


def _exit_code_from_wait_status(status: int) -> int:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    return status


def _refresh_process_state(data: dict[str, Any], record_path: Path, *, persist: bool = True) -> dict[str, Any]:
    if data.get('stopped_at'):
        data['alive'] = False
        return data

    pid = int(data['pid'])
    alive = _is_alive(pid)
    exit_code: Optional[int] = None
    if alive:
        try:
            waited_pid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            waited_pid = 0
        except OSError:
            waited_pid = pid
            status = 1
        if waited_pid == pid:
            alive = False
            exit_code = _exit_code_from_wait_status(status)

    data['alive'] = alive
    if not alive:
        data['stopped_at'] = _utc_now()
        if exit_code is not None:
            data['exit_code'] = exit_code
        if persist:
            _persist_record_state(record_path, data)
    return data


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
    if getattr(args, 'max_subagent_depth', None) not in (None, 1):
        cmd.extend(['--max-subagent-depth', str(args.max_subagent_depth)])
    if getattr(args, 'heartbeat', 0.0):
        cmd.extend(['--heartbeat', str(args.heartbeat)])
    if getattr(args, 'code_analysis', False):
        cmd.append('--code-analysis')
    if getattr(args, 'telemetry_otlp_endpoint', None):
        cmd.extend(['--telemetry-otlp-endpoint', str(args.telemetry_otlp_endpoint)])
    if getattr(args, 'telemetry_service_name', None) not in (None, 'teaagent'):
        cmd.extend(['--telemetry-service-name', str(args.telemetry_service_name)])
    if getattr(args, 'telemetry_console', False):
        cmd.append('--telemetry-console')
    if getattr(args, 'checkpoint_store', None):
        cmd.extend(['--checkpoint-store', str(args.checkpoint_store)])
    if getattr(args, 'progress', None) is True:
        cmd.append('--progress')
    if getattr(args, 'no_progress', False):
        cmd.append('--no-progress')
    if getattr(args, 'stream', False):
        cmd.append('--stream')
    if getattr(args, 'stream_raw', False):
        cmd.append('--stream-raw')
    if getattr(args, 'json_stream', False):
        cmd.append('--json-stream')
    if getattr(args, 'context_profile', None):
        cmd.extend(['--context-profile', args.context_profile])
    max_cost = int(getattr(args, 'max_estimated_cost_cents', 0) or 0)
    if max_cost > 0:
        cmd.extend(['--max-estimated-cost-cents', str(max_cost)])
    if getattr(args, 'skill_index_only', False):
        cmd.append('--skill-index-only')
    selected_skills = getattr(args, 'selected_skills', None)
    if selected_skills is not None:
        if not selected_skills:
            cmd.append('--no-auto-skills')
        else:
            for skill_name in selected_skills:
                cmd.extend(['--skill', skill_name])
    return cmd
