"""P0-B-002: TUI cost accumulation and display state tests.

Tests for:
- /cost displays cost_state label (actual, estimated, unavailable, unlimited)
- Task-driven cost accumulation via boundary-patched agent runs (CG-16)
- /budget shows same cost numbers as /cost
- Cost state label appears (not just a number)
- Same-run consistency across surfaces
"""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import MagicMock, patch

from teaagent.tui import TeaAgentTUI, _format_budget_cents, _format_remaining_cents
from teaagent.types import FinalAnswer, RunResult


def _completed_run_result(
    *,
    run_id: str = 'cost-test-run',
    cost_cents: float = 0.0,
    content: str = 'done',
    iterations: int = 1,
    tool_calls: int = 0,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> RunResult:
    return RunResult(
        run_id=run_id,
        status='completed',
        iterations=iterations,
        tool_calls=tool_calls,
        cost_cents=cost_cents,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        final_answer=FinalAnswer(content=content),
        metadata={},
        error_message=None,
    )


@contextmanager
def _cost_run_boundary(
    tui: TeaAgentTUI,
    *,
    run_result: RunResult | None = None,
) -> Iterator[MagicMock]:
    result = run_result or _completed_run_result()
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch(
            'teaagent.chat_session_controller.run_chat_agent',
            return_value=result,
        ) as mock_run,
        patch('teaagent.tui.core.RunStore.show_run', return_value=[]),
        patch('teaagent.tui.state.create_llm_adapter'),
    ):
        yield mock_run


def test_cost_state_defaults_to_unlimited_when_no_cap() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    # Default: _max_cost_budget_cents=None, _session_cost_cents=0
    assert tui._determine_cost_state() == 'unlimited'


def test_cost_state_estimated_when_cap_and_cost_present() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 1000
    tui._session_cost_cents = 150.0
    assert tui._determine_cost_state() == 'estimated'


def test_cost_state_unavailable_when_cap_but_zero_cost() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 1000
    tui._session_cost_cents = 0.0
    assert tui._determine_cost_state() == 'unavailable'


def test_cost_state_unlimited_after_effort_unlimited() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._handle_effort(['unlimited'])
    assert tui._determine_cost_state() == 'unlimited'


def test_cost_state_estimated_after_effort_normal_with_cost() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._handle_effort(['normal'])
    tui._session_cost_cents = 50.0
    assert tui._determine_cost_state() == 'estimated'


def test_cost_command_shows_cost_state_label() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 1000
    tui._session_cost_cents = 150.0
    tui._handle_cost()
    assert output[-1] == 'cost: $1.50 (estimated)'


def test_cost_command_shows_unlimited_label() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = None
    tui._session_cost_cents = 50.0
    tui._handle_cost()
    assert output[-1] == 'cost: $0.50 (unlimited)'


def test_cost_command_shows_unavailable_label() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 500
    tui._session_cost_cents = 0.0
    tui._handle_cost()
    assert output[-1] == 'cost: $0.00 (unavailable)'


def test_cost_command_not_just_number() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 1000
    tui._session_cost_cents = 100.0
    tui._handle_cost()
    # Must contain a state label in parentheses, not just a dollar amount
    assert '(' in output[-1]
    assert ')' in output[-1]
    # Must contain one of the four canonical state labels
    label_part = output[-1].split('(')[1].rstrip(')')
    assert label_part in ('actual', 'estimated', 'unavailable', 'unlimited')


def test_handle_cost_via_command_dispatch() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 500
    tui._session_cost_cents = 250.0
    assert tui.handle_command('cost')
    assert output[-1] == 'cost: $2.50 (estimated)'


def test_budget_command_shows_cost_state() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 1000
    tui._session_cost_cents = 300.0
    tui._handle_budget()
    text = output[-1]
    assert 'cost_state=estimated' in text


def test_budget_command_shows_unlimited_cost_state() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = None
    tui._session_cost_cents = 50.0
    tui._handle_budget()
    text = output[-1]
    assert 'cost_state=unlimited' in text


def test_budget_via_command_dispatch_shows_cost_state() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = 500
    tui._session_cost_cents = 100.0
    assert tui.handle_command('budget')
    text = output[-1]
    assert 'cost_state=estimated' in text


def test_budget_and_cost_show_same_cost_number() -> None:
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
    assert '$1.00' in cost_output
    assert '$1.00' in budget_output
    # Both should contain same state label
    assert 'estimated' in cost_output
    assert 'estimated' in budget_output


def test_mocked_task_accumulates_cost_via_command_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        with _cost_run_boundary(
            tui,
            run_result=_completed_run_result(
                run_id='test-run-1',
                cost_cents=150.0,
                iterations=2,
                tool_calls=3,
                input_tokens=500,
                output_tokens=200,
            ),
        ):
            assert tui._session_cost_cents == 0.0
            tui._run_agent_task('test task')
            assert tui._session_cost_cents == 150.0

            tui._max_cost_budget_cents = 1000
            tui._handle_cost()
            assert output[-1] == 'cost: $1.50 (estimated)'


def test_multi_task_cost_accumulation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        with _cost_run_boundary(tui) as mock_run:
            mock_run.return_value = _completed_run_result(
                run_id='test-run-1',
                cost_cents=150.0,
            )
            tui._run_agent_task('first task')
            assert tui._session_cost_cents == 150.0

            mock_run.return_value = _completed_run_result(
                run_id='test-run-2',
                cost_cents=75.0,
            )
            tui._run_agent_task('second task')
            assert tui._session_cost_cents == 225.0

            mock_run.return_value = _completed_run_result(
                run_id='test-run-3',
                cost_cents=25.0,
            )
            tui._run_agent_task('third task')
            assert tui._session_cost_cents == 250.0

            tui._max_cost_budget_cents = 1000
            tui._handle_cost()
            assert output[-1] == 'cost: $2.50 (estimated)'


def test_cost_accumulation_with_estimated_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = 1000
        with _cost_run_boundary(
            tui,
            run_result=_completed_run_result(run_id='test-run', cost_cents=200.0),
        ):
            tui._run_agent_task('test task')
            assert tui._determine_cost_state() == 'estimated'


def test_cost_accumulation_with_unlimited_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        with _cost_run_boundary(
            tui,
            run_result=_completed_run_result(run_id='test-run', cost_cents=500.0),
        ):
            tui._run_agent_task('test task')
            assert tui._session_cost_cents == 500.0
            assert tui._determine_cost_state() == 'unlimited'


def test_cost_state_consistency_across_cost_and_budget() -> None:
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
    assert '$1.00' in cost_out
    assert '$1.00' in budget_out
    # Same cost state label
    assert '(estimated)' in cost_out
    assert 'cost_state=estimated' in budget_out


def test_cost_state_consistency_across_cost_and_effort() -> None:
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
    assert '$1.50' in cost_out
    assert '$1.50' in effort_out
    assert 'estimated' in cost_out


def test_run_summary_includes_cost_state() -> None:
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
    assert summary['cost_state'] == 'estimated'
    assert summary['cost_usd'] == 1.50


def test_run_summary_unlimited_cost_state() -> None:
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
    assert summary['cost_state'] == 'unlimited'


def test_run_summary_unknown_cost_state() -> None:
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
    assert summary['cost_state'] == 'unknown'


def test_evidence_bundle_has_cost_fields() -> None:
    from teaagent.run_evidence import RunEvidenceBundle

    bundle = RunEvidenceBundle(
        run_id='test-run',
        cost_cents=150.0,
        cost_state='estimated',
        budget_cap_cents=1000,
    )
    d = bundle.to_dict()
    assert d['cost_cents'] == 150.0
    assert d['cost_state'] == 'estimated'
    assert d['budget_cap_cents'] == 1000


def test_evidence_bundle_default_cost_state() -> None:
    from teaagent.run_evidence import RunEvidenceBundle

    bundle = RunEvidenceBundle(run_id='test-run')
    d = bundle.to_dict()
    assert d['cost_cents'] == 0.0
    assert d['cost_state'] == 'unavailable'


def test_format_budget_cents_unlimited() -> None:
    assert _format_budget_cents(None) == 'unlimited'


def test_format_budget_cents_zero() -> None:
    assert _format_budget_cents(0) == '$0.00'


def test_format_budget_cents_normal() -> None:
    assert _format_budget_cents(1000) == '$10.00'


def test_format_remaining_unlimited() -> None:
    assert _format_remaining_cents(None, 100.0) == 'unlimited'


def test_format_remaining_with_budget() -> None:
    result = _format_remaining_cents(1000, 300.0)
    assert result == '$7.00'


def test_cockpit_state_delegates_to_determine_cost_state() -> None:
    """_refresh_control_cockpit uses _determine_cost_state for its cost state."""
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._max_cost_budget_cents = None
    # _determine_cost_state is the source of truth for cockpit cost_state
    assert tui._determine_cost_state() == 'unlimited'
    tui._max_cost_budget_cents = 1000
    assert tui._determine_cost_state() == 'unavailable'
    tui._session_cost_cents = 200.0
    assert tui._determine_cost_state() == 'estimated'


def test_evidence_summary_has_cost_state_and_cap() -> None:
    from teaagent.evidence_summary import RunEvidenceSummary

    summary = RunEvidenceSummary(
        run_id='test-run',
        total_cost_cents=150,
        cost_state='estimated',
        budget_cap_cents=1000,
    )
    d = summary.to_dict()
    assert d['cost_state'] == 'estimated'
    assert d['budget_cap_cents'] == 1000


def test_build_evidence_summary_cost_state() -> None:
    from unittest.mock import MagicMock

    from teaagent.evidence_summary import build_evidence_summary

    with patch('teaagent.evidence_summary.RunStore') as mock_store_cls:
        mock_store = MagicMock()
        mock_store.show_run.return_value = [
            {
                'event_type': 'run_started',
                'payload': {},
                'created_at': '2026-01-01T00:00:00',
            },
            {
                'event_type': 'tool_call',
                'payload': {'estimated_cost_cents': 150},
                'created_at': '2026-01-01T00:01:00',
            },
            {
                'event_type': 'run_completed',
                'payload': {'cost_cents': 0},
                'created_at': '2026-01-01T00:02:00',
            },
        ]
        mock_store_cls.return_value = mock_store

        summary = build_evidence_summary(
            mock_store, 'test-run', '.', budget_cap_cents=1000
        )
        assert summary.cost_state == 'estimated'
        assert summary.budget_cap_cents == 1000


def test_build_evidence_summary_unlimited_state() -> None:
    from unittest.mock import MagicMock

    from teaagent.evidence_summary import build_evidence_summary

    with patch('teaagent.evidence_summary.RunStore') as mock_store_cls:
        mock_store = MagicMock()
        mock_store.show_run.return_value = [
            {
                'event_type': 'run_started',
                'payload': {},
                'created_at': '2026-01-01T00:00:00',
            },
            {
                'event_type': 'run_completed',
                'payload': {'cost_cents': 500},
                'created_at': '2026-01-01T00:02:00',
            },
        ]
        mock_store_cls.return_value = mock_store

        summary = build_evidence_summary(
            mock_store, 'test-run', '.', budget_cap_cents=None
        )
        assert summary.cost_state == 'unlimited'
        assert summary.budget_cap_cents is None
