from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger, secure_audit_dir, secure_audit_file, utc_now
from teaagent.runner import RunResult
from teaagent.storage import atomic_write_text


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    task: str
    status: str
    created_at: str
    updated_at: str
    path: Path
    final_answer: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'task': self.task,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'path': str(self.path),
            'final_answer': self.final_answer,
        }


class RunStore:
    def __init__(self, root: str | Path = '.', *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.readonly = readonly
        self.store_dir = self.root / '.teaagent' / 'runs'
        if not readonly:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            secure_audit_dir(self.root / '.teaagent')
            secure_audit_dir(self.store_dir)

    def audit_logger(self, run_id: Optional[str] = None) -> AuditLogger:
        if self.readonly:
            raise RuntimeError('Cannot create audit logger in readonly mode')
        if run_id is None:
            path = self.store_dir / f'pending-{uuid4().hex}.jsonl'
        else:
            path = self.run_path(run_id)
        return AuditLogger(path=path)

    def logger_for_result(self, result: RunResult, audit: AuditLogger) -> None:
        if self.readonly:
            raise RuntimeError('Cannot persist logger result in readonly mode')
        if audit.path is None or audit.path == self.run_path(result.run_id):
            return
        target = self.run_path(result.run_id)
        from teaagent.storage import file_lock

        with file_lock(audit.path):
            content = audit.path.read_text(encoding='utf-8')
        atomic_write_text(target, content)
        secure_audit_file(target)
        audit.path.unlink(missing_ok=True)

    def run_path(self, run_id: str) -> Path:
        return self.store_dir / f'{safe_run_id(run_id)}.jsonl'

    def undo_dir(self) -> Path:
        if self.readonly:
            raise RuntimeError('Cannot access undo directory in readonly mode')
        path = self.root / '.teaagent' / 'undo'
        path.mkdir(parents=True, exist_ok=True)
        secure_audit_dir(path)
        return path

    def undo_path(self, run_id: str) -> Path:
        return self.undo_dir() / f'{safe_run_id(run_id)}.jsonl'

    def latest_run_with_undo(self, *, limit: int = 50) -> Optional[str]:
        for summary in self.list_runs(limit=limit):
            if self.undo_path(summary.run_id).is_file():
                return summary.run_id
        return None

    def record_undo_applied(
        self,
        run_id: str,
        *,
        status: str,
        restored: list[str],
        deleted: list[str],
        errors: list[str],
        undo_journal_path: Optional[str] = None,
    ) -> bool:
        """Append an ``undo_applied`` event to the run audit log when it exists."""
        if self.readonly:
            raise RuntimeError('Cannot record undo applied in readonly mode')
        path = self.run_path(run_id)
        if not path.is_file():
            return False
        from teaagent.audit_chain import last_chain_hash

        audit = AuditLogger(path=path)
        audit._prev_hash = last_chain_hash(path)
        audit.record(
            'undo_applied',
            run_id,
            status=status,
            restored=list(restored),
            deleted=list(deleted),
            errors=list(errors),
            undo_journal_path=undo_journal_path,
        )
        return audit.disk_error is None

    def list_runs(self, *, limit: int = 20) -> list[RunSummary]:
        if not self.store_dir.exists():
            return []
        summaries = [
            self.summarize(path)
            for path in sorted(
                self.store_dir.glob('*.jsonl'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        ]
        return [summary for summary in summaries if summary is not None][:limit]

    def show_run(self, run_id: str) -> list[dict[str, Any]]:
        path = self.run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"run '{run_id}' not found")
        return [
            json.loads(line)
            for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]

    def task_for_run(self, run_id: str) -> str:
        for event in self.show_run(run_id):
            if event.get('event_type') == 'run_started':
                task = event.get('payload', {}).get('task')
                if isinstance(task, str) and task:
                    return task
        raise ValueError(f"run '{run_id}' has no run_started task")

    def observations_for_run(self, run_id: str) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for event in self.show_run(run_id):
            if event.get('event_type') != 'tool_call_completed':
                continue
            payload = event.get('payload') or {}
            call_id = payload.get('call_id')
            tool_name = payload.get('tool_name')
            result = payload.get('result')
            if (
                isinstance(call_id, str)
                and isinstance(tool_name, str)
                and isinstance(result, dict)
            ):
                observations.append(
                    {'call_id': call_id, 'tool_name': tool_name, 'result': result}
                )
        return observations

    def pending_approval_for_run(self, run_id: str) -> Optional[dict[str, Any]]:
        pending: Optional[dict[str, Any]] = None
        for event in self.show_run(run_id):
            # Validate event is a dictionary
            if not isinstance(event, dict):
                continue
            
            event_type = event.get('event_type')
            payload = event.get('payload')
            
            # Validate payload is a dictionary, default to empty dict
            if not isinstance(payload, dict):
                payload = {}
            
            if event_type == 'tool_call_pending_approval':
                call_id = payload.get('call_id')
                tool_name = payload.get('tool_name')
                arguments = payload.get('arguments')
                if isinstance(call_id, str) and isinstance(tool_name, str):
                    pending = {
                        'call_id': call_id,
                        'tool_name': tool_name,
                        'arguments': arguments if isinstance(arguments, dict) else {},
                        'argument_digest': payload.get('argument_digest'),
                        'argument_digest_version': payload.get(
                            'argument_digest_version'
                        ),
                    }
            elif event_type in {
                'tool_call_approved',
                'tool_call_denied',
                'run_completed',
                'run_failed',
            }:
                if pending and isinstance(pending, dict):
                    pending_call_id = pending.get('call_id')
                    payload_call_id = payload.get('call_id')
                    if pending_call_id is not None and pending_call_id == payload_call_id:
                        pending = None
        return pending

    def heartbeat_for_run(self, run_id: str) -> dict[str, Any]:
        events = self.show_run(run_id)
        last_heartbeat: Optional[dict[str, Any]] = None
        terminal_status: Optional[str] = None
        for event in events:
            event_type = event.get('event_type')
            if event_type == 'heartbeat':
                last_heartbeat = event
            elif event_type in {'run_completed', 'run_failed'}:
                terminal_status = (
                    'completed'
                    if event_type == 'run_completed'
                    else f'failed:{event.get("payload", {}).get("category", "unknown")}'
                )
            elif event_type == 'run_paused':
                terminal_status = event.get('payload', {}).get('status', 'paused')
        return {
            'run_id': run_id,
            'status': terminal_status or 'running',
            'last_heartbeat_at': last_heartbeat.get('created_at')
            if last_heartbeat
            else None,
            'last_heartbeat_tick': last_heartbeat.get('payload', {}).get('tick')
            if last_heartbeat
            else None,
        }

    def summarize(self, path: Path) -> Optional[RunSummary]:
        try:
            events = [
                json.loads(line)
                for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            return None
        if not events:
            return None
        if not all(isinstance(event, dict) for event in events):
            return None
        run_id = events[0].get('run_id')
        if not isinstance(run_id, str) or not run_id:
            return None
        task = ''
        status = 'unknown'
        final_answer = None
        created_at = events[0].get('created_at', utc_now())
        updated_at = events[-1].get('created_at', created_at)
        for event in events:
            event_type = event.get('event_type')
            payload = event.get('payload', {})
            if event_type == 'run_started':
                task = payload.get('task', '')
                status = 'running'
            elif event_type == 'run_completed':
                status = 'completed'
                final_answer = payload.get('answer')
            elif event_type == 'run_failed':
                status = f'failed:{payload.get("category", "unknown")}'
            elif event_type == 'run_paused':
                status = payload.get('status', 'paused')
        return RunSummary(
            run_id=run_id,
            task=task,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            path=path,
            final_answer=final_answer,
        )


def safe_run_id(run_id: str) -> str:
    return ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'


def summarize_audit_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_counts: dict[str, int] = {}
    tool_names: list[str] = []
    destructive_tool_calls = 0
    approval_required = False
    status = 'unknown'
    for event in events:
        event_type = str(event.get('event_type', ''))
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        payload = event.get('payload', {})
        if not isinstance(payload, dict):
            payload = {}
        if event_type == 'tool_call_started':
            tool_name = payload.get('tool_name')
            if isinstance(tool_name, str) and tool_name not in tool_names:
                tool_names.append(tool_name)
            annotations = payload.get('annotations', {})
            if isinstance(annotations, dict) and annotations.get('destructive'):
                destructive_tool_calls += 1
        if event_type == 'tool_call_pending_approval':
            approval_required = True
        if event_type == 'run_completed':
            status = 'completed'
        elif event_type == 'run_paused':
            status = str(payload.get('status', 'pending_approval'))
        elif event_type == 'run_failed':
            status = f'failed:{payload.get("category", "system")}'
    return {
        'status': status,
        'event_counts': event_counts,
        'tool_names': tool_names,
        'destructive_tool_calls': destructive_tool_calls,
        'approval_required': approval_required,
    }
