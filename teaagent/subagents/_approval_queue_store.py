"""Disk-backed approval queue state for cross-process parent/subagent coordination."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)


@dataclass(frozen=True)
class QueueDiskSnapshot:
    parent_run_id: str
    requests: dict[str, dict[str, Any]]
    batches: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class ApprovalQueuePruneReport:
    removed_parent_run_ids: list[str] = field(default_factory=list)
    skipped_pending: list[str] = field(default_factory=list)
    skipped_recent: list[str] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.removed_parent_run_ids)


class ApprovalQueueStore:
    """Persist approval queue state under ``.teaagent/approval_queues/``."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.queue_dir = self.workspace_root / '.teaagent' / 'approval_queues'
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def queue_path(self, parent_run_id: str) -> Path:
        safe_id = parent_run_id.replace('/', '_')
        return self.queue_dir / f'{safe_id}.json'

    def list_parent_run_ids(self) -> list[str]:
        ids: list[str] = []
        for path in sorted(self.queue_dir.glob('*.json')):
            ids.append(path.stem)
        return ids

    def exists(self, parent_run_id: str) -> bool:
        return self.queue_path(parent_run_id).is_file()

    @contextmanager
    def lock(self, parent_run_id: str) -> Iterator[None]:
        path = self.queue_path(parent_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+', encoding='utf-8') as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass
            try:
                yield
            finally:
                try:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    pass

    def load(self, parent_run_id: str) -> QueueDiskSnapshot:
        path = self.queue_path(parent_run_id)
        if not path.is_file():
            return QueueDiskSnapshot(parent_run_id, {}, {})
        with self.lock(parent_run_id):
            raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return QueueDiskSnapshot(parent_run_id, {}, {})
        requests = raw.get('requests', {})
        batches = raw.get('batches', {})
        if not isinstance(requests, dict):
            requests = {}
        if not isinstance(batches, dict):
            batches = {}
        return QueueDiskSnapshot(parent_run_id, requests, batches)

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        path = self.queue_path(parent_run_id)
        payload = {
            'parent_run_id': parent_run_id,
            'requests': {rid: req.to_dict() for rid, req in requests.items()},
            'batches': {bid: batch.to_dict() for bid, batch in batches.items()},
        }
        with self.lock(parent_run_id):
            temp = path.with_suffix('.json.tmp')
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            os.replace(temp, path)

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        from datetime import datetime, timezone

        with self.lock(parent_run_id):
            snapshot = self._load_unlocked(parent_run_id)
            raw = snapshot.requests.get(request_id)
            if not raw or raw.get('status') != ApprovalRequestStatus.PENDING.value:
                return False
            now = datetime.now(timezone.utc).isoformat()
            raw['status'] = status.value
            if status == ApprovalRequestStatus.APPROVED:
                raw['approved_at'] = now
                raw['approved_by'] = approved_by
            if status == ApprovalRequestStatus.DENIED:
                raw['denied_at'] = now
                raw['denial_reason'] = reason or 'Denied by human'
            snapshot.requests[request_id] = raw
            self._save_unlocked(parent_run_id, snapshot)
        return True

    def _load_unlocked(self, parent_run_id: str) -> QueueDiskSnapshot:
        path = self.queue_path(parent_run_id)
        if not path.is_file():
            return QueueDiskSnapshot(parent_run_id, {}, {})
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return QueueDiskSnapshot(parent_run_id, {}, {})
        requests = raw.get('requests', {})
        batches = raw.get('batches', {})
        return QueueDiskSnapshot(
            parent_run_id,
            requests if isinstance(requests, dict) else {},
            batches if isinstance(batches, dict) else {},
        )

    def _save_unlocked(self, parent_run_id: str, snapshot: QueueDiskSnapshot) -> None:
        path = self.queue_path(parent_run_id)
        payload = {
            'parent_run_id': parent_run_id,
            'requests': snapshot.requests,
            'batches': snapshot.batches,
        }
        temp = path.with_suffix('.json.tmp')
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        os.replace(temp, path)

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        """Remove queue files with no pending requests older than *max_age_seconds*."""
        cutoff = (now if now is not None else time.time()) - max_age_seconds
        removed: list[str] = []
        skipped_pending: list[str] = []
        skipped_recent: list[str] = []
        for path in sorted(self.queue_dir.glob('*.json')):
            parent_run_id = path.stem
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > cutoff:
                skipped_recent.append(parent_run_id)
                continue
            snapshot = self._load_unlocked(parent_run_id)
            has_pending = any(
                raw.get('status') == ApprovalRequestStatus.PENDING.value
                for raw in snapshot.requests.values()
            )
            if has_pending:
                skipped_pending.append(parent_run_id)
                continue
            path.unlink(missing_ok=True)
            removed.append(parent_run_id)
        return ApprovalQueuePruneReport(
            removed_parent_run_ids=removed,
            skipped_pending=skipped_pending,
            skipped_recent=skipped_recent,
        )


def request_from_dict(data: dict[str, Any]) -> SubagentApprovalRequest:
    from datetime import datetime, timezone

    status = ApprovalRequestStatus(data.get('status', ApprovalRequestStatus.PENDING.value))
    return SubagentApprovalRequest(
        request_id=str(data['request_id']),
        subagent_id=str(data['subagent_id']),
        parent_run_id=str(data['parent_run_id']),
        subagent_name=str(data['subagent_name']),
        tool_name=str(data['tool_name']),
        tool_arguments=dict(data.get('tool_arguments') or {}),
        permission_mode=str(data.get('permission_mode', '')),
        isolation=str(data.get('isolation', '')),
        batch_index=data.get('batch_index'),
        worktree_path=data.get('worktree_path'),
        created_at=str(
            data.get('created_at') or datetime.now(timezone.utc).isoformat()
        ),
        status=status,
        approved_at=data.get('approved_at'),
        denied_at=data.get('denied_at'),
        denial_reason=data.get('denial_reason'),
        timeout_seconds=int(data.get('timeout_seconds', 180)),
    )


def pending_requests_from_snapshot(
    snapshot: QueueDiskSnapshot,
) -> list[SubagentApprovalRequest]:
    pending: list[SubagentApprovalRequest] = []
    for raw in snapshot.requests.values():
        if raw.get('status') == ApprovalRequestStatus.PENDING.value:
            pending.append(request_from_dict(raw))
    return pending
