# test-type: adversarial
"""DU-016: unknown remote MCP tools must not run without approval.

An MCP tool that is named in neither the global nor the server allow/deny
lists of a trust policy is "unknown". The trust pre-hook does not block it
(an empty allow-list imposes no restriction), so the approval gate is the
control that must stop it. These tests drive the real governed path
(``AgentRunner`` -> ``ApprovalPolicy`` -> ``ToolRegistry.execute``) with the
annotations the production MCP adapter assigns.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from teaagent.mcp_tool_adapter import _infer_annotations
from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    apply_mcp_trust_hooks,
    save_mcp_trust_policy,
)
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolRegistry
from teaagent.types import AuditLogger, PermissionMode

_TOOL = 'remote_unlisted_tool'
_SERVER = 'remote-server'


@pytest.fixture
def trust_key(monkeypatch):
    monkeypatch.setenv('TEAAGENT_MCP_TRUST_KEY', Fernet.generate_key().decode())


def _build_registry(calls: list[dict]) -> ToolRegistry:
    registry = ToolRegistry()

    def handler(arguments: dict) -> dict:
        calls.append(arguments)
        return {'ok': True}

    registry.register(
        name=_TOOL,
        description='unlisted remote MCP tool',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={
            'type': 'object',
            'properties': {'ok': {'type': 'boolean'}},
        },
        annotations=_infer_annotations({}),
        handler=handler,
        mcp_server_name=_SERVER,
    )
    return registry


def _trust_policy_root(tmp_path, *, allowed=(), denied=()) -> str:
    """Persist a trust policy in which the server is trusted but _TOOL is unlisted."""
    policy = MCPTrustPolicy()
    policy.servers[_SERVER] = MCPServerTrust(
        trusted=True,
        allowed_tools=list(allowed),
        denied_tools=list(denied),
    )
    save_mcp_trust_policy(tmp_path, policy)
    return str(tmp_path)


def _run_unknown_tool(registry: ToolRegistry, mode: PermissionMode):
    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        approval_policy=ApprovalPolicy(permission_mode=mode),
    )
    request = ToolRequest(tool_name=_TOOL, arguments={}, call_id='call-du016')
    script = iter([request, FinalAnswer(content='done')])
    return runner.run(task='call unlisted MCP tool', decide=lambda _: next(script))


def test_unknown_mcp_tool_under_trust_policy_prompts_in_prompt_mode(
    tmp_path, trust_key
):
    calls: list[dict] = []
    registry = _build_registry(calls)
    root = _trust_policy_root(tmp_path)
    apply_mcp_trust_hooks(registry, root)

    result = _run_unknown_tool(registry, PermissionMode.PROMPT)

    assert result.status == 'pending_approval'
    assert result.metadata.get('approval', {}).get('call_id') == 'call-du016'
    assert calls == []


def test_unknown_mcp_tool_under_trust_policy_prompts_in_workspace_write(
    tmp_path, trust_key
):
    calls: list[dict] = []
    registry = _build_registry(calls)
    root = _trust_policy_root(tmp_path)
    apply_mcp_trust_hooks(registry, root)

    result = _run_unknown_tool(registry, PermissionMode.WORKSPACE_WRITE)

    assert result.status != 'completed'
    assert calls == []


def test_unknown_mcp_tool_under_trust_policy_denied_in_read_only(tmp_path, trust_key):
    calls: list[dict] = []
    registry = _build_registry(calls)
    root = _trust_policy_root(tmp_path)
    apply_mcp_trust_hooks(registry, root)

    result = _run_unknown_tool(registry, PermissionMode.READ_ONLY)

    assert result.status != 'completed'
    assert calls == []


def test_unknown_mcp_tool_without_trust_policy_still_prompts(tmp_path):
    """No trust policy configured: the approval gate is unchanged."""
    calls: list[dict] = []
    registry = _build_registry(calls)

    result = _run_unknown_tool(registry, PermissionMode.PROMPT)

    assert result.status == 'pending_approval'
    assert calls == []


def test_explicitly_allowed_mcp_tool_still_requires_approval_in_prompt_mode(
    tmp_path, trust_key
):
    """A trust-list entry does not replace the approval gate for a destructive tool."""
    calls: list[dict] = []
    registry = _build_registry(calls)
    root = _trust_policy_root(tmp_path, allowed=[_TOOL])
    apply_mcp_trust_hooks(registry, root)

    result = _run_unknown_tool(registry, PermissionMode.PROMPT)

    assert result.status == 'pending_approval'
    assert calls == []


def test_unknown_mcp_tool_runs_in_danger_full_access_with_audit(tmp_path, trust_key):
    """Owner-chosen widening: danger-full-access proceeds under declared mode."""
    calls: list[dict] = []
    registry = _build_registry(calls)
    root = _trust_policy_root(tmp_path)
    apply_mcp_trust_hooks(registry, root)

    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        ),
    )
    request = ToolRequest(tool_name=_TOOL, arguments={}, call_id='call-full')
    script = iter([request, FinalAnswer(content='done')])
    result = runner.run(task='call unlisted MCP tool', decide=lambda _: next(script))

    assert result.status == 'completed'
    assert len(calls) == 1
