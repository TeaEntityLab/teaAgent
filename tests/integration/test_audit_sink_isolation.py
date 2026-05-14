"""IT-6: Audit sink failure isolation — a crashing sink must not crash the run.

Verifies that:
- A sink raising an exception does not propagate to the caller of ``record()``.
- Subsequent sinks still receive the event.
- The event is still appended to ``AuditLogger.events``.
- A well-behaved sink alongside a crashing sink still fires.
"""

from __future__ import annotations

from teaagent.audit import AuditEvent, AuditLogger


def test_crashing_sink_does_not_propagate():
    audit = AuditLogger()
    audit.add_sink(lambda _: (_ for _ in ()).throw(RuntimeError('boom')))  # type: ignore[misc]

    # Must not raise
    event = audit.record('test_event', 'run-001', detail='hello')
    assert event.event_type == 'test_event'


def test_crashing_sink_does_not_block_subsequent_sinks():
    received: list[AuditEvent] = []
    audit = AuditLogger()

    def bad_sink(e: AuditEvent) -> None:
        raise ValueError('bad sink')

    def good_sink(e: AuditEvent) -> None:
        received.append(e)

    audit.add_sink(bad_sink)
    audit.add_sink(good_sink)

    audit.record('run_started', 'run-001')
    assert len(received) == 1, 'good sink must still fire even when bad sink raises'


def test_crashing_sink_does_not_prevent_event_storage():
    audit = AuditLogger()

    def bad_sink(e: AuditEvent) -> None:
        raise RuntimeError('sink failure')

    audit.add_sink(bad_sink)
    audit.record('tool_call_started', 'run-002', tool_name='foo')
    assert len(audit.events) == 1
    assert audit.events[0].event_type == 'tool_call_started'


def test_multiple_crashing_sinks():
    received: list[str] = []
    audit = AuditLogger()

    for i in range(3):

        def bad_sink(e: AuditEvent, idx: int = i) -> None:
            raise RuntimeError(f'sink {idx} crashed')

        audit.add_sink(bad_sink)

    audit.add_sink(lambda e: received.append(e.event_type))

    audit.record('run_completed', 'run-003', answer='ok')
    assert received == ['run_completed']


def test_no_sinks_works():
    audit = AuditLogger()
    event = audit.record('heartbeat', 'run-004')
    assert event.event_type == 'heartbeat'
