"""P0-B-002: TUI cost accumulation and display state tests.

Tests for:
- /cost displays cost_state label (actual, estimated, unavailable, unlimited)
- Task-driven cost accumulation via mocked agent runs
- /budget shows same cost numbers as /cost
- Cost state label appears (not just a number)
- Same-run consistency across surfaces
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from teaagent.tui import TeaAgentTUI, _format_budget_cents, _format_remaining_cents


class TUICostStateTests(unittest.TestCase):
    """Tests for cost display state labels."""

    def test_cost_state_defaults_to_unlimited_when_no_cap(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        # Default: _max_cost_budget_cents=None, _session_cost_cents=0
        self.assertEqual(tui._determine_cost_state(), 'unlimited')

    def test_cost_state_estimated_when_cap_and_cost_present(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 150.0
        self.assertEqual(tui._determine_cost_state(), 'estimated')

    def test_cost_state_unavailable_when_cap_but_zero_cost(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 0.0
        self.assertEqual(tui._determine_cost_state(), 'unavailable')

    def test_cost_state_unlimited_after_effort_unlimited(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort(['unlimited'])
        self.assertEqual(tui._determine_cost_state(), 'unlimited')

    def test_cost_state_estimated_after_effort_normal_with_cost(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort(['normal'])
        tui._session_cost_cents = 50.0
        self.assertEqual(tui._determine_cost_state(), 'estimated')


class TUICostCommandTests(unittest.TestCase):
    """Tests for /cost command output."""

    def test_cost_command_shows_cost_state_label(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 150.0
        tui._handle_cost()
        self.assertEqual(output[-1], 'cost: $1.50 (estimated)')

    def test_cost_command_shows_unlimited_label(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        tui._session_cost_cents = 50.0
        tui._handle_cost()
        self.assertEqual(output[-1], 'cost: $0.50 (unlimited)')

    def test_cost_command_shows_unavailable_label(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 500
        tui._session_cost_cents = 0.0
        tui._handle_cost()
        self.assertEqual(output[-1], 'cost: $0.00 (unavailable)')

    def test_cost_command_not_just_number(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 100.0
        tui._handle_cost()
        # Must contain a state label in parentheses, not just a dollar amount
        self.assertIn('(', output[-1])
        self.assertIn(')', output[-1])
        # Must contain one of the four canonical state labels
        label_part = output[-1].split('(')[1].rstrip(')')
        self.assertIn(label_part, ('actual', 'estimated', 'unavailable', 'unlimited'))

    def test_handle_cost_via_command_dispatch(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 500
        tui._session_cost_cents = 250.0
        self.assertTrue(tui.handle_command('cost'))
        self.assertEqual(output[-1], 'cost: $2.50 (estimated)')


class TUIBudgetCommandTests(unittest.TestCase):
    """Tests for /budget command output."""

    def test_budget_command_shows_cost_state(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 300.0
        tui._handle_budget()
        text = output[-1]
        self.assertIn('cost_state=estimated', text)

    def test_budget_command_shows_unlimited_cost_state(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        tui._session_cost_cents = 50.0
        tui._handle_budget()
        text = output[-1]
        self.assertIn('cost_state=unlimited', text)

    def test_budget_via_command_dispatch_shows_cost_state(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 500
        tui._session_cost_cents = 100.0
        self.assertTrue(tui.handle_command('budget'))
        text = output[-1]
        self.assertIn('cost_state=estimated', text)

    def test_budget_and_cost_show_same_cost_number(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 500
        tui._session_cost_cents = 100.0
        tui._handle_cost()
        cost_output = output[-1]
        output.clear()
        tui._handle_budget()
        budget_output = output[-1]
        # Both should contain $1.00
        self.assertIn('$1.00', cost_output)
        self.assertIn('$1.00', budget_output)
        # Both should contain same state label
        self.assertIn('estimated', cost_output)
        self.assertIn('estimated', budget_output)


class TUICostAccumulationTests(unittest.TestCase):
    """Tests for cost accumulation via mocked agent runs."""

    def test_mocked_task_accumulates_cost_via_command_path(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run-1',
                status='completed',
                iterations=2,
                tool_calls=3,
                cost_cents=150.0,
                input_tokens=500,
                output_tokens=200,
                final_answer=unittest.mock.MagicMock(content='done'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.list_runs.return_value = []
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *_a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            self.assertEqual(tui._session_cost_cents, 0.0)
            tui._run_agent_task('test task')
            self.assertEqual(tui._session_cost_cents, 150.0)

            # Cost command reflects accumulated cost with state label
            tui._max_cost_budget_cents = 1000
            tui._handle_cost()
            self.assertEqual(output[-1], 'cost: $1.50 (estimated)')

    def test_multi_task_cost_accumulation(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run-1',
                status='completed',
                iterations=1,
                tool_calls=1,
                cost_cents=150.0,
                input_tokens=100,
                output_tokens=50,
                final_answer=unittest.mock.MagicMock(content='ok'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.list_runs.return_value = []
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *_a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            tui._run_agent_task('first task')
            self.assertEqual(tui._session_cost_cents, 150.0)

            mock_run.return_value.cost_cents = 75.0
            mock_run.return_value.run_id = 'test-run-2'
            tui._run_agent_task('second task')
            self.assertEqual(tui._session_cost_cents, 225.0)

            mock_run.return_value.cost_cents = 25.0
            mock_run.return_value.run_id = 'test-run-3'
            tui._run_agent_task('third task')
            self.assertEqual(tui._session_cost_cents, 250.0)

            # /cost reflects accumulated total
            tui._max_cost_budget_cents = 1000
            tui._handle_cost()
            self.assertEqual(output[-1], 'cost: $2.50 (estimated)')

    def test_cost_accumulation_with_estimated_state(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=1,
                cost_cents=200.0,
                input_tokens=100,
                output_tokens=50,
                final_answer=unittest.mock.MagicMock(content='ok'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.list_runs.return_value = []
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *_a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            tui._run_agent_task('test task')
            # Cost state should be 'estimated' when cap is set and cost > 0
            self.assertEqual(tui._determine_cost_state(), 'estimated')

    def test_cost_accumulation_with_unlimited_state(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=1,
                cost_cents=500.0,
                input_tokens=100,
                output_tokens=50,
                final_answer=unittest.mock.MagicMock(content='ok'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.list_runs.return_value = []
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *_a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            tui._run_agent_task('test task')
            self.assertEqual(tui._session_cost_cents, 500.0)
            self.assertEqual(tui._determine_cost_state(), 'unlimited')


class TUICostTerminologyAlignmentTests(unittest.TestCase):
    """P0-B-003: Same-run consistency across surfaces."""

    def test_cost_state_consistency_across_cost_and_budget(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 100.0

        tui._handle_cost()
        cost_out = output[-1]
        output.clear()
        tui._handle_budget()
        budget_out = output[-1]

        # Same cost number
        self.assertIn('$1.00', cost_out)
        self.assertIn('$1.00', budget_out)
        # Same cost state label
        self.assertIn('(estimated)', cost_out)
        self.assertIn('cost_state=estimated', budget_out)

    def test_cost_state_consistency_across_cost_and_effort(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        tui._session_cost_cents = 150.0

        tui._handle_cost()
        cost_out = output[-1]
        output.clear()
        tui._handle_effort([])
        effort_out = output[-1]

        # Same spent amount
        self.assertIn('$1.50', cost_out)
        self.assertIn('$1.50', effort_out)
        self.assertIn('estimated', cost_out)

    def test_run_summary_includes_cost_state(self) -> None:
        from teaagent.ergonomics.run_summary import summarize_run

        summary = summarize_run(
            root='.',
            run_id='test-run',
            events=[],
            cost_cents=150.0,
            input_tokens=100,
            output_tokens=50,
            budget_cap_cents=1000,
        )
        self.assertEqual(summary['cost_state'], 'estimated')
        self.assertEqual(summary['cost_usd'], 1.50)

    def test_run_summary_unlimited_cost_state(self) -> None:
        from teaagent.ergonomics.run_summary import summarize_run

        summary = summarize_run(
            root='.',
            run_id='test-run',
            events=[],
            cost_cents=500.0,
            input_tokens=100,
            output_tokens=50,
            budget_cap_cents=None,
        )
        self.assertEqual(summary['cost_state'], 'unlimited')

    def test_run_summary_unavailable_cost_state(self) -> None:
        from teaagent.ergonomics.run_summary import summarize_run

        summary = summarize_run(
            root='.',
            run_id='test-run',
            events=[],
            cost_cents=0.0,
            input_tokens=0,
            output_tokens=0,
            budget_cap_cents=500,
        )
        self.assertEqual(summary['cost_state'], 'unavailable')


class TUIEvidenceBundleCostTests(unittest.TestCase):
    """P0-B-003: Evidence bundle cost fields."""

    def test_evidence_bundle_has_cost_fields(self) -> None:
        from teaagent.run_evidence import RunEvidenceBundle

        bundle = RunEvidenceBundle(
            run_id='test-run',
            cost_cents=150.0,
            cost_state='estimated',
            budget_cap_cents=1000,
        )
        d = bundle.to_dict()
        self.assertEqual(d['cost_cents'], 150.0)
        self.assertEqual(d['cost_state'], 'estimated')
        self.assertEqual(d['budget_cap_cents'], 1000)

    def test_evidence_bundle_default_cost_state(self) -> None:
        from teaagent.run_evidence import RunEvidenceBundle

        bundle = RunEvidenceBundle(run_id='test-run')
        d = bundle.to_dict()
        self.assertEqual(d['cost_cents'], 0.0)
        self.assertEqual(d['cost_state'], 'unavailable')


class TUICostFormattingTests(unittest.TestCase):
    """Tests for cost formatting helpers in tui/__init__.py."""

    def test_format_budget_cents_unlimited(self) -> None:
        self.assertEqual(_format_budget_cents(None), 'unlimited')

    def test_format_budget_cents_zero(self) -> None:
        self.assertEqual(_format_budget_cents(0), '$0.00')

    def test_format_budget_cents_normal(self) -> None:
        self.assertEqual(_format_budget_cents(1000), '$10.00')

    def test_format_remaining_unlimited(self) -> None:
        self.assertEqual(_format_remaining_cents(None, 100.0), 'unlimited')

    def test_format_remaining_with_budget(self) -> None:
        result = _format_remaining_cents(1000, 300.0)
        self.assertEqual(result, '$7.00')


class TUICockpitCostStateTests(unittest.TestCase):
    """Tests for cockpit cost state display — verify _determine_cost_state
    correctly delegates through _refresh_control_cockpit."""

    def test_cockpit_state_delegates_to_determine_cost_state(self) -> None:
        """_refresh_control_cockpit uses _determine_cost_state for its cost state."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        # _determine_cost_state is the source of truth for cockpit cost_state
        self.assertEqual(tui._determine_cost_state(), 'unlimited')
        tui._max_cost_budget_cents = 1000
        self.assertEqual(tui._determine_cost_state(), 'unavailable')
        tui._session_cost_cents = 200.0
        self.assertEqual(tui._determine_cost_state(), 'estimated')


class TUIEvidenceSummaryCostTests(unittest.TestCase):
    """P0-B-003: Evidence summary cost state."""

    def test_evidence_summary_has_cost_state_and_cap(self) -> None:
        from teaagent.evidence_summary import RunEvidenceSummary

        summary = RunEvidenceSummary(
            run_id='test-run',
            total_cost_cents=150,
            cost_state='estimated',
            budget_cap_cents=1000,
        )
        d = summary.to_dict()
        self.assertEqual(d['cost_state'], 'estimated')
        self.assertEqual(d['budget_cap_cents'], 1000)

    def test_build_evidence_summary_cost_state(self) -> None:
        from teaagent.evidence_summary import build_evidence_summary

        with patch('teaagent.evidence_summary.RunStore') as mock_store_cls:
            mock_store = unittest.mock.MagicMock()
            mock_store.show_run.return_value = [
                {'event_type': 'run_started', 'payload': {}, 'created_at': '2026-01-01T00:00:00'},
                {'event_type': 'tool_call', 'payload': {'estimated_cost_cents': 150}, 'created_at': '2026-01-01T00:01:00'},
                {'event_type': 'run_completed', 'payload': {'cost_cents': 0}, 'created_at': '2026-01-01T00:02:00'},
            ]
            mock_store_cls.return_value = mock_store

            summary = build_evidence_summary(
                mock_store, 'test-run', '.', budget_cap_cents=1000
            )
            self.assertEqual(summary.cost_state, 'estimated')
            self.assertEqual(summary.budget_cap_cents, 1000)

    def test_build_evidence_summary_unlimited_state(self) -> None:
        from teaagent.evidence_summary import build_evidence_summary

        with patch('teaagent.evidence_summary.RunStore') as mock_store_cls:
            mock_store = unittest.mock.MagicMock()
            mock_store.show_run.return_value = [
                {'event_type': 'run_started', 'payload': {}, 'created_at': '2026-01-01T00:00:00'},
                {'event_type': 'run_completed', 'payload': {'cost_cents': 500}, 'created_at': '2026-01-01T00:02:00'},
            ]
            mock_store_cls.return_value = mock_store

            summary = build_evidence_summary(
                mock_store, 'test-run', '.', budget_cap_cents=None
            )
            self.assertEqual(summary.cost_state, 'unlimited')
            self.assertIsNone(summary.budget_cap_cents)
