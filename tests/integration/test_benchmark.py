"""IT: Benchmark latency/cost tracking."""

from __future__ import annotations

import time

from teaagent.benchmark import (
    BenchmarkBaseline,
    BenchmarkResult,
    BenchmarkSuite,
    run_benchmark,
)
from teaagent.eval import EvalCase


def _fast_runner(case: EvalCase) -> str:
    time.sleep(0.01)
    return 'answer'


def _make_cases() -> list[EvalCase]:
    return [EvalCase(name=f'c{i}', task=f'task {i}') for i in range(5)]


def test_run_benchmark_returns_result():
    suite = BenchmarkSuite(name='smoke', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner)
    assert isinstance(result, BenchmarkResult)
    assert result.suite_name == 'smoke'


def test_run_benchmark_case_count():
    cases = _make_cases()
    suite = BenchmarkSuite(name='count', cases=cases)
    result = run_benchmark(suite, runner=_fast_runner)
    assert len(result.case_metrics) == len(cases)


def test_case_metrics_has_latency():
    suite = BenchmarkSuite(name='lat', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner)
    for m in result.case_metrics:
        assert m.latency_ms >= 0


def test_benchmark_result_p50_p95():
    suite = BenchmarkSuite(name='percentile', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner)
    assert result.p50_ms >= 0
    assert result.p95_ms >= result.p50_ms


def test_benchmark_result_mean_latency():
    suite = BenchmarkSuite(name='mean', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner)
    assert result.mean_ms > 0


def test_case_metrics_output_captured():
    def echo(case: EvalCase) -> str:
        return f'output for {case.name}'

    suite = BenchmarkSuite(name='output', cases=[EvalCase(name='x', task='t')])
    result = run_benchmark(suite, runner=echo)
    assert result.case_metrics[0].output == 'output for x'


def test_benchmark_baseline_comparison():
    baseline = BenchmarkBaseline(p50_ms=10.0, p95_ms=20.0)
    suite = BenchmarkSuite(name='compare', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner, baseline=baseline)
    # regression_detected is a bool
    assert isinstance(result.regression_detected(baseline), bool)


def test_no_regression_when_fast():
    baseline = BenchmarkBaseline(p50_ms=10_000.0, p95_ms=20_000.0)
    suite = BenchmarkSuite(name='noregress', cases=_make_cases())
    result = run_benchmark(suite, runner=_fast_runner, baseline=baseline)
    assert not result.regression_detected(baseline)


def test_regression_detected_when_slow():
    def slow(case: EvalCase) -> str:
        time.sleep(0.05)
        return 'slow'

    baseline = BenchmarkBaseline(p50_ms=1.0, p95_ms=2.0)
    suite = BenchmarkSuite(name='regress', cases=_make_cases())
    result = run_benchmark(suite, runner=slow, baseline=baseline)
    assert result.regression_detected(baseline)


def test_benchmark_result_to_dict():
    suite = BenchmarkSuite(name='dict', cases=_make_cases()[:2])
    result = run_benchmark(suite, runner=_fast_runner)
    d = result.to_dict()
    assert 'suite_name' in d
    assert 'p50_ms' in d
    assert 'p95_ms' in d
    assert 'case_metrics' in d
