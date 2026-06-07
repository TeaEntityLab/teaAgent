"""Integration tests for tournament selection features."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from teaagent.swarm import SubagentResult
from teaagent.tournament.benchmark import (
    BenchmarkMetrics,
    BenchmarkRunner,
    metrics_from_subagent_result,
    select_winner_from_subagent_results,
)
from teaagent.tournament.branch_manager import TournamentBranchManager
from teaagent.tournament.comparator import ComparisonResult, TournamentComparator
from teaagent.tournament.hint_generator import ApproachHintGenerator
from teaagent.tournament.parallel_executor import AgentResult, ParallelExecutor


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


class TestBenchmarkMetrics:
    """Tests for BenchmarkMetrics dataclass and related functions."""

    def test_metrics_from_subagent_result_with_tests(self) -> None:
        """Test building metrics from a subagent result with test data."""
        result = SubagentResult(
            task_id='opt1',
            success=True,
            branch_name='tournament-0',
            execution_time_ms=2000.0,
            test_results={
                'passed': '8',
                'failed': '2',
                'lint_warnings': '3',
                'lines_changed': '50',
            },
        )
        metrics = metrics_from_subagent_result(result)

        assert metrics.approach_id == 'opt1'
        assert metrics.test_pass_rate == 0.8  # 8 passed out of 10
        assert metrics.correctness == 80.0
        assert metrics.lint_warnings == 3
        assert metrics.lines_changed == 50
        assert metrics.metadata['branch_name'] == 'tournament-0'

    def test_metrics_from_subagent_result_no_tests(self) -> None:
        """Test building metrics when no test data is available."""
        result = SubagentResult(
            task_id='opt2',
            success=True,
            branch_name=None,
            execution_time_ms=1000.0,
            test_results={},
        )
        metrics = metrics_from_subagent_result(result)

        assert metrics.approach_id == 'opt2'
        assert metrics.test_pass_rate == 1.0  # defaults to 1.0 on success
        assert metrics.correctness == 100.0

    def test_metrics_from_subagent_result_failed_no_tests(self) -> None:
        """Test building metrics when execution failed without test data."""
        result = SubagentResult(
            task_id='opt3',
            success=False,
            branch_name=None,
            execution_time_ms=500.0,
            test_results={},
        )
        metrics = metrics_from_subagent_result(result)

        assert metrics.test_pass_rate == 0.0  # defaults to 0.0 on failure

    def test_select_winner_empty(self) -> None:
        """Test winner selection with empty results."""
        winner_id, score, winner = select_winner_from_subagent_results([])
        assert winner_id is None
        assert score == 0.0
        assert winner is None

    def test_select_winner_single(self) -> None:
        """Test winner selection with a single result."""
        result = SubagentResult(task_id='opt1', success=True, execution_time_ms=1000.0)
        winner_id, score, winner = select_winner_from_subagent_results([result])

        assert winner_id == 'opt1'
        assert score > 0
        assert winner is not None

    def test_select_winner_multiple(self) -> None:
        """Test winner selection ranks by comparator."""
        results = [
            SubagentResult(
                task_id='opt1',
                success=True,
                execution_time_ms=1000.0,
                test_results={'passed': '10', 'failed': '0'},
            ),
            SubagentResult(
                task_id='opt2',
                success=True,
                execution_time_ms=2000.0,
                test_results={'passed': '5', 'failed': '5'},
            ),
        ]
        winner_id, score, winner = select_winner_from_subagent_results(results)

        assert winner_id == 'opt1'
        assert winner is not None
        assert score > 0

    def test_benchmark_metrics_defaults(self) -> None:
        """Test BenchmarkMetrics dataclass construction."""
        metrics = BenchmarkMetrics(
            approach_id='test',
            correctness=90.0,
            performance=80.0,
            code_quality=85.0,
            test_pass_rate=0.9,
            execution_time=1.0,
            lint_warnings=2,
            lines_changed=50,
            metadata={},
        )
        assert metrics.approach_id == 'test'
        assert metrics.correctness == 90.0
        assert isinstance(metrics.metadata, dict)


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_comparison_result_construction(self) -> None:
        """Test ComparisonResult dataclass."""
        result = ComparisonResult(
            approach_id='opt1',
            branch_name='tournament-0',
            correctness=90.0,
            performance=80.0,
            code_quality=85.0,
            weighted_score=85.5,
            test_pass_rate=0.9,
            execution_time=1.0,
            lint_warnings=2,
            lines_changed=50,
        )
        assert result.approach_id == 'opt1'
        assert result.weighted_score == 85.5


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_agent_result_construction(self) -> None:
        """Test AgentResult dataclass."""
        result = AgentResult(
            approach_id='opt1',
            branch_name='tournament-0',
            success=True,
            output='done',
            error=None,
            execution_time=1.5,
            metadata={'branch': 'tournament-0'},
        )
        assert result.approach_id == 'opt1'
        assert result.success is True
        assert result.error is None


class TestTournamentComparatorExtended:
    """Extended tests for TournamentComparator."""

    def test_generate_recommendation(self) -> None:
        """Test recommendation message generation."""
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

        msg = comparator.generate_recommendation(results, winner)
        assert 'Recommendation' in msg
        assert 'opt2' in msg
        assert 'Improvement' in msg

    def test_generate_recommendation_no_results(self) -> None:
        """Test recommendation with empty results."""
        comparator = TournamentComparator()
        msg = comparator.generate_recommendation([], None)
        assert 'No approaches' in msg

    def test_normalize_performance(self) -> None:
        """Test performance normalization."""
        runner = BenchmarkRunner.__new__(BenchmarkRunner)
        # _normalize_performance is a regular method
        # Test via its public contract
        # Use a small helper to call the private method
        # Zero time → max score
        import types

        from teaagent.tournament.benchmark import BenchmarkRunner as BR

        norm_perf = types.MethodType(BR._normalize_performance, runner)
        assert norm_perf(0.0) == 100.0
        assert norm_perf(1.0) == 50.0
        assert norm_perf(2.0) == 25.0

    def test_normalize_code_quality(self) -> None:
        """Test code quality normalization."""
        runner = BenchmarkRunner.__new__(BenchmarkRunner)
        import types

        norm_qual = types.MethodType(BenchmarkRunner._normalize_code_quality, runner)
        # No warnings, no changes → 100
        assert norm_qual(0, 0) == 100.0
        # Some warnings and changes
        score = norm_qual(5, 100)
        assert 0 < score < 100
        # Extreme values
        assert norm_qual(100, 10000) >= 0


class TestParallelExecutorInit:
    """Tests for ParallelExecutor basic construction."""

    def test_init_defaults(self, tmp_path: Path) -> None:
        """Test ParallelExecutor initialization."""
        executor = ParallelExecutor(tmp_path)
        assert executor.root == tmp_path.resolve()
        assert executor.timeout == 300
        assert executor.results == []

    def test_init_custom_timeout(self, tmp_path: Path) -> None:
        """Test ParallelExecutor with custom timeout."""
        executor = ParallelExecutor(tmp_path, timeout=600)
        assert executor.timeout == 600

    def test_execute_parallel_mismatched_args(self, tmp_path: Path) -> None:
        """Test validation of branches/approach_hints length match."""
        executor = ParallelExecutor(tmp_path)
        with pytest.raises(ValueError, match='must have same length'):
            executor.execute_parallel('task', ['b1'], ['h1', 'h2'])

    def test_agent_result_metadata(self) -> None:
        """Test AgentResult with error state."""
        result = AgentResult(
            approach_id='opt1',
            branch_name='tournament-0',
            success=False,
            output='',
            error='Something went wrong',
            execution_time=0.5,
            metadata={},
        )
        assert result.success is False
        assert result.error == 'Something went wrong'
