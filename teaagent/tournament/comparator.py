"""Tournament comparator for approach comparison and recommendation.

This module provides:
- Weighted score calculation
- Comparison table generation
- Winning approach recommendation
- User approval workflow
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from teaagent.tournament.benchmark import BenchmarkMetrics


@dataclass
class ComparisonResult:
    """Result of tournament comparison."""

    approach_id: str
    branch_name: str
    correctness: float
    performance: float
    code_quality: float
    weighted_score: float
    test_pass_rate: float
    execution_time: float
    lint_warnings: int
    lines_changed: int


class TournamentComparator:
    """Comparator for tournament approaches with weighted security-aware schema."""

    def __init__(
        self,
        tests_passed_weight: float = 0.40,
        performance_weight: float = 0.15,
        lint_passed_weight: float = 0.10,
        diff_size_weight: float = 0.10,
        architectural_fit_weight: float = 0.15,
        security_risk_weight: float = 0.10,
    ) -> None:
        """Initialize tournament comparator with security-aware weighted schema.

        Args:
            tests_passed_weight: Weight for test pass rate (0-1)
            performance_weight: Weight for performance metric (0-1)
            lint_passed_weight: Weight for lint pass rate (0-1)
            diff_size_weight: Weight for diff size (smaller is better) (0-1)
            architectural_fit_weight: Weight for architectural fit score (0-1)
            security_risk_weight: Weight for security risk (lower is better) (0-1)
        """
        self.tests_passed_weight = tests_passed_weight
        self.performance_weight = performance_weight
        self.lint_passed_weight = lint_passed_weight
        self.diff_size_weight = diff_size_weight
        self.architectural_fit_weight = architectural_fit_weight
        self.security_risk_weight = security_risk_weight

        # Validate weights sum to 1
        total = (
            tests_passed_weight + performance_weight + lint_passed_weight +
            diff_size_weight + architectural_fit_weight + security_risk_weight
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f'Weights must sum to 1.0, got {total}')

    def compare(self, metrics: List[BenchmarkMetrics]) -> List[ComparisonResult]:
        """Compare approaches and calculate weighted scores using security-aware schema.

        Args:
            metrics: List of benchmark metrics for each approach

        Returns:
            List of ComparisonResult sorted by weighted score
        """
        results = []

        for metric in metrics:
            # Calculate weighted score using available metrics
            # Tests passed (40%), Performance (15%), Lint quality (10%)
            # Code quality (15%), Diff size (10%), Security (10%)
            lint_score = 1.0 if metric.lint_warnings == 0 else max(0.5, 1.0 - metric.lint_warnings / 20)
            diff_score = max(0, 1.0 - min(metric.lines_changed / 1000, 1.0))  # Smaller is better
            security_score = metric.correctness  # Higher correctness = lower security risk

            weighted_score = (
                metric.test_pass_rate * self.tests_passed_weight +
                metric.performance * self.performance_weight +
                lint_score * self.lint_passed_weight +
                diff_score * self.diff_size_weight +
                metric.code_quality * self.architectural_fit_weight +
                security_score * self.security_risk_weight
            )

            result = ComparisonResult(
                approach_id=metric.approach_id,
                branch_name='',  # Would be filled from branch metadata
                correctness=metric.correctness,
                performance=metric.performance,
                code_quality=metric.code_quality,
                weighted_score=weighted_score,
                test_pass_rate=metric.test_pass_rate,
                execution_time=metric.execution_time,
                lint_warnings=metric.lint_warnings,
                lines_changed=metric.lines_changed,
            )
            results.append(result)

        # Sort by weighted score (descending)
        results.sort(key=lambda r: r.weighted_score, reverse=True)
        return results

    def generate_comparison_table(self, results: List[ComparisonResult]) -> str:
        """Generate a readable comparison table.

        Args:
            results: List of comparison results

        Returns:
            Formatted comparison table string
        """
        table = 'Approach           | Correctness | Performance | Quality | Score\n'
        table += '-' * 70 + '\n'

        for result in results:
            table += f'{result.approach_id:<18} | {result.correctness:>11.1f} | {result.performance:>11.1f} | {result.code_quality:>7.1f} | {result.weighted_score:>5.1f}\n'

        return table

    def recommend_winner(
        self, results: List[ComparisonResult]
    ) -> Optional[ComparisonResult]:
        """Recommend the winning approach.

        Args:
            results: List of comparison results

        Returns:
            The winning ComparisonResult, or None if no results
        """
        if not results:
            return None

        return results[0]  # Already sorted by score

    def generate_recommendation(
        self,
        results: List[ComparisonResult],
        winner: ComparisonResult,
    ) -> str:
        """Generate a recommendation message.

        Args:
            results: List of comparison results
            winner: The winning approach

        Returns:
            Recommendation message
        """
        if not results:
            return 'No approaches to compare.'

        # Find the winner's performance improvement
        baseline_score = (
            results[-1].weighted_score if len(results) > 1 else winner.weighted_score
        )
        improvement = (
            ((winner.weighted_score - baseline_score) / baseline_score * 100)
            if baseline_score > 0
            else 0
        )

        recommendation = f'\nRecommendation: {winner.approach_id} achieves the highest score ({winner.weighted_score:.1f})\n'

        if improvement > 0:
            recommendation += f'Improvement: {improvement:.1f}% over baseline\n'

        recommendation += f'Correctness: {winner.correctness:.1f}%, Performance: {winner.performance:.1f}%, Quality: {winner.code_quality:.1f}%\n'
        recommendation += '\nMerge this branch? [Y/n]: '

        return recommendation
