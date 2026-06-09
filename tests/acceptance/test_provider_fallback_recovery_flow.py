"""Acceptance: provider outage triggers configured fallback without widening risk."""

from __future__ import annotations

import argparse
from pathlib import Path

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.llm import LLMHTTPError, LLMRequest, LLMResponse
from teaagent.provider_fallback import maybe_wrap_adapter_with_fallback
from teaagent.run_store import RunStore


class _PrimaryOutageAdapter:
    provider = 'anthropic'

    def __init__(self) -> None:
        class _Cfg:
            name = 'anthropic'
            model = 'claude-sonnet'

            def resolved_model(self) -> str:
                return self.model

        self.config = _Cfg()

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise LLMHTTPError('primary outage', status_code=503)


class _FallbackAdapter:
    provider = 'gpt'

    def __init__(self) -> None:
        class _Cfg:
            name = 'gpt'
            model = 'gpt-4o-mini'

            def resolved_model(self) -> str:
                return self.model

        self.config = _Cfg()

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            provider='gpt',
            model='gpt-4o-mini',
            content='{"type":"final","content":"recovered via fallback"}',
        )


def test_provider_outage_triggers_fallback_and_preserves_permission_mode(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / '.teaagent' / 'config.json'
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"fallback_provider": "gpt"}', encoding='utf-8')

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-fallback-flow')

    def factory(provider: str, *, model=None):
        if provider == 'anthropic':
            return _PrimaryOutageAdapter()
        return _FallbackAdapter()

    adapter = maybe_wrap_adapter_with_fallback(
        _PrimaryOutageAdapter(),
        root=tmp_path,
        primary_provider='anthropic',
        primary_model='claude-sonnet',
        audit=audit,
        run_id='run-fallback-flow',
        adapter_factory=factory,
    )
    config = ChatAgentConfig.from_root(
        tmp_path,
        permission_mode='read-only',
        max_iterations=1,
        max_tool_calls=0,
    )
    result = run_chat_agent(
        config,
        'recover from outage',
        adapter=adapter,
        audit=audit,
        run_id='run-fallback-flow',
    )

    assert result.status == 'completed'
    events = store.show_run('run-fallback-flow')
    fallback_events = [e for e in events if e.get('event_type') == 'provider_fallback']
    assert fallback_events, 'provider_fallback audit event must be recorded'
    payload = fallback_events[0].get('payload', {})
    assert payload.get('from_provider') == 'anthropic'
    assert payload.get('to_provider') == 'gpt'
    started = next(e for e in events if e.get('event_type') == 'run_started')
    assert started.get('payload', {}).get('permission_mode') == 'read-only'


def test_build_agent_run_command_preserves_permission_and_approval_flags() -> None:
    from teaagent.ergonomics.background_run import build_agent_run_command

    args = argparse.Namespace(
        provider='anthropic',
        model='claude-sonnet',
        root='/tmp/ws',
        route_model=True,
        max_iterations=12,
        max_tool_calls=8,
        clarify=False,
        allow_destructive=True,
        approve_call_id=['call-abc'],
        hitl_approval=True,
        permission_mode='prompt',
        subagent=True,
        max_subagent_depth=2,
        heartbeat=5.0,
        code_analysis=True,
    )
    cmd = build_agent_run_command(args, 'background task')
    assert 'agent' in cmd and 'run' in cmd
    assert '--permission-mode' in cmd and 'prompt' in cmd
    assert '--allow-destructive' in cmd
    assert '--approve-call-id' in cmd and 'call-abc' in cmd
    assert '--hitl-approval' in cmd
    assert '--route-model' in cmd
