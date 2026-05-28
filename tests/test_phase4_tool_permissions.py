from __future__ import annotations

from teaagent.tool_permissions import (
    PermissionRequest,
    ToolPermission,
    ToolPermissionManager,
    ToolSafetyLevel,
)


class TestToolPermissionManager:
    """Test suite for ToolPermissionManager."""

    def test_manager_initialization(self):
        """Test that manager initializes with default permissions."""
        manager = ToolPermissionManager()
        assert len(manager._tool_permissions) > 0

    def test_default_tool_classifications(self):
        """Test that common tools have correct safety classifications."""
        manager = ToolPermissionManager()

        # Safe tools
        assert manager.classify_tool('read_file') == ToolSafetyLevel.SAFE
        assert manager.classify_tool('grep') == ToolSafetyLevel.SAFE

        # Inspect tools
        assert manager.classify_tool('python_repl') == ToolSafetyLevel.INSPECT
        assert manager.classify_tool('shell') == ToolSafetyLevel.INSPECT

        # Destructive tools
        assert manager.classify_tool('write_file') == ToolSafetyLevel.DESTRUCTIVE
        assert manager.classify_tool('delete_file') == ToolSafetyLevel.DESTRUCTIVE

    def test_register_custom_tool_permission(self):
        """Test registering custom tool permissions."""
        manager = ToolPermissionManager()

        custom_perm = ToolPermission(
            name='custom_tool',
            safety_level=ToolSafetyLevel.SAFE,
            description='A custom tool',
        )

        manager.register_tool_permission(custom_perm)

        retrieved = manager.get_tool_permission('custom_tool')
        assert retrieved is not None
        assert retrieved.safety_level == ToolSafetyLevel.SAFE

    def test_grant_agent_tool_access_safe_only(self):
        """Test granting agent access with safe defaults."""
        manager = ToolPermissionManager()

        tools = ('read_file', 'write_file', 'delete_file')
        manager.grant_agent_tool_access('test-agent', tools, allow_destructive=False)

        agent_tools = manager.get_agent_tools('test-agent')

        # Should only have safe tools
        assert 'read_file' in agent_tools
        assert 'write_file' not in agent_tools
        assert 'delete_file' not in agent_tools

    def test_grant_agent_tool_access_with_destructive(self):
        """Test granting agent access with destructive tools allowed."""
        manager = ToolPermissionManager()

        tools = ('read_file', 'write_file', 'delete_file')
        manager.grant_agent_tool_access('test-agent', tools, allow_destructive=True)

        agent_tools = manager.get_agent_tools('test-agent')

        # Should have all tools
        assert 'read_file' in agent_tools
        assert 'write_file' in agent_tools
        assert 'delete_file' in agent_tools

    def test_check_tool_access_allowed(self):
        """Test checking tool access for allowed tool."""
        manager = ToolPermissionManager()

        manager.grant_agent_tool_access('test-agent', ('read_file',), allow_destructive=False)

        has_access, reason = manager.check_tool_access('test-agent', 'read_file')
        assert has_access is True
        assert reason is None

    def test_check_tool_access_not_whitelisted(self):
        """Test checking tool access for non-whitelisted tool."""
        manager = ToolPermissionManager()

        manager.grant_agent_tool_access('test-agent', ('read_file',), allow_destructive=False)

        has_access, reason = manager.check_tool_access('test-agent', 'write_file')
        assert has_access is False
        assert 'not in agent whitelist' in reason

    def test_check_tool_access_requires_approval(self):
        """Test checking tool access for approval-required tool."""
        manager = ToolPermissionManager()

        # Grant destructive tool access
        manager.grant_agent_tool_access('test-agent', ('write_file',), allow_destructive=True)

        has_access, reason = manager.check_tool_access('test-agent', 'write_file')
        assert has_access is False
        assert 'requires JIT approval' in reason

    def test_apply_safe_defaults(self):
        """Test applying safe defaults to filter tools."""
        manager = ToolPermissionManager()

        requested_tools = ('read_file', 'write_file', 'delete_file', 'grep')
        filtered = manager.apply_safe_defaults('test-agent', requested_tools)

        # Should only have safe tools
        assert 'read_file' in filtered
        assert 'grep' in filtered
        assert 'write_file' not in filtered
        assert 'delete_file' not in filtered

    def test_request_tool_approval_without_callback(self):
        """Test tool approval request without callback (denied)."""
        manager = ToolPermissionManager(approval_callback=None)

        request = manager.request_tool_approval(
            'test-agent', 'write_file', 'Need to write file'
        )

        assert request.approved is False
        assert request.tool_name == 'write_file'

    def test_request_tool_approval_with_callback(self):
        """Test tool approval request with custom callback."""
        def mock_approve(request: PermissionRequest) -> bool:
            return request.tool_name == 'write_file'

        manager = ToolPermissionManager(approval_callback=mock_approve)

        # First grant the agent access to the tool (with destructive allowed)
        manager.grant_agent_tool_access('test-agent', ('write_file',), allow_destructive=True)

        request = manager.request_tool_approval(
            'test-agent', 'write_file', 'Need to write file'
        )

        assert request.approved is True

        # Verify tool was added to whitelist
        agent_tools = manager.get_agent_tools('test-agent')
        assert 'write_file' in agent_tools

        # Verify tool no longer requires approval (was updated)
        has_access, _ = manager.check_tool_access('test-agent', 'write_file')
        assert has_access is True

    def test_revoke_agent_tool_access(self):
        """Test revoking agent tool access."""
        manager = ToolPermissionManager()

        manager.grant_agent_tool_access('test-agent', ('read_file', 'write_file'), allow_destructive=True)
        manager.revoke_agent_tool_access('test-agent', 'write_file')

        agent_tools = manager.get_agent_tools('test-agent')
        assert 'read_file' in agent_tools
        assert 'write_file' not in agent_tools
