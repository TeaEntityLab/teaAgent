from __future__ import annotations

try:
    import opentelemetry  # noqa: F401

    HAS_OTEL = True
except ImportError:  # pragma: no cover
    HAS_OTEL = False  # pragma: no cover
