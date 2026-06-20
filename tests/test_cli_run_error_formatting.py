"""Tests for CLI agent run error formatting (U-P1-2).

Verifies that task-resolution, plan-gate, and background error paths route
through format_error_block with hints instead of raw JSON on stdout.
"""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.cli import main


def test_task_resolution_error_uses_format_error_block(
    capsys: pytest.CaptureFixture,
) -> None:
    """When task resolution fails, error goes to stderr via format_error_block."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            patch(
                'teaagent.cli._handlers._agent.run._resolve_run_task',
                side_effect=ValueError('task or --from-plan is required'),
            ),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ],
            )
    assert exit_code == 1
    captured = capsys.readouterr()
    # Error should be on stderr, not stdout
    assert captured.out.strip() == ''
    assert 'task or --from-plan is required' in captured.err
    # Should include a hint about provider/task order
    assert 'provider' in captured.err.lower()


def test_plan_gate_error_uses_format_error_block(capsys: pytest.CaptureFixture) -> None:
    """When plan gate blocks, error goes to stderr via format_error_block."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'some task',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'workspace-write',
                    '--require-plan',
                ],
            )
    assert exit_code == 2
    captured = capsys.readouterr()
    # Error should be on stderr, not stdout
    assert captured.out.strip() == ''
    assert 'plan' in captured.err.lower()
    assert 'PLAN_GATE' in captured.err


def test_background_run_id_error_uses_format_error_block(
    capsys: pytest.CaptureFixture,
) -> None:
    """When --background gets a run id, error goes to stderr via format_error_block."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a fake run file so the background handler detects it
        from pathlib import Path

        from teaagent.run_store import RunStore

        store = RunStore(Path(tmp))
        run_id = 'test-run-123'
        # Write a minimal run file
        run_path = store.run_path(run_id)
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text('{"run_id": "test-run-123"}', encoding='utf-8')

        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    run_id,
                    '--root',
                    tmp,
                    '--background',
                    '--permission-mode',
                    'read-only',
                ],
            )
    assert exit_code == 2
    captured = capsys.readouterr()
    # Error should be on stderr, not stdout
    assert captured.out.strip() == ''
    assert 'run id' in captured.err.lower() or 'existing run' in captured.err.lower()
    assert 'BACKGROUND' in captured.err


def test_error_block_includes_hint(capsys: pytest.CaptureFixture) -> None:
    """format_error_block output includes a hint line with arrow."""
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            patch(
                'teaagent.cli._handlers._agent.run._resolve_run_task',
                side_effect=ValueError('task or --from-plan is required'),
            ),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ],
            )
    assert exit_code == 1
    captured = capsys.readouterr()
    # The hint should mention provider coming first
    assert 'provider comes first' in captured.err.lower() or 'Usage:' in captured.err
