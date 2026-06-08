from __future__ import annotations

import json

from teaagent.acp_progress import (
    audit_event_to_session_update,
    audit_sink_for_acp_progress,
    build_session_update_notification,
    default_acp_emitter,
    stream_event_to_session_update,
    text_sink_for_acp_progress,
)
from teaagent.streaming.events import StreamEvent
from teaagent.types import AuditEvent


def test_build_session_update_notification() -> None:
    payload = build_session_update_notification('sess-1', {'sessionUpdate': 'ping'})
    assert payload['method'] == 'session/update'
    assert payload['params']['sessionId'] == 'sess-1'


def test_stream_event_mappings_cover_tool_and_run_states() -> None:
    assert (
        stream_event_to_session_update(StreamEvent('text_delta', {'text': 'hello'}))[
            'content'
        ]['text']
        == 'hello'
    )
    assert (
        stream_event_to_session_update(StreamEvent('text_delta', {'text': ''})) is None
    )
    assert (
        stream_event_to_session_update(
            StreamEvent('iteration_started', {'iteration': 2})
        )['sessionUpdate']
        == 'agent_thought_chunk'
    )
    tool = stream_event_to_session_update(
        StreamEvent(
            'tool_call_started',
            {'tool_name': 'read', 'call_id': 'c1'},
        )
    )
    assert tool['status'] == 'in_progress'
    assert (
        stream_event_to_session_update(
            StreamEvent('tool_call_completed', {'call_id': 'c1'})
        )['status']
        == 'completed'
    )
    failed = stream_event_to_session_update(
        StreamEvent('tool_call_failed', {'call_id': 'c1', 'error': 'boom'})
    )
    assert failed['status'] == 'failed'
    run_failed = stream_event_to_session_update(
        StreamEvent('run_failed', {'category': 'tool', 'message': 'denied'})
    )
    assert 'denied' in run_failed['content']['text']
    pending = stream_event_to_session_update(
        StreamEvent(
            'approval_required',
            {'call_id': 'c2', 'tool_name': 'write'},
        )
    )
    assert pending['status'] == 'pending'
    assert stream_event_to_session_update(StreamEvent('unknown', {})) is None


def test_audit_sink_and_text_sink_emit_notifications() -> None:
    lines: list[str] = []
    emit = default_acp_emitter(lines.append)
    event = AuditEvent(
        event_type='tool_call_started',
        run_id='run-1',
        payload={'tool_name': 'workspace_read_file', 'call_id': 'call-1'},
    )
    audit_sink_for_acp_progress('sess', emit)(event)
    assert lines
    payload = json.loads(lines[0])
    assert payload['params']['sessionId'] == 'sess'

    lines.clear()
    text_sink_for_acp_progress('sess', emit)('chunk text')
    assert (
        json.loads(lines[0])['params']['update']['sessionUpdate']
        == 'agent_message_chunk'
    )
    text_sink_for_acp_progress('sess', emit)('')
    assert len(lines) == 1

    assert audit_event_to_session_update(event) is not None

    lines = []
    default_acp_emitter(lines.append)(build_session_update_notification('s', {}))
    assert json.loads(lines[0])['method'] == 'session/update'
