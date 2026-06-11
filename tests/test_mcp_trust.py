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
    update_global_tools,
    update_server_tools,
)
from teaagent.types import ToolAnnotations, ToolRegistry


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

            assert registry.hook_registry is not None
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
                assert registry.hook_registry is not None
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


# ---------------------------------------------------------------------------
# Additional negative test cases for mcp_trust
# ---------------------------------------------------------------------------


def test_mcp_trust_policy_with_empty_lists():
    """Test that empty allow/deny lists are handled."""
    policy = MCPTrustPolicy(
        allowed_tools=[],
        denied_tools=[],
    )
    assert policy.allowed_tools == []
    assert policy.denied_tools == []


def test_mcp_trust_policy_with_duplicate_tools():
    """Test that duplicate tools in lists are handled."""
    policy = MCPTrustPolicy(
        allowed_tools=['tool1', 'tool1', 'tool2'],
        denied_tools=['tool3', 'tool3'],
    )
    # Duplicates should be preserved as-is
    assert len(policy.allowed_tools) == 3
    assert len(policy.denied_tools) == 2


def test_mcp_trust_policy_with_special_characters():
    """Test that special characters in tool names are handled."""
    policy = MCPTrustPolicy(
        allowed_tools=['tool-with-dash', 'tool_with_underscore', 'tool.with.dot'],
    )
    assert 'tool-with-dash' in policy.allowed_tools
    assert 'tool_with_underscore' in policy.allowed_tools
    assert 'tool.with.dot' in policy.allowed_tools


def test_mcp_trust_policy_with_unicode_tool_names():
    """Test that unicode characters in tool names are handled."""
    policy = MCPTrustPolicy(
        allowed_tools=['工具-1', 'tool-工具'],
    )
    assert '工具-1' in policy.allowed_tools
    assert 'tool-工具' in policy.allowed_tools


def test_mcp_trust_policy_negative_ttl():
    """Test that negative TTL is handled."""
    policy = MCPTrustPolicy(default_ttl_seconds=-100.0)
    assert policy.default_ttl_seconds == -100.0


def test_mcp_trust_policy_zero_ttl():
    """Test that zero TTL is handled."""
    policy = MCPTrustPolicy(default_ttl_seconds=0.0)
    assert policy.default_ttl_seconds == 0.0


def test_mcp_trust_policy_very_large_ttl():
    """Test that very large TTL is handled."""
    policy = MCPTrustPolicy(default_ttl_seconds=999999999.0)
    assert policy.default_ttl_seconds == 999999999.0


def test_mcp_server_trust_with_empty_lists():
    """Test that empty server tool lists are handled."""
    server = MCPServerTrust(
        allowed_tools=[],
        denied_tools=[],
    )
    assert server.allowed_tools == []
    assert server.denied_tools == []


def test_mcp_server_trust_with_negative_expiry():
    """Test that negative expiry timestamp is handled."""
    server = MCPServerTrust(
        trusted=True,
        expires_at=-100.0,
    )
    assert is_server_trust_expired(server) is True


def test_mcp_server_trust_with_zero_expiry():
    """Test that zero expiry timestamp is handled."""
    server = MCPServerTrust(
        trusted=True,
        expires_at=0.0,
    )
    # Zero timestamp is in the past (epoch)
    assert is_server_trust_expired(server) is True


def test_mcp_server_trust_with_very_large_expiry():
    """Test that very large expiry timestamp is handled."""
    server = MCPServerTrust(
        trusted=True,
        expires_at=9999999999.0,
    )
    assert is_server_trust_expired(server) is False


def test_update_global_tools_with_empty_lists():
    """Test that updating with empty lists is handled."""
    policy = MCPTrustPolicy(allowed_tools=['tool1'])
    policy = update_global_tools(policy, allow=[], deny=[])
    assert policy.allowed_tools == ['tool1']


def test_update_global_tools_with_duplicate_in_allow():
    """Test that adding duplicate tools is handled."""
    policy = MCPTrustPolicy(allowed_tools=['tool1'])
    policy = update_global_tools(policy, allow=['tool1', 'tool2'])
    # Should add duplicate
    assert 'tool1' in policy.allowed_tools
    assert 'tool2' in policy.allowed_tools


def test_update_global_tools_with_special_characters():
    """Test that special characters in tool names are handled."""
    policy = MCPTrustPolicy()
    policy = update_global_tools(
        policy, allow=['tool-with-dash', 'tool_with_underscore']
    )
    assert 'tool-with-dash' in policy.allowed_tools
    assert 'tool_with_underscore' in policy.allowed_tools


def test_update_server_tools_with_empty_server_name():
    """Test that empty server name is handled."""
    policy = MCPTrustPolicy()
    policy = update_server_tools(policy, '', trusted=True)
    assert '' in policy.servers


def test_update_server_tools_with_special_characters():
    """Test that special characters in server name are handled."""
    policy = MCPTrustPolicy()
    policy = update_server_tools(policy, 'server-with-dash', trusted=True)
    assert 'server-with-dash' in policy.servers


def test_update_server_tools_with_unicode_server_name():
    """Test that unicode characters in server name are handled."""
    policy = MCPTrustPolicy()
    policy = update_server_tools(policy, '服务器-1', trusted=True)
    assert '服务器-1' in policy.servers


def test_revoke_server_trust_with_nonexistent_server():
    """Test that revoking nonexistent server is handled."""
    policy = MCPTrustPolicy()
    policy = revoke_server_trust(policy, 'nonexistent')
    assert 'nonexistent' not in policy.servers


def test_revoke_server_trust_with_empty_server_name():
    """Test that revoking with empty server name is handled."""
    policy = MCPTrustPolicy()
    policy.servers[''] = MCPServerTrust(trusted=True)
    policy = revoke_server_trust(policy, '')
    assert '' not in policy.servers


def test_merged_tool_filters_with_empty_policy():
    """Test that merging with empty policy returns empty sets."""
    policy = MCPTrustPolicy()
    allowed, denied = merged_tool_filters(policy)
    assert allowed == frozenset()
    assert denied == frozenset()


def test_merged_tool_filters_with_expired_server():
    """Test that expired server tools are excluded."""
    policy = MCPTrustPolicy()
    policy.servers['expired'] = MCPServerTrust(
        allowed_tools=['tool1'],
        expires_at=time.time() - 100,
    )
    allowed, denied = merged_tool_filters(policy)
    assert 'tool1' not in allowed


def test_check_unknown_tool_prompt_with_empty_policy():
    """Test that empty policy returns True (unknown)."""
    policy = MCPTrustPolicy()
    result = check_unknown_tool_prompt(policy, 'any_tool')
    assert result is True


def test_check_unknown_tool_prompt_with_special_characters():
    """Test that special characters in tool names are handled."""
    policy = MCPTrustPolicy(allowed_tools=['tool-with-dash'])
    result = check_unknown_tool_prompt(policy, 'tool-with-dash')
    assert result is False


def test_check_unknown_tool_prompt_with_unicode():
    """Test that unicode characters in tool names are handled."""
    policy = MCPTrustPolicy(allowed_tools=['工具-1'])
    result = check_unknown_tool_prompt(policy, '工具-1')
    assert result is False


def test_mcp_trust_policy_to_dict_with_empty_servers():
    """Test that to_dict handles empty servers dict."""
    policy = MCPTrustPolicy()
    data = policy.to_dict()
    assert data['servers'] == {}


def test_mcp_trust_policy_from_dict_with_invalid_data():
    """Test that from_dict raises ValueError on invalid data."""
    data = {
        'version': 'invalid',  # Should be int
        'allowed_tools': 'not_a_list',  # Should be list
        'denied_tools': None,
        'servers': 'not_a_dict',
    }
    with pytest.raises(ValueError, match='invalid literal for int'):
        MCPTrustPolicy.from_dict(data)


def test_mcp_trust_policy_from_dict_with_missing_fields():
    """Test that from_dict handles missing fields."""
    data = {}
    policy = MCPTrustPolicy.from_dict(data)
    # Should use defaults
    assert policy.version == 1
    assert policy.allowed_tools == []
    assert policy.denied_tools == []


def test_mcp_trust_policy_public_dict_excludes_trusted():
    """Test that to_public_dict excludes trusted field."""
    policy = MCPTrustPolicy()
    policy.servers['server1'] = MCPServerTrust(trusted=True)
    public = policy.to_public_dict()
    assert 'trusted' not in public['servers']['server1']


def test_mcp_trust_policy_version_mismatch():
    """Test that version mismatch is handled."""
    data = {'version': 999, 'allowed_tools': [], 'denied_tools': [], 'servers': {}}
    policy = MCPTrustPolicy.from_dict(data)
    # Should still load despite version mismatch
    assert policy.version == 999
