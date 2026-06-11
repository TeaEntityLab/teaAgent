"""Integration tests for parallel experiments workflow."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from teaagent.git_sandbox import ParallelExperimentStack


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp = Path(tempfile.mkdtemp())
    yield temp
    assert os.path.exists(temp), (
        f'Temporary directory {temp} should still exist before cleanup'
    )
    shutil.rmtree(temp)
    assert not os.path.exists(temp), f'Temporary directory {temp} was not cleaned up'


@pytest.fixture
def experiment_stack(temp_dir):
    """Create a ParallelExperimentStack for testing."""
    run_id = 'test-run-001'
    options = ['optA', 'optB', 'optC']
    stack = ParallelExperimentStack(root=temp_dir, run_id=run_id, options=options)
    yield stack
    # Cleanup any branches created during the test
    stack.cleanup_all()


def test_parallel_experiment_creation_and_cleanup(temp_dir, experiment_stack) -> None:
    """Test creating multiple parallel experiments and cleanup."""
    # Create a base git repository
    import subprocess

    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Start parallel experiments
    results = experiment_stack.start_all(auto_stash=False)

    assert len(results) == 3
    assert all(r.success for r in results.values())

    # Verify branches exist
    result = subprocess.run(
        ['git', 'branch', '--list'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    assert 'sandbox-test-run-001-optA' in result.stdout
    assert 'sandbox-test-run-001-optB' in result.stdout
    assert 'sandbox-test-run-001-optC' in result.stdout

    # Cleanup
    experiment_stack.cleanup_all()

    # Verify branches are deleted
    result = subprocess.run(
        ['git', 'branch', '--list'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    assert 'sandbox-test-run-001-optA' not in result.stdout
    assert 'sandbox-test-run-001-optB' not in result.stdout
    assert 'sandbox-test-run-001-optC' not in result.stdout


def test_experiment_isolation(temp_dir, experiment_stack) -> None:
    """Test that parallel experiments are isolated from each other."""
    import subprocess

    # Create a base git repository
    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Start parallel experiments
    results = experiment_stack.start_all(auto_stash=False)

    # Modify optA
    optA_branch = results['optA'].branch_name
    subprocess.run(
        ['git', 'checkout', optA_branch],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    (temp_dir / 'test.txt').write_text('optA content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'optA change'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Modify optB
    optB_branch = results['optB'].branch_name
    subprocess.run(
        ['git', 'checkout', optB_branch],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    (temp_dir / 'test.txt').write_text('optB content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'optB change'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Verify isolation: optA should have optA content
    subprocess.run(
        ['git', 'checkout', optA_branch],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    optA_content = (temp_dir / 'test.txt').read_text(encoding='utf-8')
    assert optA_content == 'optA content'

    # Verify isolation: optB should have optB content
    subprocess.run(
        ['git', 'checkout', optB_branch],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    optB_content = (temp_dir / 'test.txt').read_text(encoding='utf-8')
    assert optB_content == 'optB content'

    # Cleanup
    experiment_stack.cleanup_all()


def test_experiment_selection_and_merge(temp_dir, experiment_stack) -> None:
    """Test getting sandbox for a specific option."""
    import subprocess

    # Create a base git repository
    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Start parallel experiments
    results = experiment_stack.start_all(auto_stash=False)

    # Get sandbox for optA
    sandbox = experiment_stack.get_sandbox('optA')

    assert sandbox is not None
    assert sandbox._branch_name == results['optA'].branch_name

    # Cleanup
    experiment_stack.cleanup_all()


def test_branch_comparison(temp_dir, experiment_stack) -> None:
    """Test comparing experimental branches."""
    import subprocess

    # Create a base git repository
    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Start parallel experiments
    results = experiment_stack.start_all(auto_stash=False)

    # Modify optA
    optA_branch = results['optA'].branch_name
    subprocess.run(
        ['git', 'checkout', optA_branch],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    (temp_dir / 'test.txt').write_text('optA content', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ['git', 'commit', '-m', 'optA change'],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Compare branches
    comparisons = experiment_stack.compare_branches()

    assert 'optA' in comparisons
    assert 'optB' in comparisons
    assert 'optC' in comparisons

    # optA should have changes
    assert comparisons['optA'].get('files_changed', 0) > 0

    # Cleanup
    experiment_stack.cleanup_all()
