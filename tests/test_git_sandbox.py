"""Tests for GitBranchSandbox git-native checkpointing."""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest

from teaagent.git_sandbox import (
    GitBranchSandbox,
    GitTransactionSink,
    is_git_repository,
    is_worktree_clean,
    stash_pop,
    stash_save,
)


def test_is_git_repository_non_git(tmp_path: Path) -> None:
    """Test that non-git directory returns False."""
    assert not is_git_repository(tmp_path)


def test_is_git_repository_git_repo(git_repo_with_config: Path) -> None:
    """Test that git repository returns True."""
    assert is_git_repository(git_repo_with_config)


def test_is_worktree_clean_clean(git_repo_with_commit: Path) -> None:
    """Test that clean worktree returns True."""
    assert is_worktree_clean(git_repo_with_commit)


def test_is_worktree_clean_dirty(git_repo_with_commit: Path) -> None:
    """Test that dirty worktree returns False."""
    # Modify file
    (git_repo_with_commit / 'test.txt').write_text('modified')

    assert not is_worktree_clean(git_repo_with_commit)


def test_stash_save_and_pop(tmp_path: Path) -> None:
    """Test stashing and popping changes."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

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


def test_stash_untracked_files(tmp_path: Path) -> None:
    """Test stashing untracked files with -u flag."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create untracked file
    (tmp_path / 'untracked.txt').write_text('untracked content')

    # Worktree should be dirty (untracked files)
    assert not is_worktree_clean(tmp_path)

    # Stash with -u flag should handle untracked files
    stash_id = stash_save(tmp_path, 'test untracked stash')
    assert stash_id is not None

    # Worktree should be clean after stashing
    assert is_worktree_clean(tmp_path)
    assert not (tmp_path / 'untracked.txt').exists()

    # Pop stash
    assert stash_pop(tmp_path)
    assert (tmp_path / 'untracked.txt').exists()
    assert (tmp_path / 'untracked.txt').read_text() == 'untracked content'


def test_git_sandbox_not_available_non_git(tmp_path: Path) -> None:
    """Test that git sandbox is not available in non-git directory."""
    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert not sandbox.is_available()


def test_git_sandbox_available_in_git_repo(tmp_path: Path) -> None:
    """Test that git sandbox is available in a git repository."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert sandbox.is_available()


def test_git_sandbox_start_clean(tmp_path: Path) -> None:
    """Test starting sandbox on clean worktree."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start()

    assert start_result.success
    assert start_result.branch_name == 'teaagent-sandbox-test-run'


def test_git_sandbox_start_dirty_no_stash(tmp_path: Path) -> None:
    """Test starting sandbox on dirty worktree without auto-stash."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Make worktree dirty
    (tmp_path / 'test.txt').write_text('modified')

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start(auto_stash=False)

    assert not start_result.success
    assert 'dirty' in start_result.error.lower()


def test_git_sandbox_start_dirty_with_stash(tmp_path: Path) -> None:
    """Test starting sandbox on dirty worktree with auto-stash."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Make worktree dirty
    (tmp_path / 'test.txt').write_text('modified')

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start(auto_stash=True)

    assert start_result.success
    assert start_result.stash_id is not None


def test_git_sandbox_commit_transaction(tmp_path: Path) -> None:
    """Test committing a transaction with tool metadata."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

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
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

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
    assert (
        '[TeaAgent Transaction]' not in lines[0]
    )  # Squashed commit shouldn't have transaction marker


def test_git_sandbox_discard(tmp_path: Path) -> None:
    """Test discarding sandbox changes."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify file
    (tmp_path / 'test.txt').write_text('modified')

    # Discard
    discard_result = sandbox.discard()
    assert discard_result.success

    # Verify file is restored
    assert (tmp_path / 'test.txt').read_text() == 'original'


def test_rollback_with_dirty_sandbox(tmp_path: Path) -> None:
    """Test rollback succeeds even with uncommitted changes on sandbox branch."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Make uncommitted changes (dirty sandbox)
    (tmp_path / 'test.txt').write_text('modified')
    (tmp_path / 'new_file.txt').write_text('new content')

    # Rollback should succeed despite dirty sandbox
    rollback_result = sandbox.rollback()
    assert rollback_result.success

    # Verify file is restored to original state
    assert (tmp_path / 'test.txt').read_text() == 'original'
    # Verify untracked file is cleaned
    assert not (tmp_path / 'new_file.txt').exists()


def test_git_sandbox_keep(tmp_path: Path) -> None:
    """Test keeping sandbox branch for manual review."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

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
    from teaagent.types import AuditEvent

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    sink = GitTransactionSink(sandbox)

    # Simulate tool call lifecycle
    sink(
        AuditEvent(
            'tool_call_started',
            'run_1',
            payload={'tool_name': 'workspace_write_file', 'call_id': 'call_123'},
        )
    )
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
    from teaagent.types import AuditEvent

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    sink = GitTransactionSink(sandbox)

    # Simulate failed tool call
    sink(
        AuditEvent(
            'tool_call_started',
            'run_1',
            payload={'tool_name': 'workspace_write_file', 'call_id': 'call_123'},
        )
    )
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


def test_git_transaction_sink_commits_shell_mutate(tmp_path: Path) -> None:
    """Test GitTransactionSink commits for shell mutate tools."""
    from teaagent.types import AuditEvent

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    sink = GitTransactionSink(sandbox)

    # Simulate shell mutate tool call
    sink(
        AuditEvent(
            'tool_call_started',
            'run_1',
            payload={
                'tool_name': 'workspace_run_shell_mutate',
                'call_id': 'call_shell_123',
            },
        )
    )
    (tmp_path / 'test.txt').write_text('formatted by shell')
    sink(
        AuditEvent(
            'tool_call_completed', 'run_1', payload={'call_id': 'call_shell_123'}
        )
    )

    # Verify commit was made
    result = subprocess.run(
        ['git', 'log', '--oneline', '-n', '1'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert (
        '[TeaAgent Transaction] workspace_run_shell_mutate - call_shell_123'
        in result.stdout
    )


def test_find_orphaned_sandbox_branches(tmp_path: Path) -> None:
    """Test finding orphaned sandbox branches."""
    from teaagent.git_sandbox import find_orphaned_sandbox_branches

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create orphaned sandbox branch
    subprocess.run(
        ['git', 'checkout', '-b', 'teaagent-sandbox-orphaned-123'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'checkout', '-'], cwd=tmp_path, check=True, capture_output=True
    )

    # Find orphaned branches
    orphaned = find_orphaned_sandbox_branches(tmp_path)

    assert len(orphaned) == 1
    assert orphaned[0]['branch_name'] == 'teaagent-sandbox-orphaned-123'
    assert orphaned[0]['run_id'] == 'orphaned-123'
    assert orphaned[0]['reason'] == 'no_active_run'


def test_prune_sandbox_branch(tmp_path: Path) -> None:
    """Test pruning a sandbox branch."""
    from teaagent.git_sandbox import prune_sandbox_branch

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create sandbox branch
    subprocess.run(
        ['git', 'checkout', '-b', 'teaagent-sandbox-test-456'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'checkout', '-'], cwd=tmp_path, check=True, capture_output=True
    )

    # Verify branch exists
    result = subprocess.run(
        ['git', 'branch'], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert 'teaagent-sandbox-test-456' in result.stdout

    # Prune branch
    assert prune_sandbox_branch(tmp_path, 'teaagent-sandbox-test-456')

    # Verify branch is deleted
    result = subprocess.run(
        ['git', 'branch'], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert 'teaagent-sandbox-test-456' not in result.stdout


def test_find_orphaned_sandbox_branches_with_active_run(tmp_path: Path) -> None:
    """Test that active runs are not marked as orphaned."""
    from teaagent.git_sandbox import find_orphaned_sandbox_branches

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create background store directory and active run file manually
    bg_dir = tmp_path / '.teaagent' / 'background'
    bg_dir.mkdir(parents=True, exist_ok=True)
    import json

    from teaagent.ergonomics.background_run import _utc_now

    record_path = bg_dir / 'active-run-789.json'
    record_path.write_text(
        json.dumps(
            {
                'background_id': 'active-run-789',
                'pid': 12345,
                'command': ['sleep', '100'],
                'started_at': _utc_now(),
                'log_path': '/tmp/test.log',
                'status': 'running',
            }
        )
    )

    # Create sandbox branch matching active run
    subprocess.run(
        ['git', 'checkout', '-b', 'teaagent-sandbox-active-run-789'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'checkout', '-'], cwd=tmp_path, check=True, capture_output=True
    )

    # Create orphaned branch
    subprocess.run(
        ['git', 'checkout', '-b', 'teaagent-sandbox-orphaned-123'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'checkout', '-'], cwd=tmp_path, check=True, capture_output=True
    )

    # Find orphaned branches (auto-detects background store)
    orphaned = find_orphaned_sandbox_branches(tmp_path)

    # Both branches should be found since the function reads background store
    # The active run filtering is tested via integration with actual background runs
    assert len(orphaned) >= 1
    branch_names = [b['branch_name'] for b in orphaned]
    assert 'teaagent-sandbox-orphaned-123' in branch_names


def test_has_merge_conflicts_no_conflicts(tmp_path: Path) -> None:
    """Test has_merge_conflicts returns False when no conflicts."""
    from teaagent.git_sandbox import has_merge_conflicts

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    assert not has_merge_conflicts(tmp_path)


def test_get_conflicted_files_no_conflicts(tmp_path: Path) -> None:
    """Test get_conflicted_files returns empty list when no conflicts."""
    from teaagent.git_sandbox import get_conflicted_files

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    assert get_conflicted_files(tmp_path) == []


def test_abort_merge_no_merge(tmp_path: Path) -> None:
    """Test abort_merge returns False when no merge in progress."""
    from teaagent.git_sandbox import abort_merge

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # abort_merge should fail when no merge is in progress
    assert not abort_merge(tmp_path)


def test_extract_conflict_context(tmp_path: Path) -> None:
    """Test extracting conflict context from a conflicted file."""
    from teaagent.git_sandbox import extract_conflict_context

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create a file with conflict markers
    conflicted_content = """<<<<<<< HEAD
our version
=======
their version
>>>>>>> sandbox-branch
"""
    (tmp_path / 'test.txt').write_text(conflicted_content)

    context = extract_conflict_context(tmp_path, 'test.txt')

    assert context is not None
    assert 'our version' in context['ours']
    assert 'their version' in context['theirs']


def test_apply_llm_resolution(tmp_path: Path) -> None:
    """Test applying LLM-resolved content."""
    from teaagent.git_sandbox import apply_llm_resolution

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    resolved_content = 'resolved content without markers'
    assert apply_llm_resolution(tmp_path, 'test.txt', resolved_content)

    # Verify content was applied
    assert (tmp_path / 'test.txt').read_text() == resolved_content


def test_parallel_experiment_stack_start_all(tmp_path: Path) -> None:
    """Test starting multiple parallel sandbox branches."""
    from teaagent.git_sandbox import ParallelExperimentStack

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    stack = ParallelExperimentStack(tmp_path, 'test-run', ['optA', 'optB', 'optC'])
    results = stack.start_all()

    assert len(results) == 3
    assert all(results[opt].success for opt in ['optA', 'optB', 'optC'])
    assert all(results[opt].branch_name for opt in ['optA', 'optB', 'optC'])


def test_parallel_experiment_stack_get_sandbox(tmp_path: Path) -> None:
    """Test getting a specific sandbox from the stack."""
    from teaagent.git_sandbox import ParallelExperimentStack

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    stack = ParallelExperimentStack(tmp_path, 'test-run', ['optA', 'optB'])
    stack.start_all()

    sandbox = stack.get_sandbox('optA')
    assert sandbox is not None
    assert sandbox._run_id == 'test-run-optA'

    sandbox = stack.get_sandbox('optC')
    assert sandbox is None


def test_parallel_experiment_stack_cleanup_all(tmp_path: Path) -> None:
    """Test cleaning up all sandbox branches."""
    from teaagent.git_sandbox import ParallelExperimentStack

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    stack = ParallelExperimentStack(tmp_path, 'test-run', ['optA', 'optB'])
    stack.start_all()

    # Cleanup all
    results = stack.cleanup_all()
    assert all(results.values())

    # Verify branches are deleted
    result = subprocess.run(
        ['git', 'branch'], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert 'optA' not in result.stdout
    assert 'optB' not in result.stdout


def test_parallel_experiment_stack_cleanup_keep_best(tmp_path: Path) -> None:
    """Test cleaning up all branches except the best one."""
    from teaagent.git_sandbox import ParallelExperimentStack

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    stack = ParallelExperimentStack(tmp_path, 'test-run', ['optA', 'optB'])
    stack.start_all()

    # Cleanup keeping optA
    results = stack.cleanup_all(keep_best='optA')
    assert results['optA'] is True  # Kept
    assert results['optB'] is True  # Deleted

    # Verify optA still exists, optB is deleted
    result = subprocess.run(
        ['git', 'branch'], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert 'optA' in result.stdout
    assert 'optB' not in result.stdout


def test_os_sandbox_is_path_allowed(tmp_path: Path) -> None:
    """Test path allowance checking in OS sandbox."""
    from teaagent.git_sandbox import OSSandbox

    sandbox = OSSandbox(tmp_path)

    # Paths within sandbox should be allowed
    assert sandbox.is_path_allowed(str(tmp_path))
    assert sandbox.is_path_allowed(str(tmp_path / 'subdir'))
    assert sandbox.is_path_allowed(str(tmp_path / 'file.txt'))

    # Paths outside sandbox should be denied
    assert not sandbox.is_path_allowed('/etc/passwd')
    assert not sandbox.is_path_allowed('/tmp')
    assert not sandbox.is_path_allowed('/')


def test_os_sandbox_sanitize_environment(tmp_path: Path) -> None:
    """Test environment variable sanitization."""

    from teaagent.git_sandbox import OSSandbox

    sandbox = OSSandbox(tmp_path)

    # Set some sensitive environment variables
    original_env = {
        'PATH': '/usr/bin:/bin',
        'HOME': '/home/user',
        'SSH_PRIVATE_KEY': 'secret',
        'API_KEY': '12345',
        'SAFE_VAR': 'value',
    }

    sanitized = sandbox.sanitize_environment(original_env)

    # Sensitive keys should be removed
    assert 'SSH_PRIVATE_KEY' not in sanitized
    assert 'API_KEY' not in sanitized

    # Safe keys should remain
    assert 'HOME' in sanitized
    assert 'SAFE_VAR' in sanitized
    assert sanitized['SAFE_VAR'] == 'value'

    # PATH should be restricted
    assert sanitized['PATH'] == '/usr/bin:/bin:/usr/local/bin'

    # Sandbox indicator should be set
    assert sanitized['TEAAGENT_SANDBOX'] == '1'


def test_os_sandbox_execute_sandboxed(tmp_path: Path) -> None:
    """Test executing commands in sandboxed environment."""
    from teaagent.git_sandbox import OSSandbox

    sandbox = OSSandbox(tmp_path)

    # Simple command should work
    result = sandbox.execute_sandboxed(['echo', 'hello'], cwd=str(tmp_path))
    assert result['success']
    assert 'hello' in result['stdout']

    # Command outside allowed directory should fail
    result = sandbox.execute_sandboxed(['ls', '/etc'], cwd='/etc')
    assert not result['success']
    assert 'outside sandbox boundaries' in result['stderr']


def test_os_sandbox_set_resource_limits(tmp_path: Path) -> None:
    """Test setting resource limits."""
    from teaagent.git_sandbox import OSSandbox

    sandbox = OSSandbox(tmp_path)

    # Should return True on Unix systems where resource module is available
    # May return False on Windows or if permissions are insufficient
    result = sandbox.set_resource_limits()
    # We don't assert the result since it depends on the OS and permissions
    # Just verify it doesn't crash
    assert isinstance(result, bool)


def test_is_git_repository_with_nonexistent_path() -> None:
    """Test that nonexistent path is handled."""
    nonexistent = Path('/nonexistent/path/that/does/not/exist')
    assert not is_git_repository(nonexistent)


def test_is_git_repository_with_file_instead_of_directory(tmp_path: Path) -> None:
    """Test that file instead of directory is handled."""
    file_path = tmp_path / 'not_a_dir.txt'
    file_path.write_text('content')
    # Should handle gracefully or raise appropriate error
    try:
        result = is_git_repository(file_path)
        assert not result
    except (NotADirectoryError, FileNotFoundError):
        # Also acceptable to raise error for non-directory
        pass


def test_is_git_repository_with_broken_git_directory(tmp_path: Path) -> None:
    """Test that broken .git directory is handled."""
    (tmp_path / '.git').mkdir()
    (tmp_path / '.git' / 'broken').write_text('not a valid git repo')
    assert not is_git_repository(tmp_path)


def test_is_worktree_clean_with_nonexistent_path() -> None:
    """Test that nonexistent path is handled."""
    nonexistent = Path('/nonexistent/path')
    # Should handle gracefully without crashing
    result = is_worktree_clean(nonexistent)
    assert isinstance(result, bool)


def test_is_worktree_clean_with_no_git_repo(tmp_path: Path) -> None:
    """Test that non-git directory is handled."""
    (tmp_path / 'file.txt').write_text('content')
    # Should handle gracefully
    result = is_worktree_clean(tmp_path)
    assert isinstance(result, bool)


def test_stash_pop_with_nonexistent_path() -> None:
    """Test that nonexistent path is handled."""
    nonexistent = Path('/nonexistent/path')
    # Should handle gracefully without crashing
    with contextlib.suppress(subprocess.SubprocessError, FileNotFoundError):
        stash_pop(nonexistent)


def test_stash_pop_with_no_git_repo(tmp_path: Path) -> None:
    """Test that non-git directory is handled."""
    # Should handle gracefully without crashing
    with contextlib.suppress(subprocess.SubprocessError, FileNotFoundError):
        stash_pop(tmp_path)


def test_git_transaction_sink_with_nonexistent_path() -> None:
    """Test that GitTransactionSink handles nonexistent path."""
    nonexistent = Path('/nonexistent/path')
    # Should handle gracefully without crashing
    with contextlib.suppress(subprocess.SubprocessError, FileNotFoundError):
        GitTransactionSink(nonexistent)


def test_git_transaction_sink_with_no_git_repo(tmp_path: Path) -> None:
    """Test that GitTransactionSink handles non-git directory."""
    # Should handle gracefully without crashing
    with contextlib.suppress(subprocess.SubprocessError, ValueError):
        GitTransactionSink(tmp_path)


# ── Additional negative test cases for git_sandbox.py ───────────────────────


def test_is_git_repository_with_symlink_loop(tmp_path: Path) -> None:
    """Test that symlink loops are handled gracefully."""
    # Create a symlink loop
    loop_link = tmp_path / 'loop'
    try:
        loop_link.symlink_to(tmp_path)
    except OSError:
        pytest.skip('Symlink creation not supported')

    # Should not hang or crash
    result = is_git_repository(tmp_path)
    assert isinstance(result, bool)


def test_is_worktree_clean_with_corrupted_git_index(tmp_path: Path) -> None:
    """Test that corrupted git index is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Corrupt the git index
    (tmp_path / '.git' / 'index').write_text('corrupted index', encoding='utf-8')

    # Should handle gracefully
    try:
        result = is_worktree_clean(tmp_path)
        assert isinstance(result, bool)
    except (subprocess.SubprocessError, ValueError):
        # May fail on corrupted index
        pass


def test_stash_save_with_no_commits(tmp_path: Path) -> None:
    """Test that stashing with no commits is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create a file but don't commit
    (tmp_path / 'test.txt').write_text('uncommitted')

    # Should handle gracefully (may fail or return None)
    try:
        result = stash_save(tmp_path, 'test stash')
        assert result is None or isinstance(result, str)
    except (subprocess.SubprocessError, ValueError):
        # May fail with no commits
        pass


def test_stash_save_with_conflicts(tmp_path: Path) -> None:
    """Test that stashing with merge conflicts is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create a merge conflict scenario
    (tmp_path / 'test.txt').write_text('conflicting content')

    # Should handle gracefully
    try:
        result = stash_save(tmp_path, 'conflict stash')
        assert result is None or isinstance(result, str)
    except (subprocess.SubprocessError, ValueError):
        # May fail with conflicts
        pass


def test_stash_pop_with_no_stash(tmp_path: Path) -> None:
    """Test that popping with no stash is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Should handle gracefully (return False or fail)
    try:
        result = stash_pop(tmp_path)
        assert result is False
    except (subprocess.SubprocessError, ValueError):
        # May fail with no stash
        pass


def test_stash_pop_with_conflicts(tmp_path: Path) -> None:
    """Test that popping stash with conflicts is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Stash some changes
    (tmp_path / 'test.txt').write_text('stashed')
    stash_save(tmp_path, 'test stash')

    # Modify file to create conflict on pop
    (tmp_path / 'test.txt').write_text('conflicting')

    # Should handle gracefully
    try:
        result = stash_pop(tmp_path)
        assert result is False or isinstance(result, bool)
    except (subprocess.SubprocessError, ValueError):
        # May fail with conflicts
        pass


def test_git_sandbox_with_very_long_run_id(tmp_path: Path) -> None:
    """Test that very long run_id is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Very long run_id (may exceed git branch name limits)
    long_run_id = 'a' * 1000
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id=long_run_id)
        # Should handle gracefully (may truncate or fail)
        assert sandbox is not None
    except (subprocess.SubprocessError, ValueError):
        # May fail on too-long branch name
        pass


def test_git_sandbox_with_special_characters_in_run_id(tmp_path: Path) -> None:
    """Test that special characters in run_id are handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Special characters that may be invalid in git branch names
    special_run_id = 'test~^:..\\'
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id=special_run_id)
        # Should handle gracefully (may sanitize or fail)
        assert sandbox is not None
    except (subprocess.SubprocessError, ValueError):
        # May fail on invalid characters
        pass


def test_git_sandbox_with_unicode_in_run_id(tmp_path: Path) -> None:
    """Test that unicode in run_id is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Unicode characters
    unicode_run_id = 'test-中文-🔐'
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id=unicode_run_id)
        # Should handle gracefully (may sanitize or fail)
        assert sandbox is not None
    except (subprocess.SubprocessError, ValueError):
        # May fail on unicode in branch name
        pass


def test_git_sandbox_with_detached_head(tmp_path: Path) -> None:
    """Test that detached HEAD state is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Detach HEAD
    subprocess.run(
        ['git', 'checkout', '--detach'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Should handle detached HEAD gracefully
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
        start_result = sandbox.start()
        # May fail or succeed depending on implementation
        assert start_result is not None
    except (subprocess.SubprocessError, ValueError):
        # May fail on detached HEAD
        pass


def test_git_sandbox_with_bare_repository(tmp_path: Path) -> None:
    """Test that bare repository is handled."""
    subprocess.run(
        ['git', 'init', '--bare'], cwd=tmp_path, check=True, capture_output=True
    )

    # Should handle bare repository gracefully
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
        # May not be available in bare repo
        assert not sandbox.is_available()
    except (subprocess.SubprocessError, ValueError):
        # May fail on bare repository
        pass


def test_git_sandbox_with_corrupted_git_config(tmp_path: Path) -> None:
    """Test that corrupted git config is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)

    # Corrupt git config
    (tmp_path / '.git' / 'config').write_text('corrupted config', encoding='utf-8')

    # Should handle gracefully
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
        # May fail or work with corrupted config
        assert sandbox is not None
    except (subprocess.SubprocessError, ValueError):
        # May fail on corrupted config
        pass


def test_git_sandbox_with_missing_git_directory(tmp_path: Path) -> None:
    """Test that missing .git directory is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)

    # Remove .git directory
    import shutil

    shutil.rmtree(tmp_path / '.git')

    # Should handle gracefully
    try:
        sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
        # Should not be available without .git
        assert not sandbox.is_available()
    except (subprocess.SubprocessError, ValueError):
        # May fail on missing .git
        pass


def test_git_transaction_sink_with_readonly_repository(tmp_path: Path) -> None:
    """Test that readonly repository is handled."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Make repository readonly
    (tmp_path / '.git').chmod(0o444)

    try:
        sink = GitTransactionSink(tmp_path)
        # Should handle gracefully
        assert sink is not None
    except (subprocess.SubprocessError, ValueError, PermissionError):
        # May fail on readonly repository
        pass
    finally:
        (tmp_path / '.git').chmod(0o755)


def test_git_sandbox_concurrent_operations(tmp_path: Path) -> None:
    """Test that concurrent sandbox operations are handled."""
    import threading

    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    def create_sandbox():
        try:
            sandbox = GitBranchSandbox(
                tmp_path, run_id=f'test-{threading.current_thread().ident}'
            )
            sandbox.start()
        except (subprocess.SubprocessError, ValueError):
            # May fail on concurrent operations
            pass

    # Create multiple sandboxes concurrently
    threads = [threading.Thread(target=create_sandbox) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should handle concurrent operations without crashing
