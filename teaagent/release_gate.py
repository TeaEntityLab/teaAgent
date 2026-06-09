"""Release pipeline integration for eval-gating (TASK-H5-001-06).

This module provides integration between the eval suite and release pipelines,
including gating logic, result aggregation, and release decision making.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .eval_suite import EvalRunner, EvalStatus, EvalStore


class ReleaseDecision(str, Enum):
    """Decision for release gating."""

    APPROVE = 'approve'  # Release approved
    BLOCK = 'block'  # Release blocked
    WARN = 'warn'  # Release with warnings


@dataclass
class ReleaseGateConfig:
    """Configuration for release gating."""

    gate_id: str
    name: str
    required_success_rate: float = 0.9  # Minimum success rate for approval
    critical_test_categories: set[str] = field(default_factory=set)
    block_on_critical_failure: bool = True
    allow_warnings: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'gate_id': self.gate_id,
            'name': self.name,
            'required_success_rate': self.required_success_rate,
            'critical_test_categories': list(self.critical_test_categories),
            'block_on_critical_failure': self.block_on_critical_failure,
            'allow_warnings': self.allow_warnings,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ReleaseGateConfig':
        """Create from dictionary."""
        return cls(
            gate_id=data['gate_id'],
            name=data['name'],
            required_success_rate=data.get('required_success_rate', 0.9),
            critical_test_categories=set(data.get('critical_test_categories', [])),
            block_on_critical_failure=data.get('block_on_critical_failure', True),
            allow_warnings=data.get('allow_warnings', True),
            metadata=data.get('metadata', {}),
        )


@dataclass
class ReleaseGateResult:
    """Result of release gate evaluation."""

    gate_id: str
    decision: ReleaseDecision = ReleaseDecision.BLOCK
    success_rate: float = 0.0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    critical_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ''
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'gate_id': self.gate_id,
            'decision': self.decision.value,
            'success_rate': self.success_rate,
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'summary': self.summary,
            'details': self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ReleaseGateResult':
        """Create from dictionary."""
        return cls(
            gate_id=data['gate_id'],
            decision=ReleaseDecision(data['decision']),
            success_rate=data.get('success_rate', 0.0),
            total_tests=data.get('total_tests', 0),
            passed_tests=data.get('passed_tests', 0),
            failed_tests=data.get('failed_tests', 0),
            critical_failures=data.get('critical_failures', []),
            warnings=data.get('warnings', []),
            summary=data.get('summary', ''),
            details=data.get('details', {}),
        )


class ReleaseGate:
    """Gate for release pipeline integration."""

    def __init__(self, store: EvalStore) -> None:
        """Initialize the release gate.

        Args:
            store: Eval store to use.
        """
        self.store = store
        self.runner = EvalRunner(store)

    def evaluate_gate(
        self,
        config: ReleaseGateConfig,
        suite_id: str,
    ) -> ReleaseGateResult:
        """Evaluate a release gate.

        Args:
            config: Gate configuration.
            suite_id: Suite ID to evaluate.

        Returns:
            Gate result.
        """
        result = ReleaseGateResult(gate_id=config.gate_id)

        # Load suite
        suite = self.store.load_suite(suite_id)
        if not suite:
            result.decision = ReleaseDecision.BLOCK
            result.summary = f'Suite not found: {suite_id}'
            return result

        # Get all test results
        tests = suite.get_enabled_tests()
        result.total_tests = len(tests)

        passed = 0
        failed = 0
        critical_failures = []
        warnings = []

        for test in tests:
            test_result = self.store.load_result(test.test_id)
            if not test_result:
                # No result, count as failed
                failed += 1
                continue

            if test_result.status == EvalStatus.PASSED:
                passed += 1
            elif test_result.status == EvalStatus.FAILED:
                failed += 1

                # Check if critical category
                if test.category.value in config.critical_test_categories:
                    critical_failures.append(test.test_id)
            elif test_result.status == EvalStatus.ERROR:
                failed += 1
                warnings.append(f'Test {test.test_id} encountered an error')

        result.passed_tests = passed
        result.failed_tests = failed
        result.success_rate = (
            passed / result.total_tests if result.total_tests > 0 else 0.0
        )

        # Make decision
        if config.block_on_critical_failure and critical_failures:
            result.decision = ReleaseDecision.BLOCK
            result.critical_failures = critical_failures
            result.summary = f'Release blocked due to {len(critical_failures)} critical test failures'
        elif result.success_rate < config.required_success_rate:
            result.decision = ReleaseDecision.BLOCK
            result.summary = f'Release blocked: success rate {result.success_rate:.2%} below required {config.required_success_rate:.2%}'
        elif warnings and not config.allow_warnings:
            result.decision = ReleaseDecision.BLOCK
            result.warnings = warnings
            result.summary = f'Release blocked due to {len(warnings)} warnings'
        elif warnings and config.allow_warnings:
            result.decision = ReleaseDecision.WARN
            result.warnings = warnings
            result.summary = f'Release approved with {len(warnings)} warnings'
        else:
            result.decision = ReleaseDecision.APPROVE
            result.summary = (
                f'Release approved: {passed}/{result.total_tests} tests passed'
            )

        # Details
        result.details = {
            'suite_id': suite_id,
            'suite_name': suite.name,
            'required_success_rate': config.required_success_rate,
            'critical_categories': list(config.critical_test_categories),
        }

        return result

    def run_and_evaluate(
        self,
        config: ReleaseGateConfig,
        suite_id: str,
    ) -> ReleaseGateResult:
        """Run eval suite and evaluate gate.

        Args:
            config: Gate configuration.
            suite_id: Suite ID to run and evaluate.

        Returns:
            Gate result.
        """
        # Load suite
        suite = self.store.load_suite(suite_id)
        if not suite:
            result = ReleaseGateResult(gate_id=config.gate_id)
            result.decision = ReleaseDecision.BLOCK
            result.summary = f'Suite not found: {suite_id}'
            return result

        # Run suite
        self.runner.run_suite(suite)

        # Evaluate gate
        return self.evaluate_gate(config, suite_id)

    def create_default_gate_config(self) -> ReleaseGateConfig:
        """Create default gate configuration.

        Returns:
            Default gate configuration.
        """
        return ReleaseGateConfig(
            gate_id='default-gate',
            name='Default Release Gate',
            required_success_rate=0.9,
            critical_test_categories={
                'prompt_regression',
                'repo_map_benchmark',
            },
            block_on_critical_failure=True,
            allow_warnings=True,
        )

    def export_gate_report(
        self,
        result: ReleaseGateResult,
        output_path: str | Path,
    ) -> None:
        """Export gate report to file.

        Args:
            result: Gate result to export.
            output_path: Path to export report to.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            'gate_result': result.to_dict(),
            'generated_at': result.details.get('generated_at', ''),
        }

        output_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def create_release_bundle(
        self,
        suite_id: str,
        output_path: str | Path,
    ) -> dict[str, Any]:
        """Create a release bundle with eval results.

        Args:
            suite_id: Suite ID to bundle.
            output_path: Path to export bundle to.

        Returns:
            Bundle metadata.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Load suite
        suite = self.store.load_suite(suite_id)
        if not suite:
            raise ValueError(f'Suite not found: {suite_id}')

        # Collect all results
        results = []
        for test in suite.get_enabled_tests():
            test_result = self.store.load_result(test.test_id)
            if test_result:
                results.append(test_result.to_dict())

        # Create bundle
        bundle = {
            'suite': suite.to_dict(),
            'results': results,
            'summary': self.runner.get_suite_summary(suite_id),
            'generated_at': suite.created_at,
        }

        output_path.write_text(json.dumps(bundle, indent=2), encoding='utf-8')

        return {
            'bundle_path': str(output_path),
            'suite_id': suite_id,
            'test_count': len(suite.get_enabled_tests()),
            'result_count': len(results),
        }
