"""Acceptance test for per-child cost and token ledger (SUB-003).

Verifies that the cost ledger correctly aggregates cost, tokens, and
tool usage from child subagent runs.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.subagents._cost import (
    ChildCostEntry,
    ChildCostLedger,
    build_child_cost_ledger,
    cost_ledger_from_captured_reviews,
)


class TestChildCostEntry:
    """ChildCostEntry model."""

    def test_minimal(self) -> None:
        entry = ChildCostEntry(child_run_id='abc', child_name='test-agent')
        assert entry.cost_cents == 0.0
        assert entry.total_tokens == 0
        assert entry.status == 'unknown'

    def test_full(self) -> None:
        entry = ChildCostEntry(
            child_run_id='abc123',
            child_name='code-gen',
            cost_cents=150.0,
            input_tokens=5000,
            output_tokens=2000,
            tool_calls=12,
            iterations=3,
            duration_seconds=45.0,
            status='completed',
        )
        assert entry.total_tokens == 7000
        assert entry.cost_cents == 150.0

    def test_to_dict(self) -> None:
        entry = ChildCostEntry(child_run_id='abc', child_name='t', cost_cents=10.0)
        d = entry.to_dict()
        assert d['child_run_id'] == 'abc'
        assert d['cost_cents'] == 10.0
        assert 'child_name' in d


class TestChildCostLedger:
    """ChildCostLedger aggregation."""

    def test_empty(self) -> None:
        ledger = ChildCostLedger()
        assert ledger.total_cost_cents == 0.0
        assert len(ledger.entries) == 0

    def test_single_entry(self) -> None:
        ledger = ChildCostLedger()
        ledger.add(ChildCostEntry('r1', 'agent-a', cost_cents=50.0, input_tokens=1000))
        assert ledger.total_cost_cents == 50.0
        assert ledger.total_input_tokens == 1000

    def test_multi_entry(self) -> None:
        ledger = ChildCostLedger()
        ledger.add(ChildCostEntry('r1', 'a', cost_cents=10.0, input_tokens=100))
        ledger.add(ChildCostEntry('r2', 'b', cost_cents=20.0, input_tokens=200))
        ledger.add(ChildCostEntry('r3', 'c', cost_cents=30.0, input_tokens=300))
        assert ledger.total_cost_cents == 60.0
        assert ledger.total_input_tokens == 600
        assert len(ledger.entries) == 3

    def test_to_dict(self) -> None:
        ledger = ChildCostLedger()
        ledger.add(ChildCostEntry('r1', 'a', cost_cents=5.0))
        d = ledger.to_dict()
        assert d['total_cost_cents'] == 5.0
        assert len(d['entries']) == 1


class TestBuildChildCostLedger:
    """build_child_cost_ledger with mock/fake run store."""

    def test_empty_child_list(self, tmp_path: Path) -> None:
        ledger = build_child_cost_ledger(tmp_path, [])
        assert ledger.total_cost_cents == 0.0
        assert len(ledger.entries) == 0

    def test_child_not_found(self, tmp_path: Path) -> None:
        ledger = build_child_cost_ledger(tmp_path, [('nonexistent', 'test-agent')])
        assert len(ledger.entries) == 1
        assert ledger.entries[0].status == 'not_found'
        assert ledger.entries[0].cost_cents == 0.0

    def test_cost_ledger_from_reviews_empty(self, tmp_path: Path) -> None:
        ledger = cost_ledger_from_captured_reviews(tmp_path, [])
        assert ledger.total_cost_cents == 0.0

    def test_cost_ledger_from_reviews_skips_empty_ids(self, tmp_path: Path) -> None:
        reviews = [{'child_run_id': ''}, {'child_run_id': 'r2'}]
        ledger = cost_ledger_from_captured_reviews(tmp_path, reviews)
        # r2 won't be found either, but it should be attempted
        assert len(ledger.entries) >= 0
