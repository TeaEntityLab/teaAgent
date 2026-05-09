"""OpenTelemetry exporter for TeaAgent."""

from ._audit import OTelAuditSink, configure_telemetry
from ._availability import HAS_OTEL
from ._config import TelemetryConfig, TelemetryNotAvailable
from ._metrics import (
    InMemoryMetricsSink,
    MetricSnapshot,
    OTelMetricsSink,
    configure_metrics,
)
from ._transport import TracingHTTPTransport

__all__ = [
    'HAS_OTEL',
    'InMemoryMetricsSink',
    'MetricSnapshot',
    'OTelAuditSink',
    'OTelMetricsSink',
    'TracingHTTPTransport',
    'TelemetryConfig',
    'TelemetryNotAvailable',
    'configure_metrics',
    'configure_telemetry',
]
