"""HTTP client for remote approval coordination (WDE-001 HTTP transport)."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from teaagent.http_utils import safe_urlopen
from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueuePruneReport,
    QueueDiskSnapshot,
)

BACKEND_HTTP = 'http-remote'


class ApprovalHttpError(RuntimeError):
    """Raised when the remote approval HTTP API returns an error."""


class HttpApprovalCoordinationBackend:
    """REST client for cross-machine approval queue coordination."""

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._auth_token = auth_token
        self._timeout_seconds = timeout_seconds

    @property
    def backend_id(self) -> str:
        return BACKEND_HTTP

    def _headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'teaagent-approval-client',
        }
        if self._auth_token:
            headers['Authorization'] = f'Bearer {self._auth_token}'
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        payload = json.dumps(body).encode('utf-8') if body is not None else None
        try:
            with safe_urlopen(
                f'{self._base_url}{path}',
                timeout=int(self._timeout_seconds),
                allow_http=True,
                data=payload,
                headers=self._headers(),
                method=method,
            ) as response:
                raw = response.read().decode('utf-8')
                if not raw.strip():
                    return {}
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            detail = exc.read().decode('utf-8', errors='replace')
            raise ApprovalHttpError(
                f'{method} {path} failed with HTTP {exc.code}: {detail}'
            ) from exc
        except URLError as exc:
            raise ApprovalHttpError(f'{method} {path} failed: {exc}') from exc

    def load_snapshot(self, parent_run_id: str) -> QueueDiskSnapshot:
        encoded = quote(parent_run_id, safe='')
        payload = self._request(
            'GET',
            f'/v1/queues/{encoded}',
            allow_404=True,
        )
        if payload is None:
            return QueueDiskSnapshot(parent_run_id, {}, {})
        requests = payload.get('requests', {})
        batches = payload.get('batches', {})
        return QueueDiskSnapshot(
            parent_run_id,
            requests if isinstance(requests, dict) else {},
            batches if isinstance(batches, dict) else {},
        )

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        encoded = quote(parent_run_id, safe='')
        self._request(
            'PUT',
            f'/v1/queues/{encoded}',
            body={
                'parent_run_id': parent_run_id,
                'requests': {rid: req.to_dict() for rid, req in requests.items()},
                'batches': {bid: batch.to_dict() for bid, batch in batches.items()},
            },
        )

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        encoded_parent = quote(parent_run_id, safe='')
        encoded_request = quote(request_id, safe='')
        payload = self._request(
            'POST',
            f'/v1/queues/{encoded_parent}/requests/{encoded_request}/status',
            body={
                'status': status.value,
                'reason': reason,
                'approved_by': approved_by,
            },
        )
        return bool(payload and payload.get('updated'))

    def list_parent_run_ids(self) -> list[str]:
        payload = self._request('GET', '/v1/queues') or {}
        ids = payload.get('parent_run_ids', [])
        return [str(item) for item in ids] if isinstance(ids, list) else []

    def exists(self, parent_run_id: str) -> bool:
        encoded = quote(parent_run_id, safe='')
        payload = self._request(
            'GET',
            f'/v1/queues/{encoded}',
            allow_404=True,
        )
        return payload is not None

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        payload = self._request(
            'POST',
            '/v1/queues/prune',
            body={'max_age_seconds': max_age_seconds, 'now': now},
        )
        if not payload:
            return ApprovalQueuePruneReport()
        return ApprovalQueuePruneReport(
            removed_parent_run_ids=list(
                payload.get('removed_parent_run_ids', []) or []
            ),
            skipped_pending=list(payload.get('skipped_pending', []) or []),
            skipped_recent=list(payload.get('skipped_recent', []) or []),
        )
