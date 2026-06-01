# Proposal: Reduce Tight Coupling in chat_agent.py

## Executive Summary
This proposal outlines a plan to reduce tight coupling in `chat_agent.py` by introducing dependency injection and factory patterns.

## Problem Statement

### Current State
The `ChatAgentConfig` and `run_chat_agent` function have direct dependencies on multiple backend systems:
- `CodeAnalysisConfig` (line 15-20)
- `LSPServerManager` (line 17)
- `SubagentManager` (line 54)
- `HookRegistry` (line 25)
- `MemoryCatalog` (line 31)
- `WorkspaceToolConfig` (line 56-60)

The `ChatAgentConfig.from_root()` method directly instantiates these components, creating tight coupling to implementation details.

### Impact
- **Tight Coupling**: Direct instantiation creates tight coupling
- **Testing Difficulty**: Hard to test with mock implementations
- **Flexibility**: Difficult to swap implementations
- **Extensibility**: Hard to add new components

## Proposed Solution

### Phase 1: Create ChatAgentConfigFactory
1. **Create Class**: Create `ChatAgentConfigFactory` class
2. **Move Logic**: Move initialization logic from `ChatAgentConfig.from_root()` to the factory
3. **Add Tests**: Add unit tests for the factory
4. **Update Callers**: Update callers to use the factory

### Phase 2: Introduce ConfigurationProvider Interface
1. **Create Interface**: Create `ConfigurationProvider` protocol/interface
2. **Implement Providers**: Implement providers for different configuration sources
3. **Add Tests**: Add unit tests for each provider
4. **Update ChatAgentConfig**: Update `ChatAgentConfig` to use the interface

### Phase 3: Create Backend Adapters
1. **Create Adapters**: Create adapter interfaces for each backend system
2. **Implement Adapters**: Implement adapters for code analysis, workspace tools, etc.
3. **Add Tests**: Add unit tests for each adapter
4. **Update run_chat_agent**: Update `run_chat_agent` to use adapters

### Phase 4: Use Dependency Injection
1. **Refactor**: Refactor `run_chat_agent` to accept dependencies as parameters
2. **Create Builder**: Create builder pattern for complex dependency graphs
3. **Add Tests**: Add integration tests for the new pattern
4. **Update Callers**: Update all callers to use dependency injection

## Implementation Details

### ChatAgentConfigFactory
```python
# chat_agent/factory.py
from teaagent.chat_agent import ChatAgentConfig
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.workspace_tools import WorkspaceToolConfig

class ChatAgentConfigFactory:
    """Factory for creating ChatAgentConfig."""
    
    def __init__(self, root: str | Path):
        """Initialize factory."""
        self._root = Path(root).resolve()
    
    def create_config(
        self,
        code_analysis_config: CodeAnalysisConfig | None = None,
        workspace_tool_config: WorkspaceToolConfig | None = None,
        **kwargs,
    ) -> ChatAgentConfig:
        """Create ChatAgentConfig with dependencies."""
        # Implementation from ChatAgentConfig.from_root
        pass
```

### ConfigurationProvider Interface
```python
# chat_agent/config_provider.py
from typing import Protocol, Any

class ConfigurationProvider(Protocol):
    """Protocol for configuration providers."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        ...
    
    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        ...

class FileConfigurationProvider:
    """Configuration provider from file."""
    
    def __init__(self, path: Path):
        """Initialize file configuration provider."""
        self._path = path
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value from file."""
        pass

class EnvironmentConfigurationProvider:
    """Configuration provider from environment variables."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value from environment."""
        pass
```

### Backend Adapters
```python
# chat_agent/adapters.py
from typing import Protocol

class CodeAnalysisAdapter(Protocol):
    """Adapter for code analysis backend."""
    
    def analyze(self, path: Path) -> dict[str, Any]:
        """Analyze code."""
        ...

class WorkspaceToolAdapter(Protocol):
    """Adapter for workspace tools."""
    
    def invoke(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Invoke tool."""
        ...

class LSPServerAdapter(Protocol):
    """Adapter for LSP server."""
    
    def start(self) -> None:
        """Start LSP server."""
        ...
    
    def stop(self) -> None:
        """Stop LSP server."""
        ...
```

### Refactored run_chat_agent
```python
# chat_agent/runner.py
from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_agent.adapters import (
    CodeAnalysisAdapter,
    WorkspaceToolAdapter,
    LSPServerAdapter,
)

def run_chat_agent(
    config: ChatAgentConfig,
    task: str,
    *,
    code_analysis_adapter: CodeAnalysisAdapter | None = None,
    workspace_tool_adapter: WorkspaceToolAdapter | None = None,
    lsp_server_adapter: LSPServerAdapter | None = None,
    **kwargs,
) -> RunResult:
    """Run chat agent with injected dependencies."""
    # Use injected adapters instead of direct instantiation
    pass
```

### Builder Pattern
```python
# chat_agent/builder.py
from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_agent.adapters import (
    CodeAnalysisAdapter,
    WorkspaceToolAdapter,
    LSPServerAdapter,
)

class ChatAgentBuilder:
    """Builder for chat agent dependencies."""
    
    def __init__(self, root: str | Path):
        """Initialize builder."""
        self._root = Path(root).resolve()
        self._code_analysis_adapter: CodeAnalysisAdapter | None = None
        self._workspace_tool_adapter: WorkspaceToolAdapter | None = None
        self._lsp_server_adapter: LSPServerAdapter | None = None
    
    def with_code_analysis_adapter(
        self,
        adapter: CodeAnalysisAdapter,
    ) -> 'ChatAgentBuilder':
        """Set code analysis adapter."""
        self._code_analysis_adapter = adapter
        return self
    
    def with_workspace_tool_adapter(
        self,
        adapter: WorkspaceToolAdapter,
    ) -> 'ChatAgentBuilder':
        """Set workspace tool adapter."""
        self._workspace_tool_adapter = adapter
        return self
    
    def with_lsp_server_adapter(
        self,
        adapter: LSPServerAdapter,
    ) -> 'ChatAgentBuilder':
        """Set LSP server adapter."""
        self._lsp_server_adapter = adapter
        return self
    
    def build(self) -> ChatAgentConfig:
        """Build ChatAgentConfig."""
        # Build config with configured adapters
        pass
```

## Migration Plan

### Step 1: Create Factory
1. Create `ChatAgentConfigFactory` class
2. Move initialization logic from `ChatAgentConfig.from_root()`
3. Add unit tests for factory
4. Update callers to use factory

### Step 2: Create Configuration Providers
1. Create `ConfigurationProvider` interface
2. Implement file and environment providers
3. Add unit tests for each provider
4. Update `ChatAgentConfig` to use providers

### Step 3: Create Adapters
1. Create adapter interfaces for each backend
2. Implement adapters for existing backends
3. Add unit tests for each adapter
4. Update `run_chat_agent` to use adapters

### Step 4: Implement Dependency Injection
1. Refactor `run_chat_agent` to accept dependencies
2. Create builder pattern for complex dependencies
3. Add integration tests for new pattern
4. Update all callers to use dependency injection

### Step 5: Update Tests
1. Update unit tests to use factory
2. Update integration tests to use adapters
3. Add tests for builder pattern
4. Verify all tests pass

### Step 6: Documentation
1. Update API documentation
2. Update architecture documentation
3. Create migration guide
4. Update examples

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep `ChatAgentConfig.from_root()` working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for dependency injection
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for chat agent success rate

## Timeline

### Phase 1: Create Factory (1 week)
- Week 1: Create factory, move logic, add tests

### Phase 2: Create Configuration Providers (1 week)
- Week 2: Create providers, add tests, update ChatAgentConfig

### Phase 3: Create Adapters (1 week)
- Week 3: Create adapters, add tests, update run_chat_agent

### Phase 4: Implement Dependency Injection (1 week)
- Week 4: Refactor run_chat_agent, create builder, add tests

### Phase 5: Update Callers (1 week)
- Week 5: Update callers, add tests, verify all tests pass

### Phase 6: Documentation (1 week)
- Week 6: Update documentation, create migration guide

## Success Criteria

- ✅ No direct instantiation in `run_chat_agent`
- ✅ All dependencies injected via parameters
- ✅ Factory pattern for complex initialization
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Direct Instantiation
- **Pros**: No changes required
- **Cons**: Tight coupling, hard to test
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Service Locator Pattern
- **Pros**: Minimal code changes
- **Cons**: Hidden dependencies, hard to track
- **Decision**: Rejected - dependency injection is more explicit

### Alternative 3: Use Framework-Level DI Container
- **Pros**: Automatic dependency resolution
- **Cons**: Over-engineering, adds dependency
- **Decision**: Rejected - simpler solution available

## References
- ADR-0012: Reduce tight coupling in chat_agent.py
- Current implementation in `chat_agent.py`
- Dependency injection best practices
