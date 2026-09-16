# test-type: behavior
"""Pin dogfood finding G26 (R3): scratchpad metadata must not masquerade as a run.

`runs list`, `session list`, and the `agent_status` run-list handler used to
append a ``{'scratchpad_last_goal': ...}`` pseudo-entry inside the run array, so
consumers iterating the array received a non-run element with no ``run_id`` /
``status`` — a schema-breaking output contract bug. The scratchpad goal must be
surfaced only in human/TTY rendering, never inside the machine-readable array.
"""

from __future__ import annotations

import argparse
import io
import json
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from teaagent.cli._handlers._agent.runs import agent_runs_list
from teaagent.cli._handlers._ergonomics.session import session_list_command
from teaagent.cli._handlers.agent_status import agent_runs_list as status_runs_list
from teaagent.run_store import RunResult, RunStore
from teaagent.scratchpad import Scratchpad

_GOAL = 'ship the G26 fix'

_HANDLERS = (
    ('runs_list', agent_runs_list),
    ('session_list', session_list_command),
    ('agent_status_runs', status_runs_list),
)


class _TTYStringIO(io.StringIO):
    """StringIO that reports itself as an interactive terminal."""

    def isatty(self) -> bool:
        """Force the TTY/human-rendering branch of the output helpers."""
        return True


def _seed(root: Path) -> None:
    store = RunStore(root)
    audit = store.audit_logger('run-g26')
    audit.record('run_started', 'run-g26', task='demo')
    store.logger_for_result(
        RunResult(
            run_id='run-g26',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    Scratchpad(root).write(goal=_GOAL, progress='', open_questions=[], next_step='')


@pytest.mark.parametrize('label,handler', _HANDLERS)
def test_run_array_excludes_scratchpad_pseudo_entry(
    tmp_path: Path, label: str, handler: Callable[[argparse.Namespace], int]
) -> None:
    # Falsifier: fails if any run-array element lacks run_id or carries the
    # scratchpad pseudo-entry (the pre-change ``payload.append({...})`` behavior).
    _seed(tmp_path)
    args = argparse.Namespace(root=str(tmp_path), limit=20)
    buf = io.StringIO()  # non-TTY -> raw JSON document
    with redirect_stdout(buf):
        assert handler(args) == 0
    payload = json.loads(buf.getvalue())
    assert isinstance(payload, list)
    assert payload, f'{label}: expected at least one run record'
    for element in payload:
        assert 'run_id' in element, f'{label}: element missing run_id: {element}'
        assert 'scratchpad_last_goal' not in element, (
            f'{label}: scratchpad pseudo-entry leaked into run array'
        )


@pytest.mark.parametrize('label,handler', _HANDLERS)
def test_scratchpad_goal_surfaced_in_human_rendering(
    tmp_path: Path, label: str, handler: Callable[[argparse.Namespace], int]
) -> None:
    # Falsifier: fails if the scratchpad goal is dropped entirely instead of
    # relocated to the human/TTY rendering.
    _seed(tmp_path)
    args = argparse.Namespace(root=str(tmp_path), limit=20)
    buf = _TTYStringIO()  # TTY -> human rendering branch
    with redirect_stdout(buf):
        assert handler(args) == 0
    assert _GOAL in buf.getvalue(), (
        f'{label}: scratchpad goal not surfaced in human output'
    )
