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


# --- Filtered MCP Client with OAuth and Sampling Support ---


class FilteredMCPClient:
    """MCP client wrapper with tool filtering and sampling support.

    This wrapper adds:
    - Tool allow/block lists for security
    - Sampling configuration for AI-powered tools
    - OAuth token refresh support
    """

    def __init__(
        self,
        inner: MCPHTTPClient,
        *,
        allowed_tools: Optional[frozenset[str]] = None,
        blocked_tools: Optional[frozenset[str]] = None,
        sampling_max_tokens: int = 4096,
        sampling_temperature: float = 0.7,
        oauth_token: Optional[str] = None,
    ) -> None:
        self._inner = inner
        self._allowed_tools = allowed_tools
        self._blocked_tools = blocked_tools
        self._sampling_max_tokens = sampling_max_tokens
        self._sampling_temperature = sampling_temperature
        self._oauth_token = oauth_token
        self._available_tools: Optional[list[dict[str, Any]]] = None

    def initialize(self) -> dict[str, Any]:
        result = self._inner.initialize()
        self._available_tools = self._inner.list_tools()
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if self._available_tools is None:
            self._available_tools = self._inner.list_tools()

        if self._blocked_tools:
            return [
                t
                for t in self._available_tools
                if t.get('name') not in self._blocked_tools
            ]

        if self._allowed_tools:
            return [
                t for t in self._available_tools if t.get('name') in self._allowed_tools
            ]

        return self._available_tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._check_tool_allowed(name)

        if name.startswith('mcp_ai_') or name.startswith(' sampling'):
            arguments = self._apply_sampling(arguments)

        return self._inner.call_tool(name, arguments)

    def _check_tool_allowed(self, name: str) -> None:
        if self._blocked_tools and name in self._blocked_tools:
            raise MCPClientError(f"Tool '{name}' is blocked by filter policy")

        if self._allowed_tools and name not in self._allowed_tools:
            raise MCPClientError(
                f"Tool '{name}' not in allowed list. "
                f'Allowed: {sorted(self._allowed_tools)}'
            )

    def _apply_sampling(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if 'sampling' not in arguments:
            arguments['sampling'] = {}
        arguments['sampling'].setdefault('max_tokens', self._sampling_max_tokens)
        arguments['sampling'].setdefault('temperature', self._sampling_temperature)
        return arguments

    def refresh_oauth_token(self, token: str) -> None:
        self._oauth_token = token

    def close(self) -> None:
        self._inner.close()


class MCPClientFactory:
    """Factory for creating configured MCP clients."""

    @staticmethod
    def create_http(
        endpoint: str,
        *,
        auth_token: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        blocked_tools: Optional[list[str]] = None,
        sampling_max_tokens: int = 4096,
        sampling_temperature: float = 0.7,
    ) -> FilteredMCPClient:
        inner = MCPHTTPClient(endpoint, auth_token=auth_token)
        return FilteredMCPClient(
            inner,
            allowed_tools=frozenset(allowed_tools) if allowed_tools else None,
            blocked_tools=frozenset(blocked_tools) if blocked_tools else None,
            sampling_max_tokens=sampling_max_tokens,
            sampling_temperature=sampling_temperature,
        )
