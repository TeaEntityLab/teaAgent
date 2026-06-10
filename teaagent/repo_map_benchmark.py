"""Repo-map benchmark automation for testing codebase understanding (TASK-H5-001-03).

experimental — unwired

This module provides automated benchmarking for repo-map functionality to ensure
it works correctly across different codebase structures and sizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .eval_suite import EvalCategory, EvalTest


class BenchmarkMetric(str, Enum):
    """Types of benchmark metrics."""

    ACCURACY = 'accuracy'  # Accuracy of repo-map results
    COVERAGE = 'coverage'  # Codebase coverage
    PERFORMANCE = 'performance'  # Performance metrics
    SCALABILITY = 'scalability'  # Scalability with large codebases


@dataclass
class RepoMapBenchmark:
    """A repo-map benchmark test case."""

    benchmark_id: str
    name: str
    codebase_path: str
    query: str
    expected_files: set[str] = field(default_factory=set)
    expected_functions: set[str] = field(default_factory=set)
    expected_classes: set[str] = field(default_factory=set)
    max_duration_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'benchmark_id': self.benchmark_id,
            'name': self.name,
            'codebase_path': self.codebase_path,
            'query': self.query,
            'expected_files': list(self.expected_files),
            'expected_functions': list(self.expected_functions),
            'expected_classes': list(self.expected_classes),
            'max_duration_seconds': self.max_duration_seconds,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'RepoMapBenchmark':
        """Create from dictionary."""
        return cls(
            benchmark_id=data['benchmark_id'],
            name=data['name'],
            codebase_path=data['codebase_path'],
            query=data['query'],
            expected_files=set(data.get('expected_files', [])),
            expected_functions=set(data.get('expected_functions', [])),
            expected_classes=set(data.get('expected_classes', [])),
            max_duration_seconds=data.get('max_duration_seconds', 30.0),
            metadata=data.get('metadata', {}),
        )


@dataclass
class BenchmarkResult:
    """Result of a repo-map benchmark."""

    benchmark_id: str
    actual_files: set[str] = field(default_factory=set)
    actual_functions: set[str] = field(default_factory=set)
    actual_classes: set[str] = field(default_factory=set)
    duration_seconds: float = 0.0
    file_accuracy: float = 0.0
    function_accuracy: float = 0.0
    class_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    passed: bool = False
    performance_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'benchmark_id': self.benchmark_id,
            'actual_files': list(self.actual_files),
            'actual_functions': list(self.actual_functions),
            'actual_classes': list(self.actual_classes),
            'duration_seconds': self.duration_seconds,
            'file_accuracy': self.file_accuracy,
            'function_accuracy': self.function_accuracy,
            'class_accuracy': self.class_accuracy,
            'overall_accuracy': self.overall_accuracy,
            'passed': self.passed,
            'performance_metrics': self.performance_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BenchmarkResult':
        """Create from dictionary."""
        return cls(
            benchmark_id=data['benchmark_id'],
            actual_files=set(data.get('actual_files', [])),
            actual_functions=set(data.get('actual_functions', [])),
            actual_classes=set(data.get('actual_classes', [])),
            duration_seconds=data.get('duration_seconds', 0.0),
            file_accuracy=data.get('file_accuracy', 0.0),
            function_accuracy=data.get('function_accuracy', 0.0),
            class_accuracy=data.get('class_accuracy', 0.0),
            overall_accuracy=data.get('overall_accuracy', 0.0),
            passed=data.get('passed', False),
            performance_metrics=data.get('performance_metrics', {}),
        )


class RepoMapBenchmarkRunner:
    """Runner for repo-map benchmarks."""

    def __init__(self) -> None:
        """Initialize the benchmark runner."""
        pass

    def calculate_accuracy(self, expected: set[str], actual: set[str]) -> float:
        """Calculate accuracy between expected and actual results.

        Args:
            expected: Expected set of items.
            actual: Actual set of items.

        Returns:
            Accuracy score between 0.0 and 1.0.
        """
        if not expected and not actual:
            return 1.0
        if not expected:
            return 0.0

        # Calculate precision and recall
        true_positives = len(expected.intersection(actual))
        false_positives = len(actual - expected)
        false_negatives = len(expected - actual)

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )

        # F1 score
        if precision + recall > 0:
            return 2 * (precision * recall) / (precision + recall)
        return 0.0

    def run_benchmark(
        self,
        benchmark: RepoMapBenchmark,
        codebase_root: str | Path,
    ) -> BenchmarkResult:
        """Run a repo-map benchmark.

        Args:
            benchmark: Benchmark to run.
            codebase_root: Root directory of the codebase.

        Returns:
            Benchmark result.
        """
        import time

        root = Path(codebase_root).resolve()
        result = BenchmarkResult(benchmark_id=benchmark.benchmark_id)

        start_time = time.time()

        try:
            # Simulate repo-map query execution
            # In production, this would call the actual repo-map implementation
            actual_files = self._execute_repo_map_query(
                root,
                benchmark.query,
                benchmark.metadata,
            )

            # Extract functions and classes from files
            actual_functions = self._extract_functions(root, actual_files)
            actual_classes = self._extract_classes(root, actual_files)

            result.actual_files = actual_files
            result.actual_functions = actual_functions
            result.actual_classes = actual_classes

            # Calculate accuracies
            result.file_accuracy = self.calculate_accuracy(
                benchmark.expected_files,
                actual_files,
            )
            result.function_accuracy = self.calculate_accuracy(
                benchmark.expected_functions,
                actual_functions,
            )
            result.class_accuracy = self.calculate_accuracy(
                benchmark.expected_classes,
                actual_classes,
            )

            # Calculate overall accuracy
            accuracies = [
                result.file_accuracy,
                result.function_accuracy,
                result.class_accuracy,
            ]
            result.overall_accuracy = sum(accuracies) / len(accuracies)

            # Determine if passed (overall accuracy >= 0.8)
            result.passed = result.overall_accuracy >= 0.8

            # Performance metrics
            result.duration_seconds = time.time() - start_time
            result.performance_metrics = {
                'file_count': len(actual_files),
                'function_count': len(actual_functions),
                'class_count': len(actual_classes),
                'within_time_limit': result.duration_seconds
                <= benchmark.max_duration_seconds,
            }

        except Exception as e:
            result.duration_seconds = time.time() - start_time
            result.performance_metrics = {
                'error': str(e),
                'within_time_limit': False,
            }

        return result

    def _execute_repo_map_query(
        self,
        root: Path,
        query: str,
        metadata: dict[str, Any],
    ) -> set[str]:
        """Execute a repo-map query (placeholder implementation).

        Args:
            root: Codebase root directory.
            query: Query to execute.
            metadata: Additional metadata.

        Returns:
            Set of file paths.
        """
        # Placeholder: simulate repo-map query by searching for files
        # In production, this would call the actual repo-map implementation

        # Simple file search based on query keywords
        keywords = query.lower().split()
        matching_files = set()

        for file_path in root.rglob('*.py'):
            try:
                content = file_path.read_text(encoding='utf-8').lower()
                if any(keyword in content for keyword in keywords):
                    matching_files.add(str(file_path.relative_to(root)))
            except Exception:
                continue

        return matching_files

    def _extract_functions(self, root: Path, file_paths: set[str]) -> set[str]:
        """Extract function names from files.

        Args:
            root: Codebase root directory.
            file_paths: File paths to extract from.

        Returns:
            Set of function names.
        """
        import re

        functions = set()

        for file_path in file_paths:
            full_path = root / file_path
            try:
                content = full_path.read_text(encoding='utf-8')
                # Simple regex to find function definitions
                func_matches = re.findall(r'def\s+(\w+)\s*\(', content)
                functions.update(func_matches)
            except Exception:
                continue

        return functions

    def _extract_classes(self, root: Path, file_paths: set[str]) -> set[str]:
        """Extract class names from files.

        Args:
            root: Codebase root directory.
            file_paths: File paths to extract from.

        Returns:
            Set of class names.
        """
        import re

        classes = set()

        for file_path in file_paths:
            full_path = root / file_path
            try:
                content = full_path.read_text(encoding='utf-8')
                # Simple regex to find class definitions
                class_matches = re.findall(r'class\s+(\w+)\s*[:\(]', content)
                classes.update(class_matches)
            except Exception:
                continue

        return classes

    def create_default_benchmarks(self) -> list[RepoMapBenchmark]:
        """Create default repo-map benchmarks.

        Returns:
            List of default benchmarks.
        """
        benchmarks = []

        # Benchmark 1: Function search
        benchmark1 = RepoMapBenchmark(
            benchmark_id='benchmark-001',
            name='Function Search - Authentication',
            codebase_path='.',
            query='find authentication functions',
            expected_functions={'login', 'authenticate', 'verify', 'check_auth'},
            max_duration_seconds=10.0,
        )
        benchmarks.append(benchmark1)

        # Benchmark 2: Class search
        benchmark2 = RepoMapBenchmark(
            benchmark_id='benchmark-002',
            name='Class Search - Database Models',
            codebase_path='.',
            query='find database model classes',
            expected_classes={'User', 'Model', 'Database', 'Connection'},
            max_duration_seconds=15.0,
        )
        benchmarks.append(benchmark2)

        # Benchmark 3: File search
        benchmark3 = RepoMapBenchmark(
            benchmark_id='benchmark-003',
            name='File Search - Configuration',
            codebase_path='.',
            query='find configuration files',
            expected_files={'config.py', 'settings.py', '.env', 'config.json'},
            max_duration_seconds=5.0,
        )
        benchmarks.append(benchmark3)

        return benchmarks

    def convert_to_eval_test(self, benchmark: RepoMapBenchmark) -> EvalTest:
        """Convert a benchmark to an eval test.

        Args:
            benchmark: Benchmark to convert.

        Returns:
            Eval test.
        """
        return EvalTest(
            test_id=benchmark.benchmark_id,
            name=benchmark.name,
            category=EvalCategory.REPO_MAP_BENCHMARK,
            description=f'Repo-map benchmark: {benchmark.name}',
            metadata={
                'codebase_path': benchmark.codebase_path,
                'query': benchmark.query,
                'expected_files': list(benchmark.expected_files),
                'expected_functions': list(benchmark.expected_functions),
                'expected_classes': list(benchmark.expected_classes),
                'max_duration_seconds': benchmark.max_duration_seconds,
            },
        )
