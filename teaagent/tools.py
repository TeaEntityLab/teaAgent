from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from teaagent.errors import ToolExecutionError
from teaagent.schema import validate_object_schema

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolAnnotations:
    """Safety and behavioural annotations for a registered tool."""

    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False


@dataclass(frozen=True)
class ToolRateLimit:
    """Per-tool call-rate quota enforced at execution time.

    ``max_calls`` is the maximum number of calls allowed within ``window_seconds``.
    The limiter uses a sliding-window counter protected by a lock so it is safe
    to use from multiple threads.

    Example::

        rate_limit = ToolRateLimit(max_calls=5, window_seconds=60.0)
        registry.register(name='my_tool', ..., rate_limit=rate_limit)
    """

    max_calls: int
    window_seconds: float = 60.0


@dataclass(frozen=True)
class ToolDefinition:
    """Complete definition of a registered tool: schemas, annotations, and handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: ToolAnnotations
    handler: ToolHandler
    rate_limit: Optional[ToolRateLimit] = None


class _RateLimiterState:
    """Mutable sliding-window state for one tool's rate limit."""

    def __init__(self, limit: ToolRateLimit) -> None:
        self.limit = limit
        self._lock = threading.Lock()
        self._call_times: list[float] = []

    def check_and_record(self, tool_name: str) -> None:
        """Raise ``ToolExecutionError`` if the quota is exceeded, otherwise record the call."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.limit.window_seconds
            self._call_times = [t for t in self._call_times if t >= cutoff]
            if len(self._call_times) >= self.limit.max_calls:
                raise ToolExecutionError(
                    f"tool '{tool_name}' rate limit exceeded: "
                    f'{self.limit.max_calls} calls per {self.limit.window_seconds}s'
                )
            self._call_times.append(now)

    def call_count(self) -> int:
        """Return current call count within the active window (for observability)."""
        now = time.monotonic()
        cutoff = now - self.limit.window_seconds
        with self._lock:
            return sum(1 for t in self._call_times if t >= cutoff)


class ToolRegistry:
    """Central registry for all agent tools.

    Provides registration, lookup, schema validation, rate-limit enforcement,
    and MCP‑compatible metadata export.  Use ``build_workspace_tool_registry``
    for the standard workspace‑tool set.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._rate_states: dict[str, _RateLimiterState] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        annotations: ToolAnnotations,
        handler: ToolHandler,
        rate_limit: Optional[ToolRateLimit] = None,
    ) -> None:
        if not name or ' ' in name:
            raise ValueError('tool name must be non-empty and contain no spaces')
        if name in self._tools:
            raise ValueError(f"tool '{name}' is already registered")
        if not description:
            raise ValueError('tool description is required')
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            annotations=annotations,
            handler=handler,
            rate_limit=rate_limit,
        )
        if rate_limit is not None:
            self._rate_states[name] = _RateLimiterState(rate_limit)

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool '{name}' is not registered") from exc

    def call_count(self, name: str) -> int:
        """Return the current sliding-window call count for a rate-limited tool."""
        state = self._rate_states.get(name)
        return state.call_count() if state is not None else 0

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        validate_object_schema(tool.input_schema, arguments, label=f'tool.{name}.input')
        state = self._rate_states.get(name)
        if state is not None:
            state.check_and_record(name)
        try:
            result = tool.handler(arguments)
        except ToolExecutionError:
            raise
        except (
            Exception
        ) as exc:  # pragma: no cover - preserves original detail in message
            raise ToolExecutionError(f"tool '{name}' failed: {exc}") from exc
        validate_object_schema(tool.output_schema, result, label=f'tool.{name}.output')
        return result

    def mcp_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'input_schema': tool.input_schema,
                'output_schema': tool.output_schema,
                'annotations': {
                    'readOnlyHint': tool.annotations.read_only,
                    'destructiveHint': tool.annotations.destructive,
                    'idempotentHint': tool.annotations.idempotent,
                },
            }
            for tool in self._tools.values()
        ]
