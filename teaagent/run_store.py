from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

from teaagent.audit import AuditEvent, AuditLogger, utc_now
from teaagent.runner import RunResult


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
            "run_id": self.run_id,
            "task": self.task,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "path": str(self.path),
            "final_answer": self.final_answer,
        }


class RunStore:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.store_dir = self.root / ".teaagent" / "runs"
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def audit_logger(self, run_id: Optional[str] = None) -> AuditLogger:
        if run_id is None:
            path = self.store_dir / "pending.jsonl"
        else:
            path = self.run_path(run_id)
        return AuditLogger(path=path)

    def logger_for_result(self, result: RunResult, audit: AuditLogger) -> None:
        if audit.path is None or audit.path == self.run_path(result.run_id):
            return
        target = self.run_path(result.run_id)
        target.write_text(audit.path.read_text(encoding="utf-8"), encoding="utf-8")
        audit.path.unlink(missing_ok=True)

    def run_path(self, run_id: str) -> Path:
        return self.store_dir / f"{safe_run_id(run_id)}.jsonl"

    def list_runs(self, *, limit: int = 20) -> list[RunSummary]:
        summaries = [self.summarize(path) for path in sorted(self.store_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)]
        return [summary for summary in summaries if summary is not None][:limit]

    def show_run(self, run_id: str) -> list[dict[str, Any]]:
        path = self.run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"run '{run_id}' not found")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def task_for_run(self, run_id: str) -> str:
        for event in self.show_run(run_id):
            if event.get("event_type") == "run_started":
                task = event.get("payload", {}).get("task")
                if isinstance(task, str) and task:
                    return task
        raise ValueError(f"run '{run_id}' has no run_started task")

    def summarize(self, path: Path) -> Optional[RunSummary]:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not events:
            return None
        run_id = events[0]["run_id"]
        task = ""
        status = "unknown"
        final_answer = None
        created_at = events[0].get("created_at", utc_now())
        updated_at = events[-1].get("created_at", created_at)
        for event in events:
            event_type = event.get("event_type")
            payload = event.get("payload", {})
            if event_type == "run_started":
                task = payload.get("task", "")
                status = "running"
            elif event_type == "run_completed":
                status = "completed"
                final_answer = payload.get("answer")
            elif event_type == "run_failed":
                status = f"failed:{payload.get('category', 'unknown')}"
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
    return "".join(ch for ch in run_id if ch.isalnum() or ch in {"-", "_"}) or "run"
