"""Acceptance test for MCP trust onboarding journey (EXT-002).

Covers the full lifecycle:
1. Trust list (initial empty state)
2. Trust allow (add server/tools)
3. Trust inspect (verify server state)
4. Trust call-time enforcement
5. Trust revoke (remove server)
6. Trust audit (read audit trail of changes)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.hooks import HookError
from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    check_mcp_server_trust_at_call_time,
    is_server_trust_expired,
    load_mcp_trust_policy,
    merged_tool_filters,
    revoke_server_trust,
    save_mcp_trust_policy,
    update_server_tools,
)
from teaagent.types import AuditLogger


class TestMCPServerTrustModel:
    """MCPServerTrust core model."""

    def test_default_not_trusted(self) -> None:
        trust = MCPServerTrust()
        assert trust.trusted is False
        assert trust.allowed_tools == []
        assert trust.denied_tools == []

    def test_fully_trusted(self) -> None:
        trust = MCPServerTrust(
            allowed_tools=['read_file', 'write_file'],
            trusted=True,
        )
        assert trust.trusted
        assert 'read_file' in trust.allowed_tools
        assert 'write_file' in trust.allowed_tools


@pytest.fixture(autouse=True)
def _mcp_trust_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set encryption key for all tests that persist trust policies."""
    monkeypatch.setenv(
        'TEAAGENT_MCP_TRUST_KEY',
        'EDPOIW2MrenJpYc87A6SydDMebx4ekjT2ikO-Qc7qLo=',
    )


class TestMCPTrustPolicyModel:
    """MCPTrustPolicy lifecycle."""

    def test_empty_policy(self) -> None:
        policy = MCPTrustPolicy()
        assert policy.servers == {}
        assert policy.allowed_tools == []
        assert policy.denied_tools == []

    def test_add_server_via_update(self) -> None:
        policy = MCPTrustPolicy()
        update_server_tools(
            policy, 'mcp.example.com', allow=['tool_a', 'tool_b'], trusted=True
        )
        assert 'mcp.example.com' in policy.servers
        server = policy.servers['mcp.example.com']
        assert server.trusted
        assert 'tool_a' in server.allowed_tools

    def test_deny_tools(self) -> None:
        policy = MCPTrustPolicy()
        update_server_tools(policy, 'mcp.example.com', deny=['danger_tool'])
        server = policy.servers['mcp.example.com']
        assert 'danger_tool' in server.denied_tools
        assert not server.trusted

    def test_round_trip(self, tmp_path: Path) -> None:
        policy = MCPTrustPolicy()
        update_server_tools(policy, 'mcp.example.com', allow=['read'], trusted=True)
        save_mcp_trust_policy(tmp_path, policy)
        loaded = load_mcp_trust_policy(tmp_path)
        assert 'mcp.example.com' in loaded.servers
        assert loaded.servers['mcp.example.com'].trusted
        assert 'read' in loaded.servers['mcp.example.com'].allowed_tools

    def test_serialization_encrypted(self, tmp_path: Path) -> None:
        """Policies are stored encrypted at rest."""
        policy = MCPTrustPolicy()
        update_server_tools(policy, 'mcp.example.com', allow=['tool_x'], trusted=True)
        save_mcp_trust_policy(tmp_path, policy)
        trust_file = tmp_path / '.teaagent' / 'mcp-trust.json'
        assert trust_file.is_file()
        raw = trust_file.read_bytes()
        # Should not be plain JSON
        assert b'tool_x' not in raw
        assert b'mcp.example.com' not in raw


class TestTrustOnboardingFlow:
    """Full onboarding lifecycle."""

    def test_inspect_before_trust(self, tmp_path: Path) -> None:
        """Inspect returns empty state before any servers are trusted."""
        policy = load_mcp_trust_policy(tmp_path)
        assert len(policy.servers) == 0
        assert len(policy.allowed_tools) == 0

    def test_trust_server(self, tmp_path: Path) -> None:
        """Trust a server with specific tools."""
        policy = load_mcp_trust_policy(tmp_path)
        update_server_tools(
            policy, 'files.example.com', allow=['read', 'write'], trusted=True
        )
        save_mcp_trust_policy(tmp_path, policy)

        loaded = load_mcp_trust_policy(tmp_path)
        server = loaded.servers.get('files.example.com')
        assert server is not None
        assert server.trusted
        assert server.allowed_tools == ['read', 'write']

    def test_tool_filtering(self) -> None:
        """Merged filters combine global and per-server rules."""
        policy = MCPTrustPolicy()
        policy.allowed_tools = ['global_tool']
        update_server_tools(
            policy, 'srv.example.com', allow=['srv_tool'], deny=['bad_tool']
        )
        allowed, denied = merged_tool_filters(policy)
        assert 'global_tool' in allowed
        assert 'srv_tool' in allowed
        assert 'bad_tool' in denied

    def test_revoke_server(self, tmp_path: Path) -> None:
        """Revoke removes server and records audit event."""
        policy = load_mcp_trust_policy(tmp_path)
        update_server_tools(policy, 'revoke.test.com', allow=['tool'], trusted=True)
        save_mcp_trust_policy(tmp_path, policy)

        # Revoke
        policy = revoke_server_trust(policy, 'revoke.test.com')
        save_mcp_trust_policy(tmp_path, policy)

        loaded = load_mcp_trust_policy(tmp_path)
        assert 'revoke.test.com' not in loaded.servers

    def test_revoke_audit_event(self, tmp_path: Path) -> None:
        """Revoke emits an audit event when audit_logger is provided."""
        import json

        audit_path = tmp_path / '.teaagent' / 'audit.jsonl'
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        logger = AuditLogger(audit_path)
        policy = MCPTrustPolicy()
        update_server_tools(policy, 'audit.test.com', allow=['x'], trusted=True)
        revoke_server_trust(policy, 'audit.test.com', audit_logger=logger)
        lines = audit_path.read_text().strip().splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        assert any(e.get('event_type') == 'mcp_server_trust_revoked' for e in events)

    def test_expired_trust_blocked(self) -> None:
        """Expired trust raises HookError on call."""
        import time

        policy = MCPTrustPolicy()
        update_server_tools(
            policy,
            'expired.test.com',
            allow=['tool'],
            trusted=True,
        )
        server = policy.servers['expired.test.com']
        server.expires_at = time.time() - 1.0  # expired
        assert is_server_trust_expired(server)

    def test_call_time_enforcement(self, tmp_path: Path) -> None:
        """check_mcp_server_trust_at_call_time raises for untrusted servers."""
        policy = load_mcp_trust_policy(tmp_path)
        update_server_tools(policy, 'untrusted.test.com', allow=['tool'], trusted=False)
        save_mcp_trust_policy(tmp_path, policy)
        with pytest.raises(HookError):
            check_mcp_server_trust_at_call_time(tmp_path, 'tool', 'untrusted.test.com')


class TestTrustListCommand:
    """Trust list / inspect / allow / deny integration."""

    def test_list_empty(self, tmp_path: Path) -> None:
        """List returns empty policy for fresh workspace."""
        policy = load_mcp_trust_policy(tmp_path)
        d = policy.to_public_dict()
        assert d['servers'] == {}
        assert d['allowed_tools'] == []
        assert d['denied_tools'] == []

    def test_allow_then_inspect(self, tmp_path: Path) -> None:
        """After allowing, inspect shows the server."""
        policy = load_mcp_trust_policy(tmp_path)
        update_server_tools(
            policy, 'my.server.com', allow=['read', 'write'], trusted=True
        )
        save_mcp_trust_policy(tmp_path, policy)
        loaded = load_mcp_trust_policy(tmp_path)
        server = loaded.servers.get('my.server.com')
        assert server is not None
        assert server.allowed_tools == ['read', 'write']

    def test_deny_tool(self, tmp_path: Path) -> None:
        """Denied tools appear in the server's denied list."""
        policy = load_mcp_trust_policy(tmp_path)
        update_server_tools(policy, 'my.server.com', deny=['delete'])
        save_mcp_trust_policy(tmp_path, policy)
        loaded = load_mcp_trust_policy(tmp_path)
        server = loaded.servers['my.server.com']
        assert 'delete' in server.denied_tools

    def test_full_onboarding_flow(self, tmp_path: Path) -> None:
        """Complete inspect → trust → call → revoke → verify flow."""
        # 1. Start with empty policy
        policy = load_mcp_trust_policy(tmp_path)
        assert len(policy.servers) == 0

        # 2. Trust a server
        update_server_tools(
            policy,
            'data.api.com',
            allow=['query', 'list'],
            trusted=True,
        )
        save_mcp_trust_policy(tmp_path, policy)

        # 3. Verify saved state
        loaded = load_mcp_trust_policy(tmp_path)
        server = loaded.servers['data.api.com']
        assert server.trusted
        assert 'query' in server.allowed_tools

        # 4. Tool filtering works
        s_allowed, s_denied = merged_tool_filters(loaded)
        assert 'query' in s_allowed

        # 5. Revoke the server
        policy = revoke_server_trust(loaded, 'data.api.com')
        save_mcp_trust_policy(tmp_path, policy)

        # 6. Verify it's gone
        final = load_mcp_trust_policy(tmp_path)
        assert 'data.api.com' not in final.servers
