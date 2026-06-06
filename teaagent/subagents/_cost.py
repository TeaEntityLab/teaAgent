"""Per-child cost and token ledger for subagent runs (SUB-003).

Provides a structured ledger that the parent run can use to attribute
cost, tokens, and tool usage to each child subagent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChildCostEntry:
    """Cost accounting for a single child subagent run."""

    child_run_id: str
    child_name: str
    cost_cents: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    duration_seconds: float = 0.0
    status: str = 'unknown'

    def to_dict(self) -> dict[str, Any]:
        return {
            'child_run_id': self.child_run_id,
            'child_name': self.child_name,
            'cost_cents': self.cost_cents,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'tool_calls': self.tool_calls,
            'iterations': self.iterations,
            'duration_seconds': self.duration_seconds,
            'status': self.status,
        }

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ChildCostLedger:
    """Aggregate cost ledger for all child subagents of a parent run."""

    entries: list[ChildCostEntry] = field(default_factory=list)
    total_cost_cents: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'entries': [e.to_dict() for e in self.entries],
            'total_cost_cents': self.total_cost_cents,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tool_calls': self.total_tool_calls,
        }

    def add(self, entry: ChildCostEntry) -> None:
        self.entries.append(entry)
        self.total_cost_cents += entry.cost_cents
        self.total_input_tokens += entry.input_tokens
        self.total_output_tokens += entry.output_tokens
        self.total_tool_calls += entry.tool_calls


def build_child_cost_ledger(
    workspace_root: Path,
    child_run_ids: list[tuple[str, str]],  # (child_run_id, child_name)
) -> ChildCostLedger:
    """Query the run store for each child and build a cost ledger.

    Args:
        workspace_root: Workspace root (for run store).
        child_run_ids: List of ``(child_run_id, child_name)`` pairs.

    Returns:
        A ``ChildCostLedger`` with one entry per child run.
    """
    from teaagent.run_store import RunStore

    ledger = ChildCostLedger()
    store = RunStore(workspace_root, readonly=True)

    for child_run_id, child_name in child_run_ids:
        try:
            run = store.describe_run(child_run_id)
            entry = ChildCostEntry(
                child_run_id=child_run_id,
                child_name=child_name,
                cost_cents=getattr(run, 'cost_cents', 0.0),
                input_tokens=getattr(run, 'input_tokens', 0),
                output_tokens=getattr(run, 'output_tokens', 0),
                tool_calls=0,
                iterations=0,
                duration_seconds=0.0,
                status=getattr(run, 'status', 'unknown'),
            )
            # Count tool calls from events if available
            try:
                events = store.show_run(child_run_id)
                tool_call_count = sum(
                    1
                    for e in events
                    if isinstance(e, dict) and e.get('event_type', '') == 'tool_call'
                )
                entry.tool_calls = tool_call_count
            except (FileNotFoundError, OSError):
                pass
        except (FileNotFoundError, OSError, Exception):
            entry = ChildCostEntry(
                child_run_id=child_run_id,
                child_name=child_name,
                status='not_found',
            )
        ledger.add(entry)

    return ledger


def cost_ledger_from_captured_reviews(
    workspace_root: Path,
    reviews: list[dict[str, Any]],
) -> ChildCostLedger:
    """Convenience: build a cost ledger from captured subagent reviews.

    Each review dict should have a ``child_run_id`` key.
    """
    child_ids = []
    for review in reviews:
        child_id = review.get('child_run_id', '')
        child_name = review.get('review_id', child_id)[:12]
        if child_id:
            child_ids.append((child_id, child_name))
    return build_child_cost_ledger(workspace_root, child_ids)
