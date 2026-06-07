"""Tests for WS2-001/003/004 subagent isolation and policy guards."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.subagents import SubagentManager
from teaagent.subagents._isolation import (
    DEFAULT_SUBAGENT_ISOLATION,
    resolve_subagent_isolation,
)


def _init_git_repo(root: Path) -> None:
    subprocess.run(
        ['git', 'init', '--template='], cwd=root, check=True, capture_output=True
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
        ['git', 'commit', '-m', 'init'], cwd=root, check=True, capture_output=True
    )


class SubagentIsolationPolicyTests(unittest.TestCase):
    def test_resolve_defaults_to_worktree_on_git_repo(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            assert resolve_subagent_isolation(None, root=root) == 'worktree'

    def test_resolve_requires_explicit_shared_on_git_repo(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            assert (
                resolve_subagent_isolation('shared', root=root)
                == DEFAULT_SUBAGENT_ISOLATION
            )

    def test_resolve_falls_back_to_shared_without_git(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert resolve_subagent_isolation(None, root=root) == 'shared'

    def test_manager_enforces_global_depth_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            config = ChatAgentConfig(root=root, max_subagent_depth=1)
            manager = SubagentManager(
                root=root,
                parent_config=config,
                parent_adapter=MagicMock(),
            )
            result = manager.run_subagent(
                task='too deep',
                parent_run_id='parent-1',
                depth=1,
                isolation='shared',
            )
            self.assertEqual(result['status'], 'error')
            self.assertIn('global subagent depth', result['message'])

    def test_manager_caps_child_budget_to_parent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            config = ChatAgentConfig(
                root=root,
                max_iterations=3,
                max_tool_calls=4,
                max_subagent_depth=2,
            )
            manager = SubagentManager(
                root=root,
                parent_config=config,
                parent_adapter=MagicMock(),
            )
            captured: dict[str, int] = {}

            def fake_run_chat_agent(cfg, *args, **kwargs):
                captured['max_iterations'] = cfg.max_iterations
                captured['max_tool_calls'] = cfg.max_tool_calls
                from teaagent.runner import FinalAnswer, RunResult

                return RunResult(
                    run_id='child-1',
                    final_answer=FinalAnswer(content='ok'),
                    iterations=1,
                    tool_calls=0,
                    status='completed',
                )

            with patch('teaagent.chat_agent.run_chat_agent', fake_run_chat_agent):
                manager.run_subagent(
                    task='cap me',
                    parent_run_id='parent-1',
                    depth=0,
                    max_iterations=99,
                    max_tool_calls=99,
                    isolation='shared',
                )

            self.assertEqual(captured['max_iterations'], 3)
            self.assertEqual(captured['max_tool_calls'], 4)


if __name__ == '__main__':
    unittest.main()
