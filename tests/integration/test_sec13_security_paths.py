"""SEC-13: Integration coverage for critical security paths without mocks.

Pins end-to-end wiring for audit HMAC verification, chat-agent cost tracking,
destructive approval denial, and MCP trust expiry enforcement.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.approval_manager import ApprovalManager
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.hooks import HookError
from teaagent.llm import LLMResponse
from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    apply_mcp_trust_hooks,
    merged_tool_filters,
    save_mcp_trust_policy,
)
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, ToolRequest
from teaagent.types import (
    AuditLogger,
    PermissionMode,
    ToolAnnotations,
    ToolRegistry,
    verify_audit_chain,
)

_EXPIRED = time.time() - 3600


class _CostStubAdapter:
    """Stub adapter that reports non-zero token usage (no API key required)."""

    provider = 'stub'

    def complete(self, request):
        return LLMResponse(
            provider='stub',
            model='stub-model',
            content='{"type":"final","content":"done"}',
            input_tokens=10000,
            output_tokens=5000,
        )


def test_verify_audit_chain_autoloads_persisted_hmac_key(tmp_path) -> None:
    """SEC-01/SEC-13: CLI verify path loads ~/.teaagent/run-keys/<run_id>.key."""
    log = tmp_path / 'run-autoload.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log)
        audit.record('run_started', 'r-autoload', task='sec13-autoload')

    with patch.object(Path, 'home', return_value=tmp_path):
        result = verify_audit_chain(log)

    assert result.valid, result.error
    assert result.event_count == 1


def test_run_chat_agent_accumulates_adapter_cost(tmp_path) -> None:
    """SEC-13: Full chat-agent run tracks adapter-reported usage (not mocked)."""
    adapter = _CostStubAdapter()
    config = ChatAgentConfig.from_root(tmp_path, max_estimated_cost_cents=500)
    result = run_chat_agent(config, 'track my cost', adapter=adapter)

    assert result.status == 'completed'
    assert result.input_tokens == 10000
    assert result.output_tokens == 5000
    assert result.cost_cents > 0.0


def test_runner_denies_destructive_tool_without_approval() -> None:
    """SEC-13: Approval gate rejects destructive writes with no grant (real manager)."""
    registry = ToolRegistry()
    registry.register(
        name='workspace_write_file',
        description='write file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
            'required': ['path', 'content'],
        },
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(destructive=True),
        handler=lambda args: {'path': args['path']},
    )
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY),
    )

    write_request = ToolRequest(
        tool_name='workspace_write_file',
        arguments={'path': 'out.txt', 'content': 'x'},
        call_id='call-sec13',
    )
    result = runner.run(
        task='write secret',
        decide=lambda _: write_request,
        run_id='sec13-deny',
    )

    assert result.status == 'pending_approval'
    assert any(e.event_type == 'tool_call_blocked' for e in audit.events)


def test_approval_manager_denies_destructive_without_token() -> None:
    """SEC-13: ApprovalManager.assert_allowed blocks destructive calls directly."""
    manager = ApprovalManager()
    with pytest.raises(ToolPermissionError) as exc:
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-direct-deny',
            destructive=True,
            arguments={'path': 'x.txt', 'content': 'hi'},
        )
    assert exc.value.reason_code in (
        DenialReasonCode.MISSING_STATE,
        DenialReasonCode.JIT_NO_APPROVAL,
    )


def test_expired_mcp_server_dropped_from_allowed_tools() -> None:
    """SEC-02/SEC-13: merged_tool_filters excludes expired server tools."""
    policy = MCPTrustPolicy()
    policy.servers['srv'] = MCPServerTrust(
        trusted=True,
        allowed_tools=['srv_tool'],
        expires_at=_EXPIRED,
    )
    allowed, _denied = merged_tool_filters(policy)
    assert 'srv_tool' not in allowed


def test_expired_mcp_server_blocked_at_invoke(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEC-02/SEC-13: Pre-tool hook raises when expired server tool is invoked."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv('TEAAGENT_MCP_TRUST_KEY', Fernet.generate_key().decode())
    policy = MCPTrustPolicy()
    policy.servers['srv'] = MCPServerTrust(
        trusted=True,
        allowed_tools=['srv_tool'],
        expires_at=_EXPIRED,
    )
    save_mcp_trust_policy(tmp_path, policy)

    registry = ToolRegistry()
    registry.register(
        name='srv_tool',
        description='remote MCP test tool',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {},
        mcp_server_name='srv',
    )
    apply_mcp_trust_hooks(registry, tmp_path)

    with pytest.raises(HookError, match='expired'):
        registry.hook_registry.run_pre_hooks('srv_tool', {})
