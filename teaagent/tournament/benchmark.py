"""Benchmark runner for tournament approaches.

This module provides:
- Correctness measurement (test pass rate)
- Performance measurement (execution time, memory)
- Code quality measurement (lint warnings, lines changed)
- Metric normalization
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from teaagent.swarm import SubagentResult
    from teaagent.tournament.comparator import TournamentComparator

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetrics:
    """Benchmark metrics for an approach."""

    approach_id: str
    correctness: float  # 0-100 scale
    performance: float  # 0-100 scale
    code_quality: float  # 0-100 scale
    test_pass_rate: float
    execution_time: float
    lint_warnings: int
    lines_changed: int
    metadata: Dict[str, Optional[str]]


def metrics_from_subagent_result(result: SubagentResult) -> BenchmarkMetrics:
    """Build tournament metrics from a swarm subagent result."""
    test_results = result.test_results or {}
    passed = int(test_results.get('passed', 0))
    failed = int(test_results.get('failed', 0))
    total = passed + failed
    if total > 0:
        test_pass_rate = passed / total
    else:
        test_pass_rate = 1.0 if result.success else 0.0
    execution_time = max(result.execution_time_ms / 1000.0, 0.001)
    lint_warnings = int(test_results.get('lint_warnings', 0))
    lines_changed = int(test_results.get('lines_changed', 0))
    correctness = test_pass_rate * 100.0
    performance = min(100.0, max(0.0, (1.0 / execution_time) * 50.0))
    code_quality = max(0.0, 100.0 - lint_warnings * 2 - lines_changed * 0.1)
    return BenchmarkMetrics(
        approach_id=result.task_id,
        correctness=correctness,
        performance=performance,
        code_quality=code_quality,
        test_pass_rate=test_pass_rate,
        execution_time=execution_time,
        lint_warnings=lint_warnings,
        lines_changed=lines_changed,
        metadata={'branch_name': result.branch_name or ''},
    )


def select_winner_from_subagent_results(
    results: List[SubagentResult],
    *,
    comparator: TournamentComparator | None = None,
) -> tuple[Optional[str], float, Optional[SubagentResult]]:
    """Rank subagent branches with the security-aware tournament comparator."""
    if not results:
        return None, 0.0, None
    if len(results) == 1:
        only = results[0]
        score = 1.0 if only.success else 0.0
        return only.task_id, score, only
    from teaagent.tournament.comparator import TournamentComparator

    metrics = [metrics_from_subagent_result(item) for item in results]
    comp = comparator or TournamentComparator()
    compared = comp.compare(metrics)
    winner = comp.recommend_winner(compared)
    if winner is None:
        fallback = next((item for item in results if item.success), results[0])
        return fallback.task_id, 0.0, fallback
    best = next((item for item in results if item.task_id == winner.approach_id), None)
    return winner.approach_id, winner.weighted_score, best


class BenchmarkRunner:
    """Runner for benchmarking tournament approaches."""

    def __init__(self, root: Path, baseline_branch: str = 'main') -> None:
        """Initialize benchmark runner.

        Args:
            root: The workspace root directory
            baseline_branch: The baseline branch for comparison
        """
        self.root = Path(root).resolve()
        self.baseline_branch = baseline_branch

    def benchmark_approach(
        self,
        branch: str,
        approach_id: str,
    ) -> BenchmarkMetrics:
        """Benchmark a single approach.

        Args:
            branch: The branch to benchmark
            output: The approach ID

        Returns:
            BenchmarkMetrics
        """
        # Switch to branch
        subprocess.run(
            ['git', 'checkout', branch],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )

        # Measure correctness (test pass rate)
        test_pass_rate = self._measure_correctness()

        # Measure performance (execution time)
        execution_time = self._measure_performance()

        # Measure code quality (lint warnings, lines changed)
        lint_warnings, lines_changed = self._measure_code_quality(branch)

        # Normalize metrics to 0-100 scale
        correctness = test_pass_rate * 100
        performance = self._normalize_performance(execution_time)
        code_quality = self._normalize_code_quality(lint_warnings, lines_changed)

        return BenchmarkMetrics(
            approach_id=approach_id,
            correctness=correctness,
            performance=performance,
            code_quality=code_quality,
            test_pass_rate=test_pass_rate,
            execution_time=execution_time,
            lint_warnings=lint_warnings,
            lines_changed=lines_changed,
            metadata={},
        )

    def _measure_correctness(self) -> float:
        """Measure test pass rate.

        Returns:
            Test pass rate (0-1 scale)
        """
        try:
            # Run tests
            result = subprocess.run(
                ['pytest', '--tb=no', '-q'],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse output for pass rate
            # Simplified parsing - in production would be more sophisticated
            output = result.stdout + result.stderr
            if 'passed' in output:
                # Extract pass count
                parts = output.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            passed = int(parts[i - 1])
                            # Assume total tests is passed + failed
                            total = passed
                            if 'failed' in output:
                                for j, p in enumerate(parts):
                                    if p == 'failed' and j > 0:
                                        total += int(parts[j - 1])
                                        break
                            return passed / total if total > 0 else 0.0
                        except ValueError:
                            pass

            return 1.0 if result.returncode == 0 else 0.0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 0.0
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            logger.debug('Benchmark correctness measurement failed: %s', exc)
            return 0.0

    def _measure_performance(self) -> float:
        """Measure execution time via a lightweight pytest collection pass."""
        import time

        started = time.perf_counter()
        try:
            subprocess.run(
                ['pytest', '--collect-only', '-q'],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 30.0
        except (OSError, ValueError, subprocess.SubprocessError):
            return 30.0
        return max(time.perf_counter() - started, 0.001)

    def _measure_code_quality(self, branch: str) -> tuple[int, int]:
        """Measure code quality metrics.

        Args:
            branch: The branch to measure

        Returns:
            Tuple of (lint_warnings, lines_changed)
        """
        # Get diff from baseline
        try:
            result = subprocess.run(
                ['git', 'diff', self.baseline_branch, branch, '--stat'],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse lines changed
            lines_changed = 0
            for line in result.stdout.split('\n'):
                if 'insertion' in line or 'deletion' in line:
                    try:
                        parts = line.split()
                        for part in parts:
                            if part.isdigit():
                                lines_changed += int(part)
                    except ValueError:
                        pass

            # Run linter to count warnings
            lint_warnings = 0
            try:
                lint_result = subprocess.run(
                    ['ruff', 'check', '.'],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                # Count warning lines
                lint_warnings = len(
                    [line for line in lint_result.stdout.split('\n') if line.strip()]
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            return lint_warnings, lines_changed
        except subprocess.CalledProcessError:
            return 0, 0

    def _normalize_performance(self, execution_time: float) -> float:
        """Normalize performance metric to 0-100 scale.

        Args:
            execution_time: Execution time in seconds

        Returns:
            Normalized performance score (0-100)
        """
        # Faster is better, so invert the scale
        # Assume baseline is 1.0, normalize around that
        if execution_time <= 0:
            return 100.0
        baseline = 1.0
        ratio = baseline / execution_time
        # Clamp to 0-100
        return min(100.0, max(0.0, ratio * 50))

    def _normalize_code_quality(self, lint_warnings: int, lines_changed: int) -> float:
        """Normalize code quality metric to 0-100 scale.

        Args:
            lint_warnings: Number of lint warnings
            lines_changed: Number of lines changed

        Returns:
            Normalized code quality score (0-100)
        """
        # Fewer warnings and fewer changes is better
        warning_score = max(0, 100 - lint_warnings * 2)
        change_score = max(0, 100 - lines_changed * 0.1)
        return (warning_score + change_score) / 2
