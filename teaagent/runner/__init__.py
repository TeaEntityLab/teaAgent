"""Agent runner package — decision loop, budget, and approval integration."""

from ._core import AgentRunner, validate_tool_decision
from ._events import (
    EventSpine,
    RunEvent,
    RunEventType,
    audit_event_to_run_event_type,
    read_run_events_from_audit,
    read_run_events_from_jsonl,
    register_audit_consumer,
)
from ._types import (
    ApprovalHandler,
    ApprovalRequest,
    BudgetPromptHandler,
    Decision,
    DecisionFn,
    FinalAnswer,
    RunResult,
    ToolRequest,
)

__all__ = [
    'AgentRunner',
    'ApprovalHandler',
    'ApprovalRequest',
    'BudgetPromptHandler',
    'Decision',
    'DecisionFn',
    'EventSpine',
    'FinalAnswer',
    'audit_event_to_run_event_type',
    'read_run_events_from_audit',
    'read_run_events_from_jsonl',
    'register_audit_consumer',
    'RunEvent',
    'RunEventType',
    'RunResult',
    'ToolRequest',
    'validate_tool_decision',
]
