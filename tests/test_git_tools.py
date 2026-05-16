"""Tests for git write-operation tools."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.tools import ToolRegistry
from teaagent.workspace_tools._git import (
    GitToolConfig,
    git_add,
    git_checkout,
    git_commit,
    git_create_branch,
    git_stash,
    register_git_tools,
)


def _init_repo(root: Path) -> None:
    subprocess.run(['git', '-C', str(root), 'init'], check=True, capture_output=True)
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.email', 'test@test.com'],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.name', 'Test'],
        check=True,
        capture_output=True,
    )


class TestGitAdd(unittest.TestCase):
    def test_add_all(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'hello.txt').write_text('hello', encoding='utf-8')
            config = GitToolConfig(root=root)
            result = git_add(config, '.')
            self.assertEqual(result['exit_code'], 0)

    def test_add_specific_file(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'a.txt').write_text('a', encoding='utf-8')
            (root / 'b.txt').write_text('b', encoding='utf-8')
            config = GitToolConfig(root=root)
            result = git_add(config, 'a.txt')
            self.assertEqual(result['exit_code'], 0)


class TestGitCommit(unittest.TestCase):
    def test_commit_with_message(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            result = git_commit(config, 'initial commit')
            self.assertEqual(result['exit_code'], 0)
            self.assertTrue(len(result['commit_sha']) > 0)

    def test_commit_amend(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('v1', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'first')
            (root / 'file.txt').write_text('v2', encoding='utf-8')
            git_add(config, '.')
            result = git_commit(config, 'amended', amend=True)
            self.assertEqual(result['exit_code'], 0)


class TestGitBranch(unittest.TestCase):
    def test_create_branch(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'initial')
            result = git_create_branch(config, 'feature-x')
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(result['branch'], 'feature-x')

    def test_create_and_checkout(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'initial')
            result = git_create_branch(config, 'feature-y', checkout=True)
            self.assertEqual(result['exit_code'], 0)
            current = subprocess.run(
                ['git', '-C', str(root), 'branch', '--show-current'],
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(current, 'feature-y')


class TestGitCheckout(unittest.TestCase):
    def test_checkout_existing_branch(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'initial')
            git_create_branch(config, 'dev')
            result = git_checkout(config, 'dev')
            self.assertEqual(result['exit_code'], 0)

    def test_checkout_create_new(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'initial')
            result = git_checkout(config, 'new-branch', create=True)
            self.assertEqual(result['exit_code'], 0)


class TestGitStash(unittest.TestCase):
    def test_stash_and_pop(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / 'file.txt').write_text('content', encoding='utf-8')
            config = GitToolConfig(root=root)
            git_add(config, '.')
            git_commit(config, 'initial')
            (root / 'file.txt').write_text('modified', encoding='utf-8')
            result = git_stash(config, message='wip')
            self.assertEqual(result['exit_code'], 0)
            result = git_stash(config, pop=True)
            self.assertEqual(result['exit_code'], 0)


class TestGitToolsRegistration(unittest.TestCase):
    def test_register_all_git_tools(self) -> None:
        registry = ToolRegistry()
        config = GitToolConfig(root=Path('.'))
        register_git_tools(registry, config)
        expected = {
            'git_add',
            'git_commit',
            'git_create_branch',
            'git_checkout',
            'git_push',
            'git_pull',
            'git_stash',
        }
        registered = set(registry.list_tools())
        self.assertTrue(expected.issubset(registered))

    def test_git_tools_are_destructive(self) -> None:
        registry = ToolRegistry()
        config = GitToolConfig(root=Path('.'))
        register_git_tools(registry, config)
        for name in registry.list_tools():
            tool = registry.get(name)
            self.assertTrue(
                tool.annotations.destructive,
                f'{name} should be marked destructive',
            )


if __name__ == '__main__':
    unittest.main()
