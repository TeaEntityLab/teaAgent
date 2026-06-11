from __future__ import annotations

from teaagent.llm_conformance import ConformanceTier, run_tiered_conformance


class FakeFastAdapter:
    def complete(self, request):
        class Resp:
            content = 'ok'
            model = 'fake'
            input_tokens = 1
            output_tokens = 1
            estimated_cost_cents = 0.0

        return Resp()


class FakeSlowAdapter:
    def complete(self, request):
        import time

        time.sleep(0.06)  # 60ms — will exceed a tight threshold

        class Resp:
            content = 'ok'
            model = 'fake'
            input_tokens = 1
            output_tokens = 1
            estimated_cost_cents = 0.0

        return Resp()


def test_fast_adapter_passes_generous_threshold() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.LATENCY,
        adapter_factory=lambda p, **kw: FakeFastAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
        latency_samples=3,
        latency_threshold_ms=5000.0,
    )
    assert report.tier == 'latency'
    assert report.passed == 1
    result = report.results[0]
    assert result.status == 'passed'
    check_names = [c.name for c in result.checks]
    assert 'latency_p50_ms' in check_names
    assert 'latency_p95_ms' in check_names


def test_slow_adapter_fails_tight_threshold() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.LATENCY,
        adapter_factory=lambda p, **kw: FakeSlowAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
        latency_samples=3,
        latency_threshold_ms=1.0,  # 1ms — impossibly tight
    )
    assert report.failed == 1
    p95_check = next(c for c in report.results[0].checks if c.name == 'latency_p95_ms')
    assert p95_check.status == 'failed'
    assert 'threshold' in p95_check.detail


def test_latency_tier_skipped_when_not_configured() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.LATENCY,
        adapter_factory=lambda p, **kw: FakeFastAdapter(),
        configuration_checker=lambda p: (False, 'no key'),
    )
    assert report.skipped == 1


def test_p50_check_always_passed() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.LATENCY,
        adapter_factory=lambda p, **kw: FakeFastAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
        latency_samples=5,
        latency_threshold_ms=1.0,  # p95 fails, but p50 should always pass
    )
    p50 = next(c for c in report.results[0].checks if c.name == 'latency_p50_ms')
    assert p50.status == 'passed'


def test_latency_detail_includes_ms_unit() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.LATENCY,
        adapter_factory=lambda p, **kw: FakeFastAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
        latency_samples=3,
        latency_threshold_ms=9999.0,
    )
    latency_checks = [
        c for c in report.results[0].checks if c.name.startswith('latency_')
    ]
    assert latency_checks, 'Expected latency checks to be present'
    for check in latency_checks:
        assert 'ms' in check.detail


def test_all_five_tiers_in_enum() -> None:
    values = {t.value for t in ConformanceTier}
    assert 'latency' in values
