"""Tests for cockpit run-status sub-states in the TUI state panel."""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from teaagent.cockpit import BudgetStatus, build_budget_state
from teaagent.tui import TeaAgentTUI


def _render_state_panel(tui: TeaAgentTUI) -> str:
    buffer = StringIO()
    tui._state_panel_last_printed = 0.0
    with (
        patch('sys.stdout', buffer),
        patch('shutil.get_terminal_size', return_value=(120, 30)),
        patch('teaagent.tui.core.compute_context_pressure', return_value=None),
    ):
        tui._print_state_panel()
    return buffer.getvalue()


def test_build_budget_state_status_thresholds() -> None:
    ok = build_budget_state(spent_cents=100.0, limit_cents=1000, cost_state='estimated')
    assert ok.status == BudgetStatus.OK
    assert ok.remaining_cents == 900.0

    warning = build_budget_state(
        spent_cents=900.0, limit_cents=1000, cost_state='estimated'
    )
    assert warning.status == BudgetStatus.WARNING

    exceeded = build_budget_state(
        spent_cents=1000.0, limit_cents=1000, cost_state='estimated'
    )
    assert exceeded.status == BudgetStatus.EXCEEDED

    unknown = build_budget_state(
        spent_cents=0.0, limit_cents=1000, cost_state='unavailable'
    )
    assert unknown.status == BudgetStatus.UNKNOWN


def test_refresh_cockpit_state_populates_budget_and_recoverable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tea_dir = root / '.teaagent'
        tea_dir.mkdir()
        suspension = {
            'acp_version': '1',
            'mode': 'chat',
            'timestamp': 1_700_000_000,
        }
        (tea_dir / 'suspension-test-run.json').write_text(
            json.dumps(suspension), encoding='utf-8'
        )

        tui = TeaAgentTUI(
            input_fn=lambda _: '',
            output_fn=lambda _: None,
            root=root,
            max_estimated_cost_cents=1000,
        )
        tui._session_cost_cents = 150.0
        tui._checkpoint_created = True

        tui._refresh_cockpit_state()

        assert tui._cockpit_state is not None
        assert tui._cockpit_state.budget.status == BudgetStatus.OK
        assert tui._cockpit_state.budget.spent_cents == 150.0
        assert tui._cockpit_state.budget.session_cost_cents == 150.0
        assert tui._cockpit_state.budget.cost_state == 'estimated'
        assert tui._cockpit_state.recoverable.has_suspended_session is True
        assert tui._cockpit_state.recoverable.has_checkpoint is True


def test_state_panel_renders_budget_and_suspended_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tea_dir = root / '.teaagent'
        tea_dir.mkdir()
        (tea_dir / 'suspension-test-run.json').write_text(
            json.dumps({'acp_version': '1', 'mode': 'chat', 'timestamp': 0}),
            encoding='utf-8',
        )

        tui = TeaAgentTUI(
            input_fn=lambda _: '',
            output_fn=lambda _: None,
            root=root,
            max_estimated_cost_cents=1000,
        )
        tui._session_cost_cents = 250.0
        tui._refresh_cockpit_state()

        output = _render_state_panel(tui)

        assert 'Budget:' in output
        assert 'Suspended Session: Available' in output
