"""Tests for interactive intent clarification (U-P1-1).

Verifies that --clarify triggers interactive prompting when needs_clarification
is true, and that --clarify-json preserves the machine-readable JSON output.
"""

from __future__ import annotations

import json
import tempfile
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.cli import build_parser, main
from teaagent.intent import clarify_task


def test_clarify_task_high_ambiguity_needs_clarification() -> None:
    """A vague task should trigger needs_clarification."""
    result = clarify_task('improve stuff')
    assert result.needs_clarification
    assert result.question is not None


def test_clarify_task_low_ambiguity_no_clarification() -> None:
    """A specific task should not need clarification."""
    result = clarify_task('fix the failing auth tests in tests/test_auth.py')
    assert not result.needs_clarification


def test_clarify_command_interactive_prompts(
    capsys: pytest.CaptureFixture,
) -> None:
    """clarify command should prompt interactively when stdin is a TTY."""
    parser = build_parser()
    args = parser.parse_args(['clarify', 'improve stuff'])

    # Simulate TTY stdin and provide an answer
    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', side_effect=['make the code faster', '']),
    ):
        from teaagent.cli._handlers._misc import clarify_command

        exit_code = clarify_command(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    # Should have printed the clarification result as JSON
    output = json.loads(captured.out)
    assert 'task' in output
    assert 'ambiguity' in output


def test_clarify_command_non_tty_exits_with_json(
    capsys: pytest.CaptureFixture,
) -> None:
    """clarify command in non-TTY should just print JSON without prompting."""
    parser = build_parser()
    args = parser.parse_args(['clarify', 'improve stuff'])

    with patch('sys.stdin.isatty', return_value=False):
        from teaagent.cli._handlers._misc import clarify_command

        exit_code = clarify_command(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output['needs_clarification'] is True


def test_clarify_command_clarify_json_skips_interactive(
    capsys: pytest.CaptureFixture,
) -> None:
    """clarify command with clarify_json should skip interactive prompting."""
    parser = build_parser()
    args = parser.parse_args(['clarify', 'improve stuff'])
    args.clarify_json = True

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', side_effect=['should not be called']),
    ):
        from teaagent.cli._handlers._misc import clarify_command

        exit_code = clarify_command(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output['needs_clarification'] is True


def test_agent_run_clarify_non_tty_returns_json_exit_2(
    capsys: pytest.CaptureFixture,
) -> None:
    """agent run --clarify in non-TTY should print JSON and exit 2."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            patch('sys.stdin.isatty', return_value=False),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'improve stuff',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                    '--clarify',
                ],
            )
    assert exit_code == 2
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output['status'] == 'needs_clarification'
    assert 'clarification' in output


def test_agent_run_clarify_interactive_prompts_and_proceeds(
    capsys: pytest.CaptureFixture,
) -> None:
    """agent run --clarify in TTY should prompt, accept answer, and proceed."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            patch('sys.stdin.isatty', return_value=True),
            patch('builtins.input', side_effect=['make it faster in src/', '']),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'improve stuff',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                    '--clarify',
                ],
            )
    # Should not exit 2 — should proceed to run
    assert exit_code != 2


def test_agent_run_clarify_json_skips_interactive(
    capsys: pytest.CaptureFixture,
) -> None:
    """agent run --clarify with clarify_json should skip interactive mode."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        # Manually set clarify_json since the parser flag doesn't exist yet
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            patch('sys.stdin.isatty', return_value=True),
            patch('builtins.input', side_effect=['should not be called']),
            patch(
                'teaagent.cli._handlers._agent.run.getattr',
                side_effect=lambda obj, name, default: (
                    True if name == 'clarify_json' else getattr(obj, name, default)
                ),
            ),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'improve stuff',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                    '--clarify',
                ],
            )
    assert exit_code == 2
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output['status'] == 'needs_clarification'
