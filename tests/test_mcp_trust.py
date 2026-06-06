"""Tests for MCP trust policy management."""

import os
import tempfile
import time
from unittest.mock import MagicMock

import pytest

from teaagent.hooks import HookError
from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    apply_mcp_trust_hooks,
    check_mcp_server_trust_at_call_time,
    check_unknown_tool_prompt,
    is_docker_available,
    is_server_trust_expired,
    load_mcp_trust_policy,
    merged_tool_filters,
    revoke_server_trust,
    save_mcp_trust_policy,
    update_server_tools,
)
from teaagent.tools import ToolAnnotations, ToolRegistry


def _register_mcp_tool(
    registry: ToolRegistry, tool_name: str, server_name: str
) -> None:
    registry.register(
        name=tool_name,
        description='remote MCP test tool',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {},
        mcp_server_name=server_name,
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


class TestCheckMCPServerTrustAtCallTime:
    """P2-A-001: Call-time MCP trust expiry enforcement."""

    def test_unknown_server_passes_through(self, tmp_path):
        """Unknown server should not raise — delegated to existing tool-filter hook."""
        check_mcp_server_trust_at_call_time(tmp_path, 'some_tool', 'unknown_server')

    def test_not_trusted_server_raises(self, tmp_path):
        """A server that exists but is not trusted must raise HookError."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['untrusted_srv'] = MCPServerTrust(trusted=False)
            save_mcp_trust_policy(tmp_path, policy)

            with pytest.raises(HookError, match='not trusted'):
                check_mcp_server_trust_at_call_time(
                    tmp_path, 'any_tool', 'untrusted_srv'
                )
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_expired_trust_raises(self, tmp_path):
        """An expired server trust must raise HookError regardless of tool lists."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['expired_srv'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() - 1,
                allowed_tools=['allowed_tool'],
            )
            save_mcp_trust_policy(tmp_path, policy)

            with pytest.raises(HookError, match='has expired'):
                check_mcp_server_trust_at_call_time(
                    tmp_path, 'allowed_tool', 'expired_srv'
                )
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_valid_trust_passes(self, tmp_path):
        """A trusted server with future expiry should not raise."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['good_srv'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() + 3600,
            )
            save_mcp_trust_policy(tmp_path, policy)

            check_mcp_server_trust_at_call_time(tmp_path, 'any_tool', 'good_srv')
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']


class TestHookBlocksUntrustedServer:
    """P2-A-001: The pre-tool hook must block tools from untrusted/expired servers."""

    def test_hook_blocks_untrusted_server_tool(self, tmp_path):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['bad'] = MCPServerTrust(
                trusted=False,
                allowed_tools=['dangerous_tool'],
            )
            save_mcp_trust_policy(tmp_path, policy)

            registry = ToolRegistry()
            registry.hook_registry = None
            _register_mcp_tool(registry, 'dangerous_tool', 'bad')
            apply_mcp_trust_hooks(registry, tmp_path)
            assert registry.hook_registry is not None

            with pytest.raises(HookError, match='not trusted'):
                registry.hook_registry.run_pre_hooks('dangerous_tool', {})
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_hook_blocks_expired_server_tool(self, tmp_path):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['stale'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() - 10,
                allowed_tools=['stale_tool'],
            )
            save_mcp_trust_policy(tmp_path, policy)

            registry = ToolRegistry()
            registry.hook_registry = None
            _register_mcp_tool(registry, 'stale_tool', 'stale')
            apply_mcp_trust_hooks(registry, tmp_path)
            assert registry.hook_registry is not None

            with pytest.raises(HookError, match='has expired'):
                registry.hook_registry.run_pre_hooks('stale_tool', {})
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_hook_allows_validly_trusted_server_tool(self, tmp_path):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['good'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() + 3600,
                allowed_tools=['good_tool'],
            )
            save_mcp_trust_policy(tmp_path, policy)

            registry = ToolRegistry()
            registry.hook_registry = None
            _register_mcp_tool(registry, 'good_tool', 'good')
            apply_mcp_trust_hooks(registry, tmp_path)

            result = registry.hook_registry.run_pre_hooks('good_tool', {})
            assert result == {} or result is None
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_hook_blocks_expired_server_with_empty_lists(self, tmp_path):
        """Even if a server has no allow/deny lists, expired trust should block."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['expired_no_lists'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() - 10,
            )
            save_mcp_trust_policy(tmp_path, policy)

            registry = ToolRegistry()
            registry.hook_registry = None
            _register_mcp_tool(registry, 'any_tool', 'expired_no_lists')
            apply_mcp_trust_hooks(registry, tmp_path)

            with pytest.raises(HookError, match='has expired'):
                registry.hook_registry.run_pre_hooks('any_tool', {})
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']

    def test_merged_tool_filters_excludes_expired_server(self, tmp_path):
        """merged_tool_filters should skip expired server entries."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = key
        try:
            policy = MCPTrustPolicy()
            policy.servers['live'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() + 3600,
                allowed_tools=['live_tool'],
            )
            policy.servers['dead'] = MCPServerTrust(
                trusted=True,
                expires_at=time.time() - 10,
                allowed_tools=['dead_tool'],
            )
            save_mcp_trust_policy(tmp_path, policy)

            loaded = load_mcp_trust_policy(tmp_path)
            allowed, denied = merged_tool_filters(loaded)
            assert 'live_tool' in allowed
            assert 'dead_tool' not in allowed
        finally:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']


class TestDockerAvailability:
    def test_is_docker_available_returns_bool(self):
        result = is_docker_available()
        assert isinstance(result, bool)


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
