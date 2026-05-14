"""MCP Tool Adapter — consume a remote MCP server as ToolRegistry entries.

Usage::

    from teaagent.mcp_tool_adapter import register_mcp_tools

    register_mcp_tools(
        registry,
        endpoint='http://localhost:7330',
        auth_token=os.environ.get('MCP_TOKEN'),
        # optional: only register tools whose names start with 'github_'
        name_prefix='github_',
    )

Each remote tool is registered as a local ``ToolDefinition`` whose handler
proxies the call through ``MCPHTTPClient``.  The tool name is taken verbatim
from the MCP ``tools/list`` response so that the model can address it with the
same name the MCP server advertises.

The ``input_schema`` and ``output_schema`` follow the MCP response shapes:
- ``input_schema`` comes directly from the MCP tool manifest.
- ``output_schema`` is a fixed envelope ``{content: [...], isError: bool}``
  that matches the MCP ``tools/call`` result shape.

``annotations`` are inferred from the tool name and MCP ``annotations`` hints
(``destructiveHint``, ``readOnlyHint``) when present.

The client connection is opened once during registration and closed on each
individual tool call to stay within stdlib connection semantics.  Pass a
pre-built ``MCPHTTPClient`` via the ``client`` parameter to reuse a session.
"""

from __future__ import annotations

import contextlib
from typing import Any, Optional

from teaagent.mcp_client import MCPHTTPClient
from teaagent.tools import ToolAnnotations, ToolRateLimit, ToolRegistry

_MCP_TOOL_OUTPUT_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'content': {'type': 'array', 'items': {'type': 'object'}},
        'isError': {'type': 'boolean'},
    },
    'required': ['content'],
}


def _infer_annotations(mcp_tool: dict[str, Any]) -> ToolAnnotations:
    hints = mcp_tool.get('annotations', {})
    return ToolAnnotations(
        read_only=bool(hints.get('readOnlyHint', False)),
        destructive=bool(hints.get('destructiveHint', False)),
        idempotent=bool(hints.get('idempotentHint', False)),
    )


def _make_handler(
    endpoint: str,
    auth_token: Optional[str],
    tool_name: str,
) -> Any:
    """Return a closure that calls one remote MCP tool and returns its content list."""

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        client = MCPHTTPClient(endpoint, auth_token=auth_token)
        client.initialize()
        try:
            result = client.call_tool(tool_name, arguments)
        finally:
            with contextlib.suppress(Exception):
                client.close()
        # Normalise to always return the fixed output schema shape.
        return {
            'content': result.get('content', []),
            'isError': bool(result.get('isError', False)),
        }

    return handler


def register_mcp_tools(
    registry: ToolRegistry,
    *,
    endpoint: str,
    auth_token: Optional[str] = None,
    name_prefix: str = '',
    rate_limit: Optional[ToolRateLimit] = None,
    client: Optional[MCPHTTPClient] = None,
) -> list[str]:
    """Discover tools from a remote MCP server and register them in *registry*.

    Parameters
    ----------
    registry:
        The ``ToolRegistry`` to register tools into.
    endpoint:
        Base URL of the MCP HTTP server (e.g. ``http://localhost:7330``).
    auth_token:
        Optional Bearer token for MCP server authentication.
    name_prefix:
        If set, only tools whose ``name`` starts with this string are registered.
    rate_limit:
        Optional ``ToolRateLimit`` applied uniformly to all registered remote tools.
    client:
        Optionally supply a pre-initialised ``MCPHTTPClient`` (session already
        open).  Caller is responsible for closing it after this call returns.

    Returns
    -------
    list[str]
        Names of the tools that were registered.
    """
    own_client = client is None
    if own_client:
        client = MCPHTTPClient(endpoint, auth_token=auth_token)
        client.initialize()

    try:
        mcp_tools: list[dict[str, Any]] = client.list_tools()  # type: ignore[union-attr]
    finally:
        if own_client:
            with contextlib.suppress(Exception):
                client.close()  # type: ignore[union-attr]

    registered: list[str] = []
    for mcp_tool in mcp_tools:
        name: str = mcp_tool.get('name', '')
        if not name:
            continue
        if name_prefix and not name.startswith(name_prefix):
            continue
        description: str = mcp_tool.get('description', f'Remote MCP tool: {name}')
        input_schema: dict[str, Any] = mcp_tool.get(
            'input_schema', {'type': 'object', 'properties': {}}
        )
        annotations = _infer_annotations(mcp_tool)
        handler = _make_handler(endpoint, auth_token, name)
        registry.register(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=_MCP_TOOL_OUTPUT_SCHEMA,
            annotations=annotations,
            handler=handler,
            rate_limit=rate_limit,
        )
        registered.append(name)

    return registered
