"""Tool classes for dependency injection pattern."""

from typing import Any
from teaagent.workspace_tools._files import WorkspaceToolConfig


class ReadFileTool:
    """Read file tool as a class for dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize read file tool.
        
        Args:
            config: Workspace tool configuration
        """
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute read file tool.
        
        Args:
            args: Tool arguments
            
        Returns:
            Tool result
        """
        from teaagent.workspace_tools._files import read_file
        return read_file(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config


class WriteFileTool:
    """Write file tool as a class for dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize write file tool.
        
        Args:
            config: Workspace tool configuration
        """
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute write file tool.
        
        Args:
            args: Tool arguments
            
        Returns:
            Tool result
        """
        from teaagent.workspace_tools._files import write_file
        return write_file(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config


class EditAtHashTool:
    """Edit at hash tool as a class for dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize edit at hash tool.
        
        Args:
            config: Workspace tool configuration
        """
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute edit at hash tool.
        
        Args:
            args: Tool arguments
            
        Returns:
            Tool result
        """
        from teaagent.workspace_tools._files import edit_at_hash
        return edit_at_hash(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config


class RunShellTool:
    """Run shell tool as a class for dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize run shell tool.
        
        Args:
            config: Workspace tool configuration
        """
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute run shell tool.
        
        Args:
            args: Tool arguments
            
        Returns:
            Tool result
        """
        from teaagent.workspace_tools._shell import run_shell
        return run_shell(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config


class RunShellArgvTool:
    """Run shell argv tool as a class for dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize run shell argv tool.
        
        Args:
            config: Workspace tool configuration
        """
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute run shell argv tool.
        
        Args:
            args: Tool arguments
            
        Returns:
            Tool result
        """
        from teaagent.workspace_tools._shell import run_shell_argv
        return run_shell_argv(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration.
        
        Args:
            config: New workspace tool configuration
        """
        self._config = config
