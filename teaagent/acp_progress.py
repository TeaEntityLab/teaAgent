from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional

from teaagent.audit import AuditEvent
from teaagent.streaming.events import StreamEvent, audit_event_to_stream_event


def build_session_update_notification(
    session_id: str,
    update: dict[str, Any],
) -> dict[str, Any]:
    """Build a JSON-RPC notification for ACP ``session/update``."""
    return {
        'jsonrpc': '2.0',
        'method': 'session/update',
        'params': {
            'sessionId': session_id,
            'update': update,
        },
    }


def stream_event_to_session_update(event: StreamEvent) -> Optional[dict[str, Any]]:
    """Map internal stream events to ACP session update payloads."""
    if event.type == 'text_delta':
        text = str(event.payload.get('text', ''))
        if not text:
            return None
        return {
            'sessionUpdate': 'agent_message_chunk',
            'content': {'type': 'text', 'text': text},
        }
    if event.type == 'iteration_started':
        iteration = event.payload.get('iteration')
        return {
            'sessionUpdate': 'agent_thought_chunk',
            'content': {
                'type': 'text',
                'text': f'Iteration {iteration}\n',
            },
        }
    if event.type == 'tool_call_started':
        tool_name = event.payload.get('tool_name')
        call_id = event.payload.get('call_id')
        return {
            'sessionUpdate': 'tool_call',
            'toolCallId': str(call_id or ''),
            'title': str(tool_name or 'tool'),
            'kind': 'other',
            'status': 'in_progress',
        }
    if event.type == 'tool_call_completed':
        return {
            'sessionUpdate': 'tool_call_update',
            'toolCallId': str(event.payload.get('call_id') or ''),
            'status': 'completed',
        }
    if event.type == 'tool_call_failed':
        return {
            'sessionUpdate': 'tool_call_update',
            'toolCallId': str(event.payload.get('call_id') or ''),
            'status': 'failed',
            'content': [
                {
                    'type': 'content',
                    'content': {
                        'type': 'text',
                        'text': str(event.payload.get('error') or 'tool failed'),
                    },
                }
            ],
        }
    if event.type == 'run_failed':
        return {
            'sessionUpdate': 'agent_message_chunk',
            'content': {
                'type': 'text',
                'text': (
                    f'Run failed: {event.payload.get("category")}: '
                    f'{event.payload.get("message")}\n'
                ),
            },
        }
    if event.type == 'approval_required':
        return {
            'sessionUpdate': 'tool_call',
            'toolCallId': str(event.payload.get('call_id') or ''),
            'title': str(event.payload.get('tool_name') or 'approval'),
            'kind': 'other',
            'status': 'pending',
        }
    return None


def audit_event_to_session_update(event: AuditEvent) -> Optional[dict[str, Any]]:
    mapped = audit_event_to_stream_event(event)
    if mapped is None:
        return None
    return stream_event_to_session_update(mapped)


def audit_sink_for_acp_progress(
    session_id: str,
    emit: Callable[[dict[str, Any]], None],
) -> Callable[[AuditEvent], None]:
    """Return an audit sink that emits ACP ``session/update`` notifications."""

    def _sink(event: AuditEvent) -> None:
        update = audit_event_to_session_update(event)
        if update is None:
            return
        emit(build_session_update_notification(session_id, update))

    return _sink


def text_sink_for_acp_progress(
    session_id: str,
    emit: Callable[[dict[str, Any]], None],
) -> Callable[[str], None]:
    """Return an ``on_chunk`` handler that emits ACP agent message chunks."""

    def _sink(text: str) -> None:
        if not text:
            return
        update = stream_event_to_session_update(
            StreamEvent('text_delta', {'text': text})
        )
        if update is None:
            return
        emit(build_session_update_notification(session_id, update))

    return _sink


def default_acp_emitter(
    write_line: Callable[[str], None],
) -> Callable[[dict[str, Any]], None]:
    def _emit(notification: dict[str, Any]) -> None:
        write_line(json.dumps(notification, ensure_ascii=False))

    return _emit
