from __future__ import annotations

import http.client
import json
from typing import Any, Optional
from urllib.parse import urlparse

from teaagent.mcp_http import MCP_PATH, SESSION_HEADER


class MCPClientError(RuntimeError):
    pass


class MCPHTTPClient:
    """Small stdlib client for TeaAgent's Streamable HTTP MCP transport."""

    def __init__(self, endpoint: str, *, auth_token: Optional[str] = None) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('endpoint must be an http(s) URL')
        self.endpoint = endpoint.rstrip('/')
        self.auth_token = auth_token
        self.session_id: Optional[str] = None
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self._path = parsed.path or MCP_PATH

    def initialize(self) -> dict[str, Any]:
        payload = self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'})
        if self.session_id is None:
            raise MCPClientError('initialize response missing session id')
        return payload['result']

    def list_tools(self) -> list[dict[str, Any]]:
        payload = self._post({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        return list(payload['result']['tools'])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = self._post(
            {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {'name': name, 'arguments': arguments},
            }
        )
        result = payload['result']
        if result.get('isError'):
            content = result.get('content', [])
            message = (
                content[0].get('text')
                if content and isinstance(content[0], dict)
                else 'tool call failed'
            )
            raise MCPClientError(str(message))
        return result

    def close(self) -> None:
        if self.session_id is None:
            return
        status, _headers, body = self._request('DELETE', None)
        self.session_id = None
        if status not in {204, 404}:
            raise MCPClientError(f'MCP close failed with HTTP {status}: {body!r}')

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        status, headers, data = self._request('POST', body)
        if status != 200:
            raise MCPClientError(f'MCP request failed with HTTP {status}: {data!r}')
        if SESSION_HEADER in headers:
            self.session_id = headers[SESSION_HEADER]
        try:
            response = json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MCPClientError('MCP response was not valid JSON') from exc
        if 'error' in response:
            error = response['error']
            message = error.get('message') if isinstance(error, dict) else str(error)
            raise MCPClientError(str(message))
        return response

    def _request(
        self, method: str, body: Optional[bytes]
    ) -> tuple[int, dict[str, str], bytes]:
        connection_cls = (
            http.client.HTTPSConnection
            if self._scheme == 'https'
            else http.client.HTTPConnection
        )
        headers = self._headers(body)
        conn = connection_cls(self._host, self._port, timeout=10)
        try:
            conn.request(method, self._path, body=body, headers=headers)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def _headers(self, body: Optional[bytes]) -> dict[str, str]:
        headers: dict[str, str] = {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
            headers['Content-Length'] = str(len(body))
        if self.auth_token is not None:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        if self.session_id is not None:
            headers[SESSION_HEADER] = self.session_id
        return headers
