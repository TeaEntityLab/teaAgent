from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import FakeAdapter

from teaagent import ChatAgentConfig
from teaagent.cli import main
from teaagent.policy import PermissionMode
from teaagent.subagents import SubagentManager
from teaagent.tools import ToolRegistry
from teaagent.tui import TeaAgentTUI


class RealUsageScenariosTests(unittest.TestCase):
    def test_subagent_permission_capping_safety(self) -> None:
        """Verify that child agents never inherit allow/danger-full-access from parent and get capped at workspace-write."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)

            # Setup a parent config with an unsafe permission mode
            parent_config = ChatAgentConfig(
                root=root,
                permission_mode='danger-full-access',
                max_iterations=5,
                max_tool_calls=5,
                max_subagent_depth=2,
            )

            parent_adapter = MagicMock()
            parent_adapter.provider = 'fake'

            manager = SubagentManager(
                root=root,
                parent_config=parent_config,
                parent_adapter=parent_adapter,
            )

            registry = ToolRegistry()
            manager.bind_registry(registry)

            # Mock run_chat_agent to capture the sub_config passed to the child
            captured_sub_config = None

            def fake_run_chat_agent(config, *args, **kwargs):
                nonlocal captured_sub_config
                captured_sub_config = config
                mock_result = MagicMock()
                mock_result.status = 'completed'
                mock_result.run_id = 'child-run-id'
                mock_result.iterations = 1
                mock_result.tool_calls = 0
                mock_result.cost_cents = 0.0
                mock_result.final_answer = MagicMock(content='child answer')
                mock_result.metadata = {}
                return mock_result

            with patch('teaagent.chat_agent.run_chat_agent', fake_run_chat_agent):
                res = manager.run_subagent(
                    task='do child task',
                    parent_run_id='parent-run-id',
                    depth=0,
                    isolation='shared',
                )

                self.assertEqual(res['status'], 'completed')
                self.assertIsNotNone(captured_sub_config)
                # Verify permission mode of the subagent is capped at workspace-write
                self.assertEqual(captured_sub_config.permission_mode, 'workspace-write')

    def test_subagent_batch_concurrency_and_cancellation(self) -> None:
        """Verify batch execution returns a partial status on child tasks failing or raising errors."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)

            parent_config = ChatAgentConfig(root=root)
            parent_adapter = MagicMock()
            parent_adapter.provider = 'fake'

            manager = SubagentManager(
                root=root,
                parent_config=parent_config,
                parent_adapter=parent_adapter,
            )

            registry = ToolRegistry()
            from teaagent.subagents._tools import register_subagent_tools

            register_subagent_tools(
                registry,
                adapter=parent_adapter,
                config=parent_config,
                depth=0,
                manager=manager,
            )

            # Mock run_subagent to simulate success for task1 and failure for task2
            def fake_run_subagent(**kwargs):
                task = kwargs.get('task', '')
                if 'fail' in task:
                    raise RuntimeError('Simulated task error')
                return {
                    'run_id': 'child-run',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': f'completed {task}',
                }

            with patch.object(manager, 'run_subagent', fake_run_subagent):
                res = registry.execute(
                    'subagent_batch',
                    {
                        'tasks': [
                            {'task': 'task1', 'isolation': 'shared'},
                            {'task': 'fail_task', 'isolation': 'shared'},
                        ],
                        'max_workers': 2,
                    },
                )

                self.assertEqual(res['status'], 'partial')
                self.assertEqual(res['total'], 2)
                self.assertEqual(res['completed'], 1)
                self.assertEqual(res['results'][0]['status'], 'completed')
                self.assertEqual(res['results'][1]['status'], 'error')
                self.assertIn('Simulated task error', res['results'][1]['message'])

    def test_tui_interactive_approval_denial_flow(self) -> None:
        """Verify TUI interactive prompt blocks execution upon denial and records pending approval."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            replies = iter(['no'])  # Deny approval

            # Setup a fake adapter that requests a destructive tool call
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"file.txt","content":"data"},"call_id":"write-1"}'
                ]
            )

            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: next(replies),
                output_fn=output.append,
                adapter_factory=lambda _p, _m: adapter,
                permission_mode=PermissionMode.PROMPT,
                allow_destructive=False,
            )

            # Ask the agent to write a file
            self.assertTrue(tui.handle_command('ask write to file.txt'))

            # Check the final output payload
            payload = json.loads(output[-1])
            self.assertEqual(payload['status'], 'pending_approval')
            # Verify file was not written
            self.assertFalse((Path(tmp) / 'file.txt').exists())

    @classmethod
    def _opencodezen_api_key(cls) -> str | None:
        key = os.environ.get('OPENCODEZEN_API_KEY')
        if key:
            return key
        env_file = Path.cwd() / '.teaagent' / 'env'
        if env_file.is_file():
            for line in env_file.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('export OPENCODEZEN_API_KEY='):
                    val = line.split('=', 1)[1].strip()
                    return val.strip('"').strip("'")
        return None

    def _env_for_opencodezen(self) -> dict[str, str]:
        return {'OPENCODEZEN_API_KEY': self._opencodezen_api_key() or ''}

    def test_live_model_smoke_opencodezen_go(self) -> None:
        """Live smoke test using the actual opencodezen-go model if key is present in environment."""
        api_key = self._opencodezen_api_key()
        if not api_key:
            self.skipTest('OPENCODEZEN_API_KEY not found; skipping live smoke test')

        with patch.dict(os.environ, self._env_for_opencodezen()):
            # Run model smoke command via main CLI entrypoint
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'model',
                        'smoke',
                        'opencodezen-go',
                        '--model',
                        'deepseek-v4-flash',
                        '--prompt',
                        'Reply with exactly: ok',
                    ]
                )

            self.assertEqual(exit_code, 0)
            res_str = out.getvalue().strip()
            res = json.loads(res_str)
            self.assertEqual(res['provider'], 'opencodezen-go')
            self.assertEqual(res['model'], 'deepseek-v4-flash')
            self.assertIn('ok', res['content'].lower())


if __name__ == '__main__':
    unittest.main()
