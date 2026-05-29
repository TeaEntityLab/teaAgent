"""HTTP relay for remote SSH-signed consensus votes from production peers."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from teaagent.consensus import ConsensusEngine, VoteDecision
from teaagent.ssh_signatures import build_vote_signing_message
from teaagent.ssh_signatures import (
    is_ssh_signature_blob,
    sign_message_ssh,
    verify_message_ssh,
)

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
    elif not peer.verify_signature(message, payload.signature):
        legacy = state.proposal.task_description
        if not peer.verify_signature(legacy, payload.signature):
            return False, 'dev signature verification failed'
    return True, ''


def submit_relay_vote(
    engine: ConsensusEngine,
    payload: VoteRelayPayload,
    *,
    require_ssh: bool = True,
) -> dict[str, Any]:
    """Verify and submit a vote through the consensus engine."""
    ok, reason = verify_relay_vote(engine, payload, require_ssh=require_ssh)
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


class VoteRelayClient:
    """POST SSH-signed votes to a remote relay."""

    def __init__(self, relay_base_url: str) -> None:
        self.relay_base_url = relay_base_url.rstrip('/')

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
        request = urllib.request.Request(
            f'{self.relay_base_url}/api/v1/votes',
            data=body,
            headers={'Content-Type': 'application/json'},
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
    ) -> None:
        self.engine = engine
        self.host = host
        self.port = port
        self.require_ssh = require_ssh
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, *, daemon: bool = True) -> None:
        handler = _make_relay_handler(self)
        self._httpd = VoteRelayHTTPServer((self.host, self.port), handler, self)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='vote-relay-http',
            daemon=daemon,
        )
        self._thread.start()
        logger.info('Vote relay listening on http://%s:%s', self.host, self.port)

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def serve_blocking(self) -> None:
        handler = _make_relay_handler(self)
        httpd = VoteRelayHTTPServer((self.host, self.port), handler, self)
        self._httpd = httpd
        self.port = int(httpd.server_address[1])
        print(f'Vote relay running at http://{self.host}:{self.port}')
        print('POST /api/v1/votes with SSH-signed JSON payload')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.shutdown()
            httpd.server_close()
            self._httpd = None


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

        def do_GET(self) -> None:
            if urlparse(self.path).path == '/api/health':
                self._json(HTTPStatus.OK, {'status': 'ok'})
                return
            self._json(HTTPStatus.NOT_FOUND, {'error': 'not found'})

        def do_POST(self) -> None:
            if urlparse(self.path).path != '/api/v1/votes':
                self._json(HTTPStatus.NOT_FOUND, {'error': 'not found'})
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
