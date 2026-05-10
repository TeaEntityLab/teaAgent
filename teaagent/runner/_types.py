from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from uuid import uuid4

from teaagent.audit import redact_tool_arguments


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class FinalAnswer:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


Decision = Union[ToolRequest, FinalAnswer]
DecisionFn = Callable[[dict[str, Any]], Decision]


@dataclass(frozen=True)
class ApprovalRequest:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    annotations: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            'call_id': self.call_id,
            'tool_name': self.tool_name,
            'arguments': redact_tool_arguments(self.arguments),
            'reason': self.reason,
            'annotations': self.annotations,
        }


ApprovalHandler = Callable[[ApprovalRequest], bool]


@dataclass(frozen=True)
class RunResult:
    run_id: str
    final_answer: Optional[FinalAnswer]
    iterations: int
    tool_calls: int
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
