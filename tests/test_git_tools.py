"""Tests for git write-operation tools."""

from __future__ import annotations

import subprocess
from pathlib import Path

from teaagent.types import ToolRegistry
from teaagent.workspace_tools._git import (
    GitToolConfig,
    git_add,
    git_checkout,
    git_commit,
    git_create_branch,
    git_stash,
    register_git_tools,
)


def test_add_all(git_repo_with_config: Path) -> None:
    root = git_repo_with_config
    (root / 'hello.txt').write_text('hello', encoding='utf-8')
    config = GitToolConfig(root=root)
    result = git_add(config, '.')
    assert result['exit_code'] == 0


def test_add_specific_file(git_repo_with_config: Path) -> None:
    root = git_repo_with_config
    (root / 'a.txt').write_text('a', encoding='utf-8')
    (root / 'b.txt').write_text('b', encoding='utf-8')
    config = GitToolConfig(root=root)
    result = git_add(config, 'a.txt')
    assert result['exit_code'] == 0


def test_commit_with_message(git_repo_with_config: Path) -> None:
    root = git_repo_with_config
    (root / 'file.txt').write_text('content', encoding='utf-8')
    config = GitToolConfig(root=root)
    git_add(config, '.')
    result = git_commit(config, 'initial commit')
    assert result['exit_code'] == 0
    assert len(result['commit_sha']) > 0


def test_commit_amend(git_repo_with_config: Path) -> None:
    root = git_repo_with_config
    (root / 'file.txt').write_text('v1', encoding='utf-8')
    config = GitToolConfig(root=root)
    git_add(config, '.')
    git_commit(config, 'first')
    (root / 'file.txt').write_text('v2', encoding='utf-8')
    git_add(config, '.')
    result = git_commit(config, 'amended', amend=True)
    assert result['exit_code'] == 0


def test_create_branch(git_repo_with_commit: Path) -> None:
    root = git_repo_with_commit
    config = GitToolConfig(root=root)
    result = git_create_branch(config, 'feature-x')
    assert result['exit_code'] == 0
    assert result['branch'] == 'feature-x'


def test_create_and_checkout(git_repo_with_commit: Path) -> None:
    root = git_repo_with_commit
    config = GitToolConfig(root=root)
    result = git_create_branch(config, 'feature-y', checkout=True)
    assert result['exit_code'] == 0
    current = subprocess.run(
        ['git', '-C', str(root), 'branch', '--show-current'],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert current == 'feature-y'


def test_checkout_existing_branch(git_repo_with_commit: Path) -> None:
    root = git_repo_with_commit
    config = GitToolConfig(root=root)
    git_create_branch(config, 'dev')
    result = git_checkout(config, 'dev')
    assert result['exit_code'] == 0


def test_checkout_create_new(git_repo_with_commit: Path) -> None:
    root = git_repo_with_commit
    config = GitToolConfig(root=root)
    result = git_checkout(config, 'new-branch', create=True)
    assert result['exit_code'] == 0


def test_stash_and_pop(git_repo_with_commit: Path) -> None:
    root = git_repo_with_commit
    config = GitToolConfig(root=root)
    (root / 'file.txt').write_text('modified', encoding='utf-8')
    result = git_stash(config, message='wip')
    assert result['exit_code'] == 0


def test_register_all_git_tools() -> None:
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
    assert expected.issubset(registered)


def test_git_tools_are_destructive() -> None:
    registry = ToolRegistry()
    config = GitToolConfig(root=Path('.'))
    register_git_tools(registry, config)
    for name in registry.list_tools():
        tool = registry.get(name)
        assert tool.annotations.destructive, f'{name} should be marked destructive'
