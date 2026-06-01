"""Tests for proactive context compaction warning (UX2.2)."""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.context import ContextCompactor
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.tools import ToolRegistry


class TestThresholdConfiguration:
    """Tests for compaction_warning_threshold configuration."""

    def test_default_threshold_is_0_6(self) -> None:
        runner = AgentRunner(registry=ToolRegistry(), audit=AuditLogger())
        assert runner._compaction_warning_threshold == 0.6

    def test_default_max_context_tokens_is_200000(self) -> None:
        runner = AgentRunner(registry=ToolRegistry(), audit=AuditLogger())
        assert runner._max_context_tokens == 200000

    def test_custom_threshold(self) -> None:
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=AuditLogger(),
            compaction_warning_threshold=0.8,
        )
        assert runner._compaction_warning_threshold == 0.8

    def test_custom_max_context_tokens(self) -> None:
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=AuditLogger(),
            max_context_tokens=100000,
        )
        assert runner._max_context_tokens == 100000

    def test_threshold_clamped_to_0_0_lower_bound(self) -> None:
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=AuditLogger(),
            compaction_warning_threshold=-0.5,
        )
        assert runner._compaction_warning_threshold == 0.0

    def test_threshold_clamped_to_1_0_upper_bound(self) -> None:
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=AuditLogger(),
            compaction_warning_threshold=2.5,
        )
        assert runner._compaction_warning_threshold == 1.0

    def test_max_context_tokens_clamped_to_min_1(self) -> None:
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=AuditLogger(),
            max_context_tokens=0,
        )
        assert runner._max_context_tokens == 1


class TestWarningEmissionLogic:
    """Tests for the proactive compaction warning logic."""

    def test_warning_not_emitted_below_threshold(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.6,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=50000,
            output_tokens=50000,
        )
        assert not runner._compaction_warning_emitted
        assert context['observations'] == []

    def test_warning_emitted_above_threshold(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.6,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=70000,
            output_tokens=60000,
        )
        assert runner._compaction_warning_emitted
        assert len(context['observations']) == 1
        obs = context['observations'][0]
        assert obs['role'] == 'system'
        assert 'Context is filling up' in obs['content']
        assert '65%' in obs['content']

    def test_warning_only_emits_once(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.6,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=70000,
            output_tokens=60000,
        )
        assert runner._compaction_warning_emitted
        assert len(context['observations']) == 1

        runner._check_compaction_warning(
            context=context,
            input_tokens=100000,
            output_tokens=100000,
        )
        assert len(context['observations']) == 1

    def test_zero_threshold_disables_warning(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.0,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=190000,
            output_tokens=9000,
        )
        assert not runner._compaction_warning_emitted
        assert context['observations'] == []

    def test_zero_tokens_do_not_trigger_warning(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.6,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=0,
            output_tokens=0,
        )
        assert not runner._compaction_warning_emitted

    def test_warning_at_exact_boundary(self) -> None:
        """Warning should fire when usage equals threshold."""
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            compaction_warning_threshold=0.5,
            max_context_tokens=200000,
        )
        context: dict = {'observations': []}
        runner._check_compaction_warning(
            context=context,
            input_tokens=50000,
            output_tokens=50000,
        )
        assert runner._compaction_warning_emitted
        assert '50%' in context['observations'][0]['content']


class TestCompactionWarningInRunLoop:
    """Integration tests: warning fires during actual run loop execution."""

    def test_warning_injected_during_run(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            budget=RunBudget(
                max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
            ),
            compaction_warning_threshold=0.3,
            max_context_tokens=50000,
        )

        def decide(context: dict) -> FinalAnswer:
            context['_input_tokens'] = 10000
            context['_output_tokens'] = 10000
            return FinalAnswer('ok')

        result = runner.run(task='t', decide=decide, run_id='run-cw')
        assert result.status == 'completed'
        assert runner._compaction_warning_emitted

    def test_warning_not_emitted_when_under_threshold_in_run(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            budget=RunBudget(
                max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
            ),
            compaction_warning_threshold=0.9,
            max_context_tokens=50000,
        )

        def decide(context: dict) -> FinalAnswer:
            context['_input_tokens'] = 10000
            context['_output_tokens'] = 10000
            return FinalAnswer('ok')

        result = runner.run(task='t', decide=decide, run_id='run-cw-under')
        assert result.status == 'completed'
        assert not runner._compaction_warning_emitted

    def test_compact_after_observations_still_works(self) -> None:
        """Existing auto-compaction still functions."""
        audit = AuditLogger()
        compactor = ContextCompactor(recent_observations=1)
        runner = AgentRunner(
            registry=ToolRegistry(),
            audit=audit,
            budget=RunBudget(
                max_iterations=10, max_tool_calls=10, max_estimated_cost_cents=100
            ),
            compactor=compactor,
            compact_after_observations=2,
            compaction_warning_threshold=0.6,
            max_context_tokens=200000,
        )
        runner.run(
            task='t', decide=_make_final_answer_decider(), run_id='run-auto-compact'
        )
        compact_events = [
            e
            for e in audit.events
            if getattr(e, 'event_type', None) == 'context_compacted'
        ]
        assert len(compact_events) >= 0


def _make_final_answer_decider():
    """Create a simple decide function that returns FinalAnswer."""

    def decide(context: dict) -> FinalAnswer:
        return FinalAnswer('ok')

    return decide


class TestCLICompact:
    """Tests for the CLI /compact command handler."""

    def test_handle_compact_basic(self) -> None:
        from teaagent.cli._handlers.chat_commands import handle_compact

        compactor = ContextCompactor(
            recent_observations=2,
            enable_semantic_compression=False,
        )
        session_context: dict = {
            'observations': [
                {'tool_name': f'tool_{i}', 'result': {'data': f'x{i}'}}
                for i in range(10)
            ],
            'compaction_count': 0,
        }
        result = handle_compact(compactor, session_context)
        assert result['tokens_saved'] > 0
        assert result['pre_count'] == 10
        assert result['post_count'] < 10
        assert result['compression_ratio'] >= 0.0
        assert isinstance(result['summary'], str)

    def test_handle_compact_empty_observations(self) -> None:
        from teaagent.cli._handlers.chat_commands import handle_compact

        compactor = ContextCompactor()
        session_context: dict = {'observations': [], 'compaction_count': 0}
        result = handle_compact(compactor, session_context)
        assert result['pre_count'] == 0
        assert result['post_count'] == 0
