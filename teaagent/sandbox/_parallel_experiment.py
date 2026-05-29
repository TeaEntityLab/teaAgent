"""Parallel git branch experiment runner."""

from __future__ import annotations

import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.sandbox._git_branch import (
    GitBranchSandbox,
    GitSandboxResult,
    is_git_repository,
)


@dataclass(frozen=True)
class TestExecutionResult:
    """Result of test execution on a sandbox branch."""

    option: str
    branch_name: str
    passed: bool
    duration_seconds: float
    exit_code: int
    output: str
    error: str = ''



class ParallelExperimentStack:
    """Manage multiple parallel sandbox branches for experimentation."""

    def __init__(self, root: str | Path, run_id: str, options: list[str]):
        """Initialize parallel experiment stack.

        Args:
            root: Git repository root path.
            run_id: Base run ID for all experiments.
            options: List of option names (e.g., ['optA', 'optB', 'optC']).
        """
        self._root = Path(root).resolve()
        self._run_id = run_id
        self._options = options
        self._sandboxes: dict[str, GitBranchSandbox] = {}
        self._original_branch: Optional[str] = None

    def start_all(self, auto_stash: bool = False) -> dict[str, GitSandboxResult]:
        """Start all sandbox branches for parallel experimentation.

        Args:
            auto_stash: Whether to auto-stash uncommitted changes.

        Returns:
            Dict mapping option names to their sandbox results.
        """
        results: dict[str, GitSandboxResult] = {}

        if not is_git_repository(self._root):
            for option in self._options:
                results[option] = GitSandboxResult(
                    success=False,
                    error='Not a git repository',
                )
            return results

        # Get original branch
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            self._original_branch = result.stdout.strip()
        except subprocess.CalledProcessError:
            for option in self._options:
                results[option] = GitSandboxResult(
                    success=False,
                    error='Failed to get current branch',
                )
            return results

        # Create sandbox for each option
        for option in self._options:
            GitBranchSandbox(self._root, run_id=f'{self._run_id}-{option}')
            self._sandboxes[option] = GitBranchSandbox(
                self._root, run_id=f'{self._run_id}-{option}'
            )
            results[option] = self._sandboxes[option].start(auto_stash=auto_stash)

        return results

    def get_sandbox(self, option: str) -> Optional[GitBranchSandbox]:
        """Get sandbox for a specific option.

        Args:
            option: Option name.

        Returns:
            GitBranchSandbox instance or None if not found.
        """
        return self._sandboxes.get(option)

    def compare_branches(self) -> dict[str, dict[str, Any]]:
        """Compare all experimental branches against original.

        Returns:
            Dict mapping option names to comparison stats (files_changed, insertions, deletions).
        """
        comparisons: dict[str, dict[str, Any]] = {}

        if not self._original_branch:
            return comparisons

        for option, sandbox in self._sandboxes.items():
            try:
                result = subprocess.run(
                    [
                        'git',
                        'diff',
                        '--stat',
                        self._original_branch,
                        sandbox._branch_name,
                    ],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                stats = result.stdout.strip()

                # Parse stats
                files_changed = 0
                insertions = 0
                deletions = 0

                for line in stats.split('\n'):
                    if 'file' in line or 'files' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                files_changed = int(parts[0])
                    if 'insertion' in line or 'insertions' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                insertions = int(parts[0])
                    if 'deletion' in line or 'deletions' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                deletions = int(parts[0])

                comparisons[option] = {
                    'files_changed': files_changed,
                    'insertions': insertions,
                    'deletions': deletions,
                    'diff_stat': stats,
                }
            except subprocess.CalledProcessError:
                comparisons[option] = {
                    'files_changed': 0,
                    'insertions': 0,
                    'deletions': 0,
                    'diff_stat': 'Failed to compare',
                }

        return comparisons

    def cleanup_all(
        self, keep_best: Optional[str] = None, cleanup_memory: bool = True
    ) -> dict[str, bool]:
        """Delete all sandbox branches, optionally keeping the best one.

        Args:
            keep_best: Option name to keep (e.g., 'optA').
            cleanup_memory: Whether to clean up memory entries for deleted branches.

        Returns:
            Dict mapping option names to deletion success status.
        """
        results: dict[str, bool] = {}

        # Switch back to original branch first
        if self._original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', self._original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        # Clean up memory for deleted branches
        if cleanup_memory:
            try:
                from teaagent.memory import MemoryCatalog

                catalog = MemoryCatalog(self._root)
                for option, sandbox in self._sandboxes.items():
                    if keep_best and option == keep_best:
                        continue
                    # Quarantine memory for deleted branch
                    catalog.quarantine_by_branch(
                        sandbox._branch_name,
                        reason=f'Experiment branch {option} deleted during cleanup',
                    )
            except (AttributeError, ImportError, OSError, RuntimeError, ValueError):
                pass  # Continue with git cleanup even if memory cleanup fails

        for option, sandbox in self._sandboxes.items():
            if keep_best and option == keep_best:
                results[option] = True  # Kept, not deleted
                continue

            try:
                subprocess.run(
                    ['git', 'branch', '-D', sandbox._branch_name],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                results[option] = True
            except subprocess.CalledProcessError:
                results[option] = False

        return results

    def run_tests(
        self,
        test_command: list[str],
        timeout_seconds: int = 300,
    ) -> dict[str, TestExecutionResult]:
        """Run tests on all sandbox branches and collect results.

        Args:
            test_command: Test command to run (e.g., ['pytest', '-xvs']).
            timeout_seconds: Maximum time to wait for tests per branch.

        Returns:
            Dict mapping option names to their test results.
        """
        results: dict[str, TestExecutionResult] = {}

        if not is_git_repository(self._root):
            for option in self._options:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name='',
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=-1,
                    output='',
                    error='Not a git repository',
                )
            return results

        # Switch back to original branch first
        original_branch = self._original_branch
        if original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        for option, sandbox in self._sandboxes.items():
            try:
                # Switch to sandbox branch
                subprocess.run(
                    ['git', 'checkout', sandbox._branch_name],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Run tests with timeout
                start_time = time.time()
                try:
                    result = subprocess.run(
                        test_command,
                        cwd=self._root,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                    )
                    duration = time.time() - start_time
                    passed = result.returncode == 0

                    results[option] = TestExecutionResult(
                        option=option,
                        branch_name=sandbox._branch_name,
                        passed=passed,
                        duration_seconds=duration,
                        exit_code=result.returncode,
                        output=result.stdout,
                        error=result.stderr,
                    )
                except subprocess.TimeoutExpired:
                    duration = time.time() - start_time
                    results[option] = TestExecutionResult(
                        option=option,
                        branch_name=sandbox._branch_name,
                        passed=False,
                        duration_seconds=duration,
                        exit_code=-1,
                        output='',
                        error=f'Tests timed out after {timeout_seconds} seconds',
                    )
            except subprocess.CalledProcessError as e:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name=sandbox._branch_name,
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=e.returncode,
                    output='',
                    error=str(e),
                )
            except (FileNotFoundError, OSError) as e:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name=sandbox._branch_name,
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=-1,
                    output='',
                    error=str(e),
                )

        # Switch back to original branch
        if original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        return results
