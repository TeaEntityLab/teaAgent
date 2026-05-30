"""Builder pattern for constructing ToolRegistry with dependency injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaagent.tools import ToolRegistry
from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools._files import register_workspace_tools
from teaagent.workspace_tools._git import GitToolConfig, register_git_tools
from teaagent.workspace_tools.config_provider import (
    DynamicConfigProvider,
    ToolConfigProvider,
)
from teaagent.workspace_tools.factory import ToolFactory


class ToolRegistryBuilder:
    """Builder for constructing ToolRegistry with workspace and git tools.

    Usage:
        registry = (ToolRegistryBuilder()
            .with_root('/path/to/workspace')
            .with_workspace_tools()
            .with_git_tools()
            .build())
    """

    def __init__(self) -> None:
        self._root: Path | None = None
        self._config: WorkspaceToolConfig | None = None
        self._config_provider: ToolConfigProvider | None = None
        self._factory: ToolFactory | None = None
        self._registry: ToolRegistry | None = None
        self._include_workspace = False
        self._include_git = False

    def with_root(self, root: str | Path) -> ToolRegistryBuilder:
        self._root = Path(root).resolve()
        return self

    def with_config(self, config: WorkspaceToolConfig) -> ToolRegistryBuilder:
        self._config = config
        return self

    def with_config_provider(self, provider: ToolConfigProvider) -> ToolRegistryBuilder:
        self._config_provider = provider
        return self

    def with_dynamic_config(self, loader: Any) -> ToolRegistryBuilder:
        return self.with_config_provider(DynamicConfigProvider(loader))

    def with_registry(self, registry: ToolRegistry) -> ToolRegistryBuilder:
        self._registry = registry
        return self

    def with_workspace_tools(self) -> ToolRegistryBuilder:
        self._include_workspace = True
        return self

    def with_git_tools(self) -> ToolRegistryBuilder:
        self._include_git = True
        return self

    def with_all_tools(self) -> ToolRegistryBuilder:
        self._include_workspace = True
        self._include_git = True
        return self

    def build(self) -> ToolRegistry:
        root = self._root or Path.cwd()

        config = self._config or WorkspaceToolConfig.from_root(root)
        factory = ToolFactory(config)
        registry = self._registry or ToolRegistry()

        if self._include_workspace:
            register_workspace_tools(registry, factory)
        if self._include_git:
            register_git_tools(registry, GitToolConfig(root=root))

        return registry

    def __repr__(self) -> str:
        parts = []
        if self._root:
            parts.append(f'root={self._root}')
        if self._include_workspace:
            parts.append('workspace')
        if self._include_git:
            parts.append('git')
        return f'<ToolRegistryBuilder {" ".join(parts)}>'
