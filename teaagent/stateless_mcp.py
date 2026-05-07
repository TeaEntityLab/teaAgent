from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from teaagent.tools import ToolRegistry


@dataclass(frozen=True)
class StatelessMCPRequest:
    request_id: str
    protocol_version: str
    tool_name: str
    arguments: dict[str, Any]
    client_capabilities: dict[str, Any] = field(default_factory=dict)
    shared_state: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        client_capabilities: dict[str, Any] | None = None,
        shared_state: dict[str, Any] | None = None,
    ) -> "StatelessMCPRequest":
        return cls(
            request_id=uuid4().hex,
            protocol_version="mcp-stateless-draft-2026-06",
            tool_name=tool_name,
            arguments=arguments,
            client_capabilities=client_capabilities or {},
            shared_state=shared_state or {},
        )


@dataclass(frozen=True)
class StatelessMCPResponse:
    request_id: str
    result: dict[str, Any]
    server_capabilities: dict[str, Any]
    shared_state: dict[str, Any]


def handle_stateless_tool_request(
    request: StatelessMCPRequest,
    registry: ToolRegistry,
    *,
    server_capabilities: dict[str, Any] | None = None,
) -> StatelessMCPResponse:
    result = registry.execute(request.tool_name, request.arguments)
    return StatelessMCPResponse(
        request_id=request.request_id,
        result=result,
        server_capabilities=server_capabilities or {"tools": True, "stateless": True},
        shared_state=request.shared_state,
    )
