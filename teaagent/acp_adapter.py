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
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from uuid import uuid4

from teaagent.acp_progress import (
    audit_sink_for_acp_progress,
    build_session_update_notification,
    default_acp_emitter,
    text_sink_for_acp_progress,
)
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.ergonomics.context_inject import merge_acp_context_blocks
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.llm import create_llm_adapter
from teaagent.policy import parse_permission_mode
from teaagent.run_store import RunStore
from teaagent.streaming.content_filter import DecisionContentStreamer
from teaagent.streaming.handlers import adapter_supports_streaming
from teaagent.types import JsonMapping, JsonValue

ACP_VERSION = '1.0.0'


class ACPNotificationSink(Protocol):
    """Callback receiving an ACP ``session/update`` JSON-RPC notification."""

    def __call__(self, notification: JsonMapping, /) -> None: ...


logger = logging.getLogger(__name__)


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
    params: JsonMapping = field(default_factory=dict)


@dataclass
class ACPResponse:
    """JSON-RPC 2.0 response."""

    jsonrpc: str = '2.0'
    id: Optional[str] = None
    result: Optional[JsonValue] = None
    error: Optional[JsonMapping] = None


@dataclass
class ACPToolCall:
    """Tool call notification."""

    tool_name: str
    arguments: JsonMapping
    call_id: str = field(default_factory=lambda: uuid4().hex[:8])


@dataclass
class ACPToolResult:
    """Tool call result."""

    call_id: str
    result: JsonValue
    error: Optional[str] = None


class ACPServer:
    """ACP server for IDE integration.

    Implements the core ACP methods:
    - initialize: Handshake and capability negotiation
    - tools/list: List available tools
    - tools/call: Execute a tool
    - session/prompt: Run one agent task with ``session/update`` progress
    - completion: Request completion from agent
    - tools/cancel: Cancel a running tool
    """

    def __init__(
        self,
        tool_registry: Any,
        agent_runner: Any,
        *,
        notify: Optional[ACPNotificationSink] = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._agent_runner = agent_runner
        self._initialized = False
        self._capabilities: JsonMapping = {}
        self._notify = notify
        self._active_session_id: Optional[str] = None

    def initialize(self, params: JsonMapping) -> JsonMapping:
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

    def list_tools(self) -> list[JsonMapping]:
        """List all available tools."""
        if not self._initialized:
            raise ACPError('Server not initialized')
        return self._tool_registry.mcp_metadata()

    def set_notification_sink(
        self, sink: ACPNotificationSink, *, session_id: Optional[str] = None
    ) -> None:
        """Register a callback for ACP ``session/update`` notifications."""
        self._notify = sink
        if session_id is not None:
            self._active_session_id = session_id

    def emit_session_update(self, session_id: str, update: JsonMapping) -> None:
        if self._notify is None:
            return

        self._notify(build_session_update_notification(session_id, update))

    def progress_audit_sink(self, session_id: str) -> Any:
        if self._notify is None:
            raise ACPError('ACP notification sink is not configured')
        return audit_sink_for_acp_progress(session_id, self._notify)

    def session_prompt(self, params: JsonMapping) -> JsonMapping:
        """Run one agent task and stream progress via ``session/update``."""
        if not self._initialized:
            raise ACPError('Server not initialized')
        session_id = str(
            params.get('sessionId')
            or params.get('session_id')
            or self._active_session_id
            or ''
        )
        if not session_id:
            raise ACPError('sessionId is required')
        prompt = str(params.get('prompt') or params.get('task') or '')
        if not prompt:
            raise ACPError('prompt is required')
        root = str(params.get('root') or '.')
        provider = params.get('provider')
        model = params.get('model')

        defaults = load_workspace_defaults(root)
        provider = provider or defaults.get('provider')
        if not provider:
            raise ACPError('provider is required (param or .teaagent config)')
        model = model or defaults.get('model')
        permission_mode = parse_permission_mode(
            params.get('permission_mode') or defaults.get('permission_mode') or 'prompt'
        )
        stream_requested = bool(params.get('stream', True))
        store = RunStore(root)
        audit = store.audit_logger()
        if self._notify is not None:
            audit.add_sink(self.progress_audit_sink(session_id))

        on_chunk = None
        if stream_requested and self._notify is not None:
            on_chunk = DecisionContentStreamer(
                text_sink_for_acp_progress(session_id, self._notify)
            ).feed

        adapter = create_llm_adapter(provider, model=model)
        use_stream = (
            stream_requested
            and on_chunk is not None
            and adapter_supports_streaming(adapter)
        )
        result = run_chat_agent(
            ChatAgentConfig.from_root(
                root,
                model=model,
                permission_mode=permission_mode,
                stream=use_stream,
                on_chunk=on_chunk,
                stream_text_only=True,
            ),
            prompt,
            adapter=adapter,
            audit=audit,
        )
        store.logger_for_result(result, audit)
        if self._notify is not None:
            self.emit_session_update(
                session_id,
                {
                    'sessionUpdate': 'agent_message_chunk',
                    'content': {
                        'type': 'text',
                        'text': (
                            result.final_answer.content
                            if result.final_answer
                            else f'[{result.status}]'
                        ),
                    },
                },
            )
        return {
            'sessionId': session_id,
            'runId': result.run_id,
            'status': result.status,
            'stopReason': 'completed' if result.status == 'completed' else 'failed',
        }

    def call_tool(self, params: JsonMapping) -> JsonMapping:
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
            result: JsonValue = None
            if method == 'initialize':
                result = self.initialize(params)
            elif method == 'tools/list':
                result = self.list_tools()
            elif method == 'tools/call':
                result = self.call_tool(params)
            elif method == 'prompt/assemble':
                task = str(params.get('prompt', params.get('task', '')))
                blocks = (
                    params.get('contextBlocks') or params.get('context_blocks') or []
                )
                if not isinstance(blocks, list):
                    blocks = []
                merged, injections = merge_acp_context_blocks(task, blocks)
                result = {'prompt': merged, 'context_blocks': injections}
            elif method == 'session/prompt':
                result = self.session_prompt(params)
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

    def send_request(self, method: str, params: Optional[JsonMapping] = None) -> Any:
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


def create_acp_server(
    tool_registry: Any,
    agent_runner: Any,
    *,
    notify: Optional[Any] = None,
) -> ACPServer:
    """Factory function to create ACP server."""
    return ACPServer(tool_registry, agent_runner, notify=notify)


def run_acp_server(tool_registry: Any, agent_runner: Any) -> None:
    """Run ACP server with stdio transport."""

    notify = default_acp_emitter(lambda line: print(line, file=sys.stdout, flush=True))
    server = ACPServer(tool_registry, agent_runner, notify=notify)

    for line in sys.stdin:
        request_data: JsonMapping | None = None
        try:
            request_data = json.loads(line.strip())
            if 'method' in request_data and 'id' not in request_data:
                continue
            request = ACPRequest(**request_data)
            response = server.handle_request(request)
            payload = {k: v for k, v in response.__dict__.items() if v is not None}
            print(json.dumps(payload, ensure_ascii=False), file=sys.stdout)
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as exc:
            logger.exception('ACP handler error: %s', exc)
            request_id = (
                request_data.get('id') if isinstance(request_data, dict) else None
            )
            error_response = {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {'code': -32603, 'message': str(exc)},
            }
            print(json.dumps(error_response, ensure_ascii=False), file=sys.stdout)
            sys.stdout.flush()


# --- ACP Integration with VS Code / Zed / JetBrains ---


@dataclass
class ACPIntegrationConfig:
    """Configuration for ACP IDE integration."""

    enabled: bool = False
    host: str = '127.0.0.1'
    port: int = 7331
    auto_start: bool = True
    log_requests: bool = False


def create_acp_tool_definitions() -> JsonMapping:
    """Create ACP-related tool definitions for the agent."""

    def list_acp_tools(arguments: JsonMapping) -> JsonMapping:
        return {'status': 'available', 'protocol': ACP_VERSION}

    return {
        'acp_status': {
            'description': 'Check ACP (Agent Client Protocol) integration status',
            'input_schema': {'type': 'object', 'properties': {}},
            'handler': list_acp_tools,
        }
    }
