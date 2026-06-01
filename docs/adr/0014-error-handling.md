# ADR 0014: Standardize Error Handling Across Modules

## Status
Proposed

## Context
Different modules handle errors inconsistently:
- `errors.py` defines error categories and custom exceptions with hints
- `approval_manager.py` raises `ToolPermissionError` directly without context
- `runner/_core.py` catches broad exception types and re-wraps them

The error handling patterns are not standardized. Some modules use specific error types, others use generic exceptions. Error context and recovery hints are not consistently provided.

## Decision
We will create a standardized error handling framework with consistent error types, context, and recovery hints.

### Implementation Plan

#### Phase 1: Create ErrorContext Class
1. Create `ErrorContext` class to capture error metadata (tool name, arguments, state)
2. Add fields for error classification, severity, and recovery hints
3. Add unit tests for error context
4. Update error-raising code to use ErrorContext

#### Phase 2: Implement ErrorHandler Interface
1. Create `ErrorHandler` protocol/interface for consistent error processing
2. Implement default error handler with logging and recovery
3. Add unit tests for error handling
4. Update all modules to use the error handler

#### Phase 3: Create Error Factory Methods
1. Create factory methods for common error scenarios
2. Add methods for tool errors, permission errors, validation errors
3. Add unit tests for error factories
4. Update all error-raising code to use factories

#### Phase 4: Standardize Error Recovery Hints
1. Define standard recovery hint categories
2. Add recovery hints to all error types
3. Create documentation for error handling patterns
4. Update error messages to include recovery hints

#### Phase 5: Add Error Classification
1. Define error severity levels (critical, high, medium, low)
2. Add error classification to all error types
3. Create error metrics and monitoring
4. Update error handling to respect severity

### Risk Mitigation
- Maintain backward compatibility during transition
- Add comprehensive tests before refactoring
- Use feature flags to enable new implementation gradually
- Create migration guide for breaking changes

## Consequences
- **Positive**: Consistent error handling, better debugging, improved recovery
- **Negative**: Breaking changes to error handling APIs
- **Risk**: Medium - affects error handling across all modules

## Alternatives Considered
1. Keep inconsistent error handling (rejected - technical debt)
2. Use third-party error handling library (rejected - adds dependency)
3. Use exception hierarchy only (rejected - missing context)

## References
- Original issue: Medium-severity architecture issue #5
- Related files: `errors.py`, `approval_manager.py`, `runner/_core.py`
