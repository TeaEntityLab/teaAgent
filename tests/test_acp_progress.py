from __future__ import annotations

from teaagent.acp_progress import (
    audit_event_to_session_update,
    build_session_update_notification,
    stream_event_to_session_update,
)
from teaagent.audit import AuditEvent
from teaagent.streaming.events import StreamEvent


def test_build_session_update_notification_shape() -> None:
    payload = build_session_update_notification(
        'sess-1',
        {'sessionUpdate': 'tool_call', 'toolCallId': 'c1', 'status': 'pending'},
    )
    assert payload['method'] == 'session/update'
    assert payload['params']['sessionId'] == 'sess-1'


def test_audit_event_maps_tool_call_started() -> None:
    update = audit_event_to_session_update(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r1',
            payload={'tool_name': 'workspace_read_file', 'call_id': 'c1'},
        )
    )
    assert update is not None
    assert update['sessionUpdate'] == 'tool_call'
    assert update['toolCallId'] == 'c1'


def test_text_delta_maps_agent_message_chunk() -> None:
    update = stream_event_to_session_update(
        StreamEvent('text_delta', {'text': 'hello'})
    )
    assert update is not None
    assert update['sessionUpdate'] == 'agent_message_chunk'
    assert update['content']['text'] == 'hello'
