from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from teaagent.mcp_server import handle_mcp_request
from teaagent.oauth21 import (
    _AUTHORIZATION_HEADER,
    _AUTHORIZE_PATH,
    _DPOP_HEADER,
    _DPOP_NONCE_HEADER,
    _OAUTH_METADATA_PATH,
    _TOKEN_PATH,
    _TOKEN_TYPE_DPOP,
    OAuth21AuthorizationServer,
    OAuth21Error,
    OAuth21ResourceServer,
    OAuth21TokenClaims,
)
from teaagent.tools import ToolRegistry

MCP_PATH = '/mcp'
SESSION_HEADER = 'Mcp-Session-Id'
DEFAULT_PORT = 7330

_OAUTH_PATHS = frozenset({_AUTHORIZE_PATH, _TOKEN_PATH, _OAUTH_METADATA_PATH})


class MCPSessionStore:
    """In-memory session store for the Streamable HTTP transport."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: set[str] = set()

    def create(self) -> str:
        session_id = secrets.token_urlsafe(24)
        with self._lock:
            self._sessions.add(session_id)
        return session_id

    def has(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def remove(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                self._sessions.remove(session_id)
                return True
            return False


def build_mcp_http_server(
    registry: ToolRegistry,
    *,
    host: str = '127.0.0.1',
    port: int = DEFAULT_PORT,
    auth_token: Optional[str] = None,
    allowed_origins: Optional[list[str]] = None,
    oauth_server: Optional[OAuth21AuthorizationServer] = None,
) -> tuple[ThreadingHTTPServer, MCPSessionStore]:
    sessions = MCPSessionStore()
    origins = frozenset(allowed_origins) if allowed_origins else None
    handler_cls = _make_handler(
        registry, sessions, auth_token, origins, oauth_server
    )
    server = ThreadingHTTPServer((host, port), handler_cls)
    return server, sessions


def serve_mcp_http(
    registry: ToolRegistry,
    *,
    host: str = '127.0.0.1',
    port: int = DEFAULT_PORT,
    auth_token: Optional[str] = None,
    allowed_origins: Optional[list[str]] = None,
    oauth_server: Optional[OAuth21AuthorizationServer] = None,
) -> int:
    server, _sessions = build_mcp_http_server(
        registry,
        host=host,
        port=port,
        auth_token=auth_token,
        allowed_origins=allowed_origins,
        oauth_server=oauth_server,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _make_handler(
    registry: ToolRegistry,
    sessions: MCPSessionStore,
    auth_token: Optional[str],
    allowed_origins: Optional[frozenset[str]],
    oauth_server: Optional[OAuth21AuthorizationServer],
) -> type[BaseHTTPRequestHandler]:
    resource_server: Optional[OAuth21ResourceServer] = None
    if oauth_server is not None:
        resource_server = OAuth21ResourceServer(
            signing_key=oauth_server._key.decode('utf-8'),
            issuer=oauth_server.issuer,
        )

    class MCPHandler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        _oauth_token_info: Optional[OAuth21TokenClaims] = None

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        # -- auth checking (supports bearer token + DPoP token) --

        def _check_auth(self) -> bool:
            # Legacy bearer token takes priority if configured.
            if auth_token is not None:
                header = self.headers.get(_AUTHORIZATION_HEADER, '')
                if not header.startswith('Bearer '):
                    return False
                return secrets.compare_digest(
                    header[len('Bearer '):], auth_token
                )

            # OAuth 2.1 / DPoP token validation.
            if resource_server is not None:
                try:
                    claims = resource_server.validate_request(
                        authorization_header=self.headers.get(
                            _AUTHORIZATION_HEADER
                        ),
                        dpop_header=self.headers.get(_DPOP_HEADER),
                        method=self.command,
                        url=self._request_url(),
                    )
                    self._oauth_token_info = claims
                    return True
                except OAuth21Error:
                    self._oauth_token_info = None
                    return False

            # No auth configured — allow all.
            return True

        def _request_url(self) -> str:
            """Reconstruct the full request URL for DPoP htu validation."""
            host = self.headers.get(
                'Host',
                f'{self.server.server_address[0]}:{self.server.server_address[1]}',  # type: ignore[index]
            )
            scheme = 'https' if getattr(self.connection, 'context', None) else 'http'
            return f'{scheme}://{host}{self.path}'

        # -- origin check --

        def _check_origin(self) -> bool:
            if allowed_origins is None:
                return True
            origin = self.headers.get('Origin')
            if origin is None:
                return True
            return origin in allowed_origins

        # -- response helpers --

        def _send_json(
            self,
            status: int,
            payload: Any,
            *,
            extra_headers: Optional[dict[str, str]] = None,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_status(
            self, status: int, message: Optional[str] = None
        ) -> None:
            body = (message or '').encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_dpop_error(self, dpop_nonce: str) -> None:
            body = json.dumps(
                {'error': 'use_dpop_nonce', 'error_description': 'DPoP nonce required'}
            ).encode('utf-8')
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header(_DPOP_NONCE_HEADER, dpop_nonce)
            self.end_headers()
            self.wfile.write(body)

        # -- gate: path + origin + auth --

        def _gate(self) -> bool:
            if not self._check_origin():
                self._send_status(403, 'forbidden origin')
                return False
            if not self._check_auth():
                # Return DPoP nonce if we have an AS (for DPoP negotiation).
                if oauth_server is not None:
                    dpop_error = self._build_dpop_error()
                    if dpop_error:
                        self._send_dpop_error(dpop_error)
                    else:
                        self._send_status(401, 'unauthorized')
                else:
                    self._send_status(401, 'unauthorized')
                return False
            return True

        def _build_dpop_error(self) -> Optional[str]:
            """Return a DPoP nonce if the error looks like a missing/bad DPoP proof."""
            auth_header = self.headers.get(_AUTHORIZATION_HEADER, '')
            dpop_header = self.headers.get(_DPOP_HEADER)
            # Issue a nonce if a DPoP token is presented or DPoP header exists.
            if (_TOKEN_TYPE_DPOP in auth_header or dpop_header is not None) and oauth_server is not None:
                    return oauth_server.generate_dpop_nonce()
            return None

        def _read_body(self) -> tuple[Optional[Any], Optional[str]]:
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length <= 0:
                return None, 'missing JSON-RPC body'
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode('utf-8')), None
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None, 'invalid JSON'

        # -- OAuth 2.1 endpoints --

        def _handle_oauth_metadata(self) -> None:
            if oauth_server is None:
                self._send_status(404, 'not found')
                return
            metadata = oauth_server.metadata()

            # When DPoP is requested, include a nonce.
            dpop_header = self.headers.get(_DPOP_HEADER)
            extra: dict[str, str] = {}
            if dpop_header:
                extra[_DPOP_NONCE_HEADER] = oauth_server.generate_dpop_nonce()

            self._send_json(200, metadata, extra_headers=extra or None)

        def _handle_oauth_authorize(self) -> None:
            if oauth_server is None:
                self._send_status(404, 'not found')
                return

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            client_id = _first_param(params, 'client_id')
            redirect_uri = _first_param(params, 'redirect_uri')
            code_challenge = _first_param(params, 'code_challenge')
            code_challenge_method = _first_param(params, 'code_challenge_method') or 'S256'
            scope = _first_param(params, 'scope') or 'mcp'
            state = _first_param(params, 'state')

            if not client_id or not redirect_uri or not code_challenge:
                self._send_json(
                    400,
                    {
                        'error': 'invalid_request',
                        'error_description': (
                            'client_id, redirect_uri, and code_challenge are required'
                        ),
                    },
                )
                return

            try:
                redirect_url, _ = oauth_server.create_authorization_code(
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    code_challenge=code_challenge,
                    code_challenge_method=code_challenge_method,
                    scope=scope,
                    state=state,
                )
                self.send_response(302)
                self.send_header('Location', redirect_url)
                self.send_header('Content-Length', '0')
                self.end_headers()
            except OAuth21Error as exc:
                self._send_json(
                    400,
                    {'error': 'invalid_request', 'error_description': str(exc)},
                )

        def _handle_oauth_token(self) -> None:
            if oauth_server is None:
                self._send_status(404, 'not found')
                return

            # Read form body (application/x-www-form-urlencoded)
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length <= 0:
                self._send_json(
                    400,
                    {'error': 'invalid_request', 'error_description': 'missing body'},
                )
                return
            raw = self.rfile.read(length)
            try:
                body = raw.decode('utf-8')
            except UnicodeDecodeError:
                self._send_json(
                    400,
                    {'error': 'invalid_request', 'error_description': 'invalid encoding'},
                )
                return
            params = parse_qs(body)

            grant_type = _first_param(params, 'grant_type')
            code = _first_param(params, 'code')
            code_verifier = _first_param(params, 'code_verifier')
            client_id = _first_param(params, 'client_id')
            client_secret = _first_param(params, 'client_secret')
            dpop_proof = self.headers.get(_DPOP_HEADER)

            if grant_type != 'authorization_code':
                self._send_json(
                    400,
                    {
                        'error': 'unsupported_grant_type',
                        'error_description': 'Only authorization_code is supported',
                    },
                )
                return
            if not code:
                self._send_json(
                    400,
                    {'error': 'invalid_request', 'error_description': 'code is required'},
                )
                return
            if not code_verifier:
                self._send_json(
                    400,
                    {
                        'error': 'invalid_request',
                        'error_description': 'code_verifier is required',
                    },
                )
                return

            extra_headers: dict[str, str] = {}

            # Always issue a fresh DPoP nonce
            dpop_nonce = oauth_server.generate_dpop_nonce()
            extra_headers[_DPOP_NONCE_HEADER] = dpop_nonce

            try:
                response = oauth_server.exchange_code(
                    code=code,
                    code_verifier=code_verifier,
                    client_id=client_id,
                    client_secret=client_secret,
                    dpop_proof_jwt=dpop_proof,
                )
            except OAuth21Error as exc:
                status = 400
                error_code = 'invalid_grant'
                if 'DPoP' in str(exc) or 'dpop' in str(exc).lower():
                    status = 401
                    error_code = 'invalid_dpop_proof'
                    extra_headers[_DPOP_NONCE_HEADER] = dpop_nonce
                elif 'client' in str(exc).lower():
                    status = 401
                    error_code = 'invalid_client'
                self._send_json(
                    status,
                    {'error': error_code, 'error_description': str(exc)},
                    extra_headers=extra_headers,
                )
                return

            self._send_json(
                200,
                {
                    'access_token': response.access_token,
                    'token_type': response.token_type,
                    'expires_in': response.expires_in,
                    'scope': response.scope,
                    'refresh_token': response.refresh_token,
                },
                extra_headers=extra_headers,
            )

        def _is_oauth_path(self) -> bool:
            path = self.path.split('?')[0]
            return path in _OAUTH_PATHS

        # -- HTTP method dispatchers --

        def do_POST(self) -> None:
            if self._is_oauth_path():
                if self.path.startswith(_TOKEN_PATH):
                    return self._handle_oauth_token()
                self._send_status(404)
                return

            if self.path != MCP_PATH:
                self._send_status(404, 'not found')
                return
            if not self._gate():
                return
            payload, error = self._read_body()
            if error is not None:
                self._send_status(400, error)
                return
            if not isinstance(payload, (dict, list)):
                self._send_status(400, 'JSON-RPC payload must be object or array')
                return

            session_header = self.headers.get(SESSION_HEADER)

            if isinstance(payload, dict) and payload.get('method') == 'initialize':
                response = handle_mcp_request(registry, payload)
                if response is None:
                    self._send_status(400, 'initialize requires an id')
                    return
                session_id = sessions.create()
                extra_headers: dict[str, str] = {SESSION_HEADER: session_id}
                self._add_dpop_nonce(extra_headers)
                self._send_json(200, response, extra_headers=extra_headers)
                return

            if not session_header or not sessions.has(session_header):
                self._send_status(400, 'missing or invalid Mcp-Session-Id')
                return

            if isinstance(payload, list):
                responses: list[dict[str, Any]] = []
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    response = handle_mcp_request(registry, item)
                    if response is not None:
                        responses.append(response)
                if not responses:
                    self._send_status(202)
                    return
                extra: dict[str, str] = {}
                self._add_dpop_nonce(extra)
                self._send_json(200, responses, extra_headers=extra)
                return

            response = handle_mcp_request(registry, payload)
            if response is None:
                self._send_status(202)
                return
            extra2: dict[str, str] = {}
            self._add_dpop_nonce(extra2)
            self._send_json(200, response, extra_headers=extra2)

        def do_GET(self) -> None:
            if self._is_oauth_path():
                if self.path.startswith(_AUTHORIZE_PATH):
                    return self._handle_oauth_authorize()
                if self.path.startswith(_OAUTH_METADATA_PATH):
                    return self._handle_oauth_metadata()
                self._send_status(404)
                return

            if self.path != MCP_PATH:
                self._send_status(404, 'not found')
                return
            if not self._gate():
                return
            session_header = self.headers.get(SESSION_HEADER)
            if not session_header or not sessions.has(session_header):
                self._send_status(400, 'missing or invalid Mcp-Session-Id')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self._add_dpop_nonce_to_response()
            self.end_headers()
            self.wfile.write(b': teaagent mcp stream\n\n')
            self.wfile.flush()

        def do_DELETE(self) -> None:
            if self.path != MCP_PATH:
                self._send_status(404, 'not found')
                return
            if not self._gate():
                return
            session_header = self.headers.get(SESSION_HEADER)
            if not session_header or not sessions.has(session_header):
                self._send_status(404, 'session not found')
                return
            sessions.remove(session_header)
            self._send_status(204)

        def do_OPTIONS(self) -> None:
            self._send_status(204)

        def _add_dpop_nonce(self, extra: dict[str, str]) -> None:
            if oauth_server is not None:
                extra[_DPOP_NONCE_HEADER] = oauth_server.generate_dpop_nonce()

        def _add_dpop_nonce_to_response(self) -> None:
            if oauth_server is not None:
                self.send_header(
                    _DPOP_NONCE_HEADER, oauth_server.generate_dpop_nonce()
                )

    return MCPHandler


def _first_param(params: dict[str, list[str]], key: str) -> Optional[str]:
    vals = params.get(key, [])
    return vals[0] if vals else None
