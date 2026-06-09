from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.abstract_store import AbstractStore
from teaagent.audit import AuditLogger, secure_audit_dir, secure_audit_file, utc_now
from teaagent.runner import RunResult
from teaagent.storage import append_jsonl_line, atomic_write_text


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    task: str
    status: str
    created_at: str
    updated_at: str
    path: Path
    final_answer: Optional[str] = None
    cost_cents: float = 0.0
    resumable: bool = False
    pending_approval: Optional[dict[str, Any]] = None
    warnings: list[str] = field(default_factory=list)
    token_pressure: str = 'unknown'

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'task': self.task,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'path': str(self.path),
            'final_answer': self.final_answer,
            'cost_cents': self.cost_cents,
            'resumable': self.resumable,
            'pending_approval': self.pending_approval,
            'warnings': self.warnings,
            'token_pressure': self.token_pressure,
        }


class RunStore(AbstractStore[list[dict[str, Any]]]):
    def __init__(
        self,
        root: str | Path = '.',
        *,
        tenant_id: str = 'default',
        readonly: bool = False,
    ) -> None:
        self.root = Path(root).resolve()
        self.readonly = readonly
        self.tenant_id = tenant_id
        if tenant_id == 'default':
            self.store_dir = self.root / '.teaagent' / 'runs'
        else:
            self.store_dir = self.root / '.teaagent' / 'tenants' / tenant_id / 'runs'
        self._index_path = self.store_dir / 'runs-index.jsonl'
        self._corrupt_count = 0  # Track corrupt run files for health reporting
        if not readonly:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            secure_audit_dir(self.root / '.teaagent')
            if tenant_id != 'default':
                secure_audit_dir(self.root / '.teaagent' / 'tenants')
                secure_audit_dir(self.root / '.teaagent' / 'tenants' / tenant_id)
            secure_audit_dir(self.store_dir)
        elif not self.store_dir.exists():
            # Read-only mode but directory doesn't exist - this is expected for first use
            # No warning needed since we're not creating anything
            pass

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
        # SEC-01: Move the run key file as well
        if self.tenant_id == 'default':
            key_dir = Path.home() / '.teaagent' / 'run-keys'
        else:
            key_dir = (
                Path.home() / '.teaagent' / 'tenants' / self.tenant_id / 'run-keys'
            )
        old_key = key_dir / f'{audit.path.stem}.key'
        new_key = key_dir / f'{safe_run_id(result.run_id)}.key'
        if old_key.is_file():
            try:
                new_key.parent.mkdir(parents=True, exist_ok=True)
                new_key.write_bytes(old_key.read_bytes())
                new_key.chmod(0o600)
                old_key.unlink(missing_ok=True)
            except OSError:
                pass
        audit.path.unlink(missing_ok=True)
        # Update the index with the new run summary
        self._update_index(target)

    def _update_index(self, run_path: Path) -> None:
        """Update the runs index with a summary of the given run file."""
        if self.readonly:
            return
        summary = self.summarize(run_path)
        if summary is None:
            return
        append_jsonl_line(self._index_path, json.dumps(summary.to_dict()))
        secure_audit_file(self._index_path)

    def _read_index(self) -> list[RunSummary]:
        """Read the runs index and return a list of RunSummary objects."""
        if not self._index_path.exists():
            return []
        summaries = []
        for line in self._index_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                summaries.append(
                    RunSummary(
                        run_id=data['run_id'],
                        task=data['task'],
                        status=data['status'],
                        created_at=data['created_at'],
                        updated_at=data['updated_at'],
                        path=Path(data['path']),
                        final_answer=data.get('final_answer'),
                        cost_cents=data.get('cost_cents', 0.0),
                        resumable=data.get('resumable', False),
                        pending_approval=data.get('pending_approval'),
                        warnings=data.get('warnings') or [],
                        token_pressure=data.get('token_pressure', 'unknown'),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                self._corrupt_count += 1
        return summaries

    def run_path(self, run_id: str) -> Path:
        return self.store_dir / f'{safe_run_id(run_id)}.jsonl'

    def undo_dir(self) -> Path:
        if self.readonly:
            raise RuntimeError('Cannot access undo directory in readonly mode')
        if self.tenant_id == 'default':
            path = self.root / '.teaagent' / 'undo'
        else:
            path = self.root / '.teaagent' / 'tenants' / self.tenant_id / 'undo'
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
        # Try to use the index first for O(1) lookup
        if self._index_path.exists():
            summaries = self._read_index()
            # Sort by updated_at descending
            summaries.sort(key=lambda s: s.updated_at, reverse=True)
            return summaries[:limit]
        # Fallback to the old method if index doesn't exist
        return [
            summary
            for path in sorted(
                self.store_dir.glob('*.jsonl'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if path.name != 'runs-index.jsonl'
            and not path.name.startswith('pending-')
            and (summary := self.summarize(path)) is not None
        ][:limit]

    def show_run(self, run_id: str) -> list[dict[str, Any]]:
        path = self.run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"run '{run_id}' not found")
        events = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                self._corrupt_count += 1
        return events

    def describe_run(self, run_id: str) -> RunResult:
        """Get the RunResult for a completed/failed run from the audit log.

        Args:
            run_id: The run ID to describe.

        Returns:
            A ``RunResult`` with fields populated from the audit events.
            ``iterations`` and ``tool_calls`` default to 0 (not stored in
            audit events).
        """
        events = self.show_run(run_id)
        cost_cents = 0.0
        input_tokens = 0
        output_tokens = 0
        status = 'unknown'
        final_answer = None
        error_message: Optional[str] = None

        for event in events:
            event_type = event.get('event_type')
            payload = event.get('payload', {})
            if not isinstance(payload, dict):
                payload = {}
            if event_type == 'run_completed':
                cost_cents = float(payload.get('cost_cents', 0.0))
                input_tokens = int(payload.get('input_tokens', 0))
                output_tokens = int(payload.get('output_tokens', 0))
                status = 'completed'
                answer = payload.get('answer')
                if isinstance(answer, dict):
                    from teaagent.runner._types import FinalAnswer as FA

                    final_answer = FA(
                        content=answer.get('content', ''),
                        metadata=answer.get('metadata', {}),
                    )
            elif event_type == 'run_failed':
                cost_cents = float(payload.get('cost_cents', 0.0))
                input_tokens = int(payload.get('input_tokens', 0))
                output_tokens = int(payload.get('output_tokens', 0))
                category = payload.get('category', 'unknown')
                status = f'failed:{category}'
                error_message = str(payload.get('message', ''))
            elif event_type == 'run_paused':
                paused_status = payload.get('status')
                if isinstance(paused_status, str):
                    status = paused_status

        return RunResult(
            run_id=run_id,
            final_answer=final_answer,
            iterations=0,
            tool_calls=0,
            status=status,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error_message=error_message,
        )

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
                    if (
                        pending_call_id is not None
                        and pending_call_id == payload_call_id
                    ):
                        pending = None
        return pending

    def heartbeat_for_run(self, run_id: str) -> dict[str, Any]:
        from teaagent.integration.run_state import build_run_state_snapshot

        events = self.show_run(run_id)
        from teaagent.ergonomics.run_liveness import liveness_snapshot

        undo_file = self.root / '.teaagent' / 'undo' / f'{safe_run_id(run_id)}.jsonl'
        snapshot = build_run_state_snapshot(
            events,
            run_id,
            undo_available=undo_file.is_file(),
            liveness=liveness_snapshot(self.root, run_id),
        )
        return snapshot.to_dict()

    def summarize(self, path: Path) -> Optional[RunSummary]:
        try:
            events = [
                json.loads(line)
                for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            self._corrupt_count += 1
            return None
        if not events:
            return None
        if not all(isinstance(event, dict) for event in events):
            self._corrupt_count += 1
            return None
        run_id = events[0].get('run_id')
        if not isinstance(run_id, str) or not run_id:
            return None
        task = ''
        status = 'unknown'
        final_answer = None
        cost_cents = 0.0
        created_at = events[0].get('created_at', utc_now())
        updated_at = events[-1].get('created_at', created_at)

        warnings = []
        pending_approval = None
        token_pressure = 'unknown'
        total_tokens = 0

        for event in events:
            event_type = event.get('event_type')
            payload = event.get('payload', {})
            if not isinstance(payload, dict):
                payload = {}
            if event_type == 'run_started':
                task = payload.get('task', '')
                status = 'running'
            elif event_type == 'run_completed':
                status = 'completed'
                final_answer = payload.get('answer')
                cost_cents = float(payload.get('cost_cents', 0.0))
            elif event_type == 'run_failed':
                status = f'failed:{payload.get("category", "unknown")}'
                cost_cents = float(payload.get('cost_cents', 0.0))
            elif event_type == 'run_paused':
                status = payload.get('status', 'paused')

            if event_type in (
                'budget_warning',
                'phase_budget_warning',
                'warning',
                'compaction_warning',
            ):
                msg = (
                    payload.get('message')
                    or event.get('message')
                    or payload.get('summary')
                )
                if msg:
                    warnings.append(str(msg))

            if event_type == 'tool_call_pending_approval':
                call_id = payload.get('call_id')
                tool_name = payload.get('tool_name')
                arguments = payload.get('arguments')
                if isinstance(call_id, str) and isinstance(tool_name, str):
                    pending_approval = {
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
                if pending_approval:
                    pending_call_id = pending_approval.get('call_id')
                    payload_call_id = payload.get('call_id')
                    if (
                        pending_call_id is not None
                        and pending_call_id == payload_call_id
                    ):
                        pending_approval = None

            in_tok = int(payload.get('input_tokens', 0))
            out_tok = int(payload.get('output_tokens', 0))
            if in_tok or out_tok:
                total_tokens = max(total_tokens, in_tok + out_tok)

        if total_tokens > 0:
            ratio = total_tokens / 200000
            if ratio >= 0.92:
                token_pressure = 'red'
            elif ratio >= 0.75:
                token_pressure = 'yellow'
            else:
                token_pressure = 'green'

        resumable = (
            not (status == 'completed' or status.startswith('failed:'))
            and status != 'unknown'
        )
        return RunSummary(
            run_id=run_id,
            task=task,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            path=path,
            final_answer=final_answer,
            cost_cents=cost_cents,
            resumable=resumable,
            pending_approval=pending_approval,
            warnings=warnings,
            token_pressure=token_pressure,
        )

    def health_report(self) -> dict[str, Any]:
        """Report health status including corruption count.

        Scans run files for JSON validity to detect corruption.

        Returns:
            Dict with 'corrupt_runs' count, 'total_runs', and 'healthy' boolean
        """
        total_runs = 0
        corrupt_runs = 0
        if self.store_dir.exists():
            for run_file in sorted(self.store_dir.glob('*.jsonl')):
                total_runs += 1
                try:
                    data = run_file.read_text(encoding='utf-8')
                    if not data.strip():
                        corrupt_runs += 1
                        continue
                    first_line = data.split('\n')[0].strip()
                    if first_line:
                        json.loads(first_line)
                    else:
                        corrupt_runs += 1
                except (json.JSONDecodeError, OSError):
                    corrupt_runs += 1

        return {
            'corrupt_runs': corrupt_runs,
            'total_runs': total_runs - corrupt_runs,
            'healthy': corrupt_runs == 0,
        }

    def rebuild_index(self) -> None:
        """Rebuild the runs index from scratch by scanning all run files."""
        if self.readonly:
            raise RuntimeError('Cannot rebuild index in readonly mode')
        if not self.store_dir.exists():
            return
        summaries = []
        for path in sorted(
            self.store_dir.glob('*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if path.name == 'runs-index.jsonl' or path.name.startswith('pending-'):
                continue
            summary = self.summarize(path)
            if summary is not None:
                summaries.append(summary)
        # Write the index atomically
        index_content = '\n'.join(json.dumps(s.to_dict()) for s in summaries) + '\n'
        atomic_write_text(self._index_path, index_content)
        secure_audit_file(self._index_path)

    def save(self, key: str, value: list[dict[str, Any]]) -> None:
        if self.readonly:
            raise RuntimeError('Cannot save in readonly mode')
        path = self.run_path(key)
        content = '\n'.join(json.dumps(event) for event in value) + '\n'
        atomic_write_text(path, content)

    def load(self, key: str) -> list[dict[str, Any]] | None:
        try:
            return self.show_run(key)
        except FileNotFoundError:
            return None

    def delete(self, key: str) -> bool:
        if self.readonly:
            raise RuntimeError('Cannot delete in readonly mode')
        path = self.run_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> list[str]:
        return [s.run_id for s in self.list_runs()]

    def exists(self, key: str) -> bool:
        return self.run_path(key).exists()

    def clear(self) -> None:
        if self.readonly:
            raise RuntimeError('Cannot clear in readonly mode')
        for path in self.store_dir.glob('*.jsonl'):
            path.unlink(missing_ok=True)
        if self._index_path.exists():
            self._index_path.unlink(missing_ok=True)


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
