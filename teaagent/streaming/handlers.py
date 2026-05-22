from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from teaagent.audit import AuditLogger
from teaagent.streaming.content_filter import DecisionContentStreamer
from teaagent.streaming.events import (
    StreamEvent,
    audit_sink_for_json_stream,
    audit_sink_for_progress,
    emit_stream_event,
)


@dataclass(frozen=True)
class RunStreamHandlers:
    stream: bool
    on_chunk: Optional[Callable[[str], None]]
    stream_text_only: bool = True

    def wrap_chunk(self, chunk: str) -> None:
        if self.on_chunk is not None:
            self.on_chunk(chunk)


def _default_progress_enabled(args: argparse.Namespace) -> bool:
    explicit = getattr(args, 'progress', None)
    if explicit is not None:
        return bool(explicit)
    no_progress = getattr(args, 'no_progress', False)
    if no_progress:
        return False
    if getattr(args, 'json_stream', False):
        return True
    return sys.stderr.isatty()


def build_run_stream_handlers(
    args: argparse.Namespace,
    audit: AuditLogger,
) -> RunStreamHandlers:
    """Wire progress and token streaming for CLI agent runs."""
    json_stream = bool(getattr(args, 'json_stream', False))
    progress = _default_progress_enabled(args)
    stream = bool(getattr(args, 'stream', False))
    stream_text_only = not bool(getattr(args, 'stream_raw', False))

    on_chunk: Optional[Callable[[str], None]] = None

    if json_stream:

        def emit(event: StreamEvent) -> None:
            emit_stream_event(event)

        if progress:
            audit.add_sink(audit_sink_for_json_stream(emit))
        if stream:

            def text_sink(text: str) -> None:
                emit(StreamEvent('text_delta', {'text': text}))

            base_chunk: Callable[[str], None] = text_sink
            if stream_text_only:
                filter_streamer = DecisionContentStreamer(text_sink)
                base_chunk = filter_streamer.feed
            on_chunk = base_chunk
    else:
        if progress:
            audit.add_sink(audit_sink_for_progress())
        if stream:

            def text_stdout(text: str) -> None:
                print(text, end='', file=sys.stdout, flush=True)

            if stream_text_only:
                on_chunk = DecisionContentStreamer(text_stdout).feed
            else:
                on_chunk = text_stdout

    return RunStreamHandlers(
        stream=stream,
        on_chunk=on_chunk,
        stream_text_only=stream_text_only,
    )


def adapter_supports_streaming(adapter: Any) -> bool:
    from teaagent.llm._adapters import (
        ClaudeAdapter,
        GeminiAdapter,
        OpenAICompatibleAdapter,
    )

    return isinstance(adapter, (OpenAICompatibleAdapter, ClaudeAdapter, GeminiAdapter))
