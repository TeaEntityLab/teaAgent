"""Parallel subagents in worktrees report lineage for parent review before merge."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli import main
from teaagent.runner import FinalAnswer, RunResult
from teaagent.subagent_run_context import bind_parent_run_id, reset_parent_run_id
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.tools import ToolRegistry


class SubagentParallelWorktreeMergeFlowTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> None:
        subprocess.run(['git', 'init'], cwd=root, check=True, capture_output=True)
        (root / 'README.md').write_text('# demo\n', encoding='utf-8')
        subprocess.run(
            ['git', 'add', 'README.md'], cwd=root, check=True, capture_output=True
        )
        env = {
            'GIT_AUTHOR_NAME': 'test',
            'GIT_AUTHOR_EMAIL': 'test@test.com',
            'GIT_COMMITTER_NAME': 'test',
            'GIT_COMMITTER_EMAIL': 'test@test.com',
        }
        subprocess.run(
            ['git', 'commit', '-m', 'init'],
            cwd=root,
            check=True,
            capture_output=True,
            env=env,
        )

    def test_parallel_worktree_children_expose_lineage_for_parent_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / '.teaagent').mkdir()
            registry = ToolRegistry()
            config = ChatAgentConfig(root=root, enable_subagent=True)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            worktrees = [
                '.teaagent/subagent-worktrees/alpha',
                '.teaagent/subagent-worktrees/beta',
            ]
            call_index = {'n': 0}

            def fake_run(**kwargs: object) -> dict[str, object]:
                idx = call_index['n']
                call_index['n'] += 1
                wt = worktrees[idx % len(worktrees)]
                return {
                    'run_id': f'child-{idx}',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': f'patched via {wt}',
                    'lineage': {
                        'parent_run_id': str(kwargs.get('parent_run_id', '')),
                        'def_name': 'generic',
                        'depth': 1,
                        'isolation': 'worktree',
                        'worktree_path': wt,
                    },
                    'message': 'ready for parent review',
                }

            with patch.object(manager, 'run_subagent', side_effect=fake_run):
                register_subagent_tools(
                    registry,
                    adapter=MagicMock(),
                    config=config,
                    depth=0,
                    manager=manager,
                )
                token = bind_parent_run_id('parent-merge')
                try:
                    first = registry.execute(
                        'subagent',
                        {'task': 'edit docs in worktree A', 'isolation': 'worktree'},
                    )
                    second = registry.execute(
                        'subagent',
                        {'task': 'edit tests in worktree B', 'isolation': 'worktree'},
                    )
                finally:
                    reset_parent_run_id(token)

            for result, expected_wt in zip((first, second), worktrees, strict=True):
                self.assertEqual(result['lineage']['isolation'], 'worktree')
                self.assertEqual(result['lineage']['worktree_path'], expected_wt)
                self.assertEqual(result['lineage']['parent_run_id'], 'parent-merge')
                self.assertIn('parent review', result['message'])

    def test_worktree_child_review_patch_can_be_checked_and_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            config = ChatAgentConfig(root=root, enable_subagent=True)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )

            def fake_child_run(
                config, task, adapter, audit, *args, **kwargs
            ) -> RunResult:
                child_root = config.root
                (child_root / 'feature.txt').write_text(
                    'child worktree change\n', encoding='utf-8'
                )
                return RunResult(
                    run_id='child-review',
                    final_answer=FinalAnswer('ready for review'),
                    iterations=1,
                    tool_calls=0,
                    status='completed',
                )

            with patch(
                'teaagent.chat_agent.run_chat_agent', side_effect=fake_child_run
            ):
                result = manager.run_subagent(
                    task='write feature summary',
                    parent_run_id='parent-review',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['review']['review_id'], 'child-review')
            self.assertIn('feature.txt', result['review']['changed_files'])
            self.assertTrue((root / result['review']['patch_path']).is_file())
            self.assertFalse((root / result['lineage']['worktree_path']).exists())

            check_code = main(
                [
                    'agent',
                    'subagent-review',
                    'check',
                    'child-review',
                    '--parent-run-id',
                    'parent-review',
                    '--root',
                    str(root),
                ]
            )
            self.assertEqual(check_code, 0)
            apply_code = main(
                [
                    'agent',
                    'subagent-review',
                    'apply',
                    'child-review',
                    '--parent-run-id',
                    'parent-review',
                    '--root',
                    str(root),
                ]
            )
            self.assertEqual(apply_code, 0)
            self.assertEqual(
                (root / 'feature.txt').read_text(encoding='utf-8'),
                'child worktree change\n',
            )


if __name__ == '__main__':
    unittest.main()
