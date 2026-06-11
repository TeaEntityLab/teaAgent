from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from teaagent.telemetry import (
    HAS_OTEL,
    InMemoryMetricsSink,
    OTelAuditSink,
    TelemetryConfig,
    TelemetryNotAvailable,
    TracingHTTPTransport,
    configure_telemetry,
)
from teaagent.types import AuditEvent


class _InMemorySpanExporter:
    """Minimal in-memory span exporter for testing (no InMemorySpanExporter in all OTel versions)."""

    def __init__(self) -> None:
        self.spans: list = []

    def export(self, spans: list) -> None:
        self.spans.extend(spans)

    def get_finished_spans(self) -> list:
        return list(self.spans)

    def shutdown(self) -> None:
        self.spans.clear()

    def force_flush(self, timeout_millis: int = 0) -> bool:
        return True


def test_default_config():
    cfg = TelemetryConfig()
    assert cfg.service_name == 'teaagent'
    assert cfg.otlp_endpoint is None
    assert not cfg.console


def test_custom_config():
    cfg = TelemetryConfig(
        service_name='my-agent',
        service_version='2.0.0',
        otlp_endpoint='http://otel:4318/v1/traces',
        console=True,
        sample_rate=0.5,
    )
    assert cfg.service_name == 'my-agent'
    assert cfg.otlp_endpoint == 'http://otel:4318/v1/traces'
    assert cfg.console


def test_frozen():
    cfg = TelemetryConfig()
    with pytest.raises(FrozenInstanceError):
        cfg.service_name = 'changed'


def test_error_message_is_helpful():
    exc = TelemetryNotAvailable('OPTL not installed')
    assert 'OPTL not installed' in str(exc)


def test_counts_run_and_tool_events():
    sink = InMemoryMetricsSink()

    sink.handle_event(AuditEvent(event_type='run_started', run_id='r1', payload={}))
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r1',
            payload={'tool_name': 'workspace_read_file'},
        )
    )
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_completed',
            run_id='r1',
            payload={'tool_name': 'workspace_read_file'},
        )
    )
    sink.handle_event(
        AuditEvent(
            event_type='run_completed',
            run_id='r1',
            payload={'iterations': 2, 'cost_cents': 0.3},
        )
    )

    snapshot = sink.snapshot()

    assert snapshot.counters['agent.runs.started'] == 1
    assert snapshot.counters['agent.runs.completed'] == 1
    assert snapshot.counters['agent.tool_calls.completed'] == 1
    assert snapshot.histograms['agent.run.iterations'] == [2.0]
    assert snapshot.histograms['agent.run.cost_cents'] == [0.3]


@pytest.fixture
def otel_audit_sink_setup():
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({'service.name': 'test'}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    sink = OTelAuditSink(provider, service_name='test')
    yield sink, exporter


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_run_started_creates_span(otel_audit_sink_setup):
    sink, exporter = otel_audit_sink_setup
    event = AuditEvent(
        event_type='run_started',
        run_id='r1',
        payload={'task': 'say hello'},
    )
    sink.handle_event(event)

    spans = exporter.get_finished_spans()
    assert len(spans) == 0  # not ended yet


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_full_run_lifecycle(otel_audit_sink_setup):
    sink, exporter = otel_audit_sink_setup
    # Run started
    sink.handle_event(
        AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'do X'})
    )
    # Tool call
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r1',
            payload={
                'call_id': 'c1',
                'tool_name': 'workspace_read_file',
                'annotations': {'destructive': False, 'read_only': True},
            },
        )
    )
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_completed',
            run_id='r1',
            payload={'call_id': 'c1'},
        )
    )
    # Run completed
    sink.handle_event(
        AuditEvent(
            event_type='run_completed',
            run_id='r1',
            payload={'iterations': 3},
        )
    )

    spans = exporter.get_finished_spans()
    # tool.call should be finished, agent.run should be finished
    assert len(spans) == 2
    span_names = {s.name for s in spans}
    assert 'agent.run' in span_names
    assert 'tool.call' in span_names


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_run_failed_sets_error_status(otel_audit_sink_setup):
    sink, exporter = otel_audit_sink_setup
    sink.handle_event(
        AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'fail'})
    )
    sink.handle_event(
        AuditEvent(
            event_type='run_failed',
            run_id='r1',
            payload={'error': 'something broke'},
        )
    )
    spans = exporter.get_finished_spans()
    run_spans = [s for s in spans if s.name == 'agent.run']
    assert len(run_spans) == 1
    assert not run_spans[0].status.is_ok


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_tool_span_has_attributes(otel_audit_sink_setup):
    sink, exporter = otel_audit_sink_setup
    sink.handle_event(
        AuditEvent(event_type='run_started', run_id='r2', payload={'task': 'x'})
    )
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r2',
            payload={
                'call_id': 'c2',
                'tool_name': 'workspace_run_shell_mutate',
                'annotations': {'destructive': True, 'idempotent': False},
            },
        )
    )
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_completed',
            run_id='r2',
            payload={'call_id': 'c2'},
        )
    )
    sink.handle_event(
        AuditEvent(
            event_type='run_completed',
            run_id='r2',
            payload={'iterations': 1},
        )
    )
    spans = exporter.get_finished_spans()
    tool_spans = [s for s in spans if s.name == 'tool.call']
    assert len(tool_spans) == 1
    attrs = dict(tool_spans[0].attributes or {})
    assert attrs.get('tool.name') == 'workspace_run_shell_mutate'
    assert attrs.get('tool.destructive')


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_shutdown_ends_open_spans(otel_audit_sink_setup):
    sink, exporter = otel_audit_sink_setup
    sink.handle_event(
        AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'x'})
    )
    sink.handle_event(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r1',
            payload={'call_id': 'c1', 'tool_name': 'workspace_read_file'},
        )
    )
    # No tool_call_completed or run_completed — simulate crash
    sink.shutdown()

    spans = exporter.get_finished_spans()
    assert len(spans) == 2


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_force_flush_returns_true(otel_audit_sink_setup):
    sink, _exporter = otel_audit_sink_setup
    assert sink.force_flush(timeout_millis=100)


@pytest.fixture
def tracing_http_transport_setup():
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({'service.name': 'test'}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer('test')

    class _FakeInner:
        def post_json(self, url, headers, payload, *, timeout):
            return {'ok': True}

    wrapped = TracingHTTPTransport(_FakeInner(), tracer)
    yield wrapped, exporter, tracer


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_post_json_creates_span(tracing_http_transport_setup):
    wrapped, exporter, _tracer = tracing_http_transport_setup
    result = wrapped.post_json(
        'https://api.example/chat',
        headers={'Authorization': 'Bearer x'},
        payload={'model': 'gpt-4', 'messages': []},
        timeout=30,
    )
    assert result == {'ok': True}
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == 'llm.http_call'
    attrs = dict(span.attributes or {})
    assert attrs.get('http.url') == 'https://api.example/chat'
    assert attrs.get('http.method') == 'POST'


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_post_json_error_sets_status(tracing_http_transport_setup):
    _wrapped, exporter, tracer = tracing_http_transport_setup

    class _FailingInner:
        def post_json(self, url, headers, payload, *, timeout):
            raise RuntimeError('network down')

    wrapped = TracingHTTPTransport(_FailingInner(), tracer)
    with pytest.raises(RuntimeError):
        wrapped.post_json(
            'https://api.example/chat',
            headers={},
            payload={},
            timeout=30,
        )
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert not spans[0].status.is_ok


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_console_only():
    sink, tracer = configure_telemetry(
        TelemetryConfig(service_name='test', console=True)
    )
    assert sink is not None
    assert tracer is not None
    sink.force_flush()


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_missing_otlp_endpoint_ok():
    sink, tracer = configure_telemetry(TelemetryConfig(service_name='test'))
    assert sink is not None
    sink.force_flush()


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_metrics_provider_records_run_lifecycle():
    from teaagent.telemetry import configure_metrics

    sink, provider = configure_metrics(TelemetryConfig(service_name='test'))
    try:
        sink.handle_event(AuditEvent(event_type='run_started', run_id='r1', payload={}))
        sink.handle_event(
            AuditEvent(
                event_type='run_completed',
                run_id='r1',
                payload={'iterations': 2, 'cost_cents': 0.4},
            )
        )
        assert provider.force_flush(timeout_millis=100)
    finally:
        provider.shutdown()


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry packages not installed')
def test_metrics_provider_uses_console_reader_when_requested():
    from teaagent.telemetry import configure_metrics

    sink, provider = configure_metrics(
        TelemetryConfig(service_name='test', console=True)
    )
    try:
        assert sink is not None
        assert provider is not None
        provider.force_flush(timeout_millis=100)
    finally:
        provider.shutdown()
