"""Tests for tool dependency injection implementation."""

import tempfile

import pytest

from teaagent.workspace_tools._files import (
    WorkspaceToolConfig,
)
from teaagent.workspace_tools.config_provider import (
    DynamicConfigProvider,
    StaticConfigProvider,
)
from teaagent.workspace_tools.factory import ToolFactory
from teaagent.workspace_tools.tool_classes import (
    EditAtHashTool,
    ReadFileTool,
    RunShellArgvTool,
    RunShellTool,
    WriteFileTool,
)


class TestToolFactory:
    """Tests for ToolFactory class."""

    def test_create_read_file_handler(self):
        """Test creating read_file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config)

            handler = factory.create_read_file_handler()

            assert handler is not None
            assert callable(handler)

    def test_create_write_file_handler(self):
        """Test creating write_file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config)

            handler = factory.create_write_file_handler()

            assert handler is not None
            assert callable(handler)

    def test_create_edit_at_hash_handler(self):
        """Test creating edit_at_hash handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config)

            handler = factory.create_edit_at_hash_handler()

            assert handler is not None
            assert callable(handler)

    def test_create_run_shell_handler(self):
        """Test creating run_shell handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config)

            handler = factory.create_run_shell_handler()

            assert handler is not None
            assert callable(handler)

    def test_create_run_shell_argv_handler(self):
        """Test creating run_shell_argv handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config)

            handler = factory.create_run_shell_argv_handler()

            assert handler is not None
            assert callable(handler)

    def test_update_config(self):
        """Test updating configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config1 = WorkspaceToolConfig.from_root(tmpdir)
            factory = ToolFactory(config1)

            # Create handler with initial config
            handler1 = factory.create_read_file_handler()

            # Update config
            config2 = WorkspaceToolConfig.from_root(tmpdir)
            factory.update_config(config2)

            # Create handler with updated config
            handler2 = factory.create_read_file_handler()

            # Both handlers should be callable
            assert callable(handler1)
            assert callable(handler2)


class TestToolConfigProvider:
    """Tests for ToolConfigProvider implementations."""

    def test_static_config_provider(self):
        """Test StaticConfigProvider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            provider = StaticConfigProvider(config)

            result = provider.get_config()

            assert result == config

    def test_dynamic_config_provider(self):
        """Test DynamicConfigProvider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)

            call_count = 0

            def config_loader():
                nonlocal call_count
                call_count += 1
                return config

            provider = DynamicConfigProvider(config_loader)

            result1 = provider.get_config()
            result2 = provider.get_config()

            assert result1 == config
            assert result2 == config
            assert call_count == 2  # Called each time


class TestToolClasses:
    """Tests for tool classes."""

    def test_read_file_tool(self):
        """Test ReadFileTool class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            tool = ReadFileTool(config)

            assert tool is not None
            assert callable(tool)

            # Test update_config
            new_config = WorkspaceToolConfig.from_root(tmpdir)
            tool.update_config(new_config)

            assert tool._config == new_config

    def test_write_file_tool(self):
        """Test WriteFileTool class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            tool = WriteFileTool(config)

            assert tool is not None
            assert callable(tool)

            # Test update_config
            new_config = WorkspaceToolConfig.from_root(tmpdir)
            tool.update_config(new_config)

            assert tool._config == new_config

    def test_edit_at_hash_tool(self):
        """Test EditAtHashTool class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            tool = EditAtHashTool(config)

            assert tool is not None
            assert callable(tool)

            # Test update_config
            new_config = WorkspaceToolConfig.from_root(tmpdir)
            tool.update_config(new_config)

            assert tool._config == new_config

    def test_run_shell_tool(self):
        """Test RunShellTool class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            tool = RunShellTool(config)

            assert tool is not None
            assert callable(tool)

            # Test update_config
            new_config = WorkspaceToolConfig.from_root(tmpdir)
            tool.update_config(new_config)

            assert tool._config == new_config

    def test_run_shell_argv_tool(self):
        """Test RunShellArgvTool class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)
            tool = RunShellArgvTool(config)

            assert tool is not None
            assert callable(tool)

            # Test update_config
            new_config = WorkspaceToolConfig.from_root(tmpdir)
            tool.update_config(new_config)

            assert tool._config == new_config


class TestToolFactoryIntegration:
    """Integration tests for ToolFactory with actual tool execution."""

    def test_registry_with_factory(self):
        """Test that registry works with factory-created handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.workspace_tools._files import build_workspace_tool_registry

            # Build registry using factory
            registry = build_workspace_tool_registry(tmpdir)

            # Verify tools are registered
            assert 'workspace_read_file' in registry._tools
            assert 'workspace_write_file' in registry._tools
            assert 'workspace_run_shell' in registry._tools

            # Verify handlers are callable
            for tool_name in [
                'workspace_read_file',
                'workspace_write_file',
                'workspace_run_shell',
            ]:
                handler = registry._tools[tool_name].handler
                assert callable(handler)


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_build_workspace_tool_registry_without_provider(self):
        """Test build_workspace_tool_registry works without config_provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.workspace_tools._files import build_workspace_tool_registry

            registry = build_workspace_tool_registry(tmpdir)

            assert registry is not None
            assert 'workspace_read_file' in registry._tools

    def test_build_workspace_tool_registry_with_provider(self):
        """Test build_workspace_tool_registry works with config_provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.workspace_tools._files import build_workspace_tool_registry
            from teaagent.workspace_tools.config_provider import StaticConfigProvider

            config = WorkspaceToolConfig.from_root(tmpdir)
            provider = StaticConfigProvider(config)

            registry = build_workspace_tool_registry(tmpdir, config_provider=provider)

            assert registry is not None
            assert 'workspace_read_file' in registry._tools


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
