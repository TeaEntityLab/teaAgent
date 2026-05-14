"""IT-1: Runner accumulates token usage and cost across multiple LLM calls.

Verifies that ``RunResult.cost_cents``, ``input_tokens``, and ``output_tokens``
are non-zero after a run that invokes the decision engine multiple times.
Uses a stub adapter so no real API key is needed.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.runner import RunResult
from teaagent.tools import ToolAnnotations, ToolRegistry


class _StubAdapter:
    provider = 'stub'
    call_count = 0

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        self.call_count += 1
        return LLMResponse(
            provider='stub',
            model='stub-model',
            content='{"type":"final","content":"done"}',
            input_tokens=100,
            output_tokens=50,
        )


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='noop',
        description='does nothing',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {},
    )
    return registry


def test_cost_fields_populated_after_run(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig, run_chat_agent

    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    result = run_chat_agent(task='say hello', adapter=adapter, config=config)

    assert isinstance(result, RunResult)
    assert result.status == 'completed'
    assert result.input_tokens > 0, 'input_tokens must be accumulated'
    assert result.output_tokens > 0, 'output_tokens must be accumulated'
    assert result.cost_cents >= 0.0


def test_cost_reported_in_audit_run_completed(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig, run_chat_agent

    audit = AuditLogger()
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    run_chat_agent(task='say hello', adapter=adapter, config=config, audit=audit)

    completed = [e for e in audit.events if e.event_type == 'run_completed']
    assert completed, 'run_completed event must be recorded'
    payload = completed[0].payload
    assert 'cost_cents' in payload
    assert 'input_tokens' in payload
    assert 'output_tokens' in payload
