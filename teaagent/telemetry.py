"""OpenTelemetry exporter for TeaAgent.

Maps :class:`~teaagent.audit.AuditLogger` events to OpenTelemetry spans and
exports them via OTLP (HTTP/protobuf) or to the console.

    pip install teaagent[telemetry]

Integration point — wire as an audit sink::

    from teaagent.telemetry import configure_telemetry, HAS_OTEL

    if HAS_OTEL:
        sink = configure_telemetry(TelemetryConfig(
            service_name='my-agent',
            otlp_endpoint='http://localhost:4318/v1/traces',
        ))
        audit.add_sink(sink.handle_event)

Span hierarchy produced::

    agent.run
      └── tool.call          (one per tool invocation)
           ├── tool.name
           ├── tool.destructive
           └── tool.idempotent

The module is zero-overhead when OpenTelemetry packages are not installed:
``HAS_OTEL`` is ``False`` and all functions raise :class:`TelemetryNotAvailable`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Optional OpenTelemetry imports
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.trace import Status, StatusCode

    HAS_OTEL = True
except ImportError:  # pragma: no cover
    HAS_OTEL = False  # pragma: no cover

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TelemetryConfig:
    """Configuration for the OpenTelemetry exporter.

    Attributes:
        service_name: OTel service name (becomes ``service.name`` resource
            attribute).
        service_version: Optional version string.
        otlp_endpoint: Full OTLP HTTP endpoint URL (e.g.
            ``http://localhost:4318/v1/traces``). When set, spans are
            exported via OTLP.
        otlp_headers: Additional HTTP headers for OTLP requests.
        console: When ``True``, also print spans to stderr (useful for
            debugging).
        sample_rate: Fraction of runs to sample (1.0 = always-on).
    """

    service_name: str = 'teaagent'
    service_version: str = '0.1.0'
    otlp_endpoint: Optional[str] = None
    otlp_headers: dict[str, str] = field(default_factory=dict)
    console: bool = False
    sample_rate: float = 1.0


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class TelemetryNotAvailable(RuntimeError):
    """Raised when OTel packages are not installed."""


# ---------------------------------------------------------------------------
# Audit → OTel Span Sink
# ---------------------------------------------------------------------------


class OTelAuditSink:
    """Converts :class:`~teaagent.audit.AuditEvent` instances into
    OpenTelemetry spans.

    Wire it into :class:`~teaagent.audit.AuditLogger`::

        audit.add_sink(otel_sink.handle_event)

    Span lifecycle:

    - ``run_started`` opens an ``agent.run`` root span.
    - ``tool_call_started`` opens a ``tool.call`` child span.
    - ``tool_call_completed`` closes the child span.
    - ``run_completed`` / ``run_failed`` closes the root span.
    """

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
        """AuditLogger sink callback. Accepts ``AuditEvent``."""
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
                run_span.set_attribute(
                    'agent.iterations', payload.get('iterations', 0)
                )
                run_span.end()

    def shutdown(self) -> None:
        """End any open spans and flush the provider."""
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
        """Flush the underlying tracer provider."""
        return self._tracer_provider.force_flush(timeout_millis)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# HTTP Transport Wrapper
# ---------------------------------------------------------------------------


class TracingHTTPTransport:
    """Wraps an ``HTTPTransport`` to create OpenTelemetry spans for HTTP calls.

    Each ``post_json()`` call produces an ``llm.http_call`` span with
    ``http.url``, ``http.method``, and ``http.status_code`` attributes::

        from teaagent.llm import UrllibHTTPTransport, create_llm_adapter

        wrapped = TracingHTTPTransport(UrllibHTTPTransport(), tracer, 'my-agent')
        adapter = create_llm_adapter('openai', transport=wrapped)
    """

    def __init__(
        self,
        inner: Any,
        tracer: '_otel_trace.Tracer',
    ) -> None:
        self._inner = inner
        self._tracer = tracer

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any]:
        method = 'POST'
        with self._tracer.start_as_current_span('llm.http_call') as span:
            span.set_attribute('http.url', url)
            span.set_attribute('http.method', method)
            span.set_attribute(
                'http.request_content_length',
                len(json.dumps(payload, ensure_ascii=False)),
            )
            try:
                result = self._inner.post_json(url, headers, payload, timeout=timeout)
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            span.set_status(Status(StatusCode.OK))
            return result


# ---------------------------------------------------------------------------
# One-shot configuration
# ---------------------------------------------------------------------------


def configure_telemetry(
    config: TelemetryConfig,
) -> tuple[OTelAuditSink, '_otel_trace.Tracer']:
    """One-shot OpenTelemetry setup.

    Creates a ``TracerProvider``, configures exporters, and returns an
    :class:`OTelAuditSink` ready to wire into an ``AuditLogger``.

    Returns:
        ``(sink, tracer)`` tuple. Use ``sink.handle_event`` as the audit
        sink callback; use ``tracer`` for manual instrumentation.
    """
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
        provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )

    _otel_trace.set_tracer_provider(provider)

    sink = OTelAuditSink(
        provider, service_name=config.service_name
    )
    tracer = provider.get_tracer(config.service_name)

    return sink, tracer


__all__ = [
    'HAS_OTEL',
    'OTelAuditSink',
    'TracingHTTPTransport',
    'TelemetryConfig',
    'TelemetryNotAvailable',
    'configure_telemetry',
]
