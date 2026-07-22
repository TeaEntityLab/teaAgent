# test-type: contract
"""Tests for ADR-0031 H4 policy performance evidence.

The benchmark is a deterministic scratch-store proof for criterion 3: evaluate
PolicyEngine.evaluate_with_explanation against 25 enabled policies and report
median latency. It does not flip modes or decide promotion readiness.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from teaagent.governance.h4_performance import (
    DEFAULT_THRESHOLD_MS,
    measure_policy_evaluation_performance,
)

_SCRIPT = 'scripts/benchmark_h4_policy.py'


def test_policy_performance_report_uses_all_policies() -> None:
    report = measure_policy_evaluation_performance(policy_count=25, iterations=5)

    assert report.policy_count == 25
    assert report.detail_count == 25
    assert report.effect == 'allow'
    assert report.median_ms >= 0
    assert report.ok is True
    assert 'does not flip H4' in report.to_dict()['note']


def test_policy_performance_threshold_failure_is_represented() -> None:
    report = measure_policy_evaluation_performance(
        policy_count=1,
        iterations=1,
        threshold_ms=0.000001,
    )

    assert report.ok is False
    assert report.to_dict()['ok'] is False


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [
        ({'policy_count': 0}, 'policy_count must be > 0'),
        ({'iterations': 0}, 'iterations must be > 0'),
        ({'threshold_ms': 0.0}, 'threshold_ms must be > 0'),
    ],
)
def test_policy_performance_rejects_invalid_inputs(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        measure_policy_evaluation_performance(**kwargs)


def test_policy_performance_cli_success() -> None:
    result = subprocess.run(
        [sys.executable, _SCRIPT, '--policy-count', '25', '--iterations', '3'],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload['policy_count'] == 25
    assert payload['detail_count'] == 25
    assert payload['threshold_ms'] == DEFAULT_THRESHOLD_MS
    assert payload['ok'] is True


def test_policy_performance_cli_threshold_failure() -> None:
    result = subprocess.run(
        [
            sys.executable,
            _SCRIPT,
            '--policy-count',
            '1',
            '--iterations',
            '1',
            '--threshold-ms',
            '0.000001',
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload['ok'] is False
    assert 'exceeds threshold' in result.stderr


def test_policy_performance_cli_invalid_args() -> None:
    result = subprocess.run(
        [sys.executable, _SCRIPT, '--iterations', '0'],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert 'iterations must be > 0' in result.stderr
