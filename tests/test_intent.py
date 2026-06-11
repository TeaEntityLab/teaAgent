from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.intent import build_task_spec, clarify_task


def test_clarify_task_flags_vague_task() -> None:
    result = clarify_task('improve stuff')

    assert result.needs_clarification
    assert result.question == 'What action do you want TeaAgent to take?'
    assert 'intent' in result.missing


def test_clarify_task_accepts_concrete_task() -> None:
    result = clarify_task(
        'Update docs/cli.md to document clarify command without changing APIs and verify tests pass'
    )

    assert not result.needs_clarification
    assert result.question is None


def test_build_task_spec_includes_missing_fields() -> None:
    clarification = clarify_task('fix tests')

    spec = build_task_spec('fix tests', clarification)

    assert 'Clarified task specification' in spec
    assert 'TASK: fix tests' in spec
    assert 'MISSING:' in spec


def test_cli_clarify_outputs_json() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['clarify', 'improve stuff'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['needs_clarification']
    assert payload['question'] == 'What action do you want TeaAgent to take?'


def test_cli_agent_run_clarify_stops_before_model_when_ambiguous() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['agent', 'run', 'gpt', 'improve stuff', '--clarify'])

    payload = json.loads(output.getvalue())
    assert exit_code == 2
    assert payload['status'] == 'needs_clarification'
    assert payload['clarification']['needs_clarification']
