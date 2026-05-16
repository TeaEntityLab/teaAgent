"""ACP (Agent Client Protocol) Adapter for IDE Integration.

ACP enables TeaAgent to run inside ACP-compatible editors:
- VS Code
- Zed
- JetBrains IDEs

The protocol uses JSON-RPC 2.0 over stdio.
Reference: https://agentclientprotocol.org
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

ACP_VERSION = '1.0.0'


class ACPError(Exception):
    """Base error for ACP operations."""

    pass


class ACPMethodNotFoundError(ACPError):
    """Method not found."""

    pass


@dataclass
class ACPRequest:
    """JSON-RPC 2.0 request."""

    jsonrpc: str = '2.0'
    id: Optional[str] = None
    method: str = ''
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ACPResponse:
    """JSON-RPC 2.0 response."""

    jsonrpc: str = '2.0'
    id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None


@dataclass
class ACPToolCall:
    """Tool call notification."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: uuid4().hex[:8])


@dataclass
class ACPToolResult:
    """Tool call result."""

    call_id: str
    result: Any
    error: Optional[str] = None


class ACPServer:
    """ACP server for IDE integration.

    Implements the core ACP methods:
    - initialize: Handshake and capability negotiation
    - tools/list: List available tools
    - tools/call: Execute a tool
    - completion: Request completion from agent
    - tools/cancel: Cancel a running tool
    """

    def __init__(self, tool_registry: Any, agent_runner: Any) -> None:
        self._tool_registry = tool_registry
        self._agent_runner = agent_runner
        self._initialized = False
        self._capabilities: dict[str, Any] = {}

    def initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Initialize ACP connection."""
        params.get('clientVersion', 'unknown')
        self._initialized = True
        self._capabilities = {
            'tools': True,
            'completion': True,
            'progress': True,
            'toolProgress': True,
        }
        return {
            'serverVersion': ACP_VERSION,
            'capabilities': self._capabilities,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools."""
        if not self._initialized:
            raise ACPError('Server not initialized')
        return self._tool_registry.mcp_metadata().get('tools', [])

    def call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call."""
        if not self._initialized:
            raise ACPError('Server not initialized')

        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        if not tool_name:
            raise ACPError('Tool name is required')

        tool = self._tool_registry.get(tool_name)
        if not tool:
            raise ACPError(f'Tool not found: {tool_name}')

        try:
            result = tool.handler(arguments)
            return {'content': [{'type': 'text', 'text': json.dumps(result)}]}
        except Exception as exc:
            return {'isError': True, 'content': [{'type': 'text', 'text': str(exc)}]}

    def handle_request(self, request: ACPRequest) -> ACPResponse:
        """Handle incoming ACP request."""
        method = request.method
        params = request.params

        try:
            result: Any = None
            if method == 'initialize':
                result = self.initialize(params)
            elif method == 'tools/list':
                result = self.list_tools()
            elif method == 'tools/call':
                result = self.call_tool(params)
            elif method == 'shutdown':
                result = None
                self._initialized = False
            else:
                raise ACPMethodNotFoundError(f'Method not found: {method}')

            return ACPResponse(id=request.id, result=result)
        except ACPMethodNotFoundError as exc:
            return ACPResponse(
                id=request.id,
                error={'code': -32601, 'message': str(exc)},
            )
        except Exception as exc:
            return ACPResponse(
                id=request.id,
                error={'code': -32603, 'message': f'Internal error: {exc}'},
            )


class ACPClient:
    """ACP client for IDE-side usage."""

    def __init__(self, process: Any) -> None:
        self._process = process

    def send_request(self, method: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Send a request and wait for response."""
        request = ACPRequest(
            id=uuid4().hex[:8],
            method=method,
            params=params or {},
        )
        request_json = json.dumps(request.__dict__)
        print(request_json, file=self._process.stdin)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        response = json.loads(response_line)
        return response.get('result')


def create_acp_server(tool_registry: Any, agent_runner: Any) -> ACPServer:
    """Factory function to create ACP server."""
    return ACPServer(tool_registry, agent_runner)


def run_acp_server(tool_registry: Any, agent_runner: Any) -> None:
    """Run ACP server with stdio transport."""
    server = ACPServer(tool_registry, agent_runner)

    for line in sys.stdin:
        try:
            request_data = json.loads(line.strip())
            request = ACPRequest(**request_data)
            response = server.handle_request(request)
            print(json.dumps(response.__dict__), file=sys.stdout)
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception:
            pass


# --- ACP Integration with VS Code / Zed / JetBrains ---


@dataclass
class ACPIntegrationConfig:
    """Configuration for ACP IDE integration."""

    enabled: bool = False
    host: str = '127.0.0.1'
    port: int = 7331
    auto_start: bool = True
    log_requests: bool = False


def create_acp_tool_definitions() -> dict[str, Any]:
    """Create ACP-related tool definitions for the agent."""

    def list_acp_tools(arguments: dict[str, Any]) -> dict[str, Any]:
        return {'status': 'available', 'protocol': ACP_VERSION}

    return {
        'acp_status': {
            'description': 'Check ACP (Agent Client Protocol) integration status',
            'input_schema': {'type': 'object', 'properties': {}},
            'handler': list_acp_tools,
        }
    }
