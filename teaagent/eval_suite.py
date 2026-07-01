"""Eval suite framework for quality and eval loop (TASK-H5-001-01).

This module provides a framework for automated evaluation of agent behavior,
including test discovery, execution, result aggregation, and baseline comparison.
"""

from __future__ import annotations

import difflib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.errors import ConfigError

# Callable seam: takes a prompt, returns model output text.
ModelRunner = Callable[[str], str]


class EvalStatus(str, Enum):
    """Status of an eval test."""

    PENDING = 'pending'
    RUNNING = 'running'
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    ERROR = 'error'


class EvalCategory(str, Enum):
    """Category of eval test."""

    PROMPT_REGRESSION = 'prompt_regression'
    CONVERSATIONAL = 'conversational'
    REPO_MAP_BENCHMARK = 'repo_map_benchmark'
    LONG_SESSION = 'long_session'
    SCOPE_CREEP = 'scope_creep'
    CONTEXT_HEALTH = 'context_health'
    MODEL_PERFORMANCE = 'model_performance'


@dataclass
class EvalTest:
    """A single eval test case."""

    test_id: str
    name: str
    category: EvalCategory
    description: str = ''
    fixture_path: Optional[str] = None
    baseline_path: Optional[str] = None
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'name': self.name,
            'category': self.category.value,
            'description': self.description,
            'fixture_path': self.fixture_path,
            'baseline_path': self.baseline_path,
            'timeout_seconds': self.timeout_seconds,
            'metadata': self.metadata,
            'enabled': self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EvalTest':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            name=data['name'],
            category=EvalCategory(data['category']),
            description=data.get('description', ''),
            fixture_path=data.get('fixture_path'),
            baseline_path=data.get('baseline_path'),
            timeout_seconds=data.get('timeout_seconds', 300),
            metadata=data.get('metadata', {}),
            enabled=data.get('enabled', True),
        )


@dataclass
class EvalResult:
    """Result of an eval test execution."""

    test_id: str
    status: EvalStatus
    duration_seconds: float = 0.0
    output: str = ''
    error_message: str = ''
    metrics: dict[str, Any] = field(default_factory=dict)
    baseline_comparison: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'status': self.status.value,
            'duration_seconds': self.duration_seconds,
            'output': self.output,
            'error_message': self.error_message,
            'metrics': self.metrics,
            'baseline_comparison': self.baseline_comparison,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EvalResult':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            status=EvalStatus(data['status']),
            duration_seconds=data.get('duration_seconds', 0.0),
            output=data.get('output', ''),
            error_message=data.get('error_message', ''),
            metrics=data.get('metrics', {}),
            baseline_comparison=data.get('baseline_comparison'),
            created_at=data.get('created_at'),
        )


@dataclass
class EvalSuite:
    """A collection of eval tests."""

    suite_id: str
    name: str
    description: str = ''
    tests: list[EvalTest] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    def add_test(self, test: EvalTest) -> None:
        """Add a test to the suite.

        Args:
            test: Test to add.
        """
        self.tests.append(test)

    def get_tests_by_category(self, category: EvalCategory) -> list[EvalTest]:
        """Get tests by category.

        Args:
            category: Category to filter by.

        Returns:
            List of tests in the category.
        """
        return [t for t in self.tests if t.category == category]

    def get_enabled_tests(self) -> list[EvalTest]:
        """Get all enabled tests.

        Returns:
            List of enabled tests.
        """
        return [t for t in self.tests if t.enabled]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'suite_id': self.suite_id,
            'name': self.name,
            'description': self.description,
            'tests': [t.to_dict() for t in self.tests],
            'metadata': self.metadata,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EvalSuite':
        """Create from dictionary."""
        return cls(
            suite_id=data['suite_id'],
            name=data['name'],
            description=data.get('description', ''),
            tests=[EvalTest.from_dict(t) for t in data.get('tests', [])],
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at'),
        )


class EvalStore:
    """Storage for eval suites and results."""

    def __init__(self, root: str | Path) -> None:
        """Initialize the eval store.

        Args:
            root: Workspace root directory.
        """
        self.root = Path(root).resolve()
        self.suites_dir = self.root / '.teaagent' / 'eval-suites'
        self.results_dir = self.root / '.teaagent' / 'eval-results'
        self.baselines_dir = self.root / '.teaagent' / 'eval-baselines'

        self.suites_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def _suite_path(self, suite_id: str) -> Path:
        """Get the file path for an eval suite."""
        return self.suites_dir / f'{suite_id}.json'

    def _result_path(self, result_id: str) -> Path:
        """Get the file path for an eval result."""
        return self.results_dir / f'{result_id}.json'

    def _baseline_path(self, baseline_id: str) -> Path:
        """Get the file path for a baseline."""
        return self.baselines_dir / f'{baseline_id}.json'

    def save_suite(self, suite: EvalSuite) -> None:
        """Save an eval suite to storage.

        Args:
            suite: Suite to save.
        """
        from teaagent.storage import atomic_write_text

        path = self._suite_path(suite.suite_id)

        if suite.created_at is None:
            import time

            suite.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        atomic_write_text(path, json.dumps(suite.to_dict(), indent=2))

    def load_suite(self, suite_id: str) -> Optional[EvalSuite]:
        """Load an eval suite from storage.

        Args:
            suite_id: Suite ID to load.

        Returns:
            Suite if found, None otherwise.
        """
        path = self._suite_path(suite_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return EvalSuite.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def list_suites(self) -> list[EvalSuite]:
        """List all eval suites.

        Returns:
            List of suites.
        """
        suites = []
        for path in self.suites_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                suites.append(EvalSuite.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return suites

    def save_result(self, result: EvalResult) -> None:
        """Save an eval result to storage.

        Args:
            result: Result to save.
        """
        from teaagent.storage import atomic_write_text

        path = self._result_path(result.test_id)

        if result.created_at is None:
            import time

            result.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        atomic_write_text(path, json.dumps(result.to_dict(), indent=2))

    def load_result(self, test_id: str) -> Optional[EvalResult]:
        """Load an eval result from storage.

        Args:
            test_id: Test ID to load result for.

        Returns:
            Result if found, None otherwise.
        """
        path = self._result_path(test_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return EvalResult.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def save_baseline(self, baseline_id: str, baseline_data: dict[str, Any]) -> None:
        """Save a baseline to storage.

        Args:
            baseline_id: Baseline ID.
            baseline_data: Baseline data to save.
        """
        from teaagent.storage import atomic_write_text

        path = self._baseline_path(baseline_id)
        atomic_write_text(path, json.dumps(baseline_data, indent=2))

    def load_baseline(self, baseline_id: str) -> Optional[dict[str, Any]]:
        """Load a baseline from storage.

        Args:
            baseline_id: Baseline ID to load.

        Returns:
            Baseline data if found, None otherwise.
        """
        path = self._baseline_path(baseline_id)
        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, ValueError):
            return None


class EvalRunner:
    """Runner for executing eval suites."""

    def __init__(
        self, store: EvalStore, *, model_runner: ModelRunner | None = None
    ) -> None:
        """Initialize the eval runner.

        Args:
            store: Eval store to use.
            model_runner: Optional callable that runs a prompt and returns model output.
        """
        self.store = store
        self._model_runner = model_runner

    def run_suite(
        self,
        suite: EvalSuite,
        *,
        category_filter: Optional[EvalCategory] = None,
        parallel: bool = False,
    ) -> list[EvalResult]:
        """Run an eval suite.

        Args:
            suite: Suite to run.
            category_filter: Optional filter by category.
            parallel: If True, run tests in parallel.

        Returns:
            List of eval results.
        """
        tests = suite.get_enabled_tests()

        if category_filter:
            tests = suite.get_tests_by_category(category_filter)

        results = []

        if parallel:
            # Simple parallel execution (in production, use proper thread pool)
            # For now, run sequentially
            for test in tests:
                result = self._run_test(test)
                results.append(result)
        else:
            for test in tests:
                result = self._run_test(test)
                results.append(result)

        return results

    def _run_test(self, test: EvalTest) -> EvalResult:
        """Run a single eval test.

        Args:
            test: Test to run.

        Returns:
            Eval result.
        """
        result = EvalResult(test_id=test.test_id, status=EvalStatus.RUNNING)

        start_time = time.time()

        try:
            # Load fixture if specified
            fixture_data = None
            if test.fixture_path:
                fixture_path = Path(test.fixture_path)
                if fixture_path.exists():
                    fixture_data = json.loads(fixture_path.read_text(encoding='utf-8'))

            # Load baseline if specified
            baseline_data = None
            if test.baseline_path:
                baseline_data = self.store.load_baseline(test.baseline_path)

            test_output, execution_metadata = self._execute_test(test, fixture_data)

            # Compare with baseline if available
            baseline_comparison = None
            if baseline_data:
                baseline_comparison = self._compare_with_baseline(
                    test_output, baseline_data
                )

            # Determine status based on test output
            status = self._determine_test_status(test, test_output, baseline_comparison)

            result.status = status
            result.output = test_output
            result.baseline_comparison = baseline_comparison
            result.metrics = self._extract_metrics(test_output)
            result.metrics.update(execution_metadata)

        except Exception as e:
            result.status = EvalStatus.ERROR
            result.error_message = str(e)

        result.duration_seconds = time.time() - start_time
        result.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        self.store.save_result(result)
        return result

    def _simulated_execution_metadata(self, test: EvalTest) -> dict[str, Any]:
        """Metadata stamped on every placeholder execution result."""
        return {
            'execution_mode': 'simulated',
            'executor': 'placeholder',
            'advisory_only': True,
            'category': test.category.value,
        }

    def _prompt_execution_metadata(self, test: EvalTest, mode: str) -> dict[str, Any]:
        """Metadata for prompt/conversational execution modes."""
        if mode in ('real', 'fixture'):
            return {
                'execution_mode': mode,
                'executor': 'model' if mode == 'real' else 'fixture',
                'advisory_only': False,
                'category': test.category.value,
            }
        return {
            'execution_mode': mode,
            'executor': 'placeholder',
            'advisory_only': True,
            'category': test.category.value,
        }

    def _repo_map_execution_metadata(self, test: EvalTest) -> dict[str, Any]:
        from teaagent.eval_repo_map_executor import RepoMapBenchmarkExecutor

        return RepoMapBenchmarkExecutor.execution_metadata(test)

    def _execute_test(
        self, test: EvalTest, fixture_data: Optional[dict[str, Any]]
    ) -> tuple[str, dict[str, Any]]:
        """Execute a test and return output with execution metadata.

        Args:
            test: Test to execute.
            fixture_data: Fixture data for the test.

        Returns:
            Tuple of test output and execution metadata.
        """
        if test.category in (
            EvalCategory.PROMPT_REGRESSION,
            EvalCategory.CONVERSATIONAL,
        ):
            output, mode = self._execute_prompt_regression_test(test, fixture_data)
            metadata = self._prompt_execution_metadata(test, mode)
        else:
            if test.category == EvalCategory.REPO_MAP_BENCHMARK:
                output = self._execute_repo_map_benchmark(test, fixture_data)
                metadata = self._repo_map_execution_metadata(test)
            else:
                metadata = self._simulated_execution_metadata(test)
                if test.category == EvalCategory.LONG_SESSION:
                    output = self._execute_long_session_test(test, fixture_data)
                elif test.category == EvalCategory.SCOPE_CREEP:
                    output = self._execute_scope_creep_test(test, fixture_data)
                else:
                    output = f'Test {test.test_id} executed (category: {test.category})'

        return output, metadata

    def _execute_prompt_regression_test(
        self, test: EvalTest, fixture_data: Optional[dict[str, Any]]
    ) -> tuple[str, str]:
        """Return actual output and execution mode for prompt/conversational tests."""
        import os

        if fixture_data and 'actual_output' in fixture_data:
            return str(fixture_data['actual_output']), 'fixture'
        if os.environ.get('TEAAGENT_EVAL_SEED_FAILURE') == '1':
            return (
                'intentionally wrong output for release gate failure',
                'seeded_failure',
            )
        if self._model_runner is not None:
            prompt = str(test.metadata.get('prompt', ''))
            return self._model_runner(prompt), 'real'
        return str(test.metadata.get('expected_output', '')), 'replay_baseline'

    def _execute_repo_map_benchmark(
        self, test: EvalTest, fixture_data: Optional[dict[str, Any]]
    ) -> str:
        from teaagent.eval_repo_map_executor import RepoMapBenchmarkExecutor

        return RepoMapBenchmarkExecutor.execute(test, fixture_data)

    def _execute_long_session_test(
        self, test: EvalTest, fixture_data: Optional[dict[str, Any]]
    ) -> str:
        """Execute a long-session test (placeholder)."""
        # Placeholder: simulate long-session test
        return f'Long-session test {test.test_id} completed'

    def _execute_scope_creep_test(
        self, test: EvalTest, fixture_data: Optional[dict[str, Any]]
    ) -> str:
        """Execute a scope-creep test (placeholder)."""
        # Placeholder: simulate scope-creep test
        return f'Scope-creep test {test.test_id} completed'

    def _compare_with_baseline(
        self, output: str, baseline: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare test output with baseline using a real textual diff.

        Args:
            output: Test output.
            baseline: Baseline data (the ``output`` key holds the reference text).

        Returns:
            A mapping with ``matches`` (exact equality), ``diff`` (a unified diff,
            empty when equal), and ``similarity`` (a 0..1 ratio).
        """
        baseline_output = str(baseline.get('output', ''))
        matches = output == baseline_output
        if matches:
            diff_text = ''
        else:
            diff_text = '\n'.join(
                difflib.unified_diff(
                    baseline_output.splitlines(),
                    output.splitlines(),
                    fromfile='baseline',
                    tofile='actual',
                    lineterm='',
                )
            )
        similarity = difflib.SequenceMatcher(None, baseline_output, output).ratio()
        return {
            'matches': matches,
            'diff': diff_text,
            'similarity': round(similarity, 4),
        }

    def _determine_test_status(
        self,
        test: EvalTest,
        output: str,
        baseline_comparison: Optional[dict[str, Any]],
    ) -> EvalStatus:
        """Determine test status based on output and baseline comparison.

        Args:
            test: Test that was executed.
            output: Test output.
            baseline_comparison: Baseline comparison result.

        Returns:
            Test status.
        """
        if test.category in (
            EvalCategory.PROMPT_REGRESSION,
            EvalCategory.CONVERSATIONAL,
        ):
            return self._determine_prompt_regression_status(test, output)
        if test.category == EvalCategory.REPO_MAP_BENCHMARK:
            return self._determine_repo_map_benchmark_status(output)
        return EvalStatus.PASSED

    def _determine_repo_map_benchmark_status(self, output: str) -> EvalStatus:
        from teaagent.eval_repo_map_executor import RepoMapBenchmarkExecutor

        return RepoMapBenchmarkExecutor.determine_status(output)

    def _determine_prompt_regression_status(
        self, test: EvalTest, output: str
    ) -> EvalStatus:
        from teaagent.prompt_regression import (
            PromptRegressionEvaluator,
            PromptRegressionTest,
        )

        metadata = test.metadata
        if 'expected_output' not in metadata:
            raise ConfigError(
                f'eval test {test.test_id!r} (category={test.category.value}) is '
                "missing required metadata key 'expected_output'",
                hint="Add metadata['expected_output'] to the prompt/conversational "
                'eval test so its output can be compared against a baseline.',
            )
        regression = PromptRegressionTest(
            test_id=test.test_id,
            name=test.name,
            prompt=str(metadata.get('prompt', '')),
            expected_output=str(metadata['expected_output']),
            expected_behavior=metadata.get('expected_behavior', {}),
            tolerance_threshold=float(metadata.get('tolerance_threshold', 0.9)),
            metadata={
                key: value
                for key, value in metadata.items()
                if key
                not in {
                    'prompt',
                    'expected_output',
                    'expected_behavior',
                    'tolerance_threshold',
                }
            },
        )
        result = PromptRegressionEvaluator().evaluate_regression(regression, output)
        return EvalStatus.PASSED if result.passed else EvalStatus.FAILED

    def _extract_metrics(self, output: str) -> dict[str, Any]:
        """Extract metrics from test output.

        Args:
            output: Test output.

        Returns:
            Extracted metrics.
        """
        # Placeholder: extract basic metrics
        return {
            'output_length': len(output),
            'output_lines': len(output.splitlines()),
        }

    def create_suite(
        self,
        name: str,
        description: str = '',
        metadata: Optional[dict[str, Any]] = None,
    ) -> EvalSuite:
        """Create a new eval suite.

        Args:
            name: Suite name.
            description: Suite description.
            metadata: Additional metadata.

        Returns:
            Created suite.
        """
        suite_id = str(uuid4())
        suite = EvalSuite(
            suite_id=suite_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

        self.store.save_suite(suite)
        return suite

    def add_test_to_suite(
        self,
        suite_id: str,
        name: str,
        category: EvalCategory,
        *,
        description: str = '',
        fixture_path: Optional[str] = None,
        baseline_path: Optional[str] = None,
        timeout_seconds: int = 300,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[EvalTest, EvalSuite]:
        """Add a test to a suite.

        Args:
            suite_id: Suite ID to add test to.
            name: Test name.
            category: Test category.
            description: Test description.
            fixture_path: Path to test fixture.
            baseline_path: Path to baseline.
            timeout_seconds: Test timeout.
            metadata: Additional metadata.

        Returns:
            Tuple of (created test, updated suite).
        """
        suite = self.store.load_suite(suite_id)
        if not suite:
            raise ValueError(f'Suite not found: {suite_id}')

        test_id = str(uuid4())
        test = EvalTest(
            test_id=test_id,
            name=name,
            category=category,
            description=description,
            fixture_path=fixture_path,
            baseline_path=baseline_path,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )

        suite.add_test(test)
        self.store.save_suite(suite)
        return test, suite

    def get_suite_summary(self, suite_id: str) -> dict[str, Any]:
        """Get a summary of suite execution results.

        Args:
            suite_id: Suite ID to summarize.

        Returns:
            Suite summary.
        """
        suite = self.store.load_suite(suite_id)
        if not suite:
            raise ValueError(f'Suite not found: {suite_id}')

        tests = suite.get_enabled_tests()
        results = []

        for test in tests:
            result = self.store.load_result(test.test_id)
            if result:
                results.append(result)

        passed = sum(1 for r in results if r.status == EvalStatus.PASSED)
        failed = sum(1 for r in results if r.status == EvalStatus.FAILED)
        errored = sum(1 for r in results if r.status == EvalStatus.ERROR)
        total_duration = sum(r.duration_seconds for r in results)

        return {
            'suite_id': suite_id,
            'suite_name': suite.name,
            'total_tests': len(tests),
            'total_executed': len(results),
            'passed': passed,
            'failed': failed,
            'errored': errored,
            'success_rate': passed / len(results) if results else 0.0,
            'total_duration_seconds': total_duration,
            'average_duration_seconds': total_duration / len(results)
            if results
            else 0.0,
        }
