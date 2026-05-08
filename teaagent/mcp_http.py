from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from teaagent.mcp_server import handle_mcp_request
from teaagent.tools import ToolRegistry

MCP_PATH = "/mcp"
SESSION_HEADER = "Mcp-Session-Id"
DEFAULT_PORT = 7330


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
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    auth_token: Optional[str] = None,
    allowed_origins: Optional[list[str]] = None,
) -> tuple[ThreadingHTTPServer, MCPSessionStore]:
    sessions = MCPSessionStore()
    origins = frozenset(allowed_origins) if allowed_origins else None
    handler_cls = _make_handler(registry, sessions, auth_token, origins)
    server = ThreadingHTTPServer((host, port), handler_cls)
    return server, sessions


def serve_mcp_http(
    registry: ToolRegistry,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    auth_token: Optional[str] = None,
    allowed_origins: Optional[list[str]] = None,
) -> int:
    server, _sessions = build_mcp_http_server(
        registry,
        host=host,
        port=port,
        auth_token=auth_token,
        allowed_origins=allowed_origins,
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
) -> type[BaseHTTPRequestHandler]:
    class MCPHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _check_auth(self) -> bool:
            if auth_token is None:
                return True
            header = self.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return False
            return secrets.compare_digest(header[len("Bearer ") :], auth_token)

        def _check_origin(self) -> bool:
            if allowed_origins is None:
                return True
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return origin in allowed_origins

        def _send_json(
            self,
            status: int,
            payload: Any,
            *,
            extra_headers: Optional[dict[str, str]] = None,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_status(self, status: int, message: Optional[str] = None) -> None:
            body = (message or "").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _gate(self) -> bool:
            if self.path != MCP_PATH:
                self._send_status(404, "not found")
                return False
            if not self._check_origin():
                self._send_status(403, "forbidden origin")
                return False
            if not self._check_auth():
                self._send_status(401, "unauthorized")
                return False
            return True

        def _read_body(self) -> tuple[Optional[Any], Optional[str]]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return None, "missing JSON-RPC body"
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8")), None
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None, "invalid JSON"

        def do_POST(self) -> None:
            if not self._gate():
                return
            payload, error = self._read_body()
            if error is not None:
                self._send_status(400, error)
                return
            if not isinstance(payload, (dict, list)):
                self._send_status(400, "JSON-RPC payload must be object or array")
                return

            session_header = self.headers.get(SESSION_HEADER)

            if isinstance(payload, dict) and payload.get("method") == "initialize":
                response = handle_mcp_request(registry, payload)
                if response is None:
                    self._send_status(400, "initialize requires an id")
                    return
                session_id = sessions.create()
                self._send_json(200, response, extra_headers={SESSION_HEADER: session_id})
                return

            if not session_header or not sessions.has(session_header):
                self._send_status(400, "missing or invalid Mcp-Session-Id")
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
                self._send_json(200, responses)
                return

            response = handle_mcp_request(registry, payload)
            if response is None:
                self._send_status(202)
                return
            self._send_json(200, response)

        def do_GET(self) -> None:
            if not self._gate():
                return
            session_header = self.headers.get(SESSION_HEADER)
            if not session_header or not sessions.has(session_header):
                self._send_status(400, "missing or invalid Mcp-Session-Id")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b": teaagent mcp stream\n\n")
            self.wfile.flush()

        def do_DELETE(self) -> None:
            if not self._gate():
                return
            session_header = self.headers.get(SESSION_HEADER)
            if not session_header or not sessions.has(session_header):
                self._send_status(404, "session not found")
                return
            sessions.remove(session_header)
            self._send_status(204)

        def do_OPTIONS(self) -> None:
            self._send_status(204)

    return MCPHandler
