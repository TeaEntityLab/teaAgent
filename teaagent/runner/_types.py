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
    run_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        from teaagent.ergonomics.approval_store import _compute_argument_digest

        payload: dict[str, Any] = {
            'call_id': self.call_id,
            'tool_name': self.tool_name,
            'arguments': redact_tool_arguments(self.arguments),
            'reason': self.reason,
            'annotations': self.annotations,
            'argument_digest': _compute_argument_digest(self.arguments),
            'argument_digest_version': 'v1',
        }
        if self.run_id is not None:
            payload['run_id'] = self.run_id
        return payload


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
    cost_cents: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
