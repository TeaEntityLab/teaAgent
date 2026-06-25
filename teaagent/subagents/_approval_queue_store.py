"""Disk-backed approval queue state for cross-process parent/subagent coordination."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from teaagent.errors import ConfigError
from teaagent.security_env import _env_truthy
from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)

logger = logging.getLogger(__name__)


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
    # Files whose HMAC could not be verified (legacy-unsigned or tampered).
    # Never pruned — their contents are unknown, so deleting them could lose
    # pending approval requests. Resolve via an explicit migration.
    skipped_unverified: list[str] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.removed_parent_run_ids)


class ApprovalQueueStore:
    """Persist approval queue state under ``.teaagent/approval_queues/``."""

    def __init__(
        self,
        workspace_root: Path,
        hmac_secret: Optional[str] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.queue_dir = self.workspace_root / '.teaagent' / 'approval_queues'
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        if hmac_secret is not None:
            self.hmac_secret = hmac_secret
        else:
            self.hmac_secret = _load_or_generate_hmac_key(self.workspace_root)
        self._snapshot_cache: dict[str, tuple[float, QueueDiskSnapshot]] = {}

    def queue_path(self, parent_run_id: str) -> Path:
        safe_id = parent_run_id.replace('/', '_')
        return self.queue_dir / f'{safe_id}.json'

    def list_parent_run_ids(self) -> list[str]:
        ids: list[str] = []
        for path in sorted(self.queue_dir.glob('*.json')):
            ids.append(path.stem)
        return ids

    def get_all_requests(self) -> list[dict[str, Any]]:
        """Get all requests from all parent runs.

        Returns:
            List of all request dictionaries
        """
        all_requests = []
        parent_run_ids = self.list_parent_run_ids()

        for parent_run_id in parent_run_ids:
            try:
                snapshot = self.load(parent_run_id)
                for _request_id, request_data in snapshot.requests.items():
                    all_requests.append(request_data)
            except Exception as e:
                logger.warning(f'Failed to load requests for {parent_run_id}: {e}')

        return all_requests

    def exists(self, parent_run_id: str) -> bool:
        return self.queue_path(parent_run_id).is_file()

    def _serialize_signed(self, payload: dict) -> str:
        """Serialize *payload* to JSON once and embed the HMAC.

        Rewriting the whole queue on every update is dominated by JSON
        serialization, so avoid serializing twice (once to sign, once to
        write). The canonical (sort_keys) serialization is signed and the
        ``_hmac`` field is string-spliced in, so the signed bytes are exactly
        what :meth:`_verify_hmac` recomputes (canonical, ``_hmac`` excluded).
        *payload* must not already contain an ``_hmac`` key.
        """
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if not self.hmac_secret:
            return body
        digest = hmac.new(
            self.hmac_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        prefix = '{"_hmac": ' + json.dumps(digest)
        return prefix + '}' if body == '{}' else prefix + ', ' + body[1:]

    def _verify_hmac(self, raw: dict) -> bool:
        """Verify the ``_hmac`` field on *raw* matches the computed HMAC.

        Returns ``False`` when the digest doesn't match.  When ``_hmac`` is
        absent and ``TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT`` is set to a truthy
        value the record is accepted as-is (backward compatibility).
        """
        if not self.hmac_secret:
            return True
        stored = raw.get('_hmac')
        if not stored:
            # Proper truthy parsing: "0"/"false" must NOT enable legacy accept
            # (bool('0') is True in Python). Centralized in security_env.
            return _env_truthy('TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT')
        expected = hmac.new(
            self.hmac_secret.encode('utf-8'),
            json.dumps(
                {k: v for k, v in raw.items() if k != '_hmac'},
                sort_keys=True,
                ensure_ascii=False,
            ).encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, stored)

    @contextmanager
    def lock(self, parent_run_id: str, shared: bool = False) -> Iterator[None]:
        path = self.queue_path(parent_run_id).with_suffix('.json.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+', encoding='utf-8') as handle:
            try:
                import fcntl

                lock_flag = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                fcntl.flock(handle.fileno(), lock_flag)
            except (ImportError, OSError):
                # fcntl is Unix-specific; gracefully fall back to no locking on Windows or other platforms
                pass
            try:
                yield
            finally:
                try:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    # fcntl is Unix-specific; gracefully fall back to no unlocking on Windows or other platforms
                    pass

    def load(self, parent_run_id: str) -> QueueDiskSnapshot:
        path = self.queue_path(parent_run_id)
        if not path.is_file():
            return QueueDiskSnapshot(parent_run_id, {}, {})
        mtime = path.stat().st_mtime
        cached = self._snapshot_cache.get(parent_run_id)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with self.lock(parent_run_id, shared=True):
            raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return QueueDiskSnapshot(parent_run_id, {}, {})
        if self.hmac_secret and not self._verify_hmac(raw):
            import logging

            logging.getLogger(__name__).warning(
                'HMAC verification failed for approval queue %s — returning empty snapshot',
                parent_run_id,
            )
            return QueueDiskSnapshot(parent_run_id, {}, {})
        requests = raw.get('requests', {})
        batches = raw.get('batches', {})
        if not isinstance(requests, dict):
            requests = {}
        if not isinstance(batches, dict):
            batches = {}
        snapshot = QueueDiskSnapshot(parent_run_id, requests, batches)
        self._snapshot_cache[parent_run_id] = (mtime, snapshot)
        return snapshot

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, Any],
        batches: dict[str, Any],
    ) -> None:
        path = self.queue_path(parent_run_id)
        with self.lock(parent_run_id):
            payload = {
                'parent_run_id': parent_run_id,
                'requests': {rid: req.to_dict() for rid, req in requests.items()},
                'batches': {bid: batch.to_dict() for bid, batch in batches.items()},
            }
            temp = path.with_suffix('.json.tmp')
            temp.write_text(
                self._serialize_signed(payload) + '\n',
                encoding='utf-8',
            )
            os.replace(temp, path)
        self._snapshot_cache.pop(parent_run_id, None)

    def batch_update_requests(
        self,
        parent_run_id: str,
        updates: dict[str, dict[str, Any]],
    ) -> bool:
        """Update multiple requests in a single file write operation.

        Args:
            parent_run_id: Parent run ID
            updates: Dictionary mapping request_id to update fields

        Returns:
            True if successful
        """
        try:
            with self.lock(parent_run_id):
                snapshot = self.load(parent_run_id)
                requests = dict(snapshot.requests)

                # Apply all updates
                for request_id, update_fields in updates.items():
                    if request_id in requests:
                        request_dict = requests[request_id]
                        request_dict.update(update_fields)
                        requests[request_id] = request_dict

                # Save in single operation
                self.save(parent_run_id, requests, snapshot.batches)
            return True
        except Exception as e:
            logger.error(f'Batch update failed: {e}')
            return False

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

    def _verify_file_unlocked(self, parent_run_id: str) -> bool:
        """Return whether the on-disk queue file passes HMAC verification.

        Unlike :meth:`_load_unlocked`, a verification failure is reported as
        ``False`` rather than masked as an empty snapshot, so callers (e.g.
        ``prune_stale``) can avoid deleting data they cannot verify. A missing
        or structurally-invalid file is treated as verified (nothing to lose).
        """
        path = self.queue_path(parent_run_id)
        if not path.is_file():
            return True
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(raw, dict):
            return True
        return self._verify_hmac(raw)

    def _load_unlocked(self, parent_run_id: str) -> QueueDiskSnapshot:
        path = self.queue_path(parent_run_id)
        if not path.is_file():
            return QueueDiskSnapshot(parent_run_id, {}, {})
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return QueueDiskSnapshot(parent_run_id, {}, {})
        if self.hmac_secret and not self._verify_hmac(raw):
            import logging

            logging.getLogger(__name__).warning(
                'HMAC verification failed (unlocked) for approval queue %s — returning empty',
                parent_run_id,
            )
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
            self._serialize_signed(payload) + '\n',
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
        skipped_unverified: list[str] = []
        for path in sorted(self.queue_dir.glob('*.json')):
            parent_run_id = path.stem
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > cutoff:
                skipped_recent.append(parent_run_id)
                continue
            # Acquire exclusive lock to prevent concurrent read/write races
            with self.lock(parent_run_id):
                # Fail closed: if HMAC is enforced and the on-disk file cannot
                # be verified (legacy-unsigned or tampered), its contents are
                # unknown. A failed verification surfaces as an empty snapshot,
                # which would otherwise be deleted as "no pending requests" —
                # silently losing real pending approvals. Preserve it instead
                # and let an explicit migration resolve it.
                if self.hmac_secret and not self._verify_file_unlocked(parent_run_id):
                    import logging

                    logging.getLogger(__name__).warning(
                        'approval queue %s failed HMAC verification — preserving '
                        '(not pruning); migrate or set '
                        'TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT to re-sign legacy data',
                        parent_run_id,
                    )
                    skipped_unverified.append(parent_run_id)
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
            skipped_unverified=skipped_unverified,
        )


def _key_path(workspace_root: Path) -> Path:
    return workspace_root / '.teaagent' / 'approval_queue.key'


def _load_or_generate_hmac_key(workspace_root: Path) -> str:
    """Load or generate the HMAC key for approval queue integrity.

    Priority:
    1. ``TEAAGENT_APPROVAL_HMAC_KEY`` env var (no file written).
    2. Existing ``.teaagent/approval_queue.key`` with mode 0o600.
    3. Generate a fresh 32-byte hex key and persist it with mode 0o600.

    Raises ``ConfigError`` when the key file exists but is world-readable
    (mode != 0o600).
    """
    env_key = os.environ.get('TEAAGENT_APPROVAL_HMAC_KEY')
    if env_key:
        return env_key

    kp = _key_path(workspace_root)
    if kp.is_file():
        mode = kp.stat().st_mode & 0o777
        if mode != 0o600:
            raise ConfigError(
                f'Approval queue HMAC key {kp} has mode {oct(mode)}; '
                f'expected 0o600. Fix with: chmod 0o600 {kp}'
            )
        return kp.read_text(encoding='utf-8').strip()

    raw = secrets.token_hex(32)  # 32 bytes → 64 hex chars
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_text(raw, encoding='utf-8')
    kp.chmod(0o600)
    return raw


def default_hmac_secret() -> Optional[str]:
    """Read the HMAC key from ``TEAAGENT_APPROVAL_HMAC_KEY`` env var.

    Returns ``None`` when the variable is unset or empty so that callers
    fall back to automatic key generation through ``_load_or_generate_hmac_key``.
    """
    return os.environ.get('TEAAGENT_APPROVAL_HMAC_KEY') or None


def request_from_dict(data: dict[str, Any]) -> SubagentApprovalRequest:
    """Deserialize a SubagentApprovalRequest from a dictionary with validation.

    Args:
        data: Dictionary containing request data.

    Returns:
        SubagentApprovalRequest instance.

    Raises:
        ValueError: If required fields are missing, invalid, or type mismatches occur.
        KeyError: If required fields are missing from the dictionary.
    """
    from datetime import datetime, timezone

    # Validate required fields
    required_fields = [
        'request_id',
        'subagent_id',
        'parent_run_id',
        'subagent_name',
        'tool_name',
    ]

    for req_field in required_fields:
        if req_field not in data:
            raise ValueError(f'Missing required field: {req_field}')
        if not data[req_field]:
            raise ValueError(f"Required field '{req_field}' cannot be empty or None")

    # Validate and convert status enum
    status_value = data.get('status', ApprovalRequestStatus.PENDING.value)
    try:
        status = ApprovalRequestStatus(status_value)
    except ValueError as e:
        valid_statuses = [s.value for s in ApprovalRequestStatus]
        raise ValueError(
            f"Invalid status '{status_value}'. Must be one of: {valid_statuses}"
        ) from e

    # Validate and convert tool_arguments
    tool_arguments = data.get('tool_arguments')
    if tool_arguments is None:
        tool_arguments = {}
    elif not isinstance(tool_arguments, dict):
        raise ValueError(
            f'tool_arguments must be a dict, got {type(tool_arguments).__name__}'
        )

    # Validate timeout_seconds
    timeout_seconds = data.get('timeout_seconds', 180)
    try:
        timeout_seconds = int(timeout_seconds)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid timeout_seconds '{timeout_seconds}': must be a positive integer"
        ) from e

    if timeout_seconds <= 0:
        raise ValueError(f'timeout_seconds must be positive, got {timeout_seconds}')

    # Validate optional integer fields
    batch_index = data.get('batch_index')
    if batch_index is not None:
        try:
            batch_index = int(batch_index)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid batch_index '{batch_index}': must be a non-negative integer"
            ) from e

        if batch_index < 0:
            raise ValueError(f'batch_index must be non-negative, got {batch_index}')

    # Validate timestamp fields (optional, but must be strings if present)
    for ts_field in ('created_at', 'approved_at', 'denied_at'):
        value = data.get(ts_field)
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"Field '{ts_field}' must be a string or None, got {type(value).__name__}"
            )

    # Build the request with validated data
    return SubagentApprovalRequest(
        request_id=str(data['request_id']),
        subagent_id=str(data['subagent_id']),
        parent_run_id=str(data['parent_run_id']),
        subagent_name=str(data['subagent_name']),
        tool_name=str(data['tool_name']),
        tool_arguments=tool_arguments,
        permission_mode=str(data.get('permission_mode', '')),
        isolation=str(data.get('isolation', '')),
        batch_index=batch_index,
        worktree_path=data.get('worktree_path'),
        created_at=str(
            data.get('created_at') or datetime.now(timezone.utc).isoformat()
        ),
        status=status,
        approved_at=data.get('approved_at'),
        denied_at=data.get('denied_at'),
        denial_reason=data.get('denial_reason'),
        denied_by=data.get('denied_by'),
        timeout_seconds=timeout_seconds,
    )


def pending_requests_from_snapshot(
    snapshot: QueueDiskSnapshot,
) -> list[SubagentApprovalRequest]:
    pending: list[SubagentApprovalRequest] = []
    for raw in snapshot.requests.values():
        if raw.get('status') == ApprovalRequestStatus.PENDING.value:
            pending.append(request_from_dict(raw))
    return pending
