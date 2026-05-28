"""Integration tests for parallel experiments workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.git_sandbox import ParallelExperimentStack


class ParallelExperimentsIntegrationTests(unittest.TestCase):
    """Integration tests for parallel experiment workflow."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_id = 'test-run-001'
        self.options = ['optA', 'optB', 'optC']
        self.stack = ParallelExperimentStack(
            root=self.temp_dir, run_id=self.run_id, options=self.options
        )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_parallel_experiment_creation_and_cleanup(self) -> None:
        """Test creating multiple parallel experiments and cleanup."""
        # Create a base git repository
        import subprocess

        subprocess.run(
            ['git', 'init'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (self.temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Start parallel experiments
        results = self.stack.start_all(auto_stash=False)

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results.values()))

        # Verify branches exist
        result = subprocess.run(
            ['git', 'branch', '--list'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn(f'sandbox-{self.run_id}-optA', result.stdout)
        self.assertIn(f'sandbox-{self.run_id}-optB', result.stdout)
        self.assertIn(f'sandbox-{self.run_id}-optC', result.stdout)

        # Cleanup
        self.stack.cleanup_all()

        # Verify branches are deleted
        result = subprocess.run(
            ['git', 'branch', '--list'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertNotIn(f'sandbox-{self.run_id}-optA', result.stdout)
        self.assertNotIn(f'sandbox-{self.run_id}-optB', result.stdout)
        self.assertNotIn(f'sandbox-{self.run_id}-optC', result.stdout)

    def test_experiment_isolation(self) -> None:
        """Test that parallel experiments are isolated from each other."""
        import subprocess

        # Create a base git repository
        subprocess.run(
            ['git', 'init'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (self.temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Start parallel experiments
        results = self.stack.start_all(auto_stash=False)

        # Modify optA
        optA_branch = results['optA'].branch_name
        subprocess.run(
            ['git', 'checkout', optA_branch],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        (self.temp_dir / 'test.txt').write_text('optA content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'optA change'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Modify optB
        optB_branch = results['optB'].branch_name
        subprocess.run(
            ['git', 'checkout', optB_branch],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        (self.temp_dir / 'test.txt').write_text('optB content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'optB change'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Verify isolation: optA should have optA content
        subprocess.run(
            ['git', 'checkout', optA_branch],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        optA_content = (self.temp_dir / 'test.txt').read_text(encoding='utf-8')
        self.assertEqual(optA_content, 'optA content')

        # Verify isolation: optB should have optB content
        subprocess.run(
            ['git', 'checkout', optB_branch],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        optB_content = (self.temp_dir / 'test.txt').read_text(encoding='utf-8')
        self.assertEqual(optB_content, 'optB content')

        # Cleanup
        self.stack.cleanup_all()

    def test_experiment_selection_and_merge(self) -> None:
        """Test getting sandbox for a specific option."""
        import subprocess

        # Create a base git repository
        subprocess.run(
            ['git', 'init'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (self.temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Start parallel experiments
        results = self.stack.start_all(auto_stash=False)

        # Get sandbox for optA
        sandbox = self.stack.get_sandbox('optA')

        self.assertIsNotNone(sandbox)
        self.assertEqual(sandbox._branch_name, results['optA'].branch_name)

        # Cleanup
        self.stack.cleanup_all()

    def test_branch_comparison(self) -> None:
        """Test comparing experimental branches."""
        import subprocess

        # Create a base git repository
        subprocess.run(
            ['git', 'init'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (self.temp_dir / 'test.txt').write_text('initial content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Start parallel experiments
        results = self.stack.start_all(auto_stash=False)

        # Modify optA
        optA_branch = results['optA'].branch_name
        subprocess.run(
            ['git', 'checkout', optA_branch],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )
        (self.temp_dir / 'test.txt').write_text('optA content', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=self.temp_dir, check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'commit', '-m', 'optA change'],
            cwd=self.temp_dir,
            check=True,
            capture_output=True,
        )

        # Compare branches
        comparisons = self.stack.compare_branches()

        self.assertIn('optA', comparisons)
        self.assertIn('optB', comparisons)
        self.assertIn('optC', comparisons)

        # optA should have changes
        self.assertGreater(comparisons['optA'].get('files_changed', 0), 0)

        # Cleanup
        self.stack.cleanup_all()


if __name__ == '__main__':
    unittest.main()
