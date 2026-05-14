"""AC-NEW-7: Cost tracking flow.

As a user, I want to see live token usage and estimated cost after a run
so that I can track spending and tune my budget limits.

Acceptance criteria:
- ``RunResult.cost_cents`` is >= 0.0 after a completed run.
- ``RunResult.input_tokens`` and ``output_tokens`` are accumulated correctly.
- The ``run_completed`` audit event carries ``cost_cents``, ``input_tokens``,
  and ``output_tokens`` fields.
- A ``RunBudget`` with a very low cost cap causes ``BudgetExceededError``.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent


class _StubAdapter:
    provider = 'stub'

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        return LLMResponse(
            provider='stub',
            model='stub-model',
            content='{"type":"final","content":"all done"}',
            input_tokens=200,
            output_tokens=80,
        )


def test_run_result_exposes_token_counts(tmp_path):
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    result = run_chat_agent(task='hello', adapter=adapter, config=config)

    assert result.status == 'completed'
    assert result.input_tokens == 200
    assert result.output_tokens == 80
    assert result.cost_cents >= 0.0


def test_run_completed_audit_event_has_cost_fields(tmp_path):
    audit = AuditLogger()
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    run_chat_agent(task='hello', adapter=adapter, config=config, audit=audit)

    events = [e for e in audit.events if e.event_type == 'run_completed']
    assert events, 'run_completed must be recorded'
    p = events[0].payload
    assert 'cost_cents' in p
    assert 'input_tokens' in p
    assert 'output_tokens' in p
    assert p['input_tokens'] == 200
    assert p['output_tokens'] == 80
