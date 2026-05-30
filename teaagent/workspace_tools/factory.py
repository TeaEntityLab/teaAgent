"""Factory for creating tool handlers with dependency injection."""

from typing import Any, Callable
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
        return lambda args: read_file(self._config, args)
    
    def create_write_file_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create write_file handler.
        
        Returns:
            Handler function for write_file tool
        """
        from teaagent.workspace_tools._files import write_file
        return lambda args: write_file(self._config, args)
    
    def create_edit_at_hash_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create edit_at_hash handler.
        
        Returns:
            Handler function for edit_at_hash tool
        """
        from teaagent.workspace_tools._files import edit_at_hash
        return lambda args: edit_at_hash(self._config, args)
    
    def create_run_shell_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell handler.
        
        Returns:
            Handler function for run_shell tool
        """
        from teaagent.workspace_tools._shell import run_shell
        return lambda args: run_shell(self._config, args)
    
    def create_run_shell_argv_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell_argv handler.
        
        Returns:
            Handler function for run_shell_argv tool
        """
        from teaagent.workspace_tools._shell import run_shell_argv
        return lambda args: run_shell_argv(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration for all tools.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config
