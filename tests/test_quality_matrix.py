"""Tests for dynamic test-driven quality matrix (TASK-008)."""

from __future__ import annotations

import subprocess
import tempfile

import pytest

from teaagent.git_sandbox import ParallelExperimentStack, TestExecutionResult


@pytest.fixture
def git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmp:
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
        yield tmp


def test_test_result_dataclass() -> None:
    """Test TestExecutionResult dataclass structure."""
    result = TestExecutionResult(
        option='optA',
        branch_name='teaagent-sandbox-123-optA',
        passed=True,
        duration_seconds=5.5,
        exit_code=0,
        output='All tests passed',
        error='',
    )
    assert result.option == 'optA'
    assert result.passed
    assert result.duration_seconds == 5.5
    assert result.exit_code == 0


def test_parallel_stack_run_tests_non_git_repo() -> None:
    """Test run_tests on non-git repository."""
    with tempfile.TemporaryDirectory() as tmp:
        stack = ParallelExperimentStack(tmp, 'run-123', ['optA', 'optB'])
        results = stack.run_tests(['echo', 'test'])

        assert len(results) == 2
        for _option, result in results.items():
            assert not result.passed
            assert 'Not a git repository' in result.error


def test_parallel_stack_run_tests_with_sandboxes(git_repo) -> None:
    """Test run_tests with actual git sandboxes."""
    stack = ParallelExperimentStack(git_repo, 'run-123', ['optA', 'optB'])
    stack.start_all()

    # Run a simple command instead of pytest
    results = stack.run_tests(['echo', 'test'])

    assert len(results) == 2
    for option, result in results.items():
        assert option in ['optA', 'optB']
        # Echo should pass
        assert result.passed


def test_parallel_stack_run_tests_timeout(git_repo) -> None:
    """Test run_tests with timeout."""
    stack = ParallelExperimentStack(git_repo, 'run-123', ['optA'])
    stack.start_all()

    # Run a command that will timeout
    results = stack.run_tests(['sleep', '10'], timeout_seconds=1)

    assert len(results) == 1
    result = results['optA']
    assert not result.passed
    assert 'timed out' in result.error.lower()


def test_parallel_stack_run_tests_failing_command(git_repo) -> None:
    """Test run_tests with a failing command."""
    stack = ParallelExperimentStack(git_repo, 'run-123', ['optA'])
    stack.start_all()

    # Run a command that will fail
    results = stack.run_tests(['false'])

    assert len(results) == 1
    result = results['optA']
    assert not result.passed
    assert result.exit_code == 1


def test_parallel_stack_run_tests_multiple_branches(git_repo) -> None:
    """Test run_tests across multiple branches."""
    stack = ParallelExperimentStack(git_repo, 'run-123', ['optA', 'optB', 'optC'])
    stack.start_all()

    # Run a simple command
    results = stack.run_tests(['echo', 'test'])

    assert len(results) == 3
    for option in ['optA', 'optB', 'optC']:
        assert option in results
        assert results[option].passed
