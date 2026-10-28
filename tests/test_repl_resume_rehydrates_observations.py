# test-type: lifecycle
"""TICKET-16 Phase 2: a REPL suspension rehydrates its observations on resume."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli._handlers._agent.resume import (
    agent_resume_command,
    suspend_to_background,
)
from teaagent.runner._types import FinalAnswer, RunResult


def _repl_observations(count: int) -> list[dict[str, Any]]:
    """Observations shaped as ``ChatSessionController`` records them after each run."""
    return [
        {
            'task': f'task {index}',
            'result': RunResult(
                run_id=f'run-{index}',
                final_answer=FinalAnswer(f'answer {index}'),
                iterations=1,
                tool_calls=1,
                status='completed',
            ),
            'cost_cents': 1.5,
        }
        for index in range(count)
    ]


def _git_init(root: Path) -> None:
    subprocess.run(['git', 'init'], cwd=root, capture_output=True)


def _resume_and_capture(root: Path, run_id: str, monkeypatch: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_execute(args: argparse.Namespace, task: str, **kwargs: Any) -> int:
        captured['task'] = task
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        'teaagent.cli._handlers._agent.resume._execute_agent_task', fake_execute
    )
    args = argparse.Namespace(
        run_id=run_id,
        root=str(root),
        fresh_restart=False,
        approve_call_id=[],
        provider='mock-provider',
        model='mock-model',
        auto_compact=None,
    )
    assert agent_resume_command(args) == 0
    return captured


def test_repl_suspend_resume_roundtrip(tmp_path: Path, monkeypatch: Any) -> None:
    _git_init(tmp_path)
    config = ChatAgentConfig.from_root(tmp_path)

    run_id = suspend_to_background(
        config,
        {'observations': _repl_observations(3), 'compaction_count': 0},
        set(),
        output=lambda _message: None,
    )
    assert run_id

    captured = _resume_and_capture(tmp_path, run_id, monkeypatch)

    assert captured['task'] == 'task 2'
    restored = captured['initial_observations']
    assert [obs['task'] for obs in restored] == ['task 0', 'task 1', 'task 2']
    assert [obs['result']['answer'] for obs in restored] == [
        'answer 0',
        'answer 1',
        'answer 2',
    ]


def test_repl_resume_restores_last_ten_observations(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _git_init(tmp_path)
    config = ChatAgentConfig.from_root(tmp_path)

    run_id = suspend_to_background(
        config,
        {'observations': _repl_observations(12), 'compaction_count': 0},
        set(),
        output=lambda _message: None,
    )
    assert run_id

    captured = _resume_and_capture(tmp_path, run_id, monkeypatch)

    restored_tasks = [obs['task'] for obs in captured['initial_observations']]
    assert restored_tasks == [f'task {index}' for index in range(2, 12)]
