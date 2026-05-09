from __future__ import annotations

import http.client
import json
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from teaagent.mcp_http import (
    MAX_HTTP_BODY_BYTES,
    MCP_PATH,
    SESSION_HEADER,
    build_mcp_http_server,
)
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
            host='127.0.0.1',
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

    def raw_request(self, request: bytes) -> bytes:
        with socket.create_connection((self.host, self.port), timeout=5) as sock:
            sock.sendall(request)
            sock.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            return b''.join(chunks)

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
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
    if session_id is not None:
        headers[SESSION_HEADER] = session_id
    if extra_headers:
        headers.update(extra_headers)
    return fixture.request('POST', body=body, headers=headers)


def _initialize(
    fixture: _ServerFixture, *, extra_headers: Optional[dict[str, str]] = None
) -> tuple[str, dict]:
    status, headers, data = _post(
        fixture,
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
        extra_headers=extra_headers,
    )
    assert status == 200, (status, data)
    return headers[SESSION_HEADER], json.loads(data)


class MCPHTTPTransportTests(unittest.TestCase):
    def test_initialize_returns_session_id_and_protocol_info(self) -> None:
        with server_fixture() as fixture:
            session_id, payload = _initialize(fixture)

            self.assertTrue(len(session_id) > 0)
            self.assertEqual(payload['id'], 1)
            self.assertEqual(payload['result']['serverInfo']['name'], 'teaagent')
            self.assertIn('protocolVersion', payload['result'])

    def test_subsequent_request_without_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, data = _post(
                fixture, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
            )
            self.assertEqual(status, 400)
            self.assertIn(b'Mcp-Session-Id', data)

    def test_request_with_unknown_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                session_id='not-a-real-session',
            )
            self.assertEqual(status, 400)

    def test_tools_list_with_valid_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)

            status, _, data = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            names = {tool['name'] for tool in payload['result']['tools']}
            self.assertIn('workspace_read_file', names)

    def test_tools_call_executes_workspace_tool(self) -> None:
        with server_fixture() as fixture:
            (fixture.root / 'hi.txt').write_text('hi', encoding='utf-8')
            session_id, _ = _initialize(fixture)

            status, _, data = _post(
                fixture,
                {
                    'jsonrpc': '2.0',
                    'id': 3,
                    'method': 'tools/call',
                    'params': {
                        'name': 'workspace_read_file',
                        'arguments': {'path': 'hi.txt'},
                    },
                },
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertFalse(payload['result']['isError'])
            content_text = json.loads(payload['result']['content'][0]['text'])
            self.assertEqual(content_text['content'], 'hi')

    def test_invalid_json_body_returns_400(self) -> None:
        with server_fixture() as fixture:
            body = b'{not valid json'
            status, _, _ = fixture.request(
                'POST',
                body=body,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            self.assertEqual(status, 400)

    def test_non_numeric_content_length_returns_400(self) -> None:
        with server_fixture() as fixture:
            response = fixture.raw_request(
                b'POST /mcp HTTP/1.1\r\n'
                + f'Host: {fixture.host}:{fixture.port}\r\n'.encode('ascii')
                + b'Content-Type: application/json\r\n'
                + b'Content-Length: not-a-number\r\n'
                + b'\r\n{}'
            )

            self.assertIn(b'400', response.splitlines()[0])

    def test_oversized_json_body_returns_413_without_reading_body(self) -> None:
        with server_fixture() as fixture:
            response = fixture.raw_request(
                b'POST /mcp HTTP/1.1\r\n'
                + f'Host: {fixture.host}:{fixture.port}\r\n'.encode('ascii')
                + b'Content-Type: application/json\r\n'
                + f'Content-Length: {MAX_HTTP_BODY_BYTES + 1}\r\n'.encode('ascii')
                + b'\r\n'
            )

            self.assertIn(b'413', response.splitlines()[0])
            self.assertIn(b'body too large', response)

    def test_scalar_json_payload_returns_400(self) -> None:
        with server_fixture() as fixture:
            for payload in (None, True, 1, 'method'):
                with self.subTest(payload=payload):
                    status, _, data = _post(fixture, payload)
                    self.assertEqual(status, 400)
                    self.assertIn(b'JSON-RPC payload must be object or array', data)

    def test_unknown_method_returns_jsonrpc_error_inside_200(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 7, 'method': 'nonexistent'},
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertEqual(payload['error']['code'], -32601)

    def test_notification_returns_202_with_empty_body(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                {'jsonrpc': '2.0', 'method': 'tools/list'},
                session_id=session_id,
            )

            self.assertEqual(status, 202)
            self.assertEqual(data, b'')

    def test_batch_returns_array_of_responses(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, _, data = _post(
                fixture,
                [
                    {'jsonrpc': '2.0', 'id': 10, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 11, 'method': 'tools/list'},
                ],
                session_id=session_id,
            )

            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertIsInstance(payload, list)
            self.assertEqual({entry['id'] for entry in payload}, {10, 11})

    def test_auth_token_blocks_unauthenticated_request(self) -> None:
        with server_fixture(auth_token='s3cret') as fixture:
            status, _, _ = _post(
                fixture, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
            )
            self.assertEqual(status, 401)

    def test_auth_token_accepts_correct_bearer(self) -> None:
        with server_fixture(auth_token='s3cret') as fixture:
            session_id, _ = _initialize(
                fixture, extra_headers={'Authorization': 'Bearer s3cret'}
            )
            self.assertTrue(len(session_id) > 0)

    def test_auth_token_rejects_wrong_bearer(self) -> None:
        with server_fixture(auth_token='s3cret') as fixture:
            status, _, _ = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                extra_headers={'Authorization': 'Bearer wrong'},
            )
            self.assertEqual(status, 401)

    def test_origin_not_in_allowlist_returns_403(self) -> None:
        with server_fixture(allowed_origins=['https://allowed.example']) as fixture:
            status, _, _ = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                extra_headers={'Origin': 'https://attacker.example'},
            )
            self.assertEqual(status, 403)

    def test_origin_in_allowlist_passes(self) -> None:
        with server_fixture(allowed_origins=['https://allowed.example']) as fixture:
            session_id, _ = _initialize(
                fixture, extra_headers={'Origin': 'https://allowed.example'}
            )
            self.assertTrue(len(session_id) > 0)

    def test_get_returns_sse_keepalive_for_valid_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)
            status, headers, data = fixture.request(
                'GET',
                headers={SESSION_HEADER: session_id},
            )

            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'text/event-stream')
            self.assertIn(b': teaagent mcp stream', data)

    def test_get_without_session_returns_400(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = fixture.request('GET')
            self.assertEqual(status, 400)

    def test_delete_removes_session(self) -> None:
        with server_fixture() as fixture:
            session_id, _ = _initialize(fixture)

            status, _, _ = fixture.request(
                'DELETE', headers={SESSION_HEADER: session_id}
            )
            self.assertEqual(status, 204)
            self.assertFalse(fixture.sessions.has(session_id))

            status, _, _ = _post(
                fixture,
                {'jsonrpc': '2.0', 'id': 99, 'method': 'tools/list'},
                session_id=session_id,
            )
            self.assertEqual(status, 400)

    def test_unknown_path_returns_404(self) -> None:
        with server_fixture() as fixture:
            status, _, _ = fixture.request('GET', path='/other')
            self.assertEqual(status, 404)


class MCPHTTPOAuthIntegrationTests(unittest.TestCase):
    """Integration tests for OAuth 2.1 on the MCP HTTP transport."""

    @staticmethod
    def _build_oauth_fixture(**oauth_kwargs):
        """Create a server fixture with OAuth enabled."""
        from teaagent.oauth21 import OAuth21AuthorizationServer

        oauth_server = OAuth21AuthorizationServer(
            signing_key='super-secret-key-16chars',
            issuer='http://127.0.0.1:0',
            **oauth_kwargs,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = build_workspace_tool_registry(root)
            server, sessions = build_mcp_http_server(
                registry,
                host='127.0.0.1',
                port=0,
                oauth_server=oauth_server,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                yield oauth_server, server, sessions, host, port
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def _request(
        self,
        host: str,
        port: int,
        method: str,
        path: str = MCP_PATH,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    def test_oauth_metadata_endpoint(self) -> None:
        for (
            _oauth_server,
            _server,
            _sessions,
            host,
            port,
        ) in self._build_oauth_fixture():
            status, headers, data = self._request(
                host, port, 'GET', path='/.well-known/oauth-authorization-server'
            )
            self.assertEqual(status, 200)
            meta = json.loads(data)
            self.assertIn('token_endpoint', meta)
            self.assertIn('S256', meta['code_challenge_methods_supported'])

    def test_authorization_code_flow(self) -> None:
        for oauth_server, _server, _sessions, host, port in self._build_oauth_fixture():
            oauth_server.register_client(
                'test-client', 'test-secret', ['http://localhost/callback']
            )

            # 1. Request authorization code
            from teaagent.oauth21 import (
                compute_s256_challenge,
                generate_code_verifier,
            )

            verifier = generate_code_verifier()
            challenge = compute_s256_challenge(verifier)

            status, headers, data = self._request(
                host,
                port,
                'GET',
                path=(
                    '/authorize'
                    '?client_id=test-client'
                    '&redirect_uri=http://localhost/callback'
                    f'&code_challenge={challenge}'
                    '&scope=mcp'
                    '&state=abc'
                ),
            )
            self.assertEqual(status, 302)
            location = headers.get('Location', '')
            self.assertIn('code=', location)
            self.assertIn('state=abc', location)

            # 2. Exchange code for token
            code = location.split('code=')[1].split('&')[0]
            body = (
                f'grant_type=authorization_code&code={code}&code_verifier={verifier}'
            ).encode('utf-8')
            status, _, data = self._request(
                host,
                port,
                'POST',
                path='/token',
                body=body,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Content-Length': str(len(body)),
                },
            )
            self.assertEqual(status, 200)
            token_resp = json.loads(data)
            self.assertIn('access_token', token_resp)
            self.assertEqual(token_resp['token_type'], 'Bearer')

            # 3. Use token to access MCP endpoint
            access_token = token_resp['access_token']
            body = json.dumps(
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
            ).encode('utf-8')
            status, headers, data = self._request(
                host,
                port,
                'POST',
                path=MCP_PATH,
                body=body,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                    'Authorization': f'Bearer {access_token}',
                },
            )
            self.assertEqual(status, 200)
            payload = json.loads(data)
            self.assertEqual(payload['result']['serverInfo']['name'], 'teaagent')
            session_id = headers.get(SESSION_HEADER)
            self.assertTrue(session_id)

            # 4. Subsequent request with session + token
            body2 = json.dumps(
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
            ).encode('utf-8')
            status2, _, data2 = self._request(
                host,
                port,
                'POST',
                path=MCP_PATH,
                body=body2,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body2)),
                    'Authorization': f'Bearer {access_token}',
                    SESSION_HEADER: session_id,
                },
            )
            self.assertEqual(status2, 200)

    def test_unauthorized_without_token_when_oauth_enabled(self) -> None:
        for (
            _oauth_server,
            _server,
            _sessions,
            host,
            port,
        ) in self._build_oauth_fixture():
            body = json.dumps(
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
            ).encode('utf-8')
            status, _, _ = self._request(
                host,
                port,
                'POST',
                path=MCP_PATH,
                body=body,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            self.assertEqual(status, 401)

    def test_invalid_token_rejected(self) -> None:
        for (
            _oauth_server,
            _server,
            _sessions,
            host,
            port,
        ) in self._build_oauth_fixture():
            body = json.dumps(
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
            ).encode('utf-8')
            status, _, _ = self._request(
                host,
                port,
                'POST',
                path=MCP_PATH,
                body=body,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                    'Authorization': 'Bearer invalid.token.here',
                },
            )
            self.assertEqual(status, 401)

    def test_token_endpoint_bad_code(self) -> None:
        for oauth_server, _server, _sessions, host, port in self._build_oauth_fixture():
            oauth_server.register_client('c', 's', ['http://localhost/cb'])
            body = (
                'grant_type=authorization_code'
                '&code=fake-code'
                '&code_verifier=fake-verifier'
            ).encode('utf-8')
            status, _, data = self._request(
                host,
                port,
                'POST',
                path='/token',
                body=body,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Content-Length': str(len(body)),
                },
            )
            self.assertEqual(status, 400)
            err = json.loads(data)
            self.assertEqual(err['error'], 'invalid_grant')


if __name__ == '__main__':
    unittest.main()
