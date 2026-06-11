from __future__ import annotations

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


def test_streaming_passes_when_chunks_received() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STREAMING,
        adapter_factory=lambda p, **kw: FakeStreamingAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
    )
    assert report.tier == 'streaming'
    assert report.passed == 1
    result = report.results[0]
    assert result.status == 'passed'
    check_names = [c.name for c in result.checks]
    assert 'streaming_chunks_received' in check_names


def test_streaming_fails_when_no_chunks() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STREAMING,
        adapter_factory=lambda p, **kw: FakeNoStreamAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
    )
    assert report.failed == 1
    result = report.results[0]
    check = next(c for c in result.checks if c.name == 'streaming_chunks_received')
    assert check.status == 'failed'


def test_streaming_skipped_when_not_configured() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STREAMING,
        adapter_factory=lambda p, **kw: FakeStreamingAdapter(),
        configuration_checker=lambda p: (False, 'no key'),
    )
    assert report.skipped == 1


def test_structured_output_passes_for_valid_json() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STRUCTURED_OUTPUT,
        adapter_factory=lambda p, **kw: FakeJSONAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
    )
    assert report.passed == 1
    check_names = [c.name for c in report.results[0].checks]
    assert 'structured_json_output' in check_names


def test_structured_output_fails_for_non_json() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STRUCTURED_OUTPUT,
        adapter_factory=lambda p, **kw: FakeBadJSONAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
    )
    assert report.failed == 1
    check = next(
        c for c in report.results[0].checks if c.name == 'structured_json_output'
    )
    assert check.status == 'failed'


def test_tiered_report_as_dict_includes_new_tiers() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.STRUCTURED_OUTPUT,
        adapter_factory=lambda p, **kw: FakeJSONAdapter(),
        configuration_checker=lambda p: (True, 'ok'),
    )
    d = report.as_dict()
    assert d['tier'] == 'structured_output'
    assert 'results' in d


def test_all_four_tiers_exist() -> None:
    tiers = {t.value for t in ConformanceTier}
    assert 'smoke' in tiers
    assert 'contract' in tiers
    assert 'streaming' in tiers
    assert 'structured_output' in tiers
