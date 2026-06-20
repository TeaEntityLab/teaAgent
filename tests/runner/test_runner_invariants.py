"""Shared-invariant tests (ADR 0040).

Scope of what is machine-checked here:
  * the primary runner (AgentRunner via run_chat_agent) is exercised
    end-to-end and asserted to enforce the budget and emit the required
    audit lifecycle / approval events;
  * the second framework's budget-clamp math (compute_clamped_budget) is
    asserted to never exceed the parent;
  * the budget/audit/approval invariant comparators are unit-tested with
    representative evidence bundles.

NOTE: this file does not yet drive a live ``SubagentManager.run_subagent``
run and diff its evidence against the primary path. That live differential
is tracked as a follow-up in ADR 0040 §2; today the cross-framework
guarantee rests on the static import gate
(``scripts/validate_runner_invariants.py``) ensuring the second framework
delegates to the shared ApprovalManager/EventSpine rather than
re-implementing them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FakeAdapter

from teaagent import AuditLogger, ChatAgentConfig, run_chat_agent
from teaagent.budget import RunBudget
from teaagent.policy import PermissionMode
from teaagent.runner import RunResult
from teaagent.runner._invariants import (
    ClampedBudget,
    RunnerEvidenceBundle,
    assert_approval_invariant,
    assert_audit_events_match,
    assert_audit_invariant,
    assert_budget_invariant,
    collect_approval_evidence,
    collect_audit_evidence,
    collect_budget_evidence,
    compute_clamped_budget,
)
from teaagent.tools import ToolAnnotations, ToolRegistry


def _make_strict_budget(
    max_iterations: int = 3,
    max_tool_calls: int = 3,
) -> RunBudget:
    return RunBudget(
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
        max_estimated_cost_cents=None,
    )


def _make_read_only_adapter(
    outputs: list[str] | None = None,
) -> FakeAdapter:
    return FakeAdapter(outputs or ['{"type":"final","content":"done"}'])


def _register_read_tool(registry: ToolRegistry, tmp_path: Path) -> None:
    test_file = tmp_path / 'hello.txt'
    test_file.write_text('hello')

    def _read_file(path: str) -> dict[str, object]:
        with open(path) as f:
            return {'content': f.read()}

    registry.register(
        name='read_file',
        description='Read a file from disk',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'content': {'type': 'string'}},
        },
        handler=_read_file,
        annotations=ToolAnnotations(read_only=True, idempotent=True),
    )


def _run_primary_path(
    tmp_path: Path,
    max_iterations: int = 3,
    max_tool_calls: int = 3,
) -> tuple[RunResult, AuditLogger]:
    registry = ToolRegistry()
    _register_read_tool(registry, tmp_path)
    audit = AuditLogger()

    adapter = _make_read_only_adapter()

    config = ChatAgentConfig.from_root(
        tmp_path,
        permission_mode=PermissionMode.READ_ONLY,
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
    )

    result = run_chat_agent(
        config,
        'read and report',
        adapter=adapter,
        audit=audit,
        registry=registry,
    )
    return result, audit


class TestBudgetInvariant:
    def test_primary_budget_is_enforced(self, tmp_path: Path) -> None:
        max_iters = 2
        result, _audit = _run_primary_path(tmp_path, max_iterations=max_iters)
        assert result.iterations <= max_iters, (
            f'iterations {result.iterations} exceeded max {max_iters}'
        )

    def test_clamped_budget_never_exceeds_parent(self) -> None:
        clamped = compute_clamped_budget(10, 10, 3, 3)
        assert clamped.max_iterations == 3
        assert clamped.max_tool_calls == 3

    def test_clamped_budget_defaults_to_child_when_smaller(self) -> None:
        clamped = compute_clamped_budget(2, 2, 10, 10)
        assert clamped.max_iterations == 2
        assert clamped.max_tool_calls == 2

    def test_assert_budget_invariant_positive(self) -> None:
        primary = RunnerEvidenceBundle(max_iterations=5, max_tool_calls=5)
        secondary = RunnerEvidenceBundle(max_iterations=3, max_tool_calls=3)
        assert_budget_invariant(primary, secondary)

    def test_clamped_budget_roundtrip(self) -> None:
        c = compute_clamped_budget(7, 9, 5, 4)
        assert isinstance(c, ClampedBudget)
        assert c.max_iterations == 5
        assert c.max_tool_calls == 4


class TestAuditInvariant:
    def test_primary_emits_required_lifecycle_events(self, tmp_path: Path) -> None:
        result, audit = _run_primary_path(tmp_path)
        event_types = [e.event_type for e in audit.events]

        has_started = 'run_started' in event_types
        has_completed_or_failed = (
            'run_completed' in event_types or 'run_failed' in event_types
        )

        assert has_started, f'missing run_started in {event_types}'
        assert has_completed_or_failed, (
            f'missing run_completed/run_failed in {event_types}'
        )

    def test_audit_evidence_extraction(self, tmp_path: Path) -> None:
        result, audit = _run_primary_path(tmp_path)
        evidence = collect_audit_evidence(result, audit.events)

        assert evidence.iterations_used >= 0
        assert evidence.emitted_event_types
        assert 'run_started' in evidence.emitted_event_types

    def test_assert_audit_invariant_matches(self) -> None:
        primary_events = [
            'run_started',
            'iteration_started',
            'run_completed',
        ]
        secondary_events = [
            'run_started',
            'iteration_started',
            'run_completed',
        ]
        assert_audit_invariant(primary_events, secondary_events)

    def test_assert_audit_invariant_missing_run_completed(self) -> None:
        with pytest.raises(AssertionError):
            assert_audit_invariant(
                ['run_started', 'run_failed'],
                ['run_started', 'run_completed'],
            )

    def test_assert_audit_events_match_symmetric(self) -> None:
        assert_audit_events_match(
            ['run_started', 'iteration_started', 'run_completed'],
            ['run_started', 'iteration_started', 'run_completed'],
        )

    def test_tool_call_invariant_present(self, tmp_path: Path) -> None:
        adapter = FakeAdapter(
            [
                json.dumps(
                    {
                        'type': 'tool',
                        'tool_name': 'read_file',
                        'arguments': {'path': str(tmp_path / 'hello.txt')},
                        'call_id': 'read-1',
                    }
                ),
                '{"type":"final","content":"done"}',
            ]
        )
        registry = ToolRegistry()
        _register_read_tool(registry, tmp_path)
        audit = AuditLogger()
        config = ChatAgentConfig.from_root(
            tmp_path,
            permission_mode=PermissionMode.READ_ONLY,
            max_iterations=5,
            max_tool_calls=5,
        )

        result = run_chat_agent(
            config,
            'read a file',
            adapter=adapter,
            audit=audit,
            registry=registry,
        )

        event_types = [e.event_type for e in audit.events]
        assert 'tool_call_started' in event_types
        assert result.tool_calls >= 1


class TestApprovalInvariant:
    def test_read_only_mode_blocks_destructive_tool(self, tmp_path: Path) -> None:
        registry = ToolRegistry()

        def _write_file(path: str, content: str) -> dict[str, object]:
            return {'written': path}

        registry.register(
            name='write_file',
            description='Write a file',
            input_schema={
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'content': {'type': 'string'},
                },
                'required': ['path', 'content'],
            },
            output_schema={
                'type': 'object',
                'properties': {'written': {'type': 'string'}},
            },
            handler=_write_file,
            annotations=ToolAnnotations(read_only=False, destructive=True),
        )

        adapter = FakeAdapter(
            [
                json.dumps(
                    {
                        'type': 'tool',
                        'tool_name': 'write_file',
                        'arguments': {
                            'path': str(tmp_path / 'out.txt'),
                            'content': 'data',
                        },
                        'call_id': 'write-1',
                    }
                ),
                '{"type":"final","content":"done"}',
            ]
        )

        audit = AuditLogger()
        config = ChatAgentConfig.from_root(
            tmp_path,
            permission_mode=PermissionMode.READ_ONLY,
            max_iterations=5,
            max_tool_calls=5,
        )

        result = run_chat_agent(
            config,
            'write a file',
            adapter=adapter,
            audit=audit,
            registry=registry,
        )

        assert result.status != 'completed', (
            f'expected blocked status, got {result.status}'
        )

    def test_collect_approval_evidence_empty_on_read_only(
        self,
        tmp_path: Path,
    ) -> None:
        _result, audit = _run_primary_path(tmp_path)
        evidence = collect_approval_evidence(audit.events)
        assert evidence.approval_events == []

    def test_assert_approval_invariant_none(self) -> None:
        assert_approval_invariant([], [])

    def test_approval_manager_is_importable_from_subagents(self) -> None:
        from teaagent.approval_manager import ApprovalManager

        assert ApprovalManager is not None


class TestEvidenceCollectors:
    def test_collect_budget_from_agent_runner(self, tmp_path: Path) -> None:
        registry = ToolRegistry()
        _register_read_tool(registry, tmp_path)
        audit = AuditLogger()

        adapter = _make_read_only_adapter()
        config = ChatAgentConfig.from_root(
            tmp_path,
            permission_mode=PermissionMode.READ_ONLY,
            max_iterations=2,
            max_tool_calls=2,
        )

        result = run_chat_agent(
            config,
            'read',
            adapter=adapter,
            audit=audit,
            registry=registry,
        )

        budget_evidence = collect_budget_evidence(
            {
                'iterations': result.iterations,
                'tool_calls': result.tool_calls,
            }
        )
        assert isinstance(budget_evidence, RunnerEvidenceBundle)

    def test_collect_budget_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match='Unsupported runner type'):
            collect_budget_evidence(42)
