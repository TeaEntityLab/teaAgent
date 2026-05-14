"""Benchmark runner for measuring eval latency and cost regressions.

Usage::

    from teaagent.benchmark import BenchmarkSuite, run_benchmark, BenchmarkBaseline
    from teaagent.eval import EvalCase

    cases = [EvalCase(name=f'c{i}', task=f'task {i}') for i in range(10)]
    suite = BenchmarkSuite(name='my-bench', cases=cases)
    result = run_benchmark(suite, runner=my_runner)

    print(f'p50={result.p50_ms:.0f}ms  p95={result.p95_ms:.0f}ms')

    baseline = BenchmarkBaseline(p50_ms=50.0, p95_ms=200.0)
    if result.regression_detected(baseline):
        print('REGRESSION detected!')
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class CaseMetrics:
    """Per-case timing and output captured during a benchmark run."""

    name: str
    latency_ms: float
    output: str
    cost_cents: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class BenchmarkBaseline:
    """Reference latency thresholds for regression detection."""

    p50_ms: float
    p95_ms: float
    p50_margin: float = 1.5
    p95_margin: float = 2.0

    def is_regression(self, p50: float, p95: float) -> bool:
        return (
            p50 > self.p50_ms * self.p50_margin or p95 > self.p95_ms * self.p95_margin
        )


@dataclass(frozen=True)
class BenchmarkSuite:
    """A named collection of eval cases to benchmark."""

    name: str
    cases: list[Any]
    warmup_runs: int = 0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * pct / 100) - 1)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


@dataclass(frozen=True)
class BenchmarkResult:
    """Aggregated results from a :func:`run_benchmark` call."""

    suite_name: str
    case_metrics: list[CaseMetrics]
    p50_ms: float
    p95_ms: float
    mean_ms: float

    def regression_detected(self, baseline: BenchmarkBaseline) -> bool:
        return baseline.is_regression(self.p50_ms, self.p95_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            'suite_name': self.suite_name,
            'p50_ms': self.p50_ms,
            'p95_ms': self.p95_ms,
            'mean_ms': self.mean_ms,
            'case_metrics': [
                {
                    'name': m.name,
                    'latency_ms': m.latency_ms,
                    'output': m.output,
                    'cost_cents': m.cost_cents,
                    'error': m.error,
                }
                for m in self.case_metrics
            ],
        }


def run_benchmark(
    suite: BenchmarkSuite,
    *,
    runner: Callable[[Any], str],
    baseline: Optional[BenchmarkBaseline] = None,
) -> BenchmarkResult:
    """Run all cases in *suite* and collect timing metrics.

    Parameters
    ----------
    suite:
        The :class:`BenchmarkSuite` to execute.
    runner:
        Callable that accepts an :class:`~teaagent.eval.EvalCase` and returns
        the model output string.
    baseline:
        Optional :class:`BenchmarkBaseline` stored on the result (does not
        affect execution — call :meth:`BenchmarkResult.regression_detected`
        afterwards).

    Returns
    -------
    :class:`BenchmarkResult`
        Aggregated p50/p95/mean latency metrics plus per-case details.
    """
    # Warmup runs (discarded)
    for _ in range(suite.warmup_runs):
        for case in suite.cases:
            with contextlib.suppress(Exception):
                runner(case)

    metrics: list[CaseMetrics] = []
    for case in suite.cases:
        t0 = time.perf_counter()
        output = ''
        error: Optional[str] = None
        try:
            output = runner(case)
        except Exception as exc:
            error = str(exc)
        latency_ms = (time.perf_counter() - t0) * 1000

        metrics.append(
            CaseMetrics(
                name=getattr(case, 'name', str(case)),
                latency_ms=latency_ms,
                output=output,
                error=error,
            )
        )

    latencies = [m.latency_ms for m in metrics]
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    mean = sum(latencies) / len(latencies) if latencies else 0.0

    return BenchmarkResult(
        suite_name=suite.name,
        case_metrics=metrics,
        p50_ms=p50,
        p95_ms=p95,
        mean_ms=mean,
    )
