from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TelemetryConfig:
    """Configuration for telemetry exporters."""

    service_name: str = 'teaagent'
    service_version: str = '0.1.0'
    otlp_endpoint: Optional[str] = None
    metrics_otlp_endpoint: Optional[str] = None
    otlp_headers: dict[str, str] = field(default_factory=dict)
    console: bool = False
    sample_rate: float = 1.0


class TelemetryNotAvailable(RuntimeError):
    """Raised when OTel packages are not installed."""
