from __future__ import annotations

import http.client
import json
import socket
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import pytest

from teaagent.mcp_http import (
    MAX_HTTP_BODY_BYTES,
    MCP_PATH,
    SESSION_HEADER,
    build_mcp_http_server,
)
from teaagent.workspace_tools import build_workspace_tool_registry
from test_support import skip_if_socket_bind_is_blocked


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
    skip_if_socket_bind_is_blocked()
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


def test_initialize_returns_session_id_and_protocol_info() -> None:
    with server_fixture() as fixture:
        session_id, payload = _initialize(fixture)

        assert len(session_id) > 0
        assert payload['id'] == 1
        assert payload['result']['serverInfo']['name'] == 'teaagent'
        assert 'protocolVersion' in payload['result']


def test_subsequent_request_without_session_returns_400() -> None:
    with server_fixture() as fixture:
        status, _, data = _post(
            fixture, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
        )
        assert status == 400
        assert b'Mcp-Session-Id' in data


def test_request_with_unknown_session_returns_400() -> None:
    with server_fixture() as fixture:
        status, _, _ = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            session_id='not-a-real-session',
        )
        assert status == 400


def test_tools_list_with_valid_session() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)

        status, _, data = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            session_id=session_id,
        )

        assert status == 200
        payload = json.loads(data)
        names = {tool['name'] for tool in payload['result']['tools']}
        assert 'workspace_read_file' in names


def test_tools_call_executes_workspace_tool() -> None:
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

        assert status == 200
        payload = json.loads(data)
        assert not payload['result']['isError']
        content_text = json.loads(payload['result']['content'][0]['text'])
        assert content_text['content'] == 'hi'


def test_invalid_json_body_returns_400() -> None:
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
        assert status == 400


def test_non_numeric_content_length_returns_400() -> None:
    with server_fixture() as fixture:
        response = fixture.raw_request(
            b'POST /mcp HTTP/1.1\r\n'
            + f'Host: {fixture.host}:{fixture.port}\r\n'.encode('ascii')
            + b'Content-Type: application/json\r\n'
            + b'Content-Length: not-a-number\r\n'
            + b'\r\n{}'
        )

        assert b'400' in response.splitlines()[0]


def test_oversized_json_body_returns_413_without_reading_body() -> None:
    with server_fixture() as fixture:
        response = fixture.raw_request(
            b'POST /mcp HTTP/1.1\r\n'
            + f'Host: {fixture.host}:{fixture.port}\r\n'.encode('ascii')
            + b'Content-Type: application/json\r\n'
            + f'Content-Length: {MAX_HTTP_BODY_BYTES + 1}\r\n'.encode('ascii')
            + b'\r\n'
        )

        assert b'413' in response.splitlines()[0]
        assert b'body too large' in response


@pytest.mark.parametrize('payload', [None, True, 1, 'method'])
def test_scalar_json_payload_returns_400(payload) -> None:
    with server_fixture() as fixture:
        status, _, data = _post(fixture, payload)
        assert status == 400
        assert b'JSON-RPC payload must be object or array' in data


def test_empty_batch_returns_202() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, _, data = _post(fixture, [], session_id=session_id)
        assert status == 202
        assert data == b''


def test_batch_skips_non_dict_items() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, _, data = _post(
            fixture,
            [
                {'jsonrpc': '2.0', 'id': 10, 'method': 'tools/list'},
                'not a dict',
                42,
                {'jsonrpc': '2.0', 'id': 11, 'method': 'tools/list'},
            ],
            session_id=session_id,
        )
        assert status == 200
        payload = json.loads(data)
        assert isinstance(payload, list)
        assert {entry['id'] for entry in payload} == {10, 11}


def test_initialize_without_id_returns_400() -> None:
    with server_fixture() as fixture:
        status, _, data = _post(
            fixture,
            {'jsonrpc': '2.0', 'method': 'initialize'},
        )
        assert status == 400
        assert b'initialize requires an id' in data


def test_unknown_method_returns_jsonrpc_error_inside_200() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, _, data = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 7, 'method': 'nonexistent'},
            session_id=session_id,
        )

        assert status == 200
        payload = json.loads(data)
        assert payload['error']['code'] == -32601


def test_notification_returns_202_with_empty_body() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, _, data = _post(
            fixture,
            {'jsonrpc': '2.0', 'method': 'tools/list'},
            session_id=session_id,
        )

        assert status == 202
        assert data == b''


def test_batch_returns_array_of_responses() -> None:
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

        assert status == 200
        payload = json.loads(data)
        assert isinstance(payload, list)
        assert {entry['id'] for entry in payload} == {10, 11}


def test_auth_token_blocks_unauthenticated_request() -> None:
    with server_fixture(auth_token='s3cret') as fixture:
        status, _, _ = _post(
            fixture, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
        )
        assert status == 401


def test_auth_token_accepts_correct_bearer() -> None:
    with server_fixture(auth_token='s3cret') as fixture:
        session_id, _ = _initialize(
            fixture, extra_headers={'Authorization': 'Bearer s3cret'}
        )
        assert len(session_id) > 0


def test_auth_token_rejects_wrong_bearer() -> None:
    with server_fixture(auth_token='s3cret') as fixture:
        status, _, _ = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
            extra_headers={'Authorization': 'Bearer wrong'},
        )
        assert status == 401


def test_origin_not_in_allowlist_returns_403() -> None:
    with server_fixture(allowed_origins=['https://allowed.example']) as fixture:
        status, _, _ = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
            extra_headers={'Origin': 'https://attacker.example'},
        )
        assert status == 403


def test_origin_in_allowlist_passes() -> None:
    with server_fixture(allowed_origins=['https://allowed.example']) as fixture:
        session_id, _ = _initialize(
            fixture, extra_headers={'Origin': 'https://allowed.example'}
        )
        assert len(session_id) > 0


def test_get_returns_sse_keepalive_for_valid_session() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, headers, data = fixture.request(
            'GET',
            headers={SESSION_HEADER: session_id},
        )

        assert status == 200
        assert headers['Content-Type'] == 'text/event-stream'
        assert b': teaagent mcp stream' in data


def test_get_without_session_returns_400() -> None:
    with server_fixture() as fixture:
        status, _, _ = fixture.request('GET')
        assert status == 400


def test_delete_removes_session() -> None:
    with server_fixture() as fixture:
        session_id, _ = _initialize(fixture)
        status, _, _ = fixture.request(
            'DELETE',
            headers={SESSION_HEADER: session_id},
        )
        assert status == 204
        # Subsequent request with same session should fail
        status2, _, _ = _post(
            fixture,
            {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/list'},
            session_id=session_id,
        )
        assert status2 == 400


def test_delete_nonexistent_session_returns_404() -> None:
    with server_fixture() as fixture:
        status, _, _ = fixture.request(
            'DELETE',
            headers={SESSION_HEADER: 'nonexistent-session'},
        )
        assert status == 404


def test_unknown_path_returns_404() -> None:
    with server_fixture() as fixture:
        status, _, _ = fixture.request('GET', path='/other')
        assert status == 404


@contextmanager
def _build_oauth_fixture(**oauth_kwargs):
    """Create a server fixture with OAuth enabled."""
    skip_if_socket_bind_is_blocked()
    from teaagent.oauth21 import OAuth21AuthorizationServer

    oauth_server = OAuth21AuthorizationServer(
        signing_key='super-secret-key-at-least-32-chars',
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


def test_oauth_metadata_endpoint() -> None:
    with _build_oauth_fixture() as (
        _oauth_server,
        _server,
        _sessions,
        host,
        port,
    ):
        status, headers, data = _request(
            host, port, 'GET', path='/.well-known/oauth-authorization-server'
        )
        assert status == 200
        meta = json.loads(data)
        assert 'token_endpoint' in meta
        assert 'S256' in meta['code_challenge_methods_supported']


def test_authorization_code_flow() -> None:
    with _build_oauth_fixture() as (oauth_server, _server, _sessions, host, port):
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

        status, headers, data = _request(
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
        assert status == 302
        location = headers.get('Location', '')
        assert 'code=' in location
        assert 'state=abc' in location

        # 2. Exchange code for token
        code = location.split('code=')[1].split('&')[0]
        body = (
            f'grant_type=authorization_code&code={code}&code_verifier={verifier}'
        ).encode('utf-8')
        status, _, data = _request(
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
        assert status == 200
        token_resp = json.loads(data)
        assert 'access_token' in token_resp
        assert token_resp['token_type'] == 'Bearer'

        # 3. Use token to access MCP endpoint
        access_token = token_resp['access_token']
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}).encode(
            'utf-8'
        )
        status, headers, data = _request(
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
        assert status == 200
        payload = json.loads(data)
        assert payload['result']['serverInfo']['name'] == 'teaagent'
        session_id = headers.get(SESSION_HEADER)
        assert session_id

        # 4. Subsequent request with session + token
        body2 = json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}).encode(
            'utf-8'
        )
        status2, _, data2 = _request(
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
        assert status2 == 200


def test_oauth_resource_server_uses_authorization_server_key_ring() -> None:
    from teaagent.oauth21 import (
        OAuthKeyRing,
        compute_s256_challenge,
        generate_code_verifier,
    )

    key_ring = OAuthKeyRing(
        active_kid='rotated',
        keys={
            'legacy': b'mcp-http-secret-key-at-least-16',
            'rotated': b'rotated-secret-key-at-least-16',
        },
    )
    with _build_oauth_fixture(key_ring=key_ring) as (
        oauth_server,
        _server,
        _sessions,
        host,
        port,
    ):
        oauth_server.register_client(
            'rotated-client', 'secret', ['http://localhost/callback']
        )
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, _ = oauth_server.create_authorization_code(
            client_id='rotated-client',
            redirect_uri='http://localhost/callback',
            code_challenge=challenge,
        )
        token = oauth_server.exchange_code(
            code=redirect_url.split('code=')[1].split('&')[0],
            code_verifier=verifier,
            client_id='rotated-client',
        )
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}).encode(
            'utf-8'
        )

        status, headers, data = _request(
            host,
            port,
            'POST',
            path=MCP_PATH,
            body=body,
            headers={
                'Content-Type': 'application/json',
                'Content-Length': str(len(body)),
                'Authorization': f'Bearer {token.access_token}',
            },
        )

        assert status == 200, data
        assert SESSION_HEADER in headers


def test_unauthorized_without_token_when_oauth_enabled() -> None:
    with _build_oauth_fixture() as (
        _oauth_server,
        _server,
        _sessions,
        host,
        port,
    ):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}).encode(
            'utf-8'
        )
        status, _, _ = _request(
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
        assert status == 401


def test_invalid_token_rejected() -> None:
    with _build_oauth_fixture() as (
        _oauth_server,
        _server,
        _sessions,
        host,
        port,
    ):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}).encode(
            'utf-8'
        )
        status, _, _ = _request(
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
        assert status == 401


def test_token_endpoint_bad_code() -> None:
    with _build_oauth_fixture() as (oauth_server, _server, _sessions, host, port):
        oauth_server.register_client('c', 's', ['http://localhost/cb'])
        body = (
            'grant_type=authorization_code&code=fake-code&code_verifier=fake-verifier'
        ).encode('utf-8')
        status, _, data = _request(
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
        assert status == 400
        err = json.loads(data)
        assert err['error'] == 'invalid_grant'
