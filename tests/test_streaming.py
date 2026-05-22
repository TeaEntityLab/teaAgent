from __future__ import annotations

import argparse

from teaagent.audit import AuditEvent, AuditLogger
from teaagent.streaming.content_filter import DecisionContentStreamer
from teaagent.streaming.events import audit_dict_to_stream_event, format_progress_line
from teaagent.streaming.handlers import build_run_stream_handlers


def test_decision_content_streamer_emits_only_final_content() -> None:
    chunks: list[str] = []
    streamer = DecisionContentStreamer(chunks.append)
    streamer.feed('{"type":"tool","tool_name":"x"}')
    assert chunks == []
    streamer.feed('{"type":"final","content":"hel')
    streamer.feed('lo"}')
    assert ''.join(chunks) == 'hello'


def test_format_progress_line_for_tool_call() -> None:
    event = AuditEvent(
        event_type='tool_call_started',
        run_id='r1',
        payload={'tool_name': 'workspace_read_file', 'call_id': 'c1'},
    )
    assert 'workspace_read_file' in (format_progress_line(event) or '')


def test_audit_dict_to_stream_event_maps_iteration() -> None:
    mapped = audit_dict_to_stream_event(
        {
            'event_type': 'iteration_started',
            'run_id': 'r1',
            'payload': {'iteration': 2},
        }
    )
    assert mapped is not None
    assert mapped.type == 'iteration_started'
    assert mapped.payload['iteration'] == 2


def test_build_run_stream_handlers_json_stream_progress() -> None:
    audit = AuditLogger()
    args = argparse.Namespace(
        json_stream=True,
        progress=None,
        no_progress=False,
        stream=False,
        stream_raw=False,
    )
    handlers = build_run_stream_handlers(args, audit)
    assert handlers.stream is False
    assert handlers.on_chunk is None
    assert handlers.on_chunk is None


def test_build_run_stream_handlers_enables_stream_flag() -> None:
    audit = AuditLogger()
    args = argparse.Namespace(
        json_stream=False,
        progress=False,
        no_progress=True,
        stream=True,
        stream_raw=False,
    )
    handlers = build_run_stream_handlers(args, audit)
    assert handlers.stream is True
    assert handlers.on_chunk is not None
    assert handlers.stream_text_only is True
