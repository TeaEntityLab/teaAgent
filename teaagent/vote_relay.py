"""HTTP relay for remote SSH-signed consensus votes from production peers."""

from __future__ import annotations

import json
import logging
import ssl
import threading
from contextlib import suppress
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from teaagent.consensus import ConsensusEngine, VoteDecision
from teaagent.http_rate_limit import TokenRateLimiter
from teaagent.ssh_signatures import (
    build_vote_signing_message,
    is_ssh_signature_blob,
    sign_message_ssh,
    verify_message_ssh,
)
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


@dataclass(frozen=True)
class VoteRelayPayload:
    """Remote vote submission body."""

    proposal_id: str
    peer_name: str
    decision: str
    signature: str
    comment: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoteRelayPayload:
        return cls(
            proposal_id=str(data['proposal_id']),
            peer_name=str(data['peer_name']),
            decision=str(data['decision']),
            signature=str(data['signature']),
            comment=str(data['comment']) if data.get('comment') is not None else None,
        )


def verify_relay_vote(
    engine: ConsensusEngine,
    payload: VoteRelayPayload,
    *,
    require_ssh: bool = True,
    allow_dev_signatures: bool = False,
) -> tuple[bool, str]:
    """Validate peer identity and SSH signature before casting."""
    state = engine.get_consensus_status(payload.proposal_id)
    if state is None:
        return False, 'proposal not found'
    peer = engine.peer_registry.get(payload.peer_name)
    if peer is None or not peer.is_active:
        return False, 'peer not found or inactive'
    try:
        decision = VoteDecision(payload.decision)
    except ValueError:
        return False, f'invalid decision: {payload.decision!r}'
    if require_ssh and not is_ssh_signature_blob(payload.signature):
        return False, 'production relay requires SSH signature blob'
    message = build_vote_signing_message(
        payload.proposal_id,
        payload.peer_name,
        decision.value,
        state.proposal.task_description,
    )
    if is_ssh_signature_blob(payload.signature):
        if not verify_message_ssh(peer.ssh_public_key, message, payload.signature):
            return False, 'SSH signature verification failed'
        return True, ''
    if not allow_dev_signatures:
        return False, 'dev signatures disabled; use SSH signature blob'
    if not peer.verify_signature(message, payload.signature):
        legacy = state.proposal.task_description
        if not peer.verify_signature(legacy, payload.signature):
            return False, 'dev signature verification failed'
    return True, ''


def submit_relay_vote(
    engine: ConsensusEngine,
    payload: VoteRelayPayload,
    *,
    require_ssh: bool = True,
    allow_dev_signatures: bool = False,
) -> dict[str, Any]:
    """Verify and submit a vote through the consensus engine."""
    ok, reason = verify_relay_vote(
        engine,
        payload,
        require_ssh=require_ssh,
        allow_dev_signatures=allow_dev_signatures,
    )
    if not ok:
        return {'ok': False, 'error': reason}
    decision = VoteDecision(payload.decision)
    cast = engine.submit_vote(
        payload.proposal_id,
        payload.peer_name,
        decision,
        payload.signature,
        comment=payload.comment,
    )
    if not cast:
        return {'ok': False, 'error': 'submit_vote rejected'}
    final = engine.get_consensus_status(payload.proposal_id)
    status = final.status.value if final else 'unknown'
    return {'ok': True, 'status': status}


def require_relay_bind_auth(host: str, policy: SurfaceAuthPolicy | None) -> None:
    """Fail closed when exposing relay on non-loopback without tokens."""
    if not is_loopback_host(host) and policy is None:
        raise ValueError(
            'non-loopback relay bind requires --api-token or --api-token-file'
        )


class VoteRelayClient:
    """POST SSH-signed votes to a remote relay."""

    def __init__(self, relay_base_url: str, *, api_token: str | None = None) -> None:
        self.relay_base_url = relay_base_url.rstrip('/')
        self.api_token = api_token

    def submit_vote(
        self,
        *,
        proposal_id: str,
        peer_name: str,
        decision: VoteDecision,
        task_description: str,
        private_key_path: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        message = build_vote_signing_message(
            proposal_id,
            peer_name,
            decision.value,
            task_description,
        )
        signature = sign_message_ssh(
            __import__('pathlib').Path(private_key_path),
            message,
        )
        body = json.dumps(
            {
                'proposal_id': proposal_id,
                'peer_name': peer_name,
                'decision': decision.value,
                'signature': signature,
                'comment': comment,
            }
        ).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        request = urllib.request.Request(
            f'{self.relay_base_url}/api/v1/votes',
            data=body,
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            try:
                return json.loads(detail)
            except json.JSONDecodeError:
                return {'ok': False, 'error': detail or str(exc)}


class VoteRelayServer:
    """Minimal HTTP server accepting SSH-signed votes for a shared engine."""

    def __init__(
        self,
        engine: ConsensusEngine,
        *,
        host: str = '127.0.0.1',
        port: int = 8790,
        require_ssh: bool = True,
        allow_dev_signatures: bool = False,
        auth_policy: SurfaceAuthPolicy | None = None,
        ssl_context: ssl.SSLContext | None = None,
        rate_limiter: TokenRateLimiter | None = None,
    ) -> None:
        self.engine = engine
        self.host = host
        self.port = port
        self.require_ssh = require_ssh
        self.allow_dev_signatures = allow_dev_signatures
        self.auth_policy = auth_policy
        self.ssl_context = ssl_context
        self.rate_limiter = rate_limiter
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        require_relay_bind_auth(host, auth_policy)

    def _bind_httpd(self, handler: type[BaseHTTPRequestHandler]) -> VoteRelayHTTPServer:
        httpd = VoteRelayHTTPServer((self.host, self.port), handler, self)
        if self.ssl_context is not None:
            wrap_server_socket(httpd, self.ssl_context)
        return httpd

    def start(self, *, daemon: bool = True) -> None:
        handler = _make_relay_handler(self)
        self._httpd = self._bind_httpd(handler)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='vote-relay-http',
            daemon=daemon,
        )
        self._thread.start()
        scheme = 'https' if self.ssl_context else 'http'
        logger.info('Vote relay listening on %s://%s:%s', scheme, self.host, self.port)

    def _shutdown_httpd(self, httpd: ThreadingHTTPServer | None) -> None:
        if httpd is None:
            return
        with suppress(Exception):
            httpd.shutdown()
        with suppress(Exception):
            httpd.server_close()

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        self._shutdown_httpd(httpd)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def serve_blocking(self) -> None:
        handler = _make_relay_handler(self)
        httpd = self._bind_httpd(handler)
        self._httpd = httpd
        self.port = int(httpd.server_address[1])
        scheme = 'https' if self.ssl_context else 'http'
        print(f'Vote relay running at {scheme}://{self.host}:{self.port}')
        print('POST /api/v1/votes with SSH-signed JSON payload')
        if self.auth_policy is not None:
            print('Bearer token required (Authorization or X-TeaAgent-Relay-Token)')
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
        scheme = 'https' if self.ssl_context else 'http'
        return f'{scheme}://{self.host}:{self.port}'


class VoteRelayHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying vote-relay configuration."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        relay: VoteRelayServer,
    ) -> None:
        self.relay = relay
        super().__init__(server_address, handler)


def _make_relay_handler(relay: VoteRelayServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server: VoteRelayHTTPServer  # type: ignore[assignment]

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
            path = urlparse(self.path).path
            if path == '/api/health':
                if self.server.relay.auth_policy is not None and not self._authorized():
                    return
                self._json(HTTPStatus.OK, {'status': 'ok'})
                return
            self._json(HTTPStatus.NOT_FOUND, {'error': 'not found'})

        def do_POST(self) -> None:
            if urlparse(self.path).path != '/api/v1/votes':
                self._json(HTTPStatus.NOT_FOUND, {'error': 'not found'})
                return
            if not self._authorized():
                return
            if not self._rate_limit_ok():
                return
            try:
                body = self._read_json()
                payload = VoteRelayPayload.from_dict(body)
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                return
            result = submit_relay_vote(
                self.server.relay.engine,
                payload,
                require_ssh=self.server.relay.require_ssh,
                allow_dev_signatures=self.server.relay.allow_dev_signatures,
            )
            status = HTTPStatus.OK if result.get('ok') else HTTPStatus.BAD_REQUEST
            self._json(status, result)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get('Content-Length', '0') or '0')
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
