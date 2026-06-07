"""Factory for creating tool handlers with dependency injection.

Uses ``functools.partial`` instead of lambda closures to bind the
workspace configuration to each tool handler.  Partial objects are
inspectable (``.func``, ``.args``), picklable, and avoid the
late-binding pitfalls of lambda closures.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from teaagent.workspace_tools._files import WorkspaceToolConfig


class ToolFactory:
    """Factory for creating tool handlers with dependency injection."""

    def __init__(self, config: WorkspaceToolConfig):
        """Initialize tool factory.

        Args:
            config: Workspace tool configuration
        """
        self._config = config

    def create_read_file_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create read_file handler.

        Returns:
            Handler function for read_file tool
        """
        from teaagent.workspace_tools._files import read_file

        return functools.partial(read_file, self._config)

    def create_write_file_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create write_file handler.

        Returns:
            Handler function for write_file tool
        """
        from teaagent.workspace_tools._files import write_file

        return functools.partial(write_file, self._config)

    def create_edit_at_hash_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create edit_at_hash handler.

        Returns:
            Handler function for edit_at_hash tool
        """
        from teaagent.workspace_tools._files import edit_at_hash

        return functools.partial(edit_at_hash, self._config)

    def create_run_shell_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell handler.

        Returns:
            Handler function for run_shell tool
        """
        from teaagent.workspace_tools._shell import run_shell

        return functools.partial(run_shell, self._config)

    def create_run_shell_argv_handler(
        self,
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell_argv handler.

        Returns:
            Handler function for run_shell_argv tool
        """
        from teaagent.workspace_tools._shell import run_shell_argv

        return functools.partial(run_shell_argv, self._config)

    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration for all tools.

        Args:
            config: New workspace tool configuration
        """
        self._config = config
