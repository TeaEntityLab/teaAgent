from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.errors import ErrorCategory
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)

# ADR-0032 Amendment A1: background lifecycle events live on their own chain,
# never in a run's log. The envelope run_id is ``background:<background_id>``.
LIFECYCLE_FILE_NAME = 'lifecycle.jsonl'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_tenant_id_from_argv() -> str:
    import sys

    for i, arg in enumerate(sys.argv):
        if arg == '--tenant-id':
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        elif arg.startswith('--tenant-id='):
            return arg.split('=', 1)[1]
    return 'default'


def _get_tenant_id_from_path(path: Path) -> str:
    try:
        parts = Path(path).resolve().parts
        if 'tenants' in parts:
            idx = parts.index('tenants')
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        logger.exception('tenant id extraction failed')
    return 'default'


class _LifecycleAuditLogger(AuditLogger):
    """AuditLogger that writes one explicit lifecycle payload.

    ``AuditLogger.record(event_type, run_id, **payload)`` binds ``run_id`` to the
    envelope parameter, so the A1.2 payload key ``run_id`` cannot travel as a
    keyword argument. The payload is handed over whole through
    ``_apply_audit_level``, the step ``record`` applies before redaction and
    hashing. The hash chain, tip re-read and file lock are still AuditLogger's.
    """

    def __init__(self, path: Path, payload: dict[str, object]) -> None:
        self._lifecycle_payload = dict(payload)
        super().__init__(path=path)

    def _apply_audit_level(self, payload: dict[str, object]) -> dict[str, object]:
        return super()._apply_audit_level(dict(self._lifecycle_payload))


def _command_digest(command: list[str]) -> str:
    return hashlib.sha256(json.dumps(command).encode('utf-8')).hexdigest()


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

    def __init__(
        self,
        root: str | Path = '.',
        *,
        tenant_id: Optional[str] = None,
        readonly: bool = False,
    ) -> None:
        self.root = Path(root).resolve()
        self.readonly = readonly
        if tenant_id is None:
            tenant_id = _extract_tenant_id_from_argv()
        self.tenant_id = tenant_id
        if tenant_id == 'default':
            self.dir = self.root / '.teaagent' / 'background'
        else:
            self.dir = self.root / '.teaagent' / 'tenants' / tenant_id / 'background'
        if not readonly:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, background_id: str) -> Path:
        return self.dir / f'{background_id}.json'

    def start(
        self, command: list[str], *, label: Optional[str] = None
    ) -> BackgroundRunRecord:
        if self.readonly:
            raise IOError(
                'Cannot start background run: BackgroundRunStore is in readonly mode'
            )
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
        self._emit_lifecycle(
            'BACKGROUND_SUBMITTED',
            background_id,
            {
                'background_id': background_id,
                'run_id': None,
                'pid': record.pid,
                'started_at': record.started_at,
                'command_digest': _command_digest(command),
                'label': record.label,
            },
        )
        return record

    def _emit_lifecycle(
        self,
        member_name: str,
        background_id: str,
        payload: dict[str, object],
    ) -> None:
        """Append one lifecycle event to ``lifecycle.jsonl`` (call after persist).

        Outside compliance mode a failed append is logged at ERROR with its
        category and ``background_id``, and is not retried (ADR 0032 A1.2, Q4).
        In compliance mode the failure raises.
        """
        from teaagent.runner._events import RunEventType, run_event_to_audit_event_type
        from teaagent.security_env import compliance_mode

        audit_type = run_event_to_audit_event_type(RunEventType[member_name])
        try:
            audit = _LifecycleAuditLogger(self.dir / LIFECYCLE_FILE_NAME, payload)
            audit.record(audit_type, f'background:{background_id}')
            if audit.disk_error is not None:
                raise audit.disk_error
        except Exception as exc:
            if compliance_mode():
                raise
            logger.error(
                'background lifecycle event %s not recorded for background_id=%s '
                '(category=%s): %s; not retried',
                audit_type,
                background_id,
                ErrorCategory.SYSTEM.value,
                exc,
                extra={
                    'event': 'background_lifecycle_emit_failed',
                    'background_id': background_id,
                    'error_category': ErrorCategory.SYSTEM.value,
                    'error_severity': 'high',
                },
            )

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
        return _enrich_liveness(self.root, data, record_path=record_path)

    def update_run_id(self, background_id: str, run_id: str) -> None:
        if self.readonly:
            raise IOError(
                'Cannot update run_id: BackgroundRunStore is in readonly mode'
            )
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
            rows.append(_enrich_liveness(self.root, data, record_path=path))
        return rows

    def logs(self, background_id: str, *, max_bytes: int = 64_000) -> dict[str, Any]:
        data = self.get(background_id)
        log_path = Path(str(data['log_path']))
        if not log_path.exists():
            content = ''
        else:
            with log_path.open('rb') as fh:
                if max_bytes > 0:
                    fh.seek(0, os.SEEK_END)
                    size = fh.tell()
                    fh.seek(max(0, size - max_bytes), os.SEEK_SET)
                content = fh.read().decode('utf-8', errors='replace')
        return {
            'background_id': data['background_id'],
            'log_path': data['log_path'],
            'content': content,
        }

    def stop(
        self, background_id: str, *, timeout_seconds: float = 2.0
    ) -> dict[str, Any]:
        import signal
        import time
        from contextlib import suppress

        data = self.get(background_id)
        if data.get('stopped_at') and data.get('stop_signal'):
            # BG-001 §3.6: repeated stop converges on the first stop's record.
            return data
        pid = int(data['pid'])
        signal_name = 'SIGTERM'
        if _is_alive(pid):
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
            deadline = time.time() + max(0.0, timeout_seconds)
            while time.time() < deadline and _is_alive(pid):
                time.sleep(0.05)
            if _is_alive(pid):
                with suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)
                    signal_name = 'SIGKILL'

        data['stopped_at'] = _utc_now()
        data['stop_signal'] = signal_name
        data['alive'] = False
        # A stopped record is no longer an orphan candidate; drop the derived
        # marker so it is never persisted as stored state.
        data.pop('orphaned', None)
        if not self.readonly:
            _persist_record_state(self._record_path(background_id), data)
            run_id = data.get('run_id')
            self._emit_lifecycle(
                'BACKGROUND_STOPPED',
                background_id,
                {
                    'background_id': background_id,
                    'run_id': run_id if isinstance(run_id, str) and run_id else None,
                    'pid': pid,
                    'stop_signal': signal_name,
                    'stopped_at': data['stopped_at'],
                    'exit_code': data.get('exit_code'),
                    'exit_code_derived': data.get('exit_code_derived') is True,
                },
            )
        return data


def _enrich_liveness(
    root: Path,
    data: dict[str, Any],
    *,
    record_path: Optional[Path] = None,
) -> dict[str, Any]:
    data['run_outcome'] = _derive_run_outcome(data, record_path)
    run_id = data.get('run_id')
    if isinstance(run_id, str) and run_id:
        from teaagent.ergonomics.run_liveness import liveness_snapshot

        snap = liveness_snapshot(root, run_id)
        if snap is not None:
            data['liveness_updated_at'] = snap['updated_at']
            data['liveness_age_seconds'] = snap['age_seconds']
            data['liveness_stale'] = snap['stale']
    # Orphan derivation runs for run_id-less records too (BG-001 §3.3): a dead
    # process that never wrote its run_id must still surface as orphaned.
    if record_path is not None and not data.get('alive'):
        _derive_orphan_state(record_path, data)
    return data


# Keys computed at read time from process state and the audit log. They are
# surfaced to callers but never written back into the record file.
_DERIVED_RECORD_KEYS = frozenset(
    {'alive', 'orphaned', 'run_outcome', 'exit_code_derived'}
)


def _persist_record_state(path: Path, data: dict[str, Any]) -> None:
    persisted = {k: v for k, v in data.items() if k not in _DERIVED_RECORD_KEYS}
    if data.get('exit_code_derived'):
        # A derived exit code is a read-time stand-in; storing it would make
        # it look authoritative on the next read.
        persisted.pop('exit_code', None)
    atomic_write_text(path, json.dumps(persisted, sort_keys=True))


def _exit_code_from_wait_status(status: int) -> int:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    return status


def _process_exists(pid: int) -> bool:
    """Check if process exists using os.kill(pid, 0) without reaping."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


_TERMINAL_RUN_EVENTS = frozenset(
    {'run_completed', 'run_failed', 'run_paused', 'run_cancelled'}
)


def _last_terminal_run_event(
    root: Path, run_id: str, tenant_id: str
) -> Optional[dict[str, object]]:
    try:
        from teaagent.run_store import RunStore

        events = RunStore(root, tenant_id=tenant_id, readonly=True).show_run(run_id)
    except (FileNotFoundError, OSError):
        return None
    terminal = [
        e
        for e in events
        if isinstance(e, dict) and e.get('event_type') in _TERMINAL_RUN_EVENTS
    ]
    return terminal[-1] if terminal else None


def _workspace_root_for_record(record_path: Path) -> tuple[Path, str]:
    tenant_id = _get_tenant_id_from_path(record_path)
    if tenant_id == 'default':
        return record_path.parent.parent.parent, tenant_id
    return record_path.parent.parent.parent.parent.parent, tenant_id


def _event_field(event: dict[str, object], key: str) -> object:
    payload = event.get('payload')
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return event.get(key)


def _outcome_from_terminal_event(event: dict[str, object]) -> str:
    event_type = event.get('event_type')
    if event_type == 'run_completed':
        return 'completed'
    if event_type == 'run_paused':
        # BG-001 §3.2 vocabulary: a paused run is waiting on an approval.
        return 'pending_approval'
    if event_type == 'run_cancelled':
        return 'cancelled'
    if event_type == 'run_failed':
        # RunCancelledError is recorded as run_failed; its message is the only
        # marker that distinguishes a cancellation from a genuine failure.
        message = _event_field(event, 'message')
        if isinstance(message, str) and message.lower().startswith('run cancelled'):
            return 'cancelled'
        return 'failed'
    return 'unknown'


def _derive_run_outcome(data: dict[str, object], record_path: Optional[Path]) -> str:
    """Run outcome from the audit log, kept distinct from process liveness."""
    run_id = data.get('run_id')
    if not isinstance(run_id, str) or not run_id or record_path is None:
        return 'unknown'
    w_root, tenant_id = _workspace_root_for_record(record_path)
    terminal = _last_terminal_run_event(w_root, run_id, tenant_id)
    if terminal is not None:
        return _outcome_from_terminal_event(terminal)
    if data.get('alive'):
        return 'running'
    return 'unknown'


def _derive_orphan_state(record_path: Path, data: dict[str, Any]) -> None:
    if data.get('alive') is True:
        # A live process is never an orphan, even before it writes a run_id.
        return
    if data.get('stop_signal') is not None:
        return
    if data.get('exit_code') == 0:
        return
    run_id = data.get('run_id')
    if not isinstance(run_id, str) or not run_id:
        # Dead, not stopped, no clean exit, and no run_id: nothing can prove
        # the run completed, so surface it as orphaned.
        data['orphaned'] = True
        return
    w_root, tenant_id = _workspace_root_for_record(record_path)
    terminal = _last_terminal_run_event(w_root, run_id, tenant_id)
    if terminal is not None:
        # The audit log knows the outcome, so the run is not orphaned. Only a
        # completed run may stand in for a lost exit code, and the stand-in is
        # marked derived (BG-001 §1: a fallback exit_code=0 is not authoritative).
        if (
            data.get('exit_code') is None
            and terminal.get('event_type') == 'run_completed'
        ):
            data['exit_code'] = 0
            data['exit_code_derived'] = True
        return
    data['orphaned'] = True


def _capture_failure_card(
    root: Path, run_id: str, exit_code: int, tenant_id: str = 'default'
) -> None:
    """Capture a failure card when a background task fails.

    Args:
        root: The workspace root directory
        run_id: The run ID of the failed task
        exit_code: The exit code of the failed task
        tenant_id: The tenant identifier
    """
    try:
        from teaagent.memory.failure_card import FailureCard, FailureCardStorage
        from teaagent.run_store import RunStore

        # Only capture for non-zero exit codes (actual failures)
        if exit_code == 0:
            return

        store = RunStore(root, tenant_id=tenant_id)
        try:
            # Get task description
            task = store.task_for_run(run_id)
        except (FileNotFoundError, ValueError):
            return

        # Get observations to extract error information
        observations = store.observations_for_run(run_id)

        # Extract error from the last observation if it's an error
        error_type = 'UnknownError'
        error_message = f'Task failed with exit code {exit_code}'
        file_path = ''
        line_number = None

        if observations:
            last_obs = observations[-1]
            if 'error' in last_obs:
                error_message = str(last_obs['error'])
                # Try to extract error type from message
                if ':' in error_message:
                    error_type = error_message.split(':', 1)[0].strip()
            if 'tool_name' in last_obs:
                # If it's a tool error, use the tool name as context
                error_message = f'{last_obs["tool_name"]}: {error_message}'

        # Try to extract file path from task or observations
        if '@' in task:
            # Extract file references from task
            import re

            file_refs = re.findall(r'@([^\s]+)', task)
            if file_refs:
                file_path = file_refs[0]

        # Create failure card
        storage = FailureCardStorage(root)
        card = FailureCard.create(
            run_id=run_id,
            error_type=error_type,
            file_path=file_path,
            error_message=error_message,
            task_description=task,
            context_files=[],
            line_number=line_number,
        )
        storage.append(card)

        import sys

        print(f'[TeaAgent] Failure card captured for run {run_id}', file=sys.stderr)
    except Exception as exc:
        # Don't let failure card capture break the background run system
        import sys

        print(
            f'[TeaAgent] Warning: Failed to capture failure card: {exc}',
            file=sys.stderr,
        )


def _refresh_process_state(
    data: dict[str, Any], record_path: Path, *, persist: bool = True
) -> dict[str, Any]:
    if data.get('stopped_at'):
        data['alive'] = False
        return data

    pid = int(data['pid'])
    exit_code: Optional[int] = None
    try:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        waited_pid = 0
    except OSError:
        waited_pid = 0
        status = 1

    if waited_pid == pid:
        alive = False
        exit_code = _exit_code_from_wait_status(status)
    else:
        alive = _process_exists(pid)

    data['alive'] = alive
    if not alive:
        data['stopped_at'] = _utc_now()
        if exit_code is not None:
            data['exit_code'] = exit_code
        elif data.get('exit_code') is None:
            # The child was reaped by another waitpid caller (e.g. the
            # subprocess module's _cleanup, a signal handler, or a
            # concurrent test), so the real exit code is lost. Leave it
            # unset; the orphan marker will surface the uncertainty.
            data['exit_code'] = None
        if data.get('exit_code') and data.get('run_id'):
            tenant_id = _get_tenant_id_from_path(record_path)
            if tenant_id == 'default':
                w_root = record_path.parent.parent.parent
            else:
                w_root = record_path.parent.parent.parent.parent.parent
            _capture_failure_card(
                w_root, data['run_id'], data['exit_code'], tenant_id=tenant_id
            )
        if persist:
            _persist_record_state(record_path, data)
    return data


def _reap(pid: int) -> bool:
    try:
        finished_pid, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    except OSError:
        return False
    return finished_pid == pid


def _is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if _reap(pid):
        return False
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


def build_agent_run_command(args: Any, task: Optional[str]) -> list[str]:  # noqa: C901
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
    if task:
        cmd.append(task)
    from_plan = getattr(args, 'from_plan', None)
    if from_plan:
        cmd.extend(['--from-plan', str(from_plan)])
    if getattr(args, 'allow_external_plan', False):
        cmd.append('--allow-external-plan')
    if getattr(args, 'require_plan', False):
        cmd.append('--require-plan')
    if getattr(args, 'skip_plan_check', False):
        cmd.append('--skip-plan-check')
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
    for scoped in getattr(args, 'approve_scoped', []) or []:
        cmd.extend(['--approve-scoped', scoped])
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
    max_cost = getattr(args, 'max_estimated_cost_cents', None)
    if max_cost is not None:
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
    if getattr(args, 'tenant_id', 'default') != 'default':
        cmd.extend(['--tenant-id', args.tenant_id])
    return cmd
