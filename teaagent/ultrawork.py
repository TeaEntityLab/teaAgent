from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.ergonomics.background_run import BackgroundRunStore


def _deprecate_ultrawork() -> None:
    print(
        "[TeaAgent WARNING] 'ultrawork' module and commands are deprecated. "
        "Please use 'teaagent.ergonomics.background_run' for detached worker records and "
        "'teaagent agent run \"<task>\"' or 'teaagent agent interactive-review <run_id>' instead.",
        file=sys.stderr,
    )


@dataclass(frozen=True)
class WorkerRecord:
    worker_id: str
    pid: int
    command: list[str]
    started_at: str
    log_path: str
    label: Optional[str] = None
    stopped_at: Optional[str] = None
    stop_signal: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'worker_id': self.worker_id,
            'pid': self.pid,
            'command': self.command,
            'started_at': self.started_at,
            'log_path': self.log_path,
            'label': self.label,
            'stopped_at': self.stopped_at,
            'stop_signal': self.stop_signal,
        }


class UltraworkStore:
    """Deprecated: Backward-compatibility wrapper delegating to BackgroundRunStore."""

    def __init__(
        self,
        root: str | Path = '.',
        *,
        notify_config: Any = None,
        readonly: bool = False,
    ) -> None:
        _deprecate_ultrawork()
        self._store = BackgroundRunStore(root, readonly=readonly)
        self.readonly = readonly
        self._notify_config = notify_config

    def start(self, command: list[str], *, label: Optional[str] = None) -> WorkerRecord:
        record = self._store.start(command, label=label)
        return WorkerRecord(
            worker_id=record.background_id,
            pid=record.pid,
            command=record.command,
            started_at=record.started_at,
            log_path=record.log_path,
            label=record.label,
            stopped_at=record.stopped_at,
        )

    def list(self) -> list[dict[str, Any]]:
        rows = self._store.list()
        for row in rows:
            row['worker_id'] = row.get('background_id')
        return rows

    def show(self, worker_id: str) -> dict[str, Any]:
        data = self._store.get(worker_id)
        data['worker_id'] = data.get('background_id')
        return data

    def logs(self, worker_id: str, *, max_bytes: int = 64_000) -> dict[str, Any]:
        res = self._store.logs(worker_id, max_bytes=max_bytes)
        res['worker_id'] = res.get('background_id')
        return res

    def stop(self, worker_id: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        data = self._store.stop(worker_id, timeout_seconds=timeout_seconds)
        data['worker_id'] = data.get('background_id')
        if self._notify_config is not None:
            from teaagent.notify import fire_notification

            class _Rec:
                pass

            rec = _Rec()
            rec.worker_id = worker_id  # type: ignore[attr-defined]
            rec.pid = data.get('pid')  # type: ignore[attr-defined]
            rec.started_at = data.get('started_at', '')  # type: ignore[attr-defined]
            rec.command = data.get('command', [])  # type: ignore[attr-defined]
            fire_notification(self._notify_config, rec, event='stopped')
        return data

    @staticmethod
    def _is_alive(pid: int) -> bool:
        from teaagent.ergonomics.background_run import _is_alive as run_is_alive

        return run_is_alive(pid)
