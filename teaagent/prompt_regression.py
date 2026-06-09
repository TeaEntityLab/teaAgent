"""Prompt regression suite for detecting model behavior changes (TASK-H5-001-02).

This module provides test cases and evaluation logic for detecting regression
in model behavior when prompts are updated or changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .eval_suite import EvalCategory, EvalTest


class RegressionSeverity(str, Enum):
    """Severity of regression detection."""

    CRITICAL = 'critical'  # Behavior completely changed
    HIGH = 'high'  # Significant behavior change
    MEDIUM = 'medium'  # Moderate behavior change
    LOW = 'low'  # Minor behavior change
    NONE = 'none'  # No regression detected


@dataclass
class PromptRegressionTest:
    """A prompt regression test case."""

    test_id: str
    name: str
    prompt: str
    expected_output: str
    expected_behavior: dict[str, Any] = field(default_factory=dict)
    tolerance_threshold: float = 0.9  # Similarity threshold for passing
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'name': self.name,
            'prompt': self.prompt,
            'expected_output': self.expected_output,
            'expected_behavior': self.expected_behavior,
            'tolerance_threshold': self.tolerance_threshold,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PromptRegressionTest':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            name=data['name'],
            prompt=data['prompt'],
            expected_output=data['expected_output'],
            expected_behavior=data.get('expected_behavior', {}),
            tolerance_threshold=data.get('tolerance_threshold', 0.9),
            metadata=data.get('metadata', {}),
        )


@dataclass
class RegressionResult:
    """Result of a regression test."""

    test_id: str
    actual_output: str
    similarity_score: float
    severity: RegressionSeverity
    behavior_match: dict[str, bool] = field(default_factory=dict)
    diff_details: dict[str, Any] = field(default_factory=dict)
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'actual_output': self.actual_output,
            'similarity_score': self.similarity_score,
            'severity': self.severity.value,
            'behavior_match': self.behavior_match,
            'diff_details': self.diff_details,
            'passed': self.passed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'RegressionResult':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            actual_output=data['actual_output'],
            similarity_score=data['similarity_score'],
            severity=RegressionSeverity(data['severity']),
            behavior_match=data.get('behavior_match', {}),
            diff_details=data.get('diff_details', {}),
            passed=data.get('passed', False),
        )


class PromptRegressionEvaluator:
    """Evaluator for prompt regression tests."""

    def __init__(self) -> None:
        """Initialize the regression evaluator."""
        pass

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        # Simple similarity calculation using word overlap
        # In production, use more sophisticated methods (e.g., embeddings)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def evaluate_behavior_match(
        self,
        actual_output: str,
        expected_behavior: dict[str, Any],
    ) -> dict[str, bool]:
        """Evaluate if actual output matches expected behavior.

        Args:
            actual_output: Actual model output.
            expected_behavior: Expected behavior criteria.

        Returns:
            Dictionary mapping behavior criteria to match status.
        """
        matches = {}

        # Check for expected keywords
        if 'keywords' in expected_behavior:
            keywords = expected_behavior['keywords']
            matches['keywords'] = all(
                keyword.lower() in actual_output.lower() for keyword in keywords
            )

        # Check for forbidden keywords
        if 'forbidden_keywords' in expected_behavior:
            forbidden = expected_behavior['forbidden_keywords']
            matches['forbidden_keywords'] = not any(
                keyword.lower() in actual_output.lower() for keyword in forbidden
            )

        # Check output length constraints
        if 'min_length' in expected_behavior:
            matches['min_length'] = (
                len(actual_output) >= expected_behavior['min_length']
            )

        if 'max_length' in expected_behavior:
            matches['max_length'] = (
                len(actual_output) <= expected_behavior['max_length']
            )

        # Check for specific patterns
        if 'patterns' in expected_behavior:
            import re

            patterns = expected_behavior['patterns']
            pattern_matches = []
            for pattern in patterns:
                if re.search(pattern, actual_output):
                    pattern_matches.append(True)
                else:
                    pattern_matches.append(False)
            matches['patterns'] = all(pattern_matches)

        return matches

    def determine_severity(
        self,
        similarity_score: float,
        behavior_match: dict[str, bool],
        tolerance_threshold: float,
    ) -> RegressionSeverity:
        """Determine regression severity based on similarity and behavior match.

        Args:
            similarity_score: Similarity score between expected and actual.
            behavior_match: Behavior match results.
            tolerance_threshold: Tolerance threshold for passing.

        Returns:
            Regression severity.
        """
        # Calculate overall behavior match score
        behavior_score = (
            sum(1 for match in behavior_match.values() if match) / len(behavior_match)
            if behavior_match
            else 1.0
        )

        # Combined score
        combined_score = (similarity_score + behavior_score) / 2

        if combined_score >= tolerance_threshold:
            return RegressionSeverity.NONE
        elif combined_score >= tolerance_threshold - 0.1:
            return RegressionSeverity.LOW
        elif combined_score >= tolerance_threshold - 0.2:
            return RegressionSeverity.MEDIUM
        elif combined_score >= tolerance_threshold - 0.3:
            return RegressionSeverity.HIGH
        else:
            return RegressionSeverity.CRITICAL

    def evaluate_regression(
        self,
        test: PromptRegressionTest,
        actual_output: str,
    ) -> RegressionResult:
        """Evaluate a prompt regression test.

        Args:
            test: Regression test to evaluate.
            actual_output: Actual model output.

        Returns:
            Regression result.
        """
        # Calculate similarity
        similarity_score = self.calculate_similarity(
            test.expected_output,
            actual_output,
        )

        # Evaluate behavior match
        behavior_match = self.evaluate_behavior_match(
            actual_output,
            test.expected_behavior,
        )

        # Determine severity
        severity = self.determine_severity(
            similarity_score,
            behavior_match,
            test.tolerance_threshold,
        )

        # Determine if passed
        passed = severity == RegressionSeverity.NONE

        # Generate diff details
        diff_details = {
            'expected_length': len(test.expected_output),
            'actual_length': len(actual_output),
            'length_diff': len(actual_output) - len(test.expected_output),
            'similarity_score': similarity_score,
            'tolerance_threshold': test.tolerance_threshold,
        }

        return RegressionResult(
            test_id=test.test_id,
            actual_output=actual_output,
            similarity_score=similarity_score,
            severity=severity,
            behavior_match=behavior_match,
            diff_details=diff_details,
            passed=passed,
        )

    def create_default_regression_tests(self) -> list[PromptRegressionTest]:
        """Create default prompt regression tests.

        Returns:
            List of default regression tests.
        """
        tests = []

        # Test 1: Code generation regression
        test1 = PromptRegressionTest(
            test_id='regression-001',
            name='Code Generation - Python Function',
            prompt='Write a Python function that calculates the factorial of a number.',
            expected_output='def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)',
            expected_behavior={
                'keywords': ['def', 'factorial', 'return'],
                'min_length': 50,
            },
            tolerance_threshold=0.8,
        )
        tests.append(test1)

        # Test 2: Explanation regression
        test2 = PromptRegressionTest(
            test_id='regression-002',
            name='Explanation - Technical Concept',
            prompt='Explain what a REST API is in simple terms.',
            expected_output='A REST API is a way for different software applications to communicate with each other over the internet using standard HTTP methods like GET, POST, PUT, and DELETE.',
            expected_behavior={
                'keywords': ['API', 'HTTP', 'communicate'],
                'min_length': 100,
            },
            tolerance_threshold=0.7,
        )
        tests.append(test2)

        # Test 3: Code analysis regression
        test3 = PromptRegressionTest(
            test_id='regression-003',
            name='Code Analysis - Bug Detection',
            prompt='Identify the bug in this code: x = 5; if x = 5: print("x is 5")',
            expected_output='The bug is in the if statement. It uses assignment (=) instead of comparison (==). The correct code should be: if x == 5: print("x is 5")',
            expected_behavior={
                'keywords': ['assignment', 'comparison', '=='],
                'forbidden_keywords': ['correct'],
            },
            tolerance_threshold=0.75,
        )
        tests.append(test3)

        return tests

    def convert_to_eval_test(self, regression_test: PromptRegressionTest) -> EvalTest:
        """Convert a regression test to an eval test.

        Args:
            regression_test: Regression test to convert.

        Returns:
            Eval test.
        """
        return EvalTest(
            test_id=regression_test.test_id,
            name=regression_test.name,
            category=EvalCategory.PROMPT_REGRESSION,
            description=f'Prompt regression test: {regression_test.name}',
            metadata={
                'prompt': regression_test.prompt,
                'expected_output': regression_test.expected_output,
                'expected_behavior': regression_test.expected_behavior,
                'tolerance_threshold': regression_test.tolerance_threshold,
            },
        )
