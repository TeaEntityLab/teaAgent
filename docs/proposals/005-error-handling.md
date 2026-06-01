# Proposal: Standardize Error Handling Across Modules

## Executive Summary
This proposal outlines a plan to create a standardized error handling framework with consistent error types, context, and recovery hints across all modules.

## Problem Statement

### Current State
Different modules handle errors inconsistently:
- `errors.py` defines error categories and custom exceptions with hints
- `approval_manager.py` raises `ToolPermissionError` directly without context
- `runner/_core.py` catches broad exception types and re-wraps them

The error handling patterns are not standardized. Some modules use specific error types, others use generic exceptions. Error context and recovery hints are not consistently provided.

### Impact
- **Inconsistent Patterns**: Different modules use different error handling patterns
- **Missing Context**: Error messages often lack context
- **No Recovery Hints**: No guidance on how to recover from errors
- **Hard to Debug**: Inconsistent error handling makes debugging difficult

## Proposed Solution

### Phase 1: Create ErrorContext Class
1. **Create Class**: Create `ErrorContext` class to capture error metadata
2. **Add Fields**: Add fields for error classification, severity, and recovery hints
3. **Add Tests**: Add unit tests for error context
4. **Update Error-Raising**: Update error-raising code to use ErrorContext

### Phase 2: Implement ErrorHandler Interface
1. **Create Interface**: Create `ErrorHandler` protocol/interface
2. **Implement Handler**: Implement default error handler with logging and recovery
3. **Add Tests**: Add unit tests for error handling
4. **Update Modules**: Update all modules to use the error handler

### Phase 3: Create Error Factory Methods
1. **Create Factories**: Create factory methods for common error scenarios
2. **Add Methods**: Add methods for tool errors, permission errors, validation errors
3. **Add Tests**: Add unit tests for error factories
4. **Update Code**: Update all error-raising code to use factories

### Phase 4: Standardize Error Recovery Hints
1. **Define Hints**: Define standard recovery hint categories
2. **Add Hints**: Add recovery hints to all error types
3. **Create Documentation**: Create documentation for error handling patterns
4. **Update Messages**: Update error messages to include recovery hints

### Phase 5: Add Error Classification
1. **Define Levels**: Define error severity levels (critical, high, medium, low)
2. **Add Classification**: Add error classification to all error types
3. **Create Metrics**: Create error metrics and monitoring
4. **Update Handling**: Update error handling to respect severity

## Implementation Details

### ErrorContext Class
```python
# errors/context.py
from dataclasses import dataclass
from typing import Any
from enum import Enum

class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

class ErrorCategory(Enum):
    """Error categories."""
    TOOL = 'tool'
    PERMISSION = 'permission'
    VALIDATION = 'validation'
    BACKEND = 'backend'
    CONFIGURATION = 'configuration'
    NETWORK = 'network'

@dataclass
class ErrorContext:
    """Context for error reporting."""
    
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    error: Exception | None = None
    category: ErrorCategory = ErrorCategory.TOOL
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    recovery_hint: str | None = None
    additional_context: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tool_name': self.tool_name,
            'arguments': self.arguments,
            'error': str(self.error) if self.error else None,
            'category': self.category.value,
            'severity': self.severity.value,
            'recovery_hint': self.recovery_hint,
            'additional_context': self.additional_context,
        }
```

### ErrorHandler Interface
```python
# errors/handler.py
from typing import Protocol
from teaagent.errors.context import ErrorContext

class ErrorHandler(Protocol):
    """Protocol for error handlers."""
    
    def handle(self, context: ErrorContext) -> None:
        """Handle error with given context."""
        ...

class DefaultErrorHandler:
    """Default error handler with logging and recovery."""
    
    def __init__(self):
        """Initialize default error handler."""
        import logging
        self._logger = logging.getLogger(__name__)
    
    def handle(self, context: ErrorContext) -> None:
        """Handle error with logging."""
        error_message = f'Error in {context.tool_name or "unknown"}'
        if context.recovery_hint:
            error_message += f'. Recovery: {context.recovery_hint}'
        
        if context.severity == ErrorSeverity.CRITICAL:
            self._logger.critical(error_message, exc_info=context.error)
        elif context.severity == ErrorSeverity.HIGH:
            self._logger.error(error_message, exc_info=context.error)
        elif context.severity == ErrorSeverity.MEDIUM:
            self._logger.warning(error_message, exc_info=context.error)
        else:
            self._logger.info(error_message, exc_info=context.error)
```

### Error Factory Methods
```python
# errors/factory.py
from teaagent.errors.context import ErrorContext, ErrorCategory, ErrorSeverity
from teaagent.errors.exceptions import (
    ToolPermissionError,
    ToolExecutionError,
    ValidationError,
    BackendError,
)

class ErrorFactory:
    """Factory for creating errors with context."""
    
    @staticmethod
    def tool_permission_error(
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
        recovery_hint: str | None = None,
    ) -> ToolPermissionError:
        """Create tool permission error with context."""
        context = ErrorContext(
            tool_name=tool_name,
            arguments=arguments,
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            recovery_hint=recovery_hint or 'Check permission mode or approve explicitly',
        )
        error = ToolPermissionError(reason)
        error.context = context
        return error
    
    @staticmethod
    def tool_execution_error(
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
        recovery_hint: str | None = None,
    ) -> ToolExecutionError:
        """Create tool execution error with context."""
        context = ErrorContext(
            tool_name=tool_name,
            arguments=arguments,
            category=ErrorCategory.TOOL,
            severity=ErrorSeverity.MEDIUM,
            recovery_hint=recovery_hint or 'Check tool arguments and try again',
        )
        error = ToolExecutionError(reason)
        error.context = context
        return error
    
    @staticmethod
    def validation_error(
        field: str,
        value: Any,
        reason: str,
        recovery_hint: str | None = None,
    ) -> ValidationError:
        """Create validation error with context."""
        context = ErrorContext(
            additional_context={'field': field, 'value': value},
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            recovery_hint=recovery_hint or 'Check input and provide valid value',
        )
        error = ValidationError(reason)
        error.context = context
        return error
    
    @staticmethod
    def backend_error(
        backend_name: str,
        reason: str,
        recovery_hint: str | None = None,
    ) -> BackendError:
        """Create backend error with context."""
        context = ErrorContext(
            tool_name=backend_name,
            category=ErrorCategory.BACKEND,
            severity=ErrorSeverity.HIGH,
            recovery_hint=recovery_hint or 'Check backend configuration and availability',
        )
        error = BackendError(reason)
        error.context = context
        return error
```

### Standard Error Recovery Hints
```python
# errors/recovery_hints.py

RECOVERY_HINTS = {
    'permission_denied': 'Check permission mode or approve explicitly with --approve-call-id',
    'file_not_found': 'Verify file path and ensure file exists in workspace',
    'invalid_syntax': 'Check syntax and correct formatting',
    'timeout': 'Increase timeout or check network connectivity',
    'backend_unavailable': 'Check backend configuration and restart if needed',
    'invalid_arguments': 'Review tool documentation and provide valid arguments',
    'workspace_not_initialized': 'Initialize workspace with git init or teaagent init',
    'quota_exceeded': 'Reduce context size or increase quota limit',
}
```

### Error Classification and Metrics
```python
# errors/metrics.py
from collections import defaultdict
from typing import Counter
from teaagent.errors.context import ErrorContext, ErrorCategory, ErrorSeverity

class ErrorMetrics:
    """Metrics for error tracking."""
    
    def __init__(self):
        """Initialize error metrics."""
        self._error_counts: Counter[ErrorCategory] = Counter()
        self._severity_counts: Counter[ErrorSeverity] = Counter()
        self._tool_errors: Counter[str] = Counter()
    
    def record_error(self, context: ErrorContext) -> None:
        """Record error in metrics."""
        self._error_counts[context.category] += 1
        self._severity_counts[context.severity] += 1
        if context.tool_name:
            self._tool_errors[context.tool_name] += 1
    
    def get_summary(self) -> dict[str, Any]:
        """Get error summary."""
        return {
            'by_category': dict(self._error_counts),
            'by_severity': dict(self._severity_counts),
            'by_tool': dict(self._tool_errors),
        }
```

## Migration Plan

### Step 1: Create ErrorContext
1. Create `ErrorContext` class
2. Add fields for metadata
3. Add unit tests for error context
4. Update error-raising code to use ErrorContext

### Step 2: Create ErrorHandler
1. Create `ErrorHandler` interface
2. Implement default error handler
3. Add unit tests for error handling
4. Update modules to use error handler

### Step 3: Create ErrorFactory
1. Create factory methods for common errors
2. Add unit tests for error factories
3. Update all error-raising code to use factories
4. Verify error context is included

### Step 4: Standardize Recovery Hints
1. Define standard recovery hint categories
2. Add recovery hints to all error types
3. Create documentation for error handling
4. Update error messages to include hints

### Step 5: Add Error Classification
1. Define error severity levels
2. Add error classification to all error types
3. Create error metrics and monitoring
4. Update error handling to respect severity

### Step 6: Update Tests
1. Update unit tests to use new error patterns
2. Add integration tests for error handling
3. Verify all tests pass
4. Update documentation

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep existing error types working
- Add deprecation warnings for old patterns
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for error handling
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for error rates

## Timeline

### Phase 1: Create ErrorContext (1 week)
- Week 1: Create class, add fields, add tests

### Phase 2: Create ErrorHandler (1 week)
- Week 2: Create interface, implement handler, add tests

### Phase 3: Create ErrorFactory (1 week)
- Week 3: Create factories, add tests, update code

### Phase 4: Standardize Recovery Hints (1 week)
- Week 4: Define hints, add to errors, create documentation

### Phase 5: Add Error Classification (1 week)
- Week 5: Define levels, add classification, create metrics

### Phase 6: Update Tests and Documentation (1 week)
- Week 6: Update tests, verify all tests pass, update documentation

## Success Criteria

- ✅ Consistent error handling across all modules
- ✅ All errors include context and recovery hints
- ✅ Error classification and metrics implemented
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Inconsistent Error Handling
- **Pros**: No changes required
- **Cons**: Technical debt, hard to debug
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use Third-Party Error Handling Library
- **Pros**: Off-the-shelf solution
- **Cons**: Adds dependency, may not fit needs
- **Decision**: Rejected - custom solution better suited

### Alternative 3: Use Exception Hierarchy Only
- **Pros**: Simple implementation
- **Cons**: Missing context and recovery hints
- **Decision**: Rejected - insufficient for needs

## References
- ADR-0014: Standardize error handling across modules
- Current implementation in `errors.py`, `approval_manager.py`, `runner/_core.py`
- Error handling best practices
