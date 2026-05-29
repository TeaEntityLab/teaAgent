"""Tests for tournament parallel executor and subagent manager wiring."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

from teaagent.subagents._approval_queue import get_approval_queue
from teaagent.tournament.parallel_executor import ParallelExecutor
from teaagent.tui._approval_subagents import format_subagent_approval_batch


def test_parallel_executor_routes_through_subagent_manager(tmp_path: Path) -> None:
    manager = MagicMock()
    manager.run_subagent.return_value = {
        'status': 'completed',
        'run_id': 'child-run',
        'final_answer': 'done',
    }
    executor = ParallelExecutor(
        tmp_path, subagent_manager=manager, parent_run_id='parent-tournament'
    )
    results = executor.execute_parallel(
        'optimize query',
        ['tournament-opt1'],
        ['use indexes'],
    )
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].metadata['execution'] == 'subagent_manager'
    assert results[0].metadata['parent_run_id'] == 'parent-tournament'
    manager.run_subagent.assert_called_once()
    call = manager.run_subagent.call_args.kwargs
    assert call['parent_run_id'] == 'parent-tournament'
    assert call['batch_index'] == 0
    assert call['isolation'] == 'worktree'


def test_parallel_executor_parallel_batch_indexes(tmp_path: Path) -> None:
    manager = MagicMock()
    manager.run_subagent.return_value = {'status': 'completed', 'run_id': 'x'}
    executor = ParallelExecutor(tmp_path, subagent_manager=manager)
    executor.execute_parallel(
        'task',
        ['branch-a', 'branch-b'],
        ['hint-a', 'hint-b'],
        parent_run_id='parent-batch',
    )
    assert manager.run_subagent.call_count == 2
    indexes = [
        call.kwargs['batch_index'] for call in manager.run_subagent.call_args_list
    ]
    assert sorted(indexes) == [0, 1]


def test_format_subagent_approval_batch_with_pending() -> None:
    queue = get_approval_queue('parent-fmt')
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            queue.submit_request_sync(
                subagent_id='sub-1',
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'a.py'},
                permission_mode='workspace-write',
                isolation='worktree',
                batch_index=2,
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    text = ''
    for _ in range(30):
        text, payload = format_subagent_approval_batch(parent_run_id='parent-fmt')
        if payload['count'] == 1:
            queue.approve_request_sync(payload['pending'][0]['request_id'])
            break
        thread.join(timeout=0.05)

    thread.join(timeout=2)
    assert 'workspace_write_file' in text
    assert payload['count'] == 1
    assert results == [True]
