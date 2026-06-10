"""HTTP server for remote approval coordination (WDE-001 HTTP transport)."""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from teaagent.coordination.approval_backend import FileBackedApprovalBackend
from teaagent.subagents._approval_queue import ApprovalRequestStatus

logger = logging.getLogger(__name__)


class ApprovalCoordinationHttpServer:
    """Serve durable approval queue operations over HTTP."""

    def __init__(
        self,
        backend: FileBackedApprovalBackend,
        *,
        host: str = '127.0.0.1',
        port: int = 0,
        auth_token: Optional[str] = None,
    ) -> None:
        self._backend = backend
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._httpd is None:
            raise RuntimeError('server not started')
        host = self._host
        if host in {'0.0.0.0', '::'}:
            host = '127.0.0.1'
        return f'http://{host}:{self._httpd.server_port}'

    def start(self) -> None:
        if self._httpd is not None:
            return

        backend = self._backend
        auth_token = self._auth_token

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                logger.debug('approval-http ' + format, *args)

            def _authorized(self) -> bool:
                if not auth_token:
                    return True
                header = self.headers.get('Authorization', '')
                expected = f'Bearer {auth_token}'
                return header == expected

            def _send_json(
                self,
                status: int,
                payload: dict[str, Any] | None = None,
            ) -> None:
                body = json.dumps(payload or {}).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get('Content-Length', '0') or 0)
                raw = self.rfile.read(length) if length else b'{}'
                parsed = json.loads(raw.decode('utf-8') or '{}')
                return parsed if isinstance(parsed, dict) else {}

            def do_GET(self) -> None:
                if not self._authorized():
                    self._send_json(401, {'error': 'unauthorized'})
                    return
                path = urlparse(self.path).path
                if path == '/v1/queues':
                    self._send_json(
                        200,
                        {'parent_run_ids': backend.list_parent_run_ids()},
                    )
                    return
                prefix = '/v1/queues/'
                if path.startswith(prefix):
                    parent_run_id = unquote(path[len(prefix) :])
                    if not backend.exists(parent_run_id):
                        self._send_json(404, {'error': 'not_found'})
                        return
                    snapshot = backend.load_snapshot(parent_run_id)
                    self._send_json(
                        200,
                        {
                            'parent_run_id': parent_run_id,
                            'requests': snapshot.requests,
                            'batches': snapshot.batches,
                        },
                    )
                    return
                self._send_json(404, {'error': 'not_found'})

            def do_PUT(self) -> None:
                if not self._authorized():
                    self._send_json(401, {'error': 'unauthorized'})
                    return
                path = urlparse(self.path).path
                prefix = '/v1/queues/'
                if not path.startswith(prefix) or '/requests/' in path:
                    self._send_json(404, {'error': 'not_found'})
                    return
                parent_run_id = unquote(path[len(prefix) :])
                payload = self._read_json()
                requests_raw = payload.get('requests', {})
                batches_raw = payload.get('batches', {})
                if not isinstance(requests_raw, dict):
                    requests_raw = {}
                if not isinstance(batches_raw, dict):
                    batches_raw = {}
                backend.save_raw_snapshot(parent_run_id, requests_raw, batches_raw)
                self._send_json(200, {'saved': True})

            def do_POST(self) -> None:
                if not self._authorized():
                    self._send_json(401, {'error': 'unauthorized'})
                    return
                path = urlparse(self.path).path
                if path == '/v1/queues/prune':
                    payload = self._read_json()
                    report = backend.prune_stale(
                        max_age_seconds=float(payload.get('max_age_seconds', 0)),
                        now=payload.get('now'),
                    )
                    self._send_json(
                        200,
                        {
                            'removed_parent_run_ids': report.removed_parent_run_ids,
                            'skipped_pending': report.skipped_pending,
                            'skipped_recent': report.skipped_recent,
                        },
                    )
                    return
                marker = '/requests/'
                if path.startswith('/v1/queues/') and path.endswith('/status'):
                    body = path[len('/v1/queues/') : -len('/status')]
                    if marker not in body:
                        self._send_json(404, {'error': 'not_found'})
                        return
                    parent_run_id, request_id = body.split(marker, 1)
                    parent_run_id = unquote(parent_run_id)
                    request_id = unquote(request_id.rstrip('/'))
                    payload = self._read_json()
                    status = ApprovalRequestStatus(str(payload.get('status', '')))
                    updated = backend.update_request_status(
                        parent_run_id,
                        request_id,
                        status,
                        reason=payload.get('reason'),
                        approved_by=str(payload.get('approved_by', 'human')),
                    )
                    self._send_json(200, {'updated': updated})
                    return
                self._send_json(404, {'error': 'not_found'})

        self._httpd = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='approval-http-server',
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None
