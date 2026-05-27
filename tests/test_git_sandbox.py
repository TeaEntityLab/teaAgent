"""Tests for GitBranchSandbox git-native checkpointing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from teaagent.git_sandbox import GitBranchSandbox


def test_git_sandbox_not_available_non_git(tmp_path: Path) -> None:
    """Test that git sandbox is not available in non-git directory."""
    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert not sandbox.is_available()


def test_git_sandbox_available_in_git_repo(tmp_path: Path) -> None:
    """Test that git sandbox is available in a git repository."""
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    assert sandbox.is_available()


def test_git_sandbox_start_and_rollback(tmp_path: Path) -> None:
    """Test starting a sandbox branch and rolling back."""
    # Initialize git repo with initial commit
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    start_result = sandbox.start()

    assert start_result.success
    assert start_result.branch_name == 'teaagent-run-test-run'
    assert start_result.original_branch == 'main' or start_result.original_branch == 'master'

    # Modify file on sandbox branch
    (tmp_path / 'test.txt').write_text('modified')

    # Rollback
    rollback_result = sandbox.rollback()
    assert rollback_result.success

    # Verify file is restored
    assert (tmp_path / 'test.txt').read_text() == 'original'


def test_git_sandbox_commit(tmp_path: Path) -> None:
    """Test committing changes to sandbox branch."""
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify and commit
    (tmp_path / 'test.txt').write_text('modified')
    commit_result = sandbox.commit('test commit')
    assert commit_result.success


def test_git_sandbox_merge(tmp_path: Path) -> None:
    """Test merging sandbox branch back to original."""
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / 'test.txt').write_text('original')
    subprocess.run(['git', 'add', 'test.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    sandbox.start()

    # Modify and commit on sandbox
    (tmp_path / 'test.txt').write_text('modified')
    sandbox.commit('test commit')

    # Merge back
    merge_result = sandbox.merge()
    assert merge_result.success

    # Verify file is modified on original branch
    assert (tmp_path / 'test.txt').read_text() == 'modified'


def test_git_sandbox_rollback_without_start(tmp_path: Path) -> None:
    """Test that rollback fails without starting sandbox."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True, capture_output=True)

    sandbox = GitBranchSandbox(tmp_path, run_id='test-run')
    rollback_result = sandbox.rollback()
    assert not rollback_result.success
    assert 'not properly initialized' in rollback_result.error
