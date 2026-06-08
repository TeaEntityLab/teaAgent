"""Tests for subagent parent-child lineage and batch metadata."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.runner import FinalAnswer, RunResult
from teaagent.subagent_run_context import (
    bind_parent_run_id,
    get_parent_run_id,
    reset_parent_run_id,
)
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.types import ToolRegistry


def _stub_result(run_id: str = 'child-run-1') -> RunResult:
    return RunResult(
        run_id=run_id,
        final_answer=FinalAnswer(content='done'),
        iterations=1,
        tool_calls=0,
        status='completed',
    )


class SubagentLineageTests(unittest.TestCase):
    def test_run_subagent_records_lineage_and_audit(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir()
            config = ChatAgentConfig(root=root, max_iterations=3, max_tool_calls=2)
            adapter = MagicMock()
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=adapter
            )
            with (
                patch(
                    'teaagent.chat_agent.run_chat_agent',
                    return_value=_stub_result('child-abc'),
                ) as run_mock,
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='review files',
                    parent_run_id='parent-xyz',
                    depth=0,
                    def_name=None,
                    max_iterations=2,
                    max_tool_calls=1,
                    batch_index=1,
                )

            run_mock.assert_called_once()
            call_args = run_mock.call_args.args
            # First positional arg is config
            child_config = call_args[0]
            self.assertEqual(
                child_config.max_iterations,
                2,
                'child budget should inherit per-call overrides',
            )
            self.assertEqual(
                child_config.max_tool_calls,
                1,
            )
            # initial_context_extra is passed as keyword arg
            call_kwargs = run_mock.call_args.kwargs
            self.assertEqual(
                call_kwargs['initial_context_extra']['subagent_lineage'][
                    'parent_run_id'
                ],
                'parent-xyz',
            )

            self.assertEqual(payload['run_id'], 'child-abc')
            lineage = payload['lineage']
            self.assertEqual(lineage['parent_run_id'], 'parent-xyz')
            self.assertEqual(lineage['def_name'], 'generic')
            self.assertEqual(lineage['depth'], 1)
            self.assertEqual(lineage.get('batch_index'), 1)
            self.assertEqual(lineage['isolation'], 'shared')

            session = manager._sessions['child-abc']
            self.assertEqual(session.parent_run_id, 'parent-xyz')
            self.assertEqual(session.depth, 1)

    def test_subagent_tool_uses_parent_run_context(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir()
            registry = ToolRegistry()
            config = ChatAgentConfig(root=root)
            adapter = MagicMock()
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=adapter
            )

            captured: dict[str, str] = {}

            def fake_run(**kwargs: object) -> dict:
                captured['parent_run_id'] = str(kwargs.get('parent_run_id', ''))
                return {
                    'run_id': 'child-1',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': 'ok',
                    'lineage': {
                        'parent_run_id': captured['parent_run_id'],
                        'def_name': 'generic',
                        'depth': 1,
                        'isolation': 'shared',
                    },
                    'message': '',
                }

            with patch.object(manager, 'run_subagent', side_effect=fake_run):
                register_subagent_tools(
                    registry,
                    adapter=adapter,
                    config=config,
                    depth=0,
                    manager=manager,
                )
                token = bind_parent_run_id('parent-from-runner')
                try:
                    registry.execute('subagent', {'task': 'child work'})
                finally:
                    reset_parent_run_id(token)

            self.assertEqual(captured['parent_run_id'], 'parent-from-runner')

    def test_subagent_batch_returns_ordered_lineage(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / '.teaagent').mkdir()
            registry = ToolRegistry()
            config = ChatAgentConfig(root=root)
            adapter = MagicMock()
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=adapter
            )

            def fake_run(**kwargs: object) -> dict:
                batch_index = kwargs.get('batch_index')
                return {
                    'run_id': f'run-{batch_index}',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': 'ok',
                    'lineage': {
                        'parent_run_id': kwargs.get('parent_run_id'),
                        'def_name': 'generic',
                        'depth': 1,
                        'isolation': 'shared',
                        'batch_index': batch_index,
                    },
                    'message': '',
                }

            with patch.object(manager, 'run_subagent', side_effect=fake_run):
                register_subagent_tools(
                    registry,
                    adapter=adapter,
                    config=config,
                    depth=0,
                    manager=manager,
                )
                token = bind_parent_run_id('parent-batch')
                try:
                    result = registry.execute(
                        'subagent_batch',
                        {
                            'tasks': [
                                {'task': 'first'},
                                {'task': 'second'},
                            ],
                            'max_workers': 2,
                        },
                    )
                finally:
                    reset_parent_run_id(token)

            self.assertEqual(result['status'], 'completed')
            self.assertEqual(len(result['lineage']), 2)
            self.assertEqual(result['lineage'][0]['batch_index'], 0)
            self.assertEqual(result['lineage'][1]['batch_index'], 1)
            self.assertEqual(result['lineage'][0]['parent_run_id'], 'parent-batch')
            self.assertEqual(result['results'][0]['run_id'], 'run-0')
            self.assertEqual(result['results'][1]['run_id'], 'run-1')

    def test_parent_run_context_default_empty(self) -> None:
        self.assertEqual(get_parent_run_id(), '')


if __name__ == '__main__':
    unittest.main()
