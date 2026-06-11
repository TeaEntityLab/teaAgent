"""Test module for provider fallback and recovery flow.

This module tests the provider fallback mechanism, which enables automatic failover
to a backup provider when the primary provider experiences an outage. The fallback
system is designed to improve reliability while maintaining security constraints,
ensuring that permission modes and approval requirements are preserved during failover.

Key concepts tested:
- Provider Outage Detection: The system detects when the primary provider is unavailable
- Automatic Fallback: Configured fallback provider is activated on primary failure
- Permission Preservation: Permission mode (read-only, prompt, etc.) is maintained during fallback
- Audit Trail: Fallback events are recorded in the audit log with provider details
- Background Run Preservation: Background agent runs preserve permission and approval flags
- Command Building: Agent run commands correctly preserve all security flags

Acceptance Criteria:
- AC1: Primary provider outage (503 error) triggers fallback to configured provider
- AC2: Fallback provider successfully completes the task
- AC3: Audit log records provider_fallback event with from_provider and to_provider
- AC4: Permission mode from run_started is preserved through fallback
- AC5: Background run commands preserve --permission-mode, --allow-destructive, --approve-call-id
- AC6: Background run commands preserve --hitl-approval and --route-model flags
- AC7: Fallback does not widen risk (permissions remain strict)

Technical Details:
- maybe_wrap_adapter_with_fallback wraps primary adapter with fallback logic
- LLMHTTPError with status_code 503 triggers fallback
- Fallback provider is configured in .teaagent/config.json (fallback_provider field)
- Audit events include provider_fallback type with full provider transition details
- build_agent_run_command constructs background commands with all flags preserved
- Adapter factory pattern allows testing with mock adapters

References:
- Provider fallback design: /docs/architecture/provider_fallback.md
- Audit event spec: /docs/specs/audit_events.md
- Background run design: /docs/architecture/background_runs.md
"""

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

    # Verify run completed successfully after fallback
    assert result.status == 'completed', (
        f'Expected run to complete after fallback, got status {result.status!r}'
    )
    events = store.show_run('run-fallback-flow')
    fallback_events = [e for e in events if e.get('event_type') == 'provider_fallback']
    # Verify provider_fallback audit event was recorded
    assert fallback_events, 'provider_fallback audit event must be recorded'
    payload = fallback_events[0].get('payload', {})
    # Verify fallback transition was from anthropic to gpt
    assert payload.get('from_provider') == 'anthropic', (
        f'Expected from_provider "anthropic", got {payload.get("from_provider")!r}'
    )
    assert payload.get('to_provider') == 'gpt', (
        f'Expected to_provider "gpt", got {payload.get("to_provider")!r}'
    )
    started = next(e for e in events if e.get('event_type') == 'run_started')
    # Verify permission mode was preserved through fallback
    assert started.get('payload', {}).get('permission_mode') == 'read-only', (
        f'Expected permission_mode "read-only" to be preserved, got {started.get("payload", {}).get("permission_mode")!r}'
    )


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
    # Verify command includes agent run subcommand
    assert 'agent' in cmd and 'run' in cmd, (
        f'Expected command to include "agent run", got {cmd}'
    )
    # Verify permission mode flag is preserved
    assert '--permission-mode' in cmd and 'prompt' in cmd, (
        f'Expected --permission-mode prompt in command, got {cmd}'
    )
    # Verify allow-destructive flag is preserved
    assert '--allow-destructive' in cmd, (
        f'Expected --allow-destructive in command, got {cmd}'
    )
    # Verify approve-call-id flag and value are preserved
    assert '--approve-call-id' in cmd and 'call-abc' in cmd, (
        f'Expected --approve-call-id call-abc in command, got {cmd}'
    )
    # Verify hitl-approval flag is preserved
    assert '--hitl-approval' in cmd, f'Expected --hitl-approval in command, got {cmd}'
    # Verify route-model flag is preserved
    assert '--route-model' in cmd, f'Expected --route-model in command, got {cmd}'
