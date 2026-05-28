"""HTTP control plane for workflow, focus stack, and JIT approval dashboard."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from teaagent.jit_approval_server import JITApprovalServer

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent / 'html_dashboard'

_STATIC_FILES = frozenset({'index.html', 'app.js', 'styles.css'})


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Events frame."""
    return f'event: {event_type}\ndata: {json.dumps(data, separators=(",", ":"))}\n\n'


@dataclass
class JitDiffRecord:
    """Prompt or patch diff surfaced for dashboard review."""

    request_id: str
    agent_name: str
    old_text: str
    new_text: str
    unified_diff: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            'request_id': self.request_id,
            'agent_name': self.agent_name,
            'old_text': self.old_text,
            'new_text': self.new_text,
            'unified_diff': self.unified_diff,
            'created_at': self.created_at,
        }


@dataclass
class ControlPlaneState:
    """Mutable snapshots streamed to the HTML dashboard."""

    workflow: dict[str, Any] | None = None
    focus: dict[str, Any] | None = None
    jit_diffs: list[JitDiffRecord] = field(default_factory=list)
    polish_notes: str = ''
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_workflow(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.workflow = payload

    def set_focus(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.focus = payload

    def publish_jit_diff(
        self,
        request_id: str,
        agent_name: str,
        old_text: str,
        new_text: str,
        unified_diff: str,
    ) -> JitDiffRecord:
        record = JitDiffRecord(
            request_id=request_id,
            agent_name=agent_name,
            old_text=old_text,
            new_text=new_text,
            unified_diff=unified_diff,
        )
        with self._lock:
            self.jit_diffs.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                'workflow': self.workflow,
                'focus': self.focus,
                'jit_diffs': [item.to_dict() for item in self.jit_diffs],
                'polish_notes': self.polish_notes,
            }


class ControlPlaneServer:
    """Threaded HTTP server for dashboard static assets and SSE APIs."""

    def __init__(
        self,
        *,
        host: str = '127.0.0.1',
        port: int = 0,
        state: ControlPlaneState | None = None,
        jit_server: JITApprovalServer | None = None,
        dashboard_dir: Path | None = None,
        sse_interval_seconds: float = 1.0,
        max_sse_events: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.state = state or ControlPlaneState()
        self.jit_server = jit_server
        self.dashboard_dir = (dashboard_dir or DASHBOARD_DIR).resolve()
        self.sse_interval_seconds = sse_interval_seconds
        self.max_sse_events = max_sse_events
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, *, daemon: bool = True) -> None:
        """Start serving in a background thread."""
        handler = _make_handler(self)
        self._httpd = ControlPlaneHTTPServer(
            (self.host, self.port),
            handler,
            self,
        )
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='control-plane-http',
            daemon=daemon,
        )
        self._thread.start()
        logger.info('Control plane listening on %s', self.base_url)

    def stop(self) -> None:
        """Shut down the HTTP server."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def base_url(self) -> str:
        return f'http://{self.host}:{self.port}'

    def _pending_approvals(self) -> list[dict[str, Any]]:
        if self.jit_server is None:
            return []
        return [
            {
                'request_id': record.request_id,
                'agent_name': record.request.agent_name,
                'tool_name': record.request.tool_name,
                'reason': record.request.reason,
                'status': record.status.value,
            }
            for record in self.jit_server.get_pending_requests()
        ]


def _make_handler(
    plane: ControlPlaneServer,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server: ControlPlaneHTTPServer  # type: ignore[assignment]

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug(format, *args)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ('/', '/index.html'):
                self._serve_static('index.html', 'text/html; charset=utf-8')
                return
            if path == '/styles.css':
                self._serve_static('styles.css', 'text/css; charset=utf-8')
                return
            if path == '/app.js':
                self._serve_static('app.js', 'application/javascript; charset=utf-8')
                return
            if path == '/api/health':
                self._json_response(HTTPStatus.OK, {'status': 'ok'})
                return
            if path == '/api/workflow/stream':
                self._sse_stream('workflow_update', self._workflow_payload)
                return
            if path == '/api/focus/stream':
                self._sse_stream('focus_update', self._focus_payload)
                return
            if path == '/api/jit/diff':
                self._sse_stream('jit_diff', self._jit_payload)
                return
            self._json_response(HTTPStatus.NOT_FOUND, {'error': 'not found'})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            body = self._read_json_body()
            if path == '/api/jit/approve':
                self._jit_action(body, approve=True)
                return
            if path == '/api/jit/reject':
                self._jit_action(body, approve=False)
                return
            if path == '/api/workflow/polish':
                self._polish_action(body)
                return
            self._json_response(HTTPStatus.NOT_FOUND, {'error': 'not found'})

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            if not raw:
                return {}
            payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('expected JSON object')
            return payload

        def _serve_static(self, name: str, content_type: str) -> None:
            if name not in _STATIC_FILES:
                self._json_response(HTTPStatus.NOT_FOUND, {'error': 'not found'})
                return
            path = self.server.plane.dashboard_dir / name
            if not path.is_file():
                self._json_response(HTTPStatus.NOT_FOUND, {'error': 'missing asset'})
                return
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _workflow_payload(self) -> dict[str, Any]:
            snap = self.server.plane.state.snapshot()
            return {
                'workflow': snap.get('workflow'),
                'polish_notes': snap.get('polish_notes', ''),
            }

        def _focus_payload(self) -> dict[str, Any]:
            snap = self.server.plane.state.snapshot()
            return {'focus': snap.get('focus')}

        def _jit_payload(self) -> dict[str, Any]:
            snap = self.server.plane.state.snapshot()
            return {
                'pending': self.server.plane._pending_approvals(),
                'diffs': snap.get('jit_diffs', []),
            }

        def _sse_stream(
            self,
            event_type: str,
            payload_fn: Callable[[], dict[str, Any]],
        ) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            sent = 0
            limit = self.server.plane.max_sse_events
            try:
                while limit is None or sent < limit:
                    frame = format_sse_event(event_type, payload_fn())
                    self.wfile.write(frame.encode('utf-8'))
                    self.wfile.flush()
                    sent += 1
                    if limit is not None and sent >= limit:
                        break
                    time.sleep(self.server.plane.sse_interval_seconds)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _jit_action(self, body: dict[str, Any], *, approve: bool) -> None:
            request_id = str(body.get('request_id', '')).strip()
            if not request_id:
                self._json_response(
                    HTTPStatus.BAD_REQUEST, {'error': 'request_id required'}
                )
                return
            jit = self.server.plane.jit_server
            if jit is None:
                self._json_response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {'error': 'jit server not configured'},
                )
                return
            if approve:
                jit.approve_request(request_id)
            else:
                jit.reject_request(request_id)
            record = jit.get_request_status(request_id)
            status = record.status.value if record else 'unknown'
            self._json_response(
                HTTPStatus.OK, {'request_id': request_id, 'status': status}
            )

        def _polish_action(self, body: dict[str, Any]) -> None:
            notes = str(body.get('notes', '')).strip()
            with self.server.plane.state._lock:
                self.server.plane.state.polish_notes = notes
            self._json_response(HTTPStatus.OK, {'ok': True, 'notes': notes})

    return Handler


class ControlPlaneHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server carrying control-plane configuration."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        plane: ControlPlaneServer,
    ) -> None:
        self.plane = plane
        super().__init__(server_address, handler)
