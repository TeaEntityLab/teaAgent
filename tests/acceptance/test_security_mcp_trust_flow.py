"""Acceptance: MCP trust policy persistence and tool filter merging."""

from __future__ import annotations

from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    merged_tool_filters,
    update_global_tools,
    update_server_tools,
)


class TestMCPTrustPolicy:
    def test_default_policy_empty(self):
        policy = MCPTrustPolicy()
        assert policy.version == 1
        assert policy.allowed_tools == []
        assert policy.denied_tools == []
        assert policy.servers == {}

    def test_to_dict_round_trip(self):
        policy = MCPTrustPolicy(
            version=1,
            allowed_tools=['read_file'],
            denied_tools=['write_file'],
            servers={
                'github': MCPServerTrust(
                    allowed_tools=['search'],
                    denied_tools=[],
                    trusted=True,
                ),
            },
        )
        data = policy.to_dict()
        assert data['version'] == 1
        assert 'read_file' in data['allowed_tools']
        assert 'write_file' in data['denied_tools']
        assert data['servers']['github']['trusted'] is True

        restored = MCPTrustPolicy.from_dict(data)
        assert restored.allowed_tools == ['read_file']
        assert restored.denied_tools == ['write_file']
        assert restored.servers['github'].trusted is True

    def test_from_dict_handles_invalid_servers(self):
        data = {
            'version': 1,
            'allowed_tools': [],
            'denied_tools': [],
            'servers': {
                'bad': 'not a dict',
                'good': {'allowed_tools': ['a'], 'denied_tools': [], 'trusted': False},
            },
        }
        policy = MCPTrustPolicy.from_dict(data)
        assert 'bad' not in policy.servers
        assert 'good' in policy.servers


class TestMergedToolFilters:
    def test_empty_policy_returns_empty_frozensets(self):
        policy = MCPTrustPolicy()
        allowed, denied = merged_tool_filters(policy)
        assert allowed == frozenset()
        assert denied == frozenset()

    def test_merges_global_and_server_tools(self):
        policy = MCPTrustPolicy(
            allowed_tools=['global_read'],
            denied_tools=['global_write'],
            servers={
                'srv1': MCPServerTrust(
                    allowed_tools=['srv_read'],
                    denied_tools=['srv_write'],
                ),
            },
        )
        allowed, denied = merged_tool_filters(policy)
        assert 'global_read' in allowed
        assert 'srv_read' in allowed
        assert 'global_write' in denied
        assert 'srv_write' in denied


class TestUpdateGlobalTools:
    def test_add_allowed_removes_from_denied(self):
        policy = MCPTrustPolicy(denied_tools=['tool-a'])
        result = update_global_tools(policy, allow=['tool-a'])
        assert 'tool-a' in result.allowed_tools
        assert 'tool-a' not in result.denied_tools

    def test_add_denied_removes_from_allowed(self):
        policy = MCPTrustPolicy(allowed_tools=['tool-b'])
        result = update_global_tools(policy, deny=['tool-b'])
        assert 'tool-b' in result.denied_tools
        assert 'tool-b' not in result.allowed_tools

    def test_no_duplicates_on_repeat(self):
        policy = MCPTrustPolicy()
        result = update_global_tools(policy, allow=['tool-c'])
        result = update_global_tools(result, allow=['tool-c'])
        assert result.allowed_tools.count('tool-c') == 1


class TestUpdateServerTools:
    def test_creates_server_entry_if_missing(self):
        policy = MCPTrustPolicy()
        result = update_server_tools(policy, 'github', trusted=True)
        assert 'github' in result.servers
        assert result.servers['github'].trusted is True

    def test_updates_trusted_flag(self):
        policy = MCPTrustPolicy(servers={'srv': MCPServerTrust(trusted=False)})
        result = update_server_tools(policy, 'srv', trusted=True)
        assert result.servers['srv'].trusted is True
