"""Prometheus metrics export for hybrid approval queue."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """A Prometheus metric."""

    name: str
    value: float
    metric_type: str  # 'gauge', 'counter', 'histogram'
    help_text: str
    labels: dict[str, str]


class PrometheusMetricsExporter:
    """Export metrics in Prometheus format."""

    def __init__(self) -> None:
        """Initialize metrics exporter."""
        self._metrics: dict[str, Metric] = {}

    def set_metric(
        self,
        name: str,
        value: float,
        metric_type: str = 'gauge',
        help_text: str = '',
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Set a metric value.

        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric (gauge, counter, histogram)
            help_text: Help text for the metric
            labels: Metric labels
        """
        self._metrics[name] = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            help_text=help_text,
            labels=labels or {},
        )

    def increment_metric(
        self,
        name: str,
        value: float = 1.0,
        help_text: str = '',
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Value to increment by
            help_text: Help text for the metric
            labels: Metric labels
        """
        if name in self._metrics:
            self._metrics[name].value += value
        else:
            self._metrics[name] = Metric(
                name=name,
                value=value,
                metric_type='counter',
                help_text=help_text,
                labels=labels or {},
            )

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a metric by name.

        Args:
            name: Metric name

        Returns:
            Metric or None if not found
        """
        return self._metrics.get(name)

    def export_metrics(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Metrics in Prometheus text format
        """
        lines = []

        for metric in self._metrics.values():
            # Add help text
            if metric.help_text:
                lines.append(f'# HELP {metric.name} {metric.help_text}')

            # Add type
            lines.append(f'# TYPE {metric.name} {metric.metric_type}')

            # Add metric value with labels
            if metric.labels:
                label_str = ','.join(f'{k}="{v}"' for k, v in metric.labels.items())
                lines.append(f'{metric.name}{{{label_str}}} {metric.value}')
            else:
                lines.append(f'{metric.name} {metric.value}')

        return '\n'.join(lines)

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
