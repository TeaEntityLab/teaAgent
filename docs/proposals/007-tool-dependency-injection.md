# Proposal: Add Dependency Injection for Tool Registration

## Executive Summary
This proposal outlines a plan to create a `ToolFactory` class that handles tool creation with proper dependency injection, replacing the lambda function pattern that captures configuration in closures.

## Problem Statement

### Current State
Tool registration uses lambda functions that capture configuration in closures, making it difficult to test and creating implicit dependencies:
```python
handler=lambda args: read_file(config, args),
```

This pattern is repeated throughout the file. The configuration is embedded in the handler closure, making it impossible to change configuration at runtime or inject test doubles.

### Impact
- **Implicit Dependencies**: Configuration is captured in closures
- **Testing Difficulty**: Hard to test with mock configurations
- **Runtime Inflexibility**: Cannot change configuration at runtime
- **Code Duplication**: Lambda pattern repeated throughout

## Proposed Solution

### Phase 1: Create ToolFactory Class
1. **Create Class**: Create `ToolFactory` class to handle tool creation
2. **Move Logic**: Move tool registration logic from lambdas to factory methods
3. **Add Tests**: Add unit tests for the factory
4. **Update Registration**: Update tool registration to use the factory

### Phase 2: Implement ToolConfigProvider Interface
1. **Create Interface**: Create `ToolConfigProvider` protocol
2. **Implement Providers**: Implement providers for different configuration sources
3. **Add Tests**: Add unit tests for each provider
4. **Update Tools**: Update tools to use the interface

### Phase 3: Use Partial Functions or Tool Classes
1. **Replace Lambdas**: Replace lambdas with `functools.partial` or tool classes
2. **Create Classes**: Create tool classes for complex tools
3. **Add Tests**: Add unit tests for each tool class
4. **Update Registration**: Update tool registration to use partials/classes

### Phase 4: Create ToolBuilder Pattern
1. **Create Builder**: Create `ToolBuilder` pattern for complex tool initialization
2. **Implement Builders**: Implement builders for tools with complex dependencies
3. **Add Tests**: Add unit tests for each builder
4. **Update Registration**: Update tool registration to use builders

### Phase 5: Support Tool Configuration Updates
1. **Add Methods**: Add methods to update tool configuration without re-registration
2. **Add Tests**: Add unit tests for configuration updates
3. **Update Tools**: Update tools to support dynamic configuration
4. **Update Documentation**: Update documentation for tool configuration

## Implementation Details

### ToolFactory Class
```python
# workspace_tools/factory.py
from typing import Any, Callable
from teaagent.workspace_tools._files import WorkspaceToolConfig

class ToolFactory:
    """Factory for creating tool handlers with dependency injection."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize tool factory."""
        self._config = config
    
    def create_read_file_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create read_file handler."""
        from teaagent.workspace_tools._files import read_file
        return lambda args: read_file(self._config, args)
    
    def create_write_file_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create write_file handler."""
        from teaagent.workspace_tools._files import write_file
        return lambda args: write_file(self._config, args)
    
    def create_edit_at_hash_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create edit_at_hash handler."""
        from teaagent.workspace_tools._files import edit_at_hash
        return lambda args: edit_at_hash(self._config, args)
    
    def create_run_shell_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell handler."""
        from teaagent.workspace_tools._shell import run_shell
        return lambda args: run_shell(self._config, args)
    
    def create_run_shell_argv_handler(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Create run_shell_argv handler."""
        from teaagent.workspace_tools._shell import run_shell_argv
        return lambda args: run_shell_argv(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration for all tools."""
        self._config = config
```

### ToolConfigProvider Interface
```python
# workspace_tools/config_provider.py
from typing import Protocol, Any
from teaagent.workspace_tools._files import WorkspaceToolConfig

class ToolConfigProvider(Protocol):
    """Protocol for tool configuration providers."""
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get tool configuration."""
        ...

class StaticConfigProvider:
    """Static configuration provider."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize static configuration provider."""
        self._config = config
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get static configuration."""
        return self._config

class DynamicConfigProvider:
    """Dynamic configuration provider."""
    
    def __init__(self, config_loader: Callable[[], WorkspaceToolConfig]):
        """Initialize dynamic configuration provider."""
        self._config_loader = config_loader
    
    def get_config(self) -> WorkspaceToolConfig:
        """Get dynamic configuration."""
        return self._config_loader()
```

### Tool Classes
```python
# workspace_tools/tool_classes.py
from typing import Any
from teaagent.workspace_tools._files import WorkspaceToolConfig

class ReadFileTool:
    """Read file tool as a class."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize read file tool."""
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute read file tool."""
        from teaagent.workspace_tools._files import read_file
        return read_file(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration."""
        self._config = config

class WriteFileTool:
    """Write file tool as a class."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize write file tool."""
        self._config = config
    
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute write file tool."""
        from teaagent.workspace_tools._files import write_file
        return write_file(self._config, args)
    
    def update_config(self, config: WorkspaceToolConfig) -> None:
        """Update configuration."""
        self._config = config
```

### ToolBuilder Pattern
```python
# workspace_tools/builder.py
from typing import Any
from teaagent.workspace_tools._files import WorkspaceToolConfig
from teaagent.workspace_tools.tool_classes import ReadFileTool, WriteFileTool

class ToolBuilder:
    """Builder for tool creation with complex dependencies."""
    
    def __init__(self, config: WorkspaceToolConfig):
        """Initialize tool builder."""
        self._config = config
        self._tools: dict[str, Any] = {}
    
    def add_read_file_tool(self) -> 'ToolBuilder':
        """Add read file tool."""
        self._tools['workspace_read_file'] = ReadFileTool(self._config)
        return self
    
    def add_write_file_tool(self) -> 'ToolBuilder':
        """Add write file tool."""
        self._tools['workspace_write_file'] = WriteFileTool(self._config)
        return self
    
    def add_custom_tool(
        self,
        name: str,
        tool: Any,
    ) -> 'ToolBuilder':
        """Add custom tool."""
        self._tools[name] = tool
        return self
    
    def build(self) -> dict[str, Any]:
        """Build tool registry."""
        return self._tools
```

### Refactored Tool Registration
```python
# workspace_tools/_files.py
from teaagent.workspace_tools.factory import ToolFactory
from teaagent.workspace_tools.config_provider import StaticConfigProvider

def build_workspace_tool_registry(
    root: str | Path,
    config_provider: ToolConfigProvider | None = None,
) -> ToolRegistry:
    """Build tool registry with dependency injection."""
    config = WorkspaceToolConfig.from_root(root)
    
    if config_provider is None:
        config_provider = StaticConfigProvider(config)
    
    factory = ToolFactory(config)
    
    registry = ToolRegistry()
    
    # Register tools using factory
    registry.register(
        'workspace_read_file',
        factory.create_read_file_handler(),
        # Tool metadata
    )
    
    registry.register(
        'workspace_write_file',
        factory.create_write_file_handler(),
        # Tool metadata
    )
    
    registry.register(
        'workspace_edit_at_hash',
        factory.create_edit_at_hash_handler(),
        # Tool metadata
    )
    
    return registry
```

## Migration Plan

### Step 1: Create ToolFactory
1. Create `ToolFactory` class
2. Move tool registration logic from lambdas to factory methods
3. Add unit tests for factory
4. Update tool registration to use factory

### Step 2: Create ToolConfigProvider
1. Create `ToolConfigProvider` interface
2. Implement providers for different configuration sources
3. Add unit tests for each provider
4. Update tools to use the interface

### Step 3: Replace Lambdas with Partials/Classes
1. Replace lambdas with `functools.partial` or tool classes
2. Create tool classes for complex tools
3. Add unit tests for each tool class
4. Update tool registration to use partials/classes

### Step 4: Create ToolBuilder
1. Create `ToolBuilder` pattern
2. Implement builders for complex tools
3. Add unit tests for each builder
4. Update tool registration to use builders

### Step 5: Support Configuration Updates
1. Add methods to update tool configuration
2. Add unit tests for configuration updates
3. Update tools to support dynamic configuration
4. Update documentation

### Step 6: Update Tests
1. Update unit tests to use new patterns
2. Add integration tests for dependency injection
3. Verify all tests pass
4. Update documentation

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep lambda pattern working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for dependency injection
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for tool execution

## Timeline

### Phase 1: Create ToolFactory (1 week)
- Week 1: Create factory, move logic, add tests

### Phase 2: Create ToolConfigProvider (1 week)
- Week 2: Create providers, add tests, update tools

### Phase 3: Replace Lambdas (1 week)
- Week 3: Replace lambdas, create classes, add tests

### Phase 4: Create ToolBuilder (1 week)
- Week 4: Create builder, add tests, update registration

### Phase 5: Support Configuration Updates (1 week)
- Week 5: Add methods, add tests, update tools

### Phase 6: Update Tests and Documentation (1 week)
- Week 6: Update tests, verify all tests pass, update documentation

## Success Criteria

- ✅ No lambda closures capturing configuration
- ✅ ToolFactory handles all tool creation
- ✅ Dependency injection supported
- ✅ Dynamic configuration updates supported
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Lambda Closures
- **Pros**: No changes required
- **Cons**: Hard to test, implicit dependencies
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Class-Based Tools Only
- **Pros**: Explicit dependencies
- **Cons**: Adds boilerplate for simple tools
- **Decision**: Rejected - partial functions sufficient for simple tools

### Alternative 3: Use Framework-Level DI Container
- **Pros**: Automatic dependency resolution
- **Cons**: Over-engineering, adds dependency
- **Decision**: Rejected - simpler solution available

## References
- ADR-007: Add dependency injection for tool registration
- Current implementation in `workspace_tools/_files.py`
- Dependency injection best practices
