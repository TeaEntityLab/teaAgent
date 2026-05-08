from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_PROC_HANDLES: dict[str, "subprocess.Popen[bytes]"] = {}


def _reap(pid: int) -> bool:
    try:
        finished_pid, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    except OSError:
        return False
    return finished_pid == pid


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
        return asdict(self)


class UltraworkStore:
    """Detached background workers persisted under .teaagent/ultrawork/."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.dir = self.root / ".teaagent" / "ultrawork"
        self.dir.mkdir(parents=True, exist_ok=True)

    def start(self, command: list[str], *, label: Optional[str] = None) -> WorkerRecord:
        if not command:
            raise ValueError("ultrawork command must not be empty")
        worker_id = uuid4().hex
        log_path = self.dir / f"{worker_id}.log"
        record_path = self.dir / f"{worker_id}.json"
        log_handle = log_path.open("w", encoding="utf-8")
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
        record = WorkerRecord(
            worker_id=worker_id,
            pid=proc.pid,
            command=list(command),
            started_at=_utc_now(),
            log_path=str(log_path),
            label=label,
        )
        record_path.write_text(json.dumps(record.to_dict(), sort_keys=True), encoding="utf-8")
        _PROC_HANDLES[worker_id] = proc
        return record

    def list(self) -> list[dict[str, Any]]:
        records = []
        for path in sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["alive"] = self._is_alive(int(data["pid"]))
            records.append(data)
        return records

    def show(self, worker_id: str) -> dict[str, Any]:
        record_path = self.dir / f"{worker_id}.json"
        if not record_path.exists():
            raise FileNotFoundError(f"ultrawork worker '{worker_id}' not found")
        data = json.loads(record_path.read_text(encoding="utf-8"))
        data["alive"] = self._is_alive(int(data["pid"]))
        return data

    def stop(self, worker_id: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        data = self.show(worker_id)
        pid = int(data["pid"])
        signal_name = "SIGTERM"
        proc = _PROC_HANDLES.get(worker_id)
        if self._is_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.time() + max(0.0, timeout_seconds)
            while time.time() < deadline and self._is_alive(pid):
                time.sleep(0.05)
            if self._is_alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                    signal_name = "SIGKILL"
                except ProcessLookupError:
                    pass
        if proc is not None:
            try:
                proc.wait(timeout=max(0.1, timeout_seconds))
            except subprocess.TimeoutExpired:
                pass
            _PROC_HANDLES.pop(worker_id, None)
        data["stopped_at"] = _utc_now()
        data["stop_signal"] = signal_name
        data["alive"] = False
        record_path = self.dir / f"{worker_id}.json"
        record_path.write_text(json.dumps({k: v for k, v in data.items() if k != "alive"}, sort_keys=True), encoding="utf-8")
        return data

    @staticmethod
    def _is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if _reap(pid):
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
