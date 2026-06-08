from __future__ import annotations

import contextlib
import json
from typing import Any

_otel_trace: Any = None
with contextlib.suppress(ImportError):
    from opentelemetry import trace

    _otel_trace = trace


class TracingHTTPTransport:
    """Wraps an HTTP transport to create OpenTelemetry spans for HTTP calls."""

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
        from opentelemetry.trace import Status, StatusCode

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
