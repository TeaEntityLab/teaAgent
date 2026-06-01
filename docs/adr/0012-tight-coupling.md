# ADR 0012: Reduce Tight Coupling in chat_agent.py

## Status
Proposed

## Context
The `ChatAgentConfig` and `run_chat_agent` function have direct dependencies on multiple backend systems:
- `CodeAnalysisConfig` (line 15-20)
- `LSPServerManager` (line 17)
- `SubagentManager` (line 54)
- `HookRegistry` (line 25)
- `MemoryCatalog` (line 31)
- `WorkspaceToolConfig` (line 56-60)

The `ChatAgentConfig.from_root()` method directly instantiates these components, creating tight coupling to implementation details and making the code difficult to test.

## Decision
We will introduce dependency injection and factory patterns to reduce coupling.

### Implementation Plan

#### Phase 1: Create ChatAgentConfigFactory
1. Create `ChatAgentConfigFactory` class to handle complex initialization
2. Move initialization logic from `ChatAgentConfig.from_root()` to the factory
3. Add unit tests for the factory
4. Update callers to use the factory

#### Phase 2: Introduce ConfigurationProvider Interface
1. Create `ConfigurationProvider` protocol/interface
2. Implement providers for different configuration sources
3. Add unit tests for each provider
4. Update `ChatAgentConfig` to use the interface

#### Phase 3: Create Backend Adapters
1. Create adapter interfaces for each backend system
2. Implement adapters for code analysis, workspace tools, etc.
3. Add unit tests for each adapter
4. Update `run_chat_agent` to use adapters

#### Phase 4: Use Dependency Injection
1. Refactor `run_chat_agent` to accept dependencies as parameters
2. Create a builder pattern for complex dependency graphs
3. Add integration tests for the new pattern
4. Update all callers to use dependency injection

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Reduced coupling, better testability, more flexible architecture
- **Negative**: Breaking changes to public APIs, requires migration effort
- **Risk**: Medium - affects chat agent initialization

## Alternatives Considered
1. Keep direct instantiation (rejected - tight coupling)
2. Use service locator pattern (rejected - hidden dependencies)
3. Use framework-level DI container (rejected - over-engineering)

## References
- Original issue: Medium-severity architecture issue #3
- Related files: `chat_agent.py`, `code_analysis/`, `workspace_tools/`
