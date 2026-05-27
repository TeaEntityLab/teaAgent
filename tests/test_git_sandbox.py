"""Tests for GitBranchSandbox git-native checkpointing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from teaagent.git_sandbox import (
    GitBranchSandbox,
    GitTransactionSink,
    is_git_repository,
    is_worktree_clean,
    stash_save,
    stash_pop,
)


def test_is_git_repository_non_git(tmp_path: Path) -> None:
    """Test that non-git directory returns False."""
    assert not is_git_repository(tmp_path)


def test_is_git_repository_git_repo(tmp_path: Path) -> None:
    """Test that git repository returns True."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    assert is_git_repository(tmp_path)


def test_is_worktree_clean_clean(tmp_path: Path) -> None:
    """Test that clean worktree returns True."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    assert is_worktree_clean(tmp_path)


def test_is_worktree_clean_dirty(tmp_path: Path) -> None:
    """Test that dirty worktree returns False."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    assert not is_worktree_clean(tmp_path)


def test_stash_save_and_pop(tmp_path: Path) -> None:
    """Test stashing and popping changes."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    # Stash
    stash_id = stash_save(tmp_path, 'test stash')
    assert stash_id is not None

    # Worktree should be clean
    assert is_worktree_clean(tmp_path)
    assert (tmp_path / 'test.txt').read_text() == 'original'

    # Pop stash
    assert stash_pop(tmp_path)
    assert (tmp_path / 'test.txt').read_text() == 'modified'


def test_git_sandbox_not_available_non_git(tmp_path: Path) -> None:
    """Test that git sandbox is not available in non-git directory."""
    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert not sandbox.is_available()


def test_git_sandbox_available_in_git_repo(tmp_path: Path) -> None:
    """Test that git sandbox is available in a git repository."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert sandbox.is_available()


def test_git_sandbox_start_clean(tmp_path: Path) -> None:
    """Test starting sandbox on clean worktree."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start()

    assert start_result.success
    assert start_result.branch_name == 'teaagent-sandbox-test-run'


def test_git_sandbox_start_dirty_no_stash(tmp_path: Path) -> None:
    """Test starting sandbox on dirty worktree without auto-stash."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    # Make worktree dirty
    (tmp_path / 'test.txt').write_text('modified')

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start(auto_stash=False)

    assert not start_result.success
    assert 'dirty' in start_result.error.lower()


def test_git_sandbox_start_dirty_with_stash(tmp_path: Path) -> None:
    """Test starting sandbox on dirty worktree with auto-stash."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    # Make worktree dirty
    (tmp_path / 'test.txt').write_text('modified')

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start(auto_stash=True)

    assert start_result.success
    assert start_result.stash_id is not None


def test_git_sandbox_commit_transaction(tmp_path: Path) -> None:
    """Test committing a transaction with tool metadata."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    # Commit transaction
    commit_result = sandbox.commit_transaction('workspace_write_file', 'call_123')
    assert commit_result.success

    # Verify commit message
    result = subprocess.run(
        ['git', 'log', '--oneline', '-n', '1'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '[TeaAgent Transaction] workspace_write_file - call_123' in result.stdout


def test_git_sandbox_merge_squash(tmp_path: Path) -> None:
    """Test squashing merge."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Make multiple commits
    (tmp_path / 'test.txt').write_text('modified1')
    sandbox.commit_transaction('workspace_write_file', 'call_1')
    (tmp_path / 'test.txt').write_text('modified2')
    sandbox.commit_transaction('workspace_write_file', 'call_2')

    # Squash merge
    merge_result = sandbox.merge(squash=True)
    assert merge_result.success

    # Verify single squashed commit
    result = subprocess.run(
        ['git', 'log', '--oneline', '-n', '3'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.strip().split('\n')
    assert 'chore: applied TeaAgent modifications for run test-run' in lines[0]
    assert '[TeaAgent Transaction]' not in lines[0]  # Squashed commit shouldn't have transaction marker


def test_git_sandbox_discard(tmp_path: Path) -> None:
    """Test discarding sandbox changes."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    # Discard
    discard_result = sandbox.discard()
    assert discard_result.success

    # Verify file is restored
    assert (tmp_path / 'test.txt').read_text() == 'original'


def test_git_sandbox_keep(tmp_path: Path) -> None:
    """Test keeping sandbox branch for manual review."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    # Keep
    keep_result = sandbox.keep()
    assert keep_result.success
    assert keep_result.branch_name == 'teaagent-sandbox-test-run'

    # Verify branch still exists
    result = subprocess.run(
        ['git', 'branch'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert 'teaagent-sandbox-test-run' in result.stdout


def test_git_transaction_sink(tmp_path: Path) -> None:
    """Test GitTransactionSink commits after successful tool calls."""
    from teaagent.audit import AuditEvent

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    sink = GitTransactionSink(sandbox)

    # Simulate tool call lifecycle
    sink(AuditEvent('tool_call_started', 'run_1', payload={'tool_name': 'workspace_write_file', 'call_id': 'call_123'}))
    (tmp_path / 'test.txt').write_text('modified')
    sink(AuditEvent('tool_call_completed', 'run_1', payload={'call_id': 'call_123'}))

    # Verify commit was made
    result = subprocess.run(
        ['git', 'log', '--oneline', '-n', '1'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '[TeaAgent Transaction] workspace_write_file - call_123' in result.stdout


def test_git_transaction_sink_ignores_failed_calls(tmp_path: Path) -> None:
    """Test GitTransactionSink does not commit failed tool calls."""
    from teaagent.audit import AuditEvent

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    sink = GitTransactionSink(sandbox)

    # Simulate failed tool call
    sink(AuditEvent('tool_call_started', 'run_1', payload={'tool_name': 'workspace_write_file', 'call_id': 'call_123'}))
    (tmp_path / 'test.txt').write_text('modified')
    sink(AuditEvent('tool_call_failed', 'run_1', payload={'call_id': 'call_123'}))

    # Verify no commit was made
    result = subprocess.run(
        ['git', 'log', '--oneline', '-n', '1'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '[TeaAgent Transaction]' not in result.stdout
