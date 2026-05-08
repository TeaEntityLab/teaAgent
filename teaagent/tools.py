from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from teaagent.errors import ToolExecutionError
from teaagent.schema import validate_object_schema

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolAnnotations:
    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: ToolAnnotations
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        annotations: ToolAnnotations,
        handler: ToolHandler,
    ) -> None:
        if not name or " " in name:
            raise ValueError("tool name must be non-empty and contain no spaces")
        if name in self._tools:
            raise ValueError(f"tool '{name}' is already registered")
        if not description:
            raise ValueError("tool description is required")
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            annotations=annotations,
            handler=handler,
        )

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool '{name}' is not registered") from exc

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        validate_object_schema(tool.input_schema, arguments, label=f"tool.{name}.input")
        try:
            result = tool.handler(arguments)
        except Exception as exc:  # pragma: no cover - preserves original detail in message
            raise ToolExecutionError(f"tool '{name}' failed: {exc}") from exc
        validate_object_schema(tool.output_schema, result, label=f"tool.{name}.output")
        return result

    def mcp_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
                "annotations": {
                    "readOnlyHint": tool.annotations.read_only,
                    "destructiveHint": tool.annotations.destructive,
                    "idempotentHint": tool.annotations.idempotent,
                },
            }
            for tool in self._tools.values()
        ]
