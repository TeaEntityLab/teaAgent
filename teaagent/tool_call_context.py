from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ToolCallContext:
    """Ambient context for a single tool call.

    Bound by the runner around ToolRegistry.execute() so lower layers can emit
    audit events about hook veto/mutations without changing tool schemas or the
    ToolRegistry.execute() signature.
    """

    audit: Any
    run_id: str
    call_id: str


_tool_call_context: ContextVar[Optional[ToolCallContext]] = ContextVar(
    'teaagent_tool_call_context', default=None
)


def get_tool_call_context() -> Optional[ToolCallContext]:
    return _tool_call_context.get()


def bind_tool_call_context(ctx: ToolCallContext) -> Token[Optional[ToolCallContext]]:
    return _tool_call_context.set(ctx)


def reset_tool_call_context(token: Token[Optional[ToolCallContext]]) -> None:
    _tool_call_context.reset(token)
