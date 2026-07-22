"""H4 policy-engine performance evidence (ADR-0031 criterion 3).

Builds a deterministic 25-policy scratch store and measures
``PolicyEngine.evaluate_with_explanation`` with a no-match context so every
policy is inspected. This prepares the ADR-0031 performance evidence packet
without using live workspace policies, changing H4 modes, or making promotion
claims beyond the measured threshold result.
"""

from __future__ import annotations

import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from teaagent.governance.policy_engine import (
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEngine,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)

DEFAULT_POLICY_COUNT = 25
DEFAULT_ITERATIONS = 100
DEFAULT_THRESHOLD_MS = 50.0


@dataclass(frozen=True)
class H4PolicyPerformanceReport:
    """Performance evidence for ADR-0031 criterion 3."""

    policy_count: int
    iterations: int
    threshold_ms: float
    median_ms: float
    max_ms: float
    detail_count: int
    effect: str

    @property
    def ok(self) -> bool:
        return self.median_ms < self.threshold_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            'criterion': 'ADR-0031 criterion 3 — policy evaluation performance',
            'ok': self.ok,
            'policy_count': self.policy_count,
            'iterations': self.iterations,
            'threshold_ms': self.threshold_ms,
            'median_ms': self.median_ms,
            'max_ms': self.max_ms,
            'detail_count': self.detail_count,
            'effect': self.effect,
            'note': (
                'Evidence only: benchmark uses a deterministic scratch store and '
                'does not flip H4 policy/RBAC modes or certify promotion readiness.'
            ),
        }


def _validate_positive_int(value: int, *, name: str) -> None:
    if value <= 0:
        raise ValueError(f'{name} must be > 0')


def _validate_positive_float(value: float, *, name: str) -> None:
    if value <= 0:
        raise ValueError(f'{name} must be > 0')


def _populate_no_match_policies(store: PolicyStore, *, policy_count: int) -> None:
    for index in range(policy_count):
        store.save(
            Policy(
                policy_id=f'h4-perf-policy-{index:02d}',
                policy_type=PolicyType.APPROVAL,
                effect=PolicyEffect.DENY,
                conditions=[
                    PolicyCondition('action', 'equals', f'never-match-{index:02d}')
                ],
                precedence=PolicyPrecedence.MEDIUM,
                description=f'H4 performance no-match policy {index}',
            )
        )


def measure_policy_evaluation_performance(
    *,
    policy_count: int = DEFAULT_POLICY_COUNT,
    iterations: int = DEFAULT_ITERATIONS,
    threshold_ms: float = DEFAULT_THRESHOLD_MS,
) -> H4PolicyPerformanceReport:
    """Measure ``evaluate_with_explanation`` over a deterministic scratch store.

    The context intentionally matches none of the policies, forcing the evaluator
    to inspect every enabled policy. Median latency is the ADR-0031 SLO signal.
    """
    _validate_positive_int(policy_count, name='policy_count')
    _validate_positive_int(iterations, name='iterations')
    _validate_positive_float(threshold_ms, name='threshold_ms')

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PolicyStore(root)
        _populate_no_match_policies(store, policy_count=policy_count)
        engine = PolicyEngine(store)
        context = {'action': 'approve_tool', 'tool_name': 'write_file'}

        # Warm once so import/path setup doesn't contaminate the measured series.
        effect, details = engine.evaluate_with_explanation(
            context, policy_type=PolicyType.APPROVAL
        )
        durations_ns: list[int] = []
        for _ in range(iterations):
            start = perf_counter_ns()
            effect, details = engine.evaluate_with_explanation(
                context, policy_type=PolicyType.APPROVAL
            )
            durations_ns.append(perf_counter_ns() - start)

    durations_ms = [duration / 1_000_000 for duration in durations_ns]
    return H4PolicyPerformanceReport(
        policy_count=policy_count,
        iterations=iterations,
        threshold_ms=threshold_ms,
        median_ms=float(statistics.median(durations_ms)),
        max_ms=float(max(durations_ms)),
        detail_count=len(details),
        effect=effect.value,
    )
