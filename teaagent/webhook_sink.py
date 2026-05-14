"""Webhook audit sink — forwards ``AuditEvent`` records to an HTTP endpoint.

Usage::

    from teaagent.webhook_sink import WebhookAuditSink

    sink = WebhookAuditSink(
        url='https://hooks.example.com/teaagent',
        secret='shared-hmac-secret',     # optional HMAC-SHA256 signature
        event_filter={'run_completed', 'tool_call_started'},  # None = all
        timeout=5,
    )
    audit_logger.add_sink(sink)

Each delivery is a ``POST`` with ``Content-Type: application/json`` carrying
the serialised ``AuditEvent`` payload.

When ``secret`` is set, the request includes an
``X-TeaAgent-Signature-256: sha256=<hex>`` header matching GitHub's webhook
convention so consumers can verify authenticity.

Failed deliveries are silently discarded (the ``AuditLogger`` sink contract
requires non-raising behaviour — see ``AuditLogger.record``).  Set
``raise_on_error=True`` during tests to surface delivery failures.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import ssl
from typing import Any, Optional
from urllib.parse import urlparse

from teaagent.audit import AuditEvent


class WebhookAuditSink:
    """Delivers audit events to a remote HTTP(S) endpoint.

    Parameters
    ----------
    url:
        The full HTTP(S) URL to POST to.
    secret:
        Optional shared secret for HMAC-SHA256 request signing.
    event_filter:
        If provided, only events whose ``event_type`` is in this set are
        delivered.  ``None`` means all events are delivered.
    timeout:
        Socket timeout in seconds for each delivery attempt.
    raise_on_error:
        When ``True``, HTTP and network errors are re-raised instead of
        suppressed.  Useful in tests; leave ``False`` in production.
    extra_headers:
        Additional HTTP headers added to every request (e.g. auth tokens).
    """

    def __init__(
        self,
        url: str,
        *,
        secret: Optional[str] = None,
        event_filter: Optional[set[str]] = None,
        timeout: int = 5,
        raise_on_error: bool = False,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('WebhookAuditSink url must be an http(s) URL')
        self.url = url
        self.secret = secret
        self.event_filter = event_filter
        self.timeout = timeout
        self.raise_on_error = raise_on_error
        self.extra_headers: dict[str, str] = extra_headers or {}
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self._path = parsed.path or '/'
        if parsed.query:
            self._path = f'{self._path}?{parsed.query}'

    def __call__(self, event: AuditEvent) -> None:
        """Deliver *event* to the configured webhook endpoint."""
        if self.event_filter is not None and event.event_type not in self.event_filter:
            return
        body = self._serialise(event)
        headers = self._build_headers(body)
        try:
            self._post(body, headers)
        except Exception as exc:  # noqa: BLE001
            if self.raise_on_error:
                raise
            _ = exc  # explicitly discard — sink must not crash the run

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _serialise(self, event: AuditEvent) -> bytes:
        return json.dumps(
            json.loads(event.to_json()),
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')

    def _build_headers(self, body: bytes) -> dict[str, str]:
        headers: dict[str, str] = {
            'Content-Type': 'application/json',
            'Content-Length': str(len(body)),
            'User-Agent': 'TeaAgent-WebhookSink/1',
        }
        if self.secret:
            sig = hmac.new(
                self.secret.encode('utf-8'), body, hashlib.sha256
            ).hexdigest()
            headers['X-TeaAgent-Signature-256'] = f'sha256={sig}'
        headers.update(self.extra_headers)
        return headers

    def _post(self, body: bytes, headers: dict[str, str]) -> None:
        if self._scheme == 'https':
            ctx = ssl.create_default_context()
            conn: Any = http.client.HTTPSConnection(
                self._host, self._port, timeout=self.timeout, context=ctx
            )
        else:
            conn = http.client.HTTPConnection(
                self._host, self._port, timeout=self.timeout
            )
        try:
            conn.request('POST', self._path, body=body, headers=headers)
            resp = conn.getresponse()
            resp.read()  # drain to allow connection reuse
        finally:
            conn.close()
