"""HTTP control plane for workflow, focus stack, and JIT approval dashboard."""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import suppress
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from teaagent.control_plane_tenant import (
    ControlPlaneRegistry,
    ControlPlaneState,
    sanitize_tenant_id,
)
from teaagent.jit_approval_server import JITApprovalServer
from teaagent.surface_auth import SurfaceAuthPolicy, authorize_request, is_loopback_host

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent / 'html_dashboard'

_STATIC_FILES = frozenset({'index.html', 'app.js', 'styles.css'})


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Events frame."""
    return f'event: {event_type}\ndata: {json.dumps(data, separators=(",", ":"))}\n\n'


class ControlPlaneServer:
    """Threaded HTTP server for dashboard static assets and SSE APIs."""

    def __init__(
        self,
        *,
        host: str = '127.0.0.1',
        port: int = 0,
        state: ControlPlaneState | None = None,
        tenant_registry: ControlPlaneRegistry | None = None,
        jit_server: JITApprovalServer | None = None,
        dashboard_dir: Path | None = None,
        sse_interval_seconds: float = 1.0,
        max_sse_events: int | None = None,
        auth_policy: SurfaceAuthPolicy | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.auth_policy = auth_policy
        if not is_loopback_host(host) and auth_policy is None:
            raise ValueError(
                'non-loopback control plane bind requires --api-token-file or --api-token'
            )
        self.registry = tenant_registry or ControlPlaneRegistry()
        if state is not None:
            self.registry.seed(self.registry.default_tenant, state)
        self.jit_server = jit_server
        self.dashboard_dir = (dashboard_dir or DASHBOARD_DIR).resolve()
        self.sse_interval_seconds = sse_interval_seconds
        self.max_sse_events = max_sse_events
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def state(self) -> ControlPlaneState:
        """Default-tenant state (backward compatible)."""
        return self.registry.get_or_create(self.registry.default_tenant)

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

    def _shutdown_httpd(self, httpd: ThreadingHTTPServer | None) -> None:
        if httpd is None:
            return
        with suppress(Exception):
            httpd.shutdown()
        with suppress(Exception):
            httpd.server_close()

    def stop(self) -> None:
        """Shut down the HTTP server."""
        httpd = self._httpd
        self._httpd = None
        self._shutdown_httpd(httpd)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def serve_blocking(self, *, announce: bool = True) -> None:
        """Serve on the foreground thread until interrupted."""
        handler = _make_handler(self)
        httpd = ControlPlaneHTTPServer((self.host, self.port), handler, self)
        self._httpd = httpd
        self.port = int(httpd.server_address[1])
        logger.info('Control plane listening on %s', self.base_url)
        if announce:
            print(f'TeaAgent control plane running at {self.base_url}')
            print('Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if self._httpd is httpd:
                self._httpd = None
            self._shutdown_httpd(httpd)

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

        def _resolve_tenant_id(self) -> str:
            header = self.headers.get('X-TeaAgent-Tenant', '').strip()
            parsed = urlparse(self.path)
            tenant = header
            if not tenant and parsed.path.startswith('/api/tenants/'):
                parts = [part for part in parsed.path.split('/') if part]
                if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'tenants':
                    tenant = parts[2]
            return sanitize_tenant_id(
                tenant or self.server.plane.registry.default_tenant
            )

        def _require_auth(
            self,
            *,
            tenant_id: str | None = None,
            require_admin: bool = False,
            allow_public_health: bool = False,
        ) -> bool:
            path = urlparse(self.path).path
            if (
                allow_public_health
                and path == '/api/health'
                and self.server.plane.auth_policy is None
            ):
                return True
            ok, reason = authorize_request(
                self.server.plane.auth_policy,
                self.headers,
                tenant_id=tenant_id,
                require_admin=require_admin,
            )
            if ok:
                return True
            self._json_response(HTTPStatus.UNAUTHORIZED, {'error': reason})
            return False

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == '/api/health':
                if not self._require_auth(allow_public_health=True):
                    return
                self._json_response(HTTPStatus.OK, {'status': 'ok'})
                return
            if path == '/api/tenants':
                if not self._require_auth(require_admin=True):
                    return
                self._json_response(
                    HTTPStatus.OK,
                    {'tenants': self.server.plane.registry.list_tenants()},
                )
                return
            if path in (
                '/api/workflow/stream',
                '/api/focus/stream',
                '/api/jit/diff',
            ):
                try:
                    tenant_id = self._resolve_tenant_id()
                except ValueError as exc:
                    self._json_response(HTTPStatus.BAD_REQUEST, {'error': str(exc)})
                    return
                if not self._require_auth(tenant_id=tenant_id):
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
            if path in ('/', '/index.html', '/styles.css', '/app.js'):
                if (
                    self.server.plane.auth_policy is not None
                    and not self._require_auth()
                ):
                    return
                if path in ('/', '/index.html'):
                    self._serve_static('index.html', 'text/html; charset=utf-8')
                    return
                if path == '/styles.css':
                    self._serve_static('styles.css', 'text/css; charset=utf-8')
                    return
                if path == '/app.js':
                    self._serve_static(
                        'app.js', 'application/javascript; charset=utf-8'
                    )
                    return
            self._json_response(HTTPStatus.NOT_FOUND, {'error': 'not found'})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            tenant_id: str | None = None
            if path.startswith('/api/'):
                try:
                    tenant_id = self._resolve_tenant_id()
                except ValueError as exc:
                    self._json_response(HTTPStatus.BAD_REQUEST, {'error': str(exc)})
                    return
                if not self._require_auth(tenant_id=tenant_id):
                    return
            try:
                body = self._read_json_body()
            except (ValueError, UnicodeDecodeError) as exc:
                self._json_response(
                    HTTPStatus.BAD_REQUEST, {'error': f'invalid JSON body: {exc}'}
                )
                return
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

        def _tenant_state(self) -> ControlPlaneState:
            return self.server.plane.registry.get_or_create(self._resolve_tenant_id())

        def _workflow_payload(self) -> dict[str, Any]:
            snap = self._tenant_state().snapshot()
            return {
                'workflow': snap.get('workflow'),
                'polish_notes': snap.get('polish_notes', ''),
            }

        def _focus_payload(self) -> dict[str, Any]:
            snap = self._tenant_state().snapshot()
            return {'focus': snap.get('focus')}

        def _jit_payload(self) -> dict[str, Any]:
            snap = self._tenant_state().snapshot()
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
            try:
                self._tenant_state().set_polish_notes(notes)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {'error': str(exc)})
                return
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
