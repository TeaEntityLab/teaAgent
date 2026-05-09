from __future__ import annotations

from typing import Any, Optional

from ._availability import HAS_OTEL
from ._config import TelemetryConfig, TelemetryNotAvailable

try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # pragma: no cover
    pass


class OTelAuditSink:
    def __init__(
        self,
        tracer_provider: '_otel_trace.TracerProvider',
        *,
        service_name: str = 'teaagent',
    ) -> None:
        self._tracer_provider = tracer_provider
        self._tracer = tracer_provider.get_tracer(service_name)
        self._run_spans: dict[str, '_otel_trace.Span'] = {}
        self._tool_spans: dict[str, '_otel_trace.Span'] = {}

    @property
    def tracer_provider(self) -> '_otel_trace.TracerProvider':
        return self._tracer_provider

    def handle_event(self, event: Any) -> None:
        etype: str = event.event_type
        run_id: str = event.run_id
        payload: dict[str, Any] = getattr(event, 'payload', {})

        if etype == 'run_started':
            span = self._tracer.start_span('agent.run')
            span.set_attribute('agent.task', payload.get('task', ''))
            span.set_attribute('agent.run_id', run_id)
            self._run_spans[run_id] = span

        elif etype == 'tool_call_started':
            call_id = payload.get('call_id', '')
            name = payload.get('tool_name', 'unknown')
            annotations = payload.get('annotations', {})

            parent_span = self._run_spans.get(run_id)
            ctx = (
                _otel_trace.set_span_in_context(parent_span)
                if parent_span is not None
                else None
            )
            span = self._tracer.start_span(
                'tool.call',
                context=ctx,
                attributes={
                    'tool.name': name,
                    'tool.destructive': annotations.get('destructive', False),
                    'tool.idempotent': annotations.get('idempotent', False),
                    'tool.read_only': annotations.get('read_only', True),
                },
            )
            self._tool_spans[call_id] = span

        elif etype == 'tool_call_completed':
            call_id = payload.get('call_id', '')
            tool_span: Optional['_otel_trace.Span'] = self._tool_spans.get(call_id)
            if tool_span is not None:
                tool_span.end()
                del self._tool_spans[call_id]

        elif etype in ('run_completed', 'run_failed'):
            run_span: Optional['_otel_trace.Span'] = self._run_spans.get(run_id)
            if run_span is not None:
                del self._run_spans[run_id]
                if etype == 'run_failed':
                    run_span.set_status(
                        Status(StatusCode.ERROR, payload.get('error', ''))
                    )
                else:
                    run_span.set_status(Status(StatusCode.OK))
                run_span.set_attribute('agent.outcome', etype)
                run_span.set_attribute('agent.iterations', payload.get('iterations', 0))
                run_span.end()

    def shutdown(self) -> None:
        for span in self._run_spans.values():
            if span.is_recording():
                span.set_status(Status(StatusCode.ERROR, 'agent interrupted'))
                span.end()
        for span in self._tool_spans.values():
            if span.is_recording():
                span.end()
        self._run_spans.clear()
        self._tool_spans.clear()

    def force_flush(self, timeout_millis: int = 5000) -> bool:
        return self._tracer_provider.force_flush(timeout_millis)  # type: ignore[attr-defined]


def configure_telemetry(
    config: TelemetryConfig,
) -> tuple[OTelAuditSink, '_otel_trace.Tracer']:
    if not HAS_OTEL:
        raise TelemetryNotAvailable(
            'OpenTelemetry packages are not installed. '
            'Install with: pip install teaagent[telemetry]'
        )

    resource_attrs: dict[str, Any] = {
        SERVICE_NAME: config.service_name,
    }
    if config.service_version:
        resource_attrs[SERVICE_VERSION] = config.service_version

    provider = TracerProvider(
        resource=Resource(resource_attrs),
    )

    if config.otlp_endpoint:
        exporter: Any = OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
            headers=config.otlp_headers,
        )
        processor: Any = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    if config.console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    _otel_trace.set_tracer_provider(provider)

    sink = OTelAuditSink(provider, service_name=config.service_name)
    tracer = provider.get_tracer(config.service_name)

    return sink, tracer
