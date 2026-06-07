"""Tool registry, definitions, and dispatch for TeaAgent."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from teaagent.errors import ToolExecutionError, ToolValidationError
from teaagent.hooks import HookError, HookRegistry
from teaagent.schema import validate_object_schema
from teaagent.tool_call_context import get_tool_call_context

logger = logging.getLogger(__name__)

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolAnnotations:
    """Safety and behavioural annotations for a registered tool."""

    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    stateful: bool = False
    security_tier: str = 'Medium'  # Low, Medium, High, Critical


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
    mcp_server_name: Optional[str] = None
    capability_manifest: Optional[dict[str, Any]] = (
        None  # Declared capabilities for security tier mapping
    )

    def get_security_tier(self) -> str:
        """Calculate security tier based on capability manifest and annotations."""
        if self.capability_manifest:
            declared_tier = self.capability_manifest.get('security_tier')
            if declared_tier in {'Low', 'Medium', 'High', 'Critical'}:
                return declared_tier

        # Default tier calculation based on annotations
        if self.annotations.destructive:
            if self.annotations.read_only:
                return 'Critical'  # Contradictory state is critical
            return 'High'
        elif self.annotations.read_only:
            return 'Low'
        else:
            return 'Medium'


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

    def __init__(self, *, hook_registry: Optional[HookRegistry] = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._rate_states: dict[str, _RateLimiterState] = {}
        self._mcp_trust_hook_roots: set[str] = set()
        self.hook_registry = hook_registry
        self._lookup_cache: dict[str, ToolDefinition] = {}

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
        mcp_server_name: Optional[str] = None,
        allow_override: bool = False,
    ) -> None:
        if not name or ' ' in name:
            raise ToolValidationError(
                'tool name must be non-empty and contain no spaces',
                hint='Provide a valid tool name without whitespace.',
            )
        if name in self._tools:
            if allow_override:
                logger.warning(
                    f"tool '{name}' is being overridden. Previous tool will be replaced."
                )
            else:
                logger.warning(
                    f"tool '{name}' is already registered. Use allow_override=True to replace it. "
                    f'Existing tool: {self._tools[name].description}'
                )
                raise ToolValidationError(
                    f"tool '{name}' is already registered",
                    hint='Use allow_override=True to replace the existing registration, or choose a different name.',
                )
        if not description:
            raise ToolValidationError(
                'tool description is required',
                hint='Provide a non-empty description string for the tool.',
            )
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            annotations=annotations,
            handler=handler,
            rate_limit=rate_limit,
            mcp_server_name=mcp_server_name,
        )
        if rate_limit is not None:
            self._rate_states[name] = _RateLimiterState(rate_limit)
        self._lookup_cache.pop(name, None)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry (used when plugin governance fails)."""
        self._tools.pop(name, None)
        self._rate_states.pop(name, None)
        self._lookup_cache.pop(name, None)

    def get(self, name: str) -> ToolDefinition:
        cached = self._lookup_cache.get(name)
        if cached is not None:
            return cached
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool '{name}' is not registered") from exc
        if len(self._lookup_cache) < 256:
            self._lookup_cache[name] = tool
        return tool

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools)

    def call_count(self, name: str) -> int:
        """Return the current sliding-window call count for a rate-limited tool."""
        state = self._rate_states.get(name)
        return state.call_count() if state is not None else 0

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Compatibility alias for ``execute()``.

        .. deprecated:: 0.13
            Use :meth:`execute` instead.
        """
        return self.execute(name, arguments)

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        validate_object_schema(tool.input_schema, arguments, label=f'tool.{name}.input')
        if self.hook_registry is not None:
            ctx = get_tool_call_context()
            original_args = dict(arguments)
            try:
                modified_args = self.hook_registry.run_pre_hooks(name, dict(arguments))
            except HookError as exc:
                if ctx is not None:
                    ctx.audit.record(
                        'tool_hook_vetoed',
                        ctx.run_id,
                        call_id=ctx.call_id,
                        tool_name=name,
                        error=str(exc),
                    )
                raise
            if modified_args is not None:
                arguments = modified_args
            if arguments != original_args and tool.annotations.destructive:
                if ctx is not None:
                    ctx.audit.record(
                        'tool_hook_pre_mutation_blocked',
                        ctx.run_id,
                        call_id=ctx.call_id,
                        tool_name=name,
                    )
                raise ToolExecutionError(
                    f"pre-tool hooks may not mutate destructive tool '{name}' arguments"
                )
            validate_object_schema(
                tool.input_schema, arguments, label=f'tool.{name}.input'
            )
            if ctx is not None and arguments != original_args:
                before_keys = set(original_args)
                after_keys = set(arguments)
                ctx.audit.record(
                    'tool_hook_pre_mutation',
                    ctx.run_id,
                    call_id=ctx.call_id,
                    tool_name=name,
                    added_keys=sorted(after_keys - before_keys),
                    removed_keys=sorted(before_keys - after_keys),
                    modified_keys=sorted(
                        k
                        for k in (before_keys & after_keys)
                        if original_args.get(k) != arguments.get(k)
                    ),
                )
        state = self._rate_states.get(name)
        if state is not None:
            state.check_and_record(name)
        t0 = time.monotonic()
        try:
            result = tool.handler(arguments)
        except ToolExecutionError:
            raise
        except (
            Exception
        ) as exc:  # pragma: no cover - preserves original detail in message
            raise ToolExecutionError(f"tool '{name}' failed: {exc}") from exc
        duration_ms = round((time.monotonic() - t0) * 1000.0, 2)
        logger.info(
            '%s executed',
            name,
            extra={
                'event': 'tool_executed',
                'tool_name': name,
                'duration_ms': duration_ms,
            },
        )
        if self.hook_registry is not None:
            ctx = get_tool_call_context()
            original_result = result
            try:
                modified_result = self.hook_registry.run_post_hooks(
                    name, arguments, result
                )
            except HookError as exc:
                if ctx is not None:
                    ctx.audit.record(
                        'tool_hook_post_failed',
                        ctx.run_id,
                        call_id=ctx.call_id,
                        tool_name=name,
                        error=str(exc),
                    )
                raise
            if modified_result is not None:
                result = modified_result
            if ctx is not None and result != original_result:
                before_keys = set(original_result)
                after_keys = set(result)
                ctx.audit.record(
                    'tool_hook_post_mutation',
                    ctx.run_id,
                    call_id=ctx.call_id,
                    tool_name=name,
                    added_keys=sorted(after_keys - before_keys),
                    removed_keys=sorted(before_keys - after_keys),
                    modified_keys=sorted(
                        k
                        for k in (before_keys & after_keys)
                        if original_result.get(k) != result.get(k)
                    ),
                )
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
                    'statefulHint': tool.annotations.stateful,
                },
            }
            for tool in self._tools.values()
        ]
