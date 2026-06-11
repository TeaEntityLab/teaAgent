"""Tests for CLI experiment commands."""

from __future__ import annotations

import subprocess
import tempfile

from teaagent.cli._handlers._experiment import (
    experiment_cancel,
    experiment_compare,
    experiment_list,
    experiment_select,
)


def test_experiment_list_non_git_repo() -> None:
    """Test experiment list in non-git repository."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a mock args object
        class Args:
            root = tmp

        result = experiment_list(Args())
        assert result == 1


def test_experiment_list_git_repo() -> None:
    """Test experiment list in git repository."""
    with tempfile.TemporaryDirectory() as tmp:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmp, capture_output=True, check=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', 'init'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )

        class Args:
            root = tmp

        result = experiment_list(Args())
        assert result == 0


def test_experiment_compare_non_git_repo() -> None:
    """Test experiment compare in non-git repository."""
    with tempfile.TemporaryDirectory() as tmp:

        class Args:
            root = tmp
            run_id = 'test-run'
            options = 'opt1,opt2'

        result = experiment_compare(Args())
        assert result == 1


def test_experiment_compare_no_options() -> None:
    """Test experiment compare with no options."""
    with tempfile.TemporaryDirectory() as tmp:

        class Args:
            root = tmp
            run_id = 'test-run'
            options = None

        result = experiment_compare(Args())
        assert result == 1


def test_experiment_select_non_git_repo() -> None:
    """Test experiment select in non-git repository."""
    with tempfile.TemporaryDirectory() as tmp:

        class Args:
            root = tmp
            run_id = 'test-run'
            options = 'opt1,opt2'
            select = 'opt1'
            squash = False

        result = experiment_select(Args())
        assert result == 1


def test_experiment_select_invalid_option() -> None:
    """Test experiment select with invalid option."""
    with tempfile.TemporaryDirectory() as tmp:

        class Args:
            root = tmp
            run_id = 'test-run'
            options = 'opt1,opt2'
            select = 'opt3'  # Not in options
            squash = False

        result = experiment_select(Args())
        assert result == 1


def test_experiment_cancel_non_git_repo() -> None:
    """Test experiment cancel in non-git repository."""
    with tempfile.TemporaryDirectory() as tmp:

        class Args:
            root = tmp
            run_id = 'test-run'
            options = None

        result = experiment_cancel(Args())
        assert result == 1


def test_experiment_cancel_orphaned_only() -> None:
    """Test experiment cancel with orphaned branches only."""
    with tempfile.TemporaryDirectory() as tmp:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmp, capture_output=True, check=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', 'init'],
            cwd=tmp,
            capture_output=True,
            check=True,
        )

        class Args:
            root = tmp
            run_id = None
            options = None

        result = experiment_cancel(Args())
        assert result == 0
