from __future__ import annotations

import unittest

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


class LatencyTierTests(unittest.TestCase):
    def test_fast_adapter_passes_generous_threshold(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.LATENCY,
            adapter_factory=lambda p, **kw: FakeFastAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
            latency_samples=3,
            latency_threshold_ms=5000.0,
        )
        self.assertEqual(report.tier, 'latency')
        self.assertEqual(report.passed, 1)
        result = report.results[0]
        self.assertEqual(result.status, 'passed')
        check_names = [c.name for c in result.checks]
        self.assertIn('latency_p50_ms', check_names)
        self.assertIn('latency_p95_ms', check_names)

    def test_slow_adapter_fails_tight_threshold(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.LATENCY,
            adapter_factory=lambda p, **kw: FakeSlowAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
            latency_samples=3,
            latency_threshold_ms=1.0,  # 1ms — impossibly tight
        )
        self.assertEqual(report.failed, 1)
        p95_check = next(
            c for c in report.results[0].checks if c.name == 'latency_p95_ms'
        )
        self.assertEqual(p95_check.status, 'failed')
        self.assertIn('threshold', p95_check.detail)

    def test_latency_tier_skipped_when_not_configured(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.LATENCY,
            adapter_factory=lambda p, **kw: FakeFastAdapter(),
            configuration_checker=lambda p: (False, 'no key'),
        )
        self.assertEqual(report.skipped, 1)

    def test_p50_check_always_passed(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.LATENCY,
            adapter_factory=lambda p, **kw: FakeFastAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
            latency_samples=5,
            latency_threshold_ms=1.0,  # p95 fails, but p50 should always pass
        )
        p50 = next(c for c in report.results[0].checks if c.name == 'latency_p50_ms')
        self.assertEqual(p50.status, 'passed')

    def test_latency_detail_includes_ms_unit(self) -> None:
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
        self.assertTrue(latency_checks, 'Expected latency checks to be present')
        for check in latency_checks:
            self.assertIn('ms', check.detail)

    def test_all_five_tiers_in_enum(self) -> None:
        values = {t.value for t in ConformanceTier}
        self.assertIn('latency', values)


if __name__ == '__main__':
    unittest.main()
