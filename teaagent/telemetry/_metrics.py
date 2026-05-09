from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ._availability import HAS_OTEL
from ._config import TelemetryConfig, TelemetryNotAvailable

try:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class MetricSnapshot:
    counters: dict[str, int]
    histograms: dict[str, list[float]]


class InMemoryMetricsSink:
    """Audit sink that keeps lightweight counters and histogram samples."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def handle_event(self, event: Any) -> None:
        etype: str = event.event_type
        payload: dict[str, Any] = getattr(event, 'payload', {})
        if etype == 'run_started':
            self._increment('agent.runs.started')
        elif etype == 'run_completed':
            self._increment('agent.runs.completed')
            self._observe_payload_number('agent.run.iterations', payload, 'iterations')
            self._observe_payload_number('agent.run.cost_cents', payload, 'cost_cents')
        elif etype == 'run_failed':
            self._increment('agent.runs.failed')
            self._observe_payload_number('agent.run.cost_cents', payload, 'cost_cents')
        elif etype == 'tool_call_started':
            tool_name = str(payload.get('tool_name', 'unknown'))
            self._increment('agent.tool_calls.started')
            self._increment(f'agent.tool_calls.started.{tool_name}')
        elif etype == 'tool_call_completed':
            tool_name = str(payload.get('tool_name', 'unknown'))
            self._increment('agent.tool_calls.completed')
            self._increment(f'agent.tool_calls.completed.{tool_name}')

    def snapshot(self) -> MetricSnapshot:
        return MetricSnapshot(
            counters=dict(self._counters),
            histograms={key: list(value) for key, value in self._histograms.items()},
        )

    def _increment(self, name: str) -> None:
        self._counters[name] += 1

    def _observe_payload_number(
        self, metric_name: str, payload: dict[str, Any], payload_key: str
    ) -> None:
        value = payload.get(payload_key)
        if isinstance(value, (int, float)):
            self._histograms[metric_name].append(float(value))


class OTelMetricsSink:
    """Audit sink that maps run/tool lifecycle events to OTel metrics."""

    def __init__(
        self,
        meter_provider: 'MeterProvider',
        *,
        service_name: str = 'teaagent',
    ) -> None:
        if not HAS_OTEL:
            raise TelemetryNotAvailable(
                'OpenTelemetry packages are not installed. '
                'Install with: pip install teaagent[telemetry]'
            )
        meter = meter_provider.get_meter(service_name)
        self._run_counter = meter.create_counter('agent.runs')
        self._tool_call_counter = meter.create_counter('agent.tool_calls')
        self._iteration_histogram = meter.create_histogram('agent.run.iterations')
        self._cost_histogram = meter.create_histogram('agent.run.cost_cents')

    def handle_event(self, event: Any) -> None:
        etype: str = event.event_type
        payload: dict[str, Any] = getattr(event, 'payload', {})
        if etype in {'run_started', 'run_completed', 'run_failed'}:
            self._run_counter.add(1, {'event_type': etype})
            self._record_number(self._iteration_histogram, payload, 'iterations')
            self._record_number(self._cost_histogram, payload, 'cost_cents')
        elif etype in {'tool_call_started', 'tool_call_completed'}:
            self._tool_call_counter.add(
                1,
                {
                    'event_type': etype,
                    'tool_name': str(payload.get('tool_name', 'unknown')),
                },
            )

    def _record_number(
        self, instrument: Any, payload: dict[str, Any], key: str
    ) -> None:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            instrument.record(float(value))


def configure_metrics(
    config: TelemetryConfig,
) -> tuple[OTelMetricsSink, 'MeterProvider']:
    """Set up an OpenTelemetry MeterProvider and return a wired metrics sink."""
    if not HAS_OTEL:
        raise TelemetryNotAvailable(
            'OpenTelemetry packages are not installed. '
            'Install with: pip install teaagent[telemetry]'
        )

    resource_attrs: dict[str, Any] = {SERVICE_NAME: config.service_name}
    if config.service_version:
        resource_attrs[SERVICE_VERSION] = config.service_version

    readers: list[Any] = []
    if config.metrics_otlp_endpoint:
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=config.metrics_otlp_endpoint,
                    headers=config.otlp_headers,
                )
            )
        )
    if config.console:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

    provider = MeterProvider(
        resource=Resource(resource_attrs),
        metric_readers=readers,
    )
    sink = OTelMetricsSink(provider, service_name=config.service_name)
    return sink, provider
