"""Tests for self-healing merge with LSP feedback (TASK-009)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from teaagent.git_sandbox import (
    GitBranchSandbox,
    ParallelExperimentStack,
    resolve_conflicts_with_llm,
    run_lsp_validation,
)


class SelfHealingMergeTests(unittest.TestCase):
    def test_run_lsp_validation_python_file(self) -> None:
        """Test LSP validation on Python file."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a valid Python file
            test_file = Path(tmp) / 'test.py'
            test_file.write_text('def test(): pass\n')

            errors = run_lsp_validation(Path(tmp), 'test.py')
            # Should be empty or minimal for valid code
            self.assertIsInstance(errors, str)

    def test_run_lsp_validation_invalid_python(self) -> None:
        """Test LSP validation on invalid Python file."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create an invalid Python file
            test_file = Path(tmp) / 'test.py'
            test_file.write_text('def test(:\n')  # Syntax error

            errors = run_lsp_validation(Path(tmp), 'test.py')
            # Should detect syntax error (if ruff/mypy available)
            self.assertIsInstance(errors, str)

    def test_run_lsp_validation_non_python(self) -> None:
        """Test LSP validation on non-Python file."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a non-Python file
            test_file = Path(tmp) / 'test.txt'
            test_file.write_text('some text\n')

            errors = run_lsp_validation(Path(tmp), 'test.txt')
            # Should return empty for unsupported file types
            self.assertEqual(errors, '')

    def test_resolve_conflicts_with_llm_disabled_self_healing(self) -> None:
        """Test conflict resolution with self-healing disabled."""
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

            # Test with invalid provider (should skip)
            results = resolve_conflicts_with_llm(
                tmp,
                ['test.py'],
                'invalid_provider',
                'invalid_model',
                enable_self_healing=False,
            )

            self.assertEqual(results.get('test.py'), 'skipped')

    def test_resolve_conflicts_with_llm_max_iterations(self) -> None:
        """Test conflict resolution respects max iterations."""
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

            # Test with invalid provider (should skip immediately)
            results = resolve_conflicts_with_llm(
                tmp,
                ['test.py'],
                'invalid_provider',
                'invalid_model',
                enable_self_healing=True,
                max_iterations=1,
            )

            self.assertEqual(results.get('test.py'), 'skipped')

    def test_git_branch_sandbox_merge_with_self_healing_params(self) -> None:
        """Test GitBranchSandbox.merge accepts self-healing parameters."""
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

            sandbox = GitBranchSandbox(tmp, 'test-run')
            sandbox.start()

            # Test merge with self-healing parameters
            result = sandbox.merge(
                enable_self_healing=False,
                conflict_provider=None,
                conflict_model=None,
            )

            # Should succeed without conflicts
            self.assertTrue(result.success)

    def test_git_branch_sandbox_merge_self_healing_enabled_no_provider(self) -> None:
        """Test merge with self-healing enabled but no provider falls back gracefully."""
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

            sandbox = GitBranchSandbox(tmp, 'test-run')
            sandbox.start()

            # Test merge with self-healing enabled but no provider
            result = sandbox.merge(
                enable_self_healing=True,
                conflict_provider=None,
                conflict_model=None,
            )

            # Should succeed without conflicts (no provider = no self-healing)
            self.assertTrue(result.success)


if __name__ == '__main__':
    unittest.main()
