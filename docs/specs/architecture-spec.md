# TeaAgent Architecture Specifications

## Overview
This document describes the architectural specifications for the TeaAgent codebase, including system architecture, component interactions, and design principles.

## System Architecture

### Core Components

#### 1. Chat Agent
- **Purpose**: Main agent orchestration and task execution
- **Dependencies**: CodeAnalysis, WorkspaceTools, SubagentManager, HookRegistry, MemoryCatalog
- **Interface**: `ChatAgentConfig`, `run_chat_agent()`
- **Current State**: High coupling to backend systems

#### 2. Approval System
- **Purpose**: Permission management and approval workflow
- **Components**: ApprovalManager, ApprovalPolicy, ApprovalStore
- **Current State**: Circular dependencies, God class issue

#### 3. Workspace Tools
- **Purpose**: File operations and shell command execution
- **Components**: File tools, Shell tools, Git tools
- **Security**: Safe command parsing, environment filtering

#### 4. Backend Systems
- **Knowledge Search**: Knowledge backends for context retrieval
- **Code Parse**: Code analysis backends for structure extraction
- **Current State**: Global state, no abstraction layer

#### 5. Error Handling
- **Purpose**: Consistent error handling across modules
- **Components**: Error types, error handlers, error recovery
- **Current State**: Inconsistent patterns across modules

#### 6. Configuration
- **Purpose**: Configuration management and loading
- **Components**: ConfigLoader, configuration sources
- **Current State**: Hard-coded configuration keys

## Design Principles

### 1. Separation of Concerns
- Each component should have a single responsibility
- Components should be loosely coupled
- Dependencies should be explicit, not implicit

### 2. Dependency Injection
- Components should receive dependencies via constructor parameters
- Avoid direct instantiation of dependencies
- Use factories for complex object creation

### 3. Interface-Based Design
- Use protocols/interfaces for component contracts
- Implement adapters for external systems
- Standardize interfaces across similar components

### 4. Error Handling Consistency
- Use specific exception types for different error categories
- Include error context and recovery hints
- Standardize error handling patterns

### 5. Configuration Extensibility
- Support dynamic configuration key registration
- Allow plugins to add their own configuration
- Use schema validation for configuration

## Component Interactions

### Chat Agent Flow
```
User Input → ChatAgentConfig → run_chat_agent()
    ↓
CodeAnalysisConfig → LSPServerManager → SubagentManager
    ↓
WorkspaceToolConfig → ToolRegistry → Tool Execution
    ↓
HookRegistry → Audit Logging → Result
```

### Approval Flow
```
Tool Call → ApprovalManager → PermissionModeEnforcer
    ↓
JITApprovalManager → ApprovalStore → MultiSigQuorumManager
    ↓
ApprovalPolicy → Decision → Allow/Deny
```

### Backend System Flow
```
Backend Request → BackendRegistry → BackendAdapter
    ↓
BackendFactory → Backend Instance → Result
    ↓
BackendHealthCheck → Health Status → Monitoring
```

## Data Flow

### 1. Task Execution Flow
```
Task → Intent Clarification → Plan Generation
    ↓
Tool Execution → Approval → Tool Result
    ↓
Context Update → Memory Catalog → Audit Log
```

### 2. File Operation Flow
```
File Request → Path Validation → Symlink Check
    ↓
Permission Check → File Operation → Atomic Write
    ↓
Audit Log → Result Return
```

### 3. Error Handling Flow
```
Error Occurs → ErrorContext Capture → ErrorHandler
    ↓
Error Classification → Recovery Hint → Logging
    ↓
Error Propagation → User Notification
```

## Security Architecture

### 1. Command Execution Security
- Safe parsing with `shlex.split()`
- Environment variable allowlist
- Destructive command blocking

### 2. File System Security
- Path traversal prevention
- Symlink validation
- Atomic file operations
- mtime validation

### 3. Cryptographic Security
- Secure random generation with `secrets` module
- Strong token hashing with PBKDF2
- Salted hashing for new tokens

### 4. Information Security
- Sensitive data redaction
- Audit trail integrity
- Secure secret storage

## Performance Considerations

### 1. Caching
- Memory catalog caching for context retrieval
- Knowledge backend caching
- LSP server state caching

### 2. Async Operations
- Subagent execution in parallel
- Backend system async calls
- Non-blocking I/O operations

### 3. Resource Management
- Connection pooling for backend systems
- Thread pool for signature operations
- Memory limits for large files

## Scalability

### 1. Horizontal Scaling
- Subagent parallelization
- Backend system clustering
- Distributed audit storage

### 2. Vertical Scaling
- Resource limits per run
- Memory limits for large contexts
- Timeout configurations

## Reliability

### 1. Error Recovery
- Retry logic with exponential backoff
- Graceful degradation on backend failures
- Audit trail for debugging

### 2. State Management
- Externalized state (audit log, memory catalog)
- State snapshots for resumption
- State validation on load

### 3. Monitoring
- Health checks for backend systems
- Metrics for performance monitoring
- Alerting for critical failures

## References
- ADR-001 through ADR-008 for detailed refactoring plans
- Component-specific documentation in respective modules
- Architecture decision records in docs/adr/
