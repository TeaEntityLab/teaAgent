from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from teaagent.mcp_http import MCP_PATH, SESSION_HEADER, build_mcp_http_server
from teaagent.workspace_tools import build_workspace_tool_registry


class _ServerFixture:
    def __init__(
        self,
        *,
        root: str,
        auth_token: Optional[str] = None,
        allowed_origins: Optional[list[str]] = None,
    ) -> None:
        self.root = Path(root)
        self.registry = build_workspace_tool_registry(root)
        self.server, self.sessions = build_mcp_http_server(
            self.registry,
            host="127.0.0.1",
            port=0,
            auth_token=auth_token,
            allowed_origins=allowed_origins,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[:2]

    def request(
        self,
        method: str,
        *,
        body: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
        path: str = MCP_PATH,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            return response.status, dict(response.getheaders()), data
        finally:
            conn.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


@contextmanager
def server_fixture(**kwargs) -> Iterator[_ServerFixture]:
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _ServerFixture(root=tmp, **kwargs)
        try:
            yield fixture
        finally:
            fixture.close()


def _post(
    fixture: _ServerFixture,
    payload: object,
    *,
    session_id: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    if session_id is not None:
        headers[SESSION_HEADER] = session_id
    if extra_headers:
        headers.update(extra_headers)
    return fixture.request("POST", body=body, headers=headers)


def _initialize(fixture: _ServerFixture, *, extra_headers: Optional[dict[str, str]] = None) -> tuple[str, dict]:
    status, headers, data = _post(
        fixture,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        extra_headers=extra_headers,
    )
    assert status == 200, (status, data)
    return headers[SESSION_HEADER], json.loads(data)


class MCPHTTPTransportTests(unittest.TestCase):
    def test_initialize_returns_session_id_and_protocol_info(self) -> None:
        with server_fixture() as fixture:
            session_id, payload = _initialize(fixture)

            self.assertTrue(len(session_id) > 0)
            self.assertEqual(payload["id"], 1)
            self.assertEqual(payload["result"]["serverInfo"]["name"], "teaagent")
            self.assertIn("protocolVersion", payload["result"])

    def test_subsequent_request_without_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, data = _post(fixture, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            self.assertEqual(status, 400)
            self.assertIn(b"Mcp-Session-Id", data)

    def test_request_with_unknown_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                session_id="not-a-real-session",
            )
            self.assertEqual(status, 400)

    def test_tools_list_with_valid_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)

            status, _, data = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            names = {tool["name"] for tool in payload["result"]["tools"]}
            self.assertIn("workspace_read_file", names)

    def test_tools_call_executes_workspace_tool(self) -> None:
        with server_fixture() as fixture:
            (fixture.root / "hi.txt").write_text("hi", encoding="utf-8")
            session_id, _ = _initialize(fixture)

            status, _, data = _post(
                fixture,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "workspace_read_file", "arguments": {"path": "hi.txt"}},
                },
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertFalse(payload["result"]["isError"])
            content_text = json.loads(payload["result"]["content"][0]["text"])
            self.assertEqual(content_text["content"], "hi")

    def test_invalid_json_body_returns_400(self) -> None:
        with server_fixture() as fixture:
            body = b"{not valid json"
            status, _, _ = fixture.request(
                "POST",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                },
            )
            self.assertEqual(status, 400)

    def test_unknown_method_returns_jsonrpc_error_inside_200(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 7, "method": "nonexistent"},
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertEqual(payload["error"]["code"], -32601)

    def test_notification_returns_202_with_empty_body(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                {"jsonrpc": "2.0", "method": "tools/list"},
                session_id=session_id,
            )

            self.assertEqual(status, 202)
            self.assertEqual(data, b"")

    def test_batch_returns_array_of_responses(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                [
                    {"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 11, "method": "tools/list"},
                ],
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertIsInstance(payload, list)
            self.assertEqual({entry["id"] for entry in payload}, {10, 11})

    def test_auth_token_blocks_unauthenticated_request(self) -> None:
        with server_fixture(auth_token="s3cret") as fixture:
            status, _, _ = _post(fixture, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            self.assertEqual(status, 401)

    def test_auth_token_accepts_correct_bearer(self) -> None:
        with server_fixture(auth_token="s3cret") as fixture:
            session_id, _ = _initialize(fixture, extra_headers={"Authorization": "Bearer s3cret"})
            self.assertTrue(len(session_id) > 0)

    def test_auth_token_rejects_wrong_bearer(self) -> None:
        with server_fixture(auth_token="s3cret") as fixture:
            status, _, _ = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                extra_headers={"Authorization": "Bearer wrong"},
            )
            self.assertEqual(status, 401)

    def test_origin_not_in_allowlist_returns_403(self) -> None:
        with server_fixture(allowed_origins=["https://allowed.example"]) as fixture:
            status, _, _ = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                extra_headers={"Origin": "https://attacker.example"},
            )
            self.assertEqual(status, 403)

    def test_origin_in_allowlist_passes(self) -> None:
        with server_fixture(allowed_origins=["https://allowed.example"]) as fixture:
            session_id, _ = _initialize(fixture, extra_headers={"Origin": "https://allowed.example"})
            self.assertTrue(len(session_id) > 0)

    def test_get_returns_sse_keepalive_for_valid_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, headers, data = fixture.request(
                "GET",
                headers={SESSION_HEADER: session_id},
            )

            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "text/event-stream")
            self.assertIn(b": teaagent mcp stream", data)

    def test_get_without_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = fixture.request("GET")
            self.assertEqual(status, 400)

    def test_delete_removes_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)

            status, _, _ = fixture.request("DELETE", headers={SESSION_HEADER: session_id})
            self.assertEqual(status, 204)
            self.assertFalse(fixture.sessions.has(session_id))

            status, _, _ = _post(
                fixture,
                {"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
                session_id=session_id,
            )
            self.assertEqual(status, 400)

    def test_unknown_path_returns_404(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = fixture.request("GET", path="/other")
            self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
