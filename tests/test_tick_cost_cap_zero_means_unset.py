"""DU-010A: `agent tick --max-cost-cents 0` must mean "unset", not a zero-spend cap.

Trace (before the fix):
  cli/_agent_parsers.py `--max-cost-cents` default=0 ("0 means unset")
  -> cli/_handlers/_agent/automation.py `_automation_draft_from_args` stores 0
  -> automations.py re-reads the saved spec with max_cost_cents=0
  -> automation.py `_start_automation_background_run` passed
     max_estimated_cost_cents=spec.max_cost_cents (0)
  -> ergonomics/background_run.py forwarded `--max-estimated-cost-cents 0`
  -> runner/_governed_execution.py treats 0 as a zero-spend cap.

The tick/automation boundary must map 0 (and None) to "no flag forwarded".
A positive cap must still be forwarded unchanged. `agent run` semantics for an
explicit zero cap are a runner contract and must not change.
"""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import MagicMock, patch

from teaagent.automations import AutomationStore
from teaagent.cli._handlers._agent import _run_automation_once
from teaagent.ergonomics.background_run import build_agent_run_command

_FLAG = '--max-estimated-cost-cents'


def _create_spec(root: Any, max_cost_cents: int) -> Any:
    store = AutomationStore(root)
    return store.create(
        name=f'tick-cap-{max_cost_cents}',
        task='summarize the repo status into the notes file',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        max_cost_cents=max_cost_cents,
    )


def _tick_run_command(root: Any, max_cost_cents: int) -> list[str]:
    """Drive the real tick path (save -> re-read -> run args -> command)."""
    _create_spec(root, max_cost_cents)
    # Re-read from disk, exactly as the tick loop does.
    spec = AutomationStore(root).list()[0]
    assert spec.max_cost_cents == max_cost_cents

    captured: list[list[str]] = []

    class _Record:
        def to_dict(self) -> dict[str, Any]:
            return {
                'background_id': 'bg-test',
                'pid': 1,
                'alive': True,
                'log_path': str(root / 'bg-test.log'),
            }

    class _Store:
        def start(self, command: list[str], label: str) -> _Record:
            captured.append(list(command))
            return _Record()

    factory = MagicMock()
    factory.return_value.create_background_run_store.return_value = _Store()
    with patch(
        'teaagent.cli._handlers._agent.automation.AgentExecutionFactory',
        factory,
    ):
        _run_automation_once(str(root), spec)

    assert len(captured) == 1
    return captured[0]


def test_tick_with_zero_max_cost_cents_forwards_no_zero_cost_cap(tmp_path) -> None:
    """(a) max_cost_cents=0 is unset: no zero spend cap reaches the run."""
    cmd = _tick_run_command(tmp_path, max_cost_cents=0)

    assert _FLAG not in cmd
    if _FLAG in cmd:
        assert cmd[cmd.index(_FLAG) + 1] != '0'


def test_tick_with_positive_max_cost_cents_forwards_value(tmp_path) -> None:
    """(b) a positive cap is still forwarded unchanged."""
    cmd = _tick_run_command(tmp_path, max_cost_cents=250)

    assert _FLAG in cmd
    assert cmd[cmd.index(_FLAG) + 1] == '250'


def test_agent_run_explicit_zero_cap_is_still_forwarded() -> None:
    """(c) `agent run` zero cap semantics are untouched: 0 is forwarded as 0."""
    args = argparse.Namespace(
        root='.',
        provider=None,
        model=None,
        route_model=False,
        max_iterations=5,
        max_tool_calls=5,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode='read-only',
        subagent=False,
        heartbeat=0.0,
        code_analysis=False,
        context_profile='lean',
        selected_skills=[],
        max_estimated_cost_cents=0,
    )
    cmd = build_agent_run_command(args, 'summarize')

    assert cmd[cmd.index(_FLAG) + 1] == '0'
