# ADR-007: Add Dependency Injection for Tool Registration

## Status
Proposed

## Context
Tool registration uses lambda functions that capture configuration in closures, making it difficult to test and creating implicit dependencies:
```python
handler=lambda args: read_file(config, args),
```

This pattern is repeated throughout the file. The configuration is embedded in the handler closure, making it impossible to change configuration at runtime or inject test doubles.

## Decision
We will create a `ToolFactory` class that handles tool creation with proper dependency injection.

### Implementation Plan

#### Phase 1: Create ToolFactory Class
1. Create `ToolFactory` class to handle tool creation
2. Move tool registration logic from lambdas to factory methods
3. Add unit tests for the factory
4. Update tool registration to use the factory

#### Phase 2: Implement ToolConfigProvider Interface
1. Create `ToolConfigProvider` protocol for runtime configuration
2. Implement providers for different configuration sources
3. Add unit tests for each provider
4. Update tools to use the interface

#### Phase 3: Use Partial Functions or Tool Classes
1. Replace lambdas with `functools.partial` or tool classes
2. Create tool classes for complex tools
3. Add unit tests for each tool class
4. Update tool registration to use partials/classes

#### Phase 4: Create ToolBuilder Pattern
1. Create `ToolBuilder` pattern for complex tool initialization
2. Implement builders for tools with complex dependencies
3. Add unit tests for each builder
4. Update tool registration to use builders

#### Phase 5: Support Tool Configuration Updates
1. Add methods to update tool configuration without re-registration
2. Add unit tests for configuration updates
3. Update tools to support dynamic configuration
4. Update documentation for tool configuration

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Better testability, dynamic configuration, cleaner code
- **Negative**: Breaking changes to tool registration API
- **Risk**: Medium - affects tool registration system

## Alternatives Considered
1. Keep lambda closures (rejected - hard to test, implicit dependencies)
2. Use class-based tools only (rejected - adds boilerplate)
3. Use framework-level DI container (rejected - over-engineering)

## References
- Original issue: Medium-severity architecture issue #7
- Related files: `workspace_tools/_files.py`
