# test-type: behavior
"""Batch timeout must bound wall-clock time and label running tasks correctly."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.subagents._tools import register_subagent_tools
from teaagent.types import ToolRegistry
from tests.test_subagent_batch import _make_manager


def test_batch_timeout_is_wall_clock_bounded_and_labels_running_tasks() -> None:
    release = threading.Event()
    # Safety valve: release the blocked worker even if the code under test hangs,
    # so the thread never leaks past this test.
    safety = threading.Timer(5.0, release.set)
    safety.start()

    def fake_run_subagent(**kwargs: object) -> dict:
        if kwargs.get('task') == 'blocker':
            release.wait(timeout=10)
        return {
            'run_id': 'fake',
            'status': 'completed',
            'iterations': 1,
            'tool_calls': 0,
            'final_answer': 'done',
        }

    try:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir(exist_ok=True)
            registry = ToolRegistry()
            manager, adapter = _make_manager(root)
            config = ChatAgentConfig(root=root)

            with patch.object(manager, 'run_subagent', fake_run_subagent):
                register_subagent_tools(
                    registry,
                    adapter=adapter,
                    config=config,
                    depth=0,
                    manager=manager,
                )

                started = time.monotonic()
                result = registry.execute(
                    'subagent_batch',
                    {
                        'tasks': [
                            {'task': 'blocker'},
                            {'task': 'queued'},
                        ],
                        'max_workers': 1,
                        'timeout_seconds': 1,
                    },
                )
                elapsed = time.monotonic() - started
    finally:
        release.set()
        safety.cancel()

    assert elapsed < 3, f'batch took {elapsed:.2f}s; timeout did not bound wall-clock'
    assert result['timed_out'] == 2
    running, queued = result['results']
    assert running['status'] == 'error'
    assert 'while task was running' in running['message']
    assert queued['status'] == 'error'
    assert 'before task started' in queued['message']
