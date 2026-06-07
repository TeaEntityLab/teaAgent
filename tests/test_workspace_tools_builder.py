from __future__ import annotations

from pathlib import Path

from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools.builder import ToolRegistryBuilder


class TestToolRegistryBuilder:
    def test_build_empty(self) -> None:
        registry = ToolRegistryBuilder().build()
        assert registry.list_tools() == []

    def test_build_with_workspace_tools(self) -> None:
        registry = ToolRegistryBuilder().with_workspace_tools().build()
        tools = registry.list_tools()
        assert 'workspace_read_file' in tools

    def test_build_with_git_tools(self) -> None:
        registry = ToolRegistryBuilder().with_git_tools().build()
        tools = registry.list_tools()
        assert 'git_add' in tools

    def test_build_with_all_tools(self) -> None:
        registry = ToolRegistryBuilder().with_all_tools().build()
        tools = registry.list_tools()
        assert 'workspace_read_file' in tools
        assert 'git_add' in tools

    def test_custom_root(self) -> None:
        registry = (
            ToolRegistryBuilder().with_root('/tmp').with_workspace_tools().build()
        )
        assert 'workspace_read_file' in registry.list_tools()

    def test_custom_registry(self) -> None:
        from teaagent.tools import ToolRegistry

        existing = ToolRegistry()
        result = ToolRegistryBuilder().with_registry(existing).build()
        assert result is existing

    def test_with_config(self) -> None:
        config = WorkspaceToolConfig(root=Path('/tmp'))
        builder = ToolRegistryBuilder().with_config(config).with_workspace_tools()
        registry = builder.build()
        assert 'workspace_read_file' in registry.list_tools()

    def test_with_dynamic_config(self) -> None:
        config = WorkspaceToolConfig(root=Path('/tmp'))
        builder = ToolRegistryBuilder().with_dynamic_config(loader=lambda: config)
        registry = builder.with_workspace_tools().build()
        assert 'workspace_read_file' in registry.list_tools()

    def test_with_config_provider(self) -> None:
        from teaagent.workspace_tools.config_provider import StaticConfigProvider

        config = WorkspaceToolConfig(root=Path('/tmp'))
        builder = ToolRegistryBuilder().with_config_provider(
            StaticConfigProvider(config)
        )
        registry = builder.with_workspace_tools().build()
        assert 'workspace_read_file' in registry.list_tools()

    def test_repr_includes_flags(self) -> None:
        r = repr(ToolRegistryBuilder().with_root('/p').with_all_tools())
        assert 'root=/p' in r
        assert 'workspace' in r
        assert 'git' in r

    def test_repr_empty(self) -> None:
        r = repr(ToolRegistryBuilder())
        assert 'ToolRegistryBuilder' in r
