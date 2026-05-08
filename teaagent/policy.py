from __future__ import annotations

from dataclasses import dataclass, field

from teaagent.errors import ToolPermissionError


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls."""

    approved_call_ids: frozenset[str] = field(default_factory=frozenset)
    allow_all_destructive: bool = False

    def assert_allowed(self, *, tool_name: str, call_id: str, destructive: bool) -> None:
        if destructive and self.allow_all_destructive:
            return
        if destructive and call_id not in self.approved_call_ids:
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' requires explicit approval."
            )
