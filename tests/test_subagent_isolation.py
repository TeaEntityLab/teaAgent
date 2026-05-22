"""Tests for subagent workspace isolation (shared vs worktree)."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.runner import FinalAnswer, RunResult
from teaagent.subagents import SubagentManager
from teaagent.subagents._isolation import (
    IsolationContext,
    normalize_subagent_isolation,
    prepare_subagent_isolation,
)


def _init_git_repo(root: Path) -> None:
    subprocess.run(
        ['git', 'init', '--template='],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'TeaAgent Test'],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / 'README.md').write_text('hello', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=root, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'init'],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _stub_result(run_id: str = 'child-run-1') -> RunResult:
    return RunResult(
        run_id=run_id,
        final_answer=FinalAnswer(content='done'),
        iterations=1,
        tool_calls=0,
        status='completed',
    )


class SubagentIsolationTests(unittest.TestCase):
    def test_normalize_subagent_isolation_defaults_and_rejects_unknown(self) -> None:
        self.assertEqual(normalize_subagent_isolation(None), 'shared')
        self.assertEqual(normalize_subagent_isolation('worktree'), 'worktree')
        self.assertIsNone(normalize_subagent_isolation('container'))
        self.assertIsNone(normalize_subagent_isolation('invalid'))

    def test_prepare_worktree_requires_git_repository(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx, error = prepare_subagent_isolation(
                root, isolation='worktree', session_key='child-1'
            )
            self.assertIsNone(ctx)
            self.assertIn('git repository', error)

    def test_prepare_worktree_creates_and_cleans_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                _init_git_repo(root)
            except subprocess.CalledProcessError:
                self.skipTest('git unavailable in this environment')
            ctx, error = prepare_subagent_isolation(
                root, isolation='worktree', session_key='child-1'
            )
            if error:
                self.skipTest(error)
            assert ctx is not None
            self.assertTrue(ctx.worktree_path is not None)
            self.assertTrue(ctx.child_root.is_dir())
            marker = ctx.child_root / 'README.md'
            self.assertTrue(marker.is_file())
            ctx.cleanup()
            self.assertFalse(ctx.worktree_path.exists())

    def test_run_subagent_worktree_uses_isolated_root(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            worktree = root / '.teaagent' / 'subagent-worktrees' / 'child-1'
            worktree.mkdir(parents=True)
            config = ChatAgentConfig(root=root)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
            )
            captured: dict[str, Path] = {}
            iso_ctx = IsolationContext(
                parent_root=root,
                child_root=worktree,
                isolation='worktree',
                worktree_path=worktree,
            )

            def capture_run(**kwargs: object) -> RunResult:
                cfg = kwargs['config']
                captured['child_root'] = cfg.root  # type: ignore[attr-defined]
                return _stub_result('child-wt')

            with (
                patch(
                    'teaagent.subagents._manager.prepare_subagent_isolation',
                    return_value=(iso_ctx, ''),
                ),
                patch('teaagent.chat_agent.run_chat_agent', side_effect=capture_run),
                patch('teaagent.run_store.RunStore.logger_for_result'),
            ):
                payload = manager.run_subagent(
                    task='inspect README',
                    parent_run_id='parent-1',
                    depth=0,
                    isolation='worktree',
                )

            self.assertEqual(payload['status'], 'completed')
            self.assertEqual(payload['lineage']['isolation'], 'worktree')
            self.assertIn('worktree_path', payload['lineage'])
            self.assertEqual(captured['child_root'].resolve(), worktree.resolve())


if __name__ == '__main__':
    unittest.main()
