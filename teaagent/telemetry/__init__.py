"""Telemetry and observability integrations.

This package provides integrations for exporting telemetry data to
external observability platforms like OpenTelemetry.
"""

from __future__ import annotations

from teaagent.telemetry._audit import OTelAuditSink, configure_telemetry
from teaagent.telemetry._availability import HAS_OTEL
from teaagent.telemetry._config import TelemetryConfig, TelemetryNotAvailable
from teaagent.telemetry._metrics import (
    InMemoryMetricsSink,
    MetricSnapshot,
    OTelMetricsSink,
    configure_metrics,
)
from teaagent.telemetry._transport import TracingHTTPTransport

__all__ = [
    'HAS_OTEL',
    'InMemoryMetricsSink',
    'MetricSnapshot',
    'OTelAuditSink',
    'OTelMetricsSink',
    'TelemetryConfig',
    'TelemetryNotAvailable',
    'TracingHTTPTransport',
    'configure_metrics',
    'configure_telemetry',
]
