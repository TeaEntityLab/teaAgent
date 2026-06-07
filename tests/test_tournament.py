"""Integration tests for tournament selection features."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from teaagent.tournament.benchmark import BenchmarkMetrics
from teaagent.tournament.branch_manager import TournamentBranchManager
from teaagent.tournament.comparator import TournamentComparator
from teaagent.tournament.hint_generator import ApproachHintGenerator


class TestApproachHintGenerator:
    """Test approach hint generator."""

    def test_generate_hints_optimize(self) -> None:
        """Test generating hints for optimization task."""
        generator = ApproachHintGenerator()
        hints = generator.generate_hints('Optimize the database query', 3)

        assert len(hints) == 3
        assert all(isinstance(h, str) for h in hints)
        assert len(hints) == len(set(hints))  # Hints should be distinct

    def test_generate_hints_refactor(self) -> None:
        """Test generating hints for refactoring task."""
        generator = ApproachHintGenerator()
        hints = generator.generate_hints('Refactor the legacy code', 2)

        assert len(hints) == 2
        assert any('refactor' in h.lower() or 'pattern' in h.lower() for h in hints)

    def test_generate_hints_default(self) -> None:
        """Test generating hints for generic task."""
        generator = ApproachHintGenerator()
        hints = generator.generate_hints('Implement something generic', 2)

        assert len(hints) == 2
        assert all('Approach' in h for h in hints)


class TestTournamentComparator:
    """Test tournament comparator."""

    def test_compare_approaches(self) -> None:
        """Test comparing multiple approaches."""
        comparator = TournamentComparator()

        metrics = [
            BenchmarkMetrics(
                approach_id='opt1',
                correctness=90.0,
                performance=80.0,
                code_quality=85.0,
                test_pass_rate=0.9,
                execution_time=1.0,
                lint_warnings=2,
                lines_changed=50,
                metadata={},
            ),
            BenchmarkMetrics(
                approach_id='opt2',
                correctness=95.0,
                performance=70.0,
                code_quality=90.0,
                test_pass_rate=0.95,
                execution_time=1.5,
                lint_warnings=1,
                lines_changed=30,
                metadata={},
            ),
        ]

        results = comparator.compare(metrics)

        assert len(results) == 2
        assert results[0].weighted_score >= results[1].weighted_score  # Sorted by score

    def test_weight_validation(self) -> None:
        """Test weight validation."""
        with pytest.raises(ValueError):
            TournamentComparator(
                tests_passed_weight=0.5, performance_weight=0.6, lint_passed_weight=0.2
            )

    def test_generate_comparison_table(self) -> None:
        """Test comparison table generation."""
        comparator = TournamentComparator()

        metrics = [
            BenchmarkMetrics(
                approach_id='opt1',
                correctness=90.0,
                performance=80.0,
                code_quality=85.0,
                test_pass_rate=0.9,
                execution_time=1.0,
                lint_warnings=2,
                lines_changed=50,
                metadata={},
            ),
        ]

        results = comparator.compare(metrics)
        table = comparator.generate_comparison_table(results)

        assert 'Approach' in table
        assert 'Correctness' in table
        assert 'opt1' in table

    def test_recommend_winner(self) -> None:
        """Test winner recommendation."""
        comparator = TournamentComparator()

        metrics = [
            BenchmarkMetrics(
                approach_id='opt1',
                correctness=90.0,
                performance=80.0,
                code_quality=85.0,
                test_pass_rate=0.9,
                execution_time=1.0,
                lint_warnings=2,
                lines_changed=50,
                metadata={},
            ),
            BenchmarkMetrics(
                approach_id='opt2',
                correctness=95.0,
                performance=85.0,
                code_quality=90.0,
                test_pass_rate=0.95,
                execution_time=0.8,
                lint_warnings=1,
                lines_changed=30,
                metadata={},
            ),
        ]

        results = comparator.compare(metrics)
        winner = comparator.recommend_winner(results)

        assert winner is not None
        assert winner.approach_id == 'opt2'  # Higher score

    def test_no_results(self) -> None:
        """Test with no results."""
        comparator = TournamentComparator()
        winner = comparator.recommend_winner([])

        assert winner is None


class TestTournamentBranchManager:
    """Test tournament branch manager."""

    @pytest.fixture
    def temp_root(self) -> Iterator[Path]:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=root, capture_output=True)
            subprocess.run(
                ['git', 'config', 'user.email', 'test@test.com'],
                cwd=root,
                capture_output=True,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'Test User'],
                cwd=root,
                capture_output=True,
            )
            # Create initial commit
            (root / 'test.txt').write_text('test')
            subprocess.run(['git', 'add', 'test.txt'], cwd=root, capture_output=True)
            subprocess.run(
                ['git', 'commit', '-m', 'Initial'], cwd=root, capture_output=True
            )
            yield root

    def test_create_branches(self, temp_root: Path) -> None:
        """Test creating tournament branches."""
        manager = TournamentBranchManager(temp_root)

        hints = ['Approach 1', 'Approach 2']
        branches = manager.create_branches(2, hints)

        assert len(branches) == 2
        assert all(b.branch_name.startswith('tournament-') for b in branches)
        assert len(manager.branches) == 2

    def test_cleanup_branches(self, temp_root: Path) -> None:
        """Test cleaning up tournament branches."""
        manager = TournamentBranchManager(temp_root)

        hints = ['Approach 1']
        manager.create_branches(1, hints)

        assert len(manager.branches) == 1

        manager.cleanup_branches()

        assert len(manager.branches) == 0

    def test_disk_space_check(self, temp_root: Path) -> None:
        """Test disk space checking."""
        manager = TournamentBranchManager(temp_root)

        # Request too many branches
        with pytest.raises(RuntimeError, match='Insufficient disk space'):
            manager.create_branches(1000, ['Approach'] * 1000)
