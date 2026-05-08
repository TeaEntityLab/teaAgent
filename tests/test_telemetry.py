from __future__ import annotations

import unittest

from teaagent.audit import AuditEvent
from teaagent.telemetry import (
    HAS_OTEL,
    OTelAuditSink,
    TelemetryConfig,
    TelemetryNotAvailable,
    TracingHTTPTransport,
    configure_telemetry,
)


class _InMemorySpanExporter:
    """Minimal in-memory span exporter for testing (no InMemorySpanExporter in all OTel versions)."""

    def __init__(self) -> None:
        self.spans: list = []

    def export(self, spans: list) -> None:
        self.spans.extend(spans)

    def get_finished_spans(self) -> list:
        return list(self.spans)

    def shutdown(self) -> None:
        self.spans.clear()

    def force_flush(self, timeout_millis: int = 0) -> bool:
        return True


class TelemetryConfigTests(unittest.TestCase):
    def test_default_config(self) -> None:
        cfg = TelemetryConfig()
        self.assertEqual(cfg.service_name, 'teaagent')
        self.assertIsNone(cfg.otlp_endpoint)
        self.assertFalse(cfg.console)

    def test_custom_config(self) -> None:
        cfg = TelemetryConfig(
            service_name='my-agent',
            service_version='2.0.0',
            otlp_endpoint='http://otel:4318/v1/traces',
            console=True,
            sample_rate=0.5,
        )
        self.assertEqual(cfg.service_name, 'my-agent')
        self.assertEqual(cfg.otlp_endpoint, 'http://otel:4318/v1/traces')
        self.assertTrue(cfg.console)

    def test_frozen(self) -> None:
        cfg = TelemetryConfig()
        with self.assertRaises(Exception):
            cfg.service_name = 'changed'  # type: ignore[misc]


class TelemetryNotAvailableTests(unittest.TestCase):
    def test_error_message_is_helpful(self) -> None:
        exc = TelemetryNotAvailable('OPTL not installed')
        self.assertIn('OPTL not installed', str(exc))


@unittest.skipUnless(HAS_OTEL, 'opentelemetry packages not installed')
class OTelAuditSinkTests(unittest.TestCase):
    def setUp(self) -> None:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        self._exporter = _InMemorySpanExporter()
        self._provider = TracerProvider(resource=Resource.create({'service.name': 'test'}))
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))
        self._sink = OTelAuditSink(self._provider, service_name='test')

    def test_run_started_creates_span(self) -> None:
        event = AuditEvent(
            event_type='run_started',
            run_id='r1',
            payload={'task': 'say hello'},
        )
        self._sink.handle_event(event)

        spans = self._exporter.get_finished_spans()
        self.assertEqual(len(spans), 0)  # not ended yet

    def test_full_run_lifecycle(self) -> None:
        # Run started
        self._sink.handle_event(
            AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'do X'})
        )
        # Tool call
        self._sink.handle_event(
            AuditEvent(
                event_type='tool_call_started',
                run_id='r1',
                payload={
                    'call_id': 'c1',
                    'tool_name': 'workspace_read_file',
                    'annotations': {'destructive': False, 'read_only': True},
                },
            )
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='tool_call_completed',
                run_id='r1',
                payload={'call_id': 'c1'},
            )
        )
        # Run completed
        self._sink.handle_event(
            AuditEvent(
                event_type='run_completed',
                run_id='r1',
                payload={'iterations': 3},
            )
        )

        spans = self._exporter.get_finished_spans()
        # tool.call should be finished, agent.run should be finished
        self.assertEqual(len(spans), 2)
        span_names = {s.name for s in spans}
        self.assertIn('agent.run', span_names)
        self.assertIn('tool.call', span_names)

    def test_run_failed_sets_error_status(self) -> None:
        self._sink.handle_event(
            AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'fail'})
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='run_failed',
                run_id='r1',
                payload={'error': 'something broke'},
            )
        )
        spans = self._exporter.get_finished_spans()
        run_spans = [s for s in spans if s.name == 'agent.run']
        self.assertEqual(len(run_spans), 1)
        self.assertFalse(run_spans[0].status.is_ok)

    def test_tool_span_has_attributes(self) -> None:
        self._sink.handle_event(
            AuditEvent(event_type='run_started', run_id='r2', payload={'task': 'x'})
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='tool_call_started',
                run_id='r2',
                payload={
                    'call_id': 'c2',
                    'tool_name': 'workspace_run_shell_mutate',
                    'annotations': {'destructive': True, 'idempotent': False},
                },
            )
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='tool_call_completed',
                run_id='r2',
                payload={'call_id': 'c2'},
            )
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='run_completed',
                run_id='r2',
                payload={'iterations': 1},
            )
        )
        spans = self._exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.name == 'tool.call']
        self.assertEqual(len(tool_spans), 1)
        attrs = dict(tool_spans[0].attributes or {})
        self.assertEqual(attrs.get('tool.name'), 'workspace_run_shell_mutate')
        self.assertTrue(attrs.get('tool.destructive'))

    def test_shutdown_ends_open_spans(self) -> None:
        self._sink.handle_event(
            AuditEvent(event_type='run_started', run_id='r1', payload={'task': 'x'})
        )
        self._sink.handle_event(
            AuditEvent(
                event_type='tool_call_started',
                run_id='r1',
                payload={'call_id': 'c1', 'tool_name': 'workspace_read_file'},
            )
        )
        # No tool_call_completed or run_completed — simulate crash
        self._sink.shutdown()

        spans = self._exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)

    def test_force_flush_returns_true(self) -> None:
        self.assertTrue(self._sink.force_flush(timeout_millis=100))


@unittest.skipUnless(HAS_OTEL, 'opentelemetry packages not installed')
class TracingHTTPTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        self._exporter = _InMemorySpanExporter()
        self._provider = TracerProvider(resource=Resource.create({'service.name': 'test'}))
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))
        self._tracer = self._provider.get_tracer('test')

        class _FakeInner:
            def post_json(self, url, headers, payload, *, timeout):
                return {'ok': True}

        self._wrapped = TracingHTTPTransport(_FakeInner(), self._tracer)

    def test_post_json_creates_span(self) -> None:
        result = self._wrapped.post_json(
            'https://api.example/chat',
            headers={'Authorization': 'Bearer x'},
            payload={'model': 'gpt-4', 'messages': []},
            timeout=30,
        )
        self.assertEqual(result, {'ok': True})
        spans = self._exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, 'llm.http_call')
        attrs = dict(span.attributes or {})
        self.assertEqual(attrs.get('http.url'), 'https://api.example/chat')
        self.assertEqual(attrs.get('http.method'), 'POST')

    def test_post_json_error_sets_status(self) -> None:
        class _FailingInner:
            def post_json(self, url, headers, payload, *, timeout):
                raise RuntimeError('network down')

        wrapped = TracingHTTPTransport(_FailingInner(), self._tracer)
        with self.assertRaises(RuntimeError):
            wrapped.post_json(
                'https://api.example/chat',
                headers={},
                payload={},
                timeout=30,
            )
        spans = self._exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertFalse(spans[0].status.is_ok)


@unittest.skipUnless(HAS_OTEL, 'opentelemetry packages not installed')
class ConfigureTelemetryTests(unittest.TestCase):
    def test_console_only(self) -> None:
        sink, tracer = configure_telemetry(
            TelemetryConfig(service_name='test', console=True)
        )
        self.assertIsNotNone(sink)
        self.assertIsNotNone(tracer)
        sink.force_flush()

    def test_missing_otlp_endpoint_ok(self) -> None:
        sink, tracer = configure_telemetry(
            TelemetryConfig(service_name='test')
        )
        self.assertIsNotNone(sink)
        sink.force_flush()


if __name__ == '__main__':
    unittest.main()
