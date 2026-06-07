from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from teaagent.workspace_tools._git import GitToolConfig, register_git_tools


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init'], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@test.com'],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test'],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    (repo / 'initial.txt').write_text('hello')
    subprocess.run(['git', 'add', '.'], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'initial'], cwd=repo, capture_output=True, check=True
    )
    return repo


@pytest.fixture
def config(git_repo: Path) -> GitToolConfig:
    return GitToolConfig(root=git_repo)


class TestGitFunctions:
    def test_git_add(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_add

        (config.root / 'new.txt').write_text('content')
        result = git_add(config, 'new.txt')
        assert result['exit_code'] == 0

    def test_git_add_all(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_add

        (config.root / 'a.txt').write_text('a')
        (config.root / 'b.txt').write_text('b')
        result = git_add(config, '.')
        assert result['exit_code'] == 0

    def test_git_commit(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_commit

        (config.root / 'file2.txt').write_text('world')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_commit(config, 'test commit')
        assert result['exit_code'] == 0
        assert len(result['commit_sha']) > 0

    def test_git_commit_amend(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_commit

        (config.root / 'amend.txt').write_text('amend')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_commit(config, 'amended', amend=True)
        assert result['exit_code'] == 0

    def test_git_commit_no_verify(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_commit

        (config.root / 'nv.txt').write_text('no-verify')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_commit(config, 'no verify', no_verify=True)
        assert result['exit_code'] == 0

    def test_git_create_branch(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_create_branch

        result = git_create_branch(config, 'feature-x')
        assert result['exit_code'] == 0
        assert result['branch'] == 'feature-x'

    def test_git_create_branch_with_start_point(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_create_branch

        result = git_create_branch(config, 'from-main', start_point='HEAD')
        assert result['exit_code'] == 0

    def test_git_create_branch_with_checkout(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_create_branch

        result = git_create_branch(config, 'feature-y', checkout=True)
        assert result['exit_code'] == 0

    def test_git_checkout_existing(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_checkout

        subprocess.run(
            ['git', 'branch', 'other'], cwd=config.root, capture_output=True, check=True
        )
        result = git_checkout(config, 'other')
        assert result['exit_code'] == 0
        assert result['branch'] == 'other'

    def test_git_checkout_create(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_checkout

        result = git_checkout(config, 'new-branch', create=True)
        assert result['exit_code'] == 0

    def test_git_checkout_create_with_start_point(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_checkout

        result = git_checkout(config, 'from-head', create=True, start_point='HEAD')
        assert result['exit_code'] == 0

    def test_git_stash(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_stash

        (config.root / 'stash.txt').write_text('stash me')
        result = git_stash(config)
        assert result['exit_code'] == 0

    def test_git_stash_with_message(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_stash

        (config.root / 'msg.txt').write_text('msg')
        result = git_stash(config, message='test stash')
        assert result['exit_code'] == 0

    def test_git_stash_with_untracked(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_stash

        (config.root / 'untracked.txt').write_text('untracked')
        result = git_stash(config, include_untracked=True)
        assert result['exit_code'] == 0

    def test_git_stash_pop(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_stash

        (config.root / 'pop.txt').write_text('pop me')
        git_stash(config)

        (config.root / 'pop.txt').write_text('changed')
        with pytest.raises(subprocess.CalledProcessError):
            git_stash(config, pop=True)

    def test_git_pull_no_remote(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_pull

        with pytest.raises(subprocess.CalledProcessError):
            git_pull(config)

    def test_git_push_no_remote(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_push

        with pytest.raises(subprocess.CalledProcessError):
            git_push(config)

    def test_git_push_with_branch(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_push

        with pytest.raises(subprocess.CalledProcessError):
            git_push(config, branch='main')

    def test_git_push_with_upstream(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_push

        with pytest.raises(subprocess.CalledProcessError):
            git_push(config, set_upstream=True)

    def test_git_pull_with_rebase(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_pull

        with pytest.raises(subprocess.CalledProcessError):
            git_pull(config, rebase=True)

    def test_git_lore_commit(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_lore_commit

        (config.root / 'lore.txt').write_text('lore')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_lore_commit(config, 'feat: add lore', 'why test', 'what test')
        assert result['exit_code'] == 0

    def test_git_lore_commit_with_session(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_lore_commit

        (config.root / 'lore2.txt').write_text('lore2')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_lore_commit(
            config, 'feat: add lore2', 'why test', 'what test', session_id='ses_123'
        )
        assert result['exit_code'] == 0

    def test_lore_commit_amend(self, config: GitToolConfig) -> None:
        from teaagent.workspace_tools._git import git_lore_commit

        (config.root / 'lore3.txt').write_text('lore3')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        git_lore_commit(config, 'first', 'why', 'what')
        (config.root / 'lore3.txt').write_text('lore3 amended')
        subprocess.run(
            ['git', 'add', '.'], cwd=config.root, capture_output=True, check=True
        )
        result = git_lore_commit(config, 'amended lore', 'why', 'what', amend=True)
        assert result['exit_code'] == 0


class TestGitRegistration:
    def test_all_tools_have_destructive_annotation(self) -> None:
        registry = __import__(
            'teaagent.tools', fromlist=['ToolRegistry']
        ).ToolRegistry()
        register_git_tools(registry, GitToolConfig(root=Path.cwd()))

        for name in [
            'git_add',
            'git_commit',
            'git_create_branch',
            'git_checkout',
            'git_push',
            'git_pull',
            'git_stash',
        ]:
            tool = registry.get(name)
            assert tool.annotations.destructive is True, f'{name} not destructive'

    def test_rate_limits(self) -> None:
        registry = __import__(
            'teaagent.tools', fromlist=['ToolRegistry']
        ).ToolRegistry()
        register_git_tools(registry, GitToolConfig(root=Path.cwd()))

        for name in ['git_commit', 'git_lore_commit', 'git_push']:
            tool = registry.get(name)
            assert tool.rate_limit is not None
            assert tool.rate_limit.max_calls > 0

    def test_lore_commit_registered(self) -> None:
        registry = __import__(
            'teaagent.tools', fromlist=['ToolRegistry']
        ).ToolRegistry()
        register_git_tools(registry, GitToolConfig(root=Path.cwd()))

        tool = registry.get('git_lore_commit')
        assert tool is not None
        assert 'Lore-compliant' in tool.description

    def test_git_stash_registered(self) -> None:
        registry = __import__(
            'teaagent.tools', fromlist=['ToolRegistry']
        ).ToolRegistry()
        register_git_tools(registry, GitToolConfig(root=Path.cwd()))

        tool = registry.get('git_stash')
        assert tool is not None
        assert 'Stash' in tool.description
