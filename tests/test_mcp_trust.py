"""Tests for MCP trust policy management."""

import os
import tempfile
import time
from unittest.mock import MagicMock

from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    check_unknown_tool_prompt,
    is_server_trust_expired,
    load_mcp_trust_policy,
    revoke_server_trust,
    save_mcp_trust_policy,
    update_server_tools,
)


def test_mcp_trust_policy_serialization():
    """Test MCPTrustPolicy serialization/deserialization with expiry."""
    policy = MCPTrustPolicy(
        allowed_tools=['tool1'],
        denied_tools=['tool2'],
        default_ttl_seconds=3600.0,
    )
    policy.servers['server1'] = MCPServerTrust(
        allowed_tools=['server_tool1'],
        denied_tools=['server_tool2'],
        trusted=True,
        expires_at=time.time() + 3600,
    )

    data = policy.to_dict()
    restored = MCPTrustPolicy.from_dict(data)

    assert restored.allowed_tools == ['tool1']
    assert restored.denied_tools == ['tool2']
    assert restored.default_ttl_seconds == 3600.0
    assert 'server1' in restored.servers
    assert restored.servers['server1'].trusted is True
    assert restored.servers['server1'].expires_at is not None


def test_server_trust_expiry():
    """Test server trust expiry checking."""
    # Not expired
    server_trust = MCPServerTrust(trusted=True, expires_at=time.time() + 3600)
    assert is_server_trust_expired(server_trust) is False

    # Expired
    server_trust_expired = MCPServerTrust(trusted=True, expires_at=time.time() - 3600)
    assert is_server_trust_expired(server_trust_expired) is True

    # No expiry set
    server_trust_no_expiry = MCPServerTrust(trusted=True, expires_at=None)
    assert is_server_trust_expired(server_trust_no_expiry) is False


def test_update_server_tools_with_ttl():
    """Test updating server tools with TTL."""
    policy = MCPTrustPolicy(default_ttl_seconds=7200.0)

    # Trust server with default TTL
    policy = update_server_tools(policy, 'server1', trusted=True)
    assert 'server1' in policy.servers
    assert policy.servers['server1'].trusted is True
    assert policy.servers['server1'].expires_at is not None
    assert policy.servers['server1'].expires_at > time.time()

    # Trust server with custom TTL
    policy = update_server_tools(policy, 'server2', trusted=True, ttl_seconds=1800.0)
    assert policy.servers['server2'].expires_at is not None
    expected_expiry = time.time() + 1800.0
    assert abs(policy.servers['server2'].expires_at - expected_expiry) < 5.0


def test_revoke_server_trust():
    """Test revoking server trust with audit event."""
    policy = MCPTrustPolicy()
    policy.servers['server1'] = MCPServerTrust(allowed_tools=['tool1'], trusted=True)

    mock_audit = MagicMock()
    mock_audit.record = MagicMock()

    policy = revoke_server_trust(
        policy, 'server1', audit_logger=mock_audit, run_id='test-run'
    )

    assert 'server1' not in policy.servers
    assert mock_audit.record.called
    call_args = mock_audit.record.call_args
    assert call_args[1]['event_type'] == 'mcp_server_trust_revoked'
    assert call_args[1]['server'] == 'server1'
    assert call_args[1]['previous_trusted'] is True


def test_check_unknown_tool_prompt():
    """Check unknown tool prompt detection."""
    policy = MCPTrustPolicy(
        allowed_tools=['known_tool1'], denied_tools=['blocked_tool1']
    )
    policy.servers['server1'] = MCPServerTrust(
        allowed_tools=['server_tool1'], denied_tools=['server_blocked_tool1']
    )

    # Known global tool - no prompt
    assert check_unknown_tool_prompt(policy, 'known_tool1') is False

    # Blocked global tool - no prompt (already denied)
    assert check_unknown_tool_prompt(policy, 'blocked_tool1') is False

    # Unknown global tool - prompt
    assert check_unknown_tool_prompt(policy, 'unknown_tool') is True

    # Known server tool - no prompt
    assert check_unknown_tool_prompt(policy, 'server_tool1', server='server1') is False

    # Blocked server tool - no prompt
    assert (
        check_unknown_tool_prompt(policy, 'server_blocked_tool1', server='server1')
        is False
    )

    # Unknown server tool - prompt
    assert (
        check_unknown_tool_prompt(policy, 'unknown_server_tool', server='server1')
        is True
    )


def test_mcp_trust_policy_persistence():
    """Test saving and loading MCP trust policy."""
    from cryptography.fernet import Fernet

    with tempfile.TemporaryDirectory() as tmpdir:
        # Set encryption key
        test_key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = test_key
        try:
            policy = MCPTrustPolicy(
                allowed_tools=['tool1'],
                default_ttl_seconds=3600.0,
            )
            policy.servers['server1'] = MCPServerTrust(
                trusted=True, expires_at=time.time() + 3600
            )

            save_mcp_trust_policy(tmpdir, policy)
            loaded = load_mcp_trust_policy(tmpdir)

            assert loaded.allowed_tools == ['tool1']
            assert loaded.default_ttl_seconds == 3600.0
            assert 'server1' in loaded.servers
            assert loaded.servers['server1'].trusted is True
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']
