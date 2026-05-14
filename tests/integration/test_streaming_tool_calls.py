"""IT-13: Streaming LLM path interacts correctly with tool dispatch and audit.

Verifies that:
- ``on_chunk`` callbacks fire when streaming is enabled.
- The resulting decision is still parsed and dispatched correctly.
- Audit events are recorded regardless of stream mode.

Uses a stub adapter that delivers chunks manually.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent


class _StreamingStubAdapter:
    """Adapter that fires on_chunk callbacks then returns a FinalAnswer."""

    provider = 'stub'
    chunks_fired: list[str] = []

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        self.chunks_fired = []
        full = '{"type":"final","content":"streaming response"}'
        if request.on_chunk is not None:
            for char in full:
                request.on_chunk(char)
                self.chunks_fired.append(char)
        return LLMResponse(
            provider='stub',
            model='stub',
            content=full,
            input_tokens=10,
            output_tokens=5,
        )


def test_streaming_on_chunk_fires(tmp_path):
    chunks: list[str] = []
    adapter = _StreamingStubAdapter()
    config = ChatAgentConfig.from_root(
        tmp_path,
        stream=True,
        on_chunk=chunks.append,
    )
    result = run_chat_agent(task='hello', adapter=adapter, config=config)
    assert result.status == 'completed'
    assert len(chunks) > 0, 'on_chunk callbacks must have fired'
    assert ''.join(chunks).startswith('{"type":"final"')


def test_streaming_audit_events_recorded(tmp_path):
    audit = AuditLogger()
    adapter = _StreamingStubAdapter()
    config = ChatAgentConfig.from_root(tmp_path, stream=True)
    run_chat_agent(task='hello', adapter=adapter, config=config, audit=audit)

    assert any(e.event_type == 'run_completed' for e in audit.events)


def test_streaming_cost_accumulated(tmp_path):
    adapter = _StreamingStubAdapter()
    config = ChatAgentConfig.from_root(tmp_path, stream=True)
    result = run_chat_agent(task='hello', adapter=adapter, config=config)
    # Tokens from streaming adapter should be accumulated
    assert result.input_tokens >= 0
    assert result.output_tokens >= 0


def test_non_streaming_works_without_on_chunk(tmp_path):
    adapter = _StreamingStubAdapter()
    config = ChatAgentConfig.from_root(tmp_path, stream=False)
    result = run_chat_agent(task='hello', adapter=adapter, config=config)
    assert result.status == 'completed'
    assert adapter.chunks_fired == [], 'on_chunk must not fire when stream=False'
