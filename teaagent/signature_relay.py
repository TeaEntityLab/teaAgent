"""HTTP relay for WAN multi-sig approval requests and peer signatures."""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from teaagent.http_rate_limit import TokenRateLimiter
from teaagent.surface_auth import (
    SurfaceAuthPolicy,
    authorize_request,
    extract_bearer_token,
    hash_token,
    is_loopback_host,
    normalize_http_headers,
)
from teaagent.tls_server import wrap_server_socket

logger = logging.getLogger(__name__)

MAX_HTTP_BODY_BYTES = 1_048_576


@dataclass(frozen=True)
class ApprovalRequestPayload:
    """Inbound approval request for a peer relay."""

    request_id: str
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    request_hash: str
    timestamp: float
    requester_agent_id: str
    required_approvals: int
    timeout_seconds: int
    target_peer_id: str | None = None
    signature_submit_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequestPayload:
        return cls(
            request_id=str(data['request_id']),
            tool_name=str(data['tool_name']),
            call_id=str(data['call_id']),
            arguments=dict(data.get('arguments') or {}),
            request_hash=str(data['request_hash']),
            timestamp=float(data['timestamp']),
            requester_agent_id=str(data['requester_agent_id']),
            required_approvals=int(data.get('required_approvals', 1)),
            timeout_seconds=int(data.get('timeout_seconds', 300)),
            target_peer_id=(
                str(data['target_peer_id']) if data.get('target_peer_id') else None
            ),
            signature_submit_url=(
                str(data['signature_submit_url'])
                if data.get('signature_submit_url')
                else None
            ),
        )


@dataclass(frozen=True)
class ApprovalSignaturePayload:
    """Peer signature submission body."""

    request_id: str
    peer_id: str
    signature: str
    ssh_key_id: str | None = None
    timestamp: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalSignaturePayload:
        return cls(
            request_id=str(data['request_id']),
            peer_id=str(data['peer_id']),
            signature=str(data['signature']),
            ssh_key_id=(
                str(data['ssh_key_id']) if data.get('ssh_key_id') is not None else None
            ),
            timestamp=float(data.get('timestamp') or time.time()),
        )


class SignatureRelayStore:
    """Thread-safe in-memory store for approval requests and signatures."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, dict[str, Any]] = {}
        self._signatures: dict[str, list[dict[str, Any]]] = {}

    def put_request(self, payload: ApprovalRequestPayload) -> None:
        with self._lock:
            self._requests[payload.request_id] = asdict(payload)

    def list_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._requests.values())

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._requests.get(request_id)
            return dict(item) if item is not None else None

    def add_signature(self, payload: ApprovalSignaturePayload) -> bool:
        with self._lock:
            entries = self._signatures.setdefault(payload.request_id, [])
            if any(entry.get('peer_id') == payload.peer_id for entry in entries):
                return False
            entries.append(asdict(payload))
            return True

    def list_signatures(self, request_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._signatures.get(request_id, ())]


def require_signature_relay_bind_auth(
    host: str, policy: SurfaceAuthPolicy | None
) -> None:
    """Fail closed when exposing signature relay on non-loopback without tokens."""
    if not is_loopback_host(host) and policy is None:
        raise ValueError(
            'non-loopback signature relay bind requires --api-token or --api-token-file'
        )


class SignatureRelayClient:
    """HTTP client for approval request broadcast and signature collection."""

    def __init__(self, *, api_token: str | None = None) -> None:
        self.api_token = api_token

    def _headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        data = None if body is None else json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode('utf-8')
                if not raw.strip():
                    return {'ok': True}
                parsed = json.loads(raw)
                return (
                    parsed if isinstance(parsed, dict) else {'ok': True, 'data': parsed}
                )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            try:
                return json.loads(detail)
            except json.JSONDecodeError:
                return {'ok': False, 'error': detail or str(exc)}

    def post_approval_request(
        self, relay_base_url: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        url = f'{relay_base_url.rstrip("/")}/api/v1/approval-requests'
        return self._request('POST', url, body=payload)

    def post_signature(
        self, submit_url: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request('POST', submit_url, body=payload)

    def fetch_signatures(
        self, relay_base_url: str, request_id: str
    ) -> list[dict[str, Any]]:
        url = (
            f'{relay_base_url.rstrip("/")}/api/v1/approval-signatures'
            f'?request_id={request_id}'
        )
        result = self._request('GET', url)
        if not result.get('ok', False):
            return []
        signatures: list[dict[str, Any]] = []
        for item in result.get('signatures', []):
            if isinstance(item, dict):
                signatures.append(item)
        return signatures


class SignatureRelayServer:
    """Minimal HTTP server for WAN multi-sig approval relay."""

    def __init__(
        self,
        *,
        host: str = '127.0.0.1',
        port: int = 8791,
        auth_policy: SurfaceAuthPolicy | None = None,
        ssl_context: ssl.SSLContext | None = None,
        rate_limiter: TokenRateLimiter | None = None,
        store: SignatureRelayStore | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.auth_policy = auth_policy
        self.ssl_context = ssl_context
        self.rate_limiter = rate_limiter
        self.store = store or SignatureRelayStore()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        require_signature_relay_bind_auth(host, auth_policy)

    def _bind_httpd(
        self, handler: type[BaseHTTPRequestHandler]
    ) -> SignatureRelayHTTPServer:
        httpd = SignatureRelayHTTPServer((self.host, self.port), handler, self)
        if self.ssl_context is not None:
            wrap_server_socket(httpd, self.ssl_context)
        return httpd

    def start(self, *, daemon: bool = True) -> None:
        handler = _make_signature_relay_handler(self)
        self._httpd = self._bind_httpd(handler)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='signature-relay-http',
            daemon=daemon,
        )
        self._thread.start()
        scheme = 'https' if self.ssl_context else 'http'
        logger.info(
            'Signature relay listening on %s://%s:%s', scheme, self.host, self.port
        )

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is not None:
            with suppress(Exception):
                httpd.shutdown()
            with suppress(Exception):
                httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def serve_blocking(self) -> None:
        handler = _make_signature_relay_handler(self)
        httpd = self._bind_httpd(handler)
        self._httpd = httpd
        self.port = int(httpd.server_address[1])
        scheme = 'https' if self.ssl_context else 'http'
        print(f'Signature relay running at {scheme}://{self.host}:{self.port}')
        print('POST /api/v1/approval-requests  GET/POST /api/v1/approval-signatures')
        if self.auth_policy is not None:
            print('Bearer token required (Authorization or X-TeaAgent-Relay-Token)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if self._httpd is httpd:
                self._httpd = None
            with suppress(Exception):
                httpd.shutdown()
            with suppress(Exception):
                httpd.server_close()

    @property
    def base_url(self) -> str:
        scheme = 'https' if self.ssl_context else 'http'
        return f'{scheme}://{self.host}:{self.port}'


class SignatureRelayHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying signature-relay configuration."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        relay: SignatureRelayServer,
    ) -> None:
        self.relay = relay
        super().__init__(server_address, handler)


def _make_signature_relay_handler(
    relay: SignatureRelayServer,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server: SignatureRelayHTTPServer  # type: ignore[assignment]

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug(format, *args)

        def _authorized(self) -> bool:
            ok, reason = authorize_request(
                self.server.relay.auth_policy,
                normalize_http_headers(self.headers),
            )
            if ok:
                return True
            self._json(HTTPStatus.UNAUTHORIZED, {'ok': False, 'error': reason})
            return False

        def _rate_limit_ok(self) -> bool:
            limiter = self.server.relay.rate_limiter
            if limiter is None:
                return True
            raw = (
                extract_bearer_token(normalize_http_headers(self.headers))
                or 'anonymous'
            )
            key = hash_token(raw) if raw != 'anonymous' else 'anonymous'
            ok, reason = limiter.allow(key)
            if ok:
                return True
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {'ok': False, 'error': reason})
            return False

        def do_GET(self) -> None:
            if not self._authorized():
                return
            path = urlparse(self.path).path
            if path == '/api/health':
                self._json(HTTPStatus.OK, {'status': 'ok'})
                return
            if path == '/api/v1/approval-requests':
                self._json(
                    HTTPStatus.OK,
                    {'ok': True, 'requests': self.server.relay.store.list_requests()},
                )
                return
            if path == '/api/v1/approval-signatures':
                query = parse_qs(urlparse(self.path).query)
                request_ids = query.get('request_id', [])
                if not request_ids:
                    self._json(
                        HTTPStatus.BAD_REQUEST,
                        {'ok': False, 'error': 'request_id query parameter required'},
                    )
                    return
                request_id = request_ids[0]
                signatures = self.server.relay.store.list_signatures(request_id)
                self._json(HTTPStatus.OK, {'ok': True, 'signatures': signatures})
                return
            self._json(HTTPStatus.NOT_FOUND, {'ok': False, 'error': 'not found'})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path not in {
                '/api/v1/approval-requests',
                '/api/v1/approval-signatures',
            }:
                self._json(HTTPStatus.NOT_FOUND, {'ok': False, 'error': 'not found'})
                return
            if not self._authorized():
                return
            if not self._rate_limit_ok():
                return
            try:
                body = self._read_json()
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                return
            if path == '/api/v1/approval-requests':
                try:
                    payload = ApprovalRequestPayload.from_dict(body)
                except (KeyError, TypeError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                    return
                self.server.relay.store.put_request(payload)
                self._json(
                    HTTPStatus.OK, {'ok': True, 'request_id': payload.request_id}
                )
                return
            try:
                sig = ApprovalSignaturePayload.from_dict(body)
            except (KeyError, TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                return
            added = self.server.relay.store.add_signature(sig)
            status = HTTPStatus.OK if added else HTTPStatus.CONFLICT
            self._json(
                status,
                {
                    'ok': added,
                    'request_id': sig.request_id,
                    'peer_id': sig.peer_id,
                    'error': None if added else 'duplicate peer signature',
                },
            )

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length > MAX_HTTP_BODY_BYTES:
                raise ValueError('body too large')
            raw = self.rfile.read(length) if length > 0 else b'{}'
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('expected JSON object')
            return data

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
