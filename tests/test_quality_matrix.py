"""Tests for dynamic test-driven quality matrix (TASK-008)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest

from teaagent.git_sandbox import ParallelExperimentStack, TestExecutionResult


class QualityMatrixTests(unittest.TestCase):
    def test_test_result_dataclass(self) -> None:
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
        self.assertEqual(result.option, 'optA')
        self.assertTrue(result.passed)
        self.assertEqual(result.duration_seconds, 5.5)
        self.assertEqual(result.exit_code, 0)

    def test_parallel_stack_run_tests_non_git_repo(self) -> None:
        """Test run_tests on non-git repository."""
        with tempfile.TemporaryDirectory() as tmp:
            stack = ParallelExperimentStack(tmp, 'run-123', ['optA', 'optB'])
            results = stack.run_tests(['echo', 'test'])

            self.assertEqual(len(results), 2)
            for _option, result in results.items():
                self.assertFalse(result.passed)
                self.assertIn('Not a git repository', result.error)

    def test_parallel_stack_run_tests_with_sandboxes(self) -> None:
        """Test run_tests with actual git sandboxes."""
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

            stack = ParallelExperimentStack(tmp, 'run-123', ['optA', 'optB'])
            stack.start_all()

            # Run a simple command instead of pytest
            results = stack.run_tests(['echo', 'test'])

            self.assertEqual(len(results), 2)
            for option, result in results.items():
                self.assertIn(option, ['optA', 'optB'])
                # Echo should pass
                self.assertTrue(result.passed)

    def test_parallel_stack_run_tests_timeout(self) -> None:
        """Test run_tests with timeout."""
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

            stack = ParallelExperimentStack(tmp, 'run-123', ['optA'])
            stack.start_all()

            # Run a command that will timeout
            results = stack.run_tests(['sleep', '10'], timeout_seconds=1)

            self.assertEqual(len(results), 1)
            result = results['optA']
            self.assertFalse(result.passed)
            self.assertIn('timed out', result.error.lower())

    def test_parallel_stack_run_tests_failing_command(self) -> None:
        """Test run_tests with a failing command."""
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

            stack = ParallelExperimentStack(tmp, 'run-123', ['optA'])
            stack.start_all()

            # Run a command that will fail
            results = stack.run_tests(['false'])

            self.assertEqual(len(results), 1)
            result = results['optA']
            self.assertFalse(result.passed)
            self.assertEqual(result.exit_code, 1)

    def test_parallel_stack_run_tests_multiple_branches(self) -> None:
        """Test run_tests across multiple branches."""
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

            stack = ParallelExperimentStack(tmp, 'run-123', ['optA', 'optB', 'optC'])
            stack.start_all()

            # Run a simple command
            results = stack.run_tests(['echo', 'test'])

            self.assertEqual(len(results), 3)
            for option in ['optA', 'optB', 'optC']:
                self.assertIn(option, results)
                self.assertTrue(results[option].passed)


if __name__ == '__main__':
    unittest.main()
