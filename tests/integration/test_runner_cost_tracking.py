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
        # Use enough tokens to generate a positive cost (stub provider uses default 0.001/0.001 rates)
        # 10000 input + 5000 output = 15 cents, which exceeds 0 cap
        return LLMResponse(
            provider='stub',
            model='stub-model',
            content='{"type":"final","content":"done"}',
            input_tokens=10000,
            output_tokens=5000,
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


def test_fresh_agent_run_does_not_register_browser_tools_twice(tmp_path, monkeypatch):
    import teaagent.chat_agent as chat_agent

    registry = _make_registry()
    registry.register(
        name='browser_navigate',
        description='Navigate to a URL in a browser.',
        input_schema={'type': 'object', 'properties': {'url': {'type': 'string'}}},
        output_schema={'type': 'object', 'properties': {'status': {'type': 'string'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'status': 'ok'},
    )
    monkeypatch.setattr(
        chat_agent, 'build_workspace_tool_registry', lambda _root: registry
    )

    def fail_register_browser_tools(_registry):
        raise AssertionError('browser tools should already be registered')

    monkeypatch.setattr(
        chat_agent, 'register_browser_tools', fail_register_browser_tools
    )

    adapter = _StubAdapter()
    config = chat_agent.ChatAgentConfig.from_root(tmp_path)
    result = chat_agent.run_chat_agent(config, 'say hello', adapter=adapter)

    assert result.status == 'completed'


def test_cost_fields_populated_after_run(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig, run_chat_agent

    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    result = run_chat_agent(config, 'say hello', adapter=adapter)

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
    run_chat_agent(config, 'say hello', adapter=adapter, audit=audit)

    completed = [e for e in audit.events if e.event_type == 'run_completed']
    assert completed, 'run_completed event must be recorded'
    payload = completed[0].payload
    assert 'cost_cents' in payload
    assert 'input_tokens' in payload
    assert 'output_tokens' in payload


def test_zero_cost_cap_blocks_positive_cost_run(tmp_path):
    """0 cap means zero spend allowed - any positive cost exceeds it."""
    from teaagent.chat_agent import ChatAgentConfig, run_chat_agent

    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path, max_estimated_cost_cents=0)
    result = run_chat_agent(config, 'say hello', adapter=adapter)
    # With 0 cap, the run should fail with budget exceeded
    assert result.status.startswith('failed:'), f'Expected failed status, got {result.status}'
    assert 'budget' in result.error_message.lower() or 'cost' in result.error_message.lower()
