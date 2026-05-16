"""Tests for parallel subagent batch execution."""

from __future__ import annotations

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.tools import ToolRegistry


def _make_manager(root: Path) -> tuple[SubagentManager, MagicMock]:
    config = ChatAgentConfig(root=root)
    adapter = MagicMock()
    adapter.provider = 'fake'
    adapter.complete = MagicMock(
        return_value=MagicMock(
            content='{"type":"final","content":"done"}',
            input_tokens=0,
            output_tokens=0,
            tool_calls=[],
        )
    )
    manager = SubagentManager(root=root, parent_config=config, parent_adapter=adapter)
    return manager, adapter


class TestSubagentBatch(unittest.TestCase):
    def test_batch_tool_is_registered(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir(exist_ok=True)
            registry = ToolRegistry()
            manager, adapter = _make_manager(root)
            config = ChatAgentConfig(root=root)
            register_subagent_tools(
                registry,
                adapter=adapter,
                config=config,
                depth=0,
                manager=manager,
            )
            names = registry.list_tools()
            self.assertIn('subagent_batch', names)

    def test_batch_runs_tasks_concurrently(self) -> None:
        """Verify that batch tasks run in parallel, not sequentially."""
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir(exist_ok=True)
            registry = ToolRegistry()
            manager, adapter = _make_manager(root)
            config = ChatAgentConfig(root=root)

            call_times: list[float] = []

            def fake_run_subagent(**kwargs: object) -> dict:
                call_times.append(time.monotonic())
                time.sleep(0.1)  # simulate work
                return {
                    'run_id': 'fake',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': 'done',
                }

            with patch.object(manager, 'run_subagent', fake_run_subagent):
                register_subagent_tools(
                    registry,
                    adapter=adapter,
                    config=config,
                    depth=0,
                    manager=manager,
                )

                result = registry.execute(
                    'subagent_batch',
                    {
                        'tasks': [
                            {'task': 'task 1'},
                            {'task': 'task 2'},
                            {'task': 'task 3'},
                        ],
                        'max_workers': 3,
                    },
                )

            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['total'], 3)
            self.assertEqual(result['completed'], 3)
            # If tasks ran in parallel, all start times should be within ~50ms
            if len(call_times) >= 2:
                spread = max(call_times) - min(call_times)
                self.assertLess(
                    spread,
                    0.2,
                    f'Tasks did not run in parallel (spread={spread:.3f}s)',
                )

    def test_batch_returns_error_for_empty_tasks(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir(exist_ok=True)
            registry = ToolRegistry()
            manager, adapter = _make_manager(root)
            config = ChatAgentConfig(root=root)
            register_subagent_tools(
                registry,
                adapter=adapter,
                config=config,
                depth=0,
                manager=manager,
            )
            result = registry.execute('subagent_batch', {'tasks': []})
            self.assertEqual(result['status'], 'error')

    def test_batch_handles_task_failure(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir(exist_ok=True)
            registry = ToolRegistry()
            manager, adapter = _make_manager(root)
            config = ChatAgentConfig(root=root)

            def fake_run_subagent(**kwargs: object) -> dict:
                task = kwargs.get('task', '')
                if task == 'fail':
                    raise RuntimeError('simulated failure')
                return {
                    'run_id': 'fake',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': 'ok',
                }

            with patch.object(manager, 'run_subagent', fake_run_subagent):
                register_subagent_tools(
                    registry,
                    adapter=adapter,
                    config=config,
                    depth=0,
                    manager=manager,
                )

                result = registry.execute(
                    'subagent_batch',
                    {
                        'tasks': [
                            {'task': 'ok'},
                            {'task': 'fail'},
                            {'task': 'ok'},
                        ],
                        'max_workers': 3,
                    },
                )

            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['total'], 3)
            self.assertEqual(result['completed'], 2)
            self.assertEqual(result['results'][1]['status'], 'error')


if __name__ == '__main__':
    unittest.main()
