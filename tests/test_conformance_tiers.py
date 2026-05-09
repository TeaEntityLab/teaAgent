from __future__ import annotations

import unittest

from teaagent.llm_conformance import (
    ConformanceTier,
    run_tiered_conformance,
)


class FakeStreamingAdapter:
    def complete(self, request):
        on_chunk = getattr(request, 'on_chunk', None)
        if on_chunk and getattr(request, 'stream', False):
            on_chunk('chunk-1')
            on_chunk('chunk-2')

        class Resp:
            content = 'chunk-1chunk-2'
            model = 'fake-model'
            input_tokens = 5
            output_tokens = 5
            estimated_cost_cents = 0.0

        return Resp()


class FakeNoStreamAdapter:
    def complete(self, request):
        class Resp:
            content = 'some text'
            model = 'fake-model'
            input_tokens = 5
            output_tokens = 5
            estimated_cost_cents = 0.0

        return Resp()


class FakeJSONAdapter:
    def complete(self, request):
        class Resp:
            content = '{"status": "ok"}'
            model = 'fake-model'
            input_tokens = 5
            output_tokens = 5
            estimated_cost_cents = 0.0

        return Resp()


class FakeBadJSONAdapter:
    def complete(self, request):
        class Resp:
            content = 'This is not JSON at all.'
            model = 'fake-model'
            input_tokens = 5
            output_tokens = 5
            estimated_cost_cents = 0.0

        return Resp()


class StreamingTierTests(unittest.TestCase):
    def test_streaming_passes_when_chunks_received(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STREAMING,
            adapter_factory=lambda p, **kw: FakeStreamingAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
        )
        self.assertEqual(report.tier, 'streaming')
        self.assertEqual(report.passed, 1)
        result = report.results[0]
        self.assertEqual(result.status, 'passed')
        check_names = [c.name for c in result.checks]
        self.assertIn('streaming_chunks_received', check_names)

    def test_streaming_fails_when_no_chunks(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STREAMING,
            adapter_factory=lambda p, **kw: FakeNoStreamAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
        )
        self.assertEqual(report.failed, 1)
        result = report.results[0]
        check = next(c for c in result.checks if c.name == 'streaming_chunks_received')
        self.assertEqual(check.status, 'failed')

    def test_streaming_skipped_when_not_configured(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STREAMING,
            adapter_factory=lambda p, **kw: FakeStreamingAdapter(),
            configuration_checker=lambda p: (False, 'no key'),
        )
        self.assertEqual(report.skipped, 1)


class StructuredOutputTierTests(unittest.TestCase):
    def test_structured_output_passes_for_valid_json(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STRUCTURED_OUTPUT,
            adapter_factory=lambda p, **kw: FakeJSONAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
        )
        self.assertEqual(report.passed, 1)
        check_names = [c.name for c in report.results[0].checks]
        self.assertIn('structured_json_output', check_names)

    def test_structured_output_fails_for_non_json(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STRUCTURED_OUTPUT,
            adapter_factory=lambda p, **kw: FakeBadJSONAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
        )
        self.assertEqual(report.failed, 1)
        check = next(
            c for c in report.results[0].checks if c.name == 'structured_json_output'
        )
        self.assertEqual(check.status, 'failed')

    def test_tiered_report_as_dict_includes_new_tiers(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.STRUCTURED_OUTPUT,
            adapter_factory=lambda p, **kw: FakeJSONAdapter(),
            configuration_checker=lambda p: (True, 'ok'),
        )
        d = report.as_dict()
        self.assertEqual(d['tier'], 'structured_output')
        self.assertIn('results', d)


class ConformanceTierEnumTests(unittest.TestCase):
    def test_all_four_tiers_exist(self) -> None:
        tiers = {t.value for t in ConformanceTier}
        self.assertIn('smoke', tiers)
        self.assertIn('contract', tiers)
        self.assertIn('streaming', tiers)
        self.assertIn('structured_output', tiers)


if __name__ == '__main__':
    unittest.main()
