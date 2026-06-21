# TeaAgent API Specifications

## Overview
This document describes the API specifications for the TeaAgent codebase, including public interfaces, data structures, and usage patterns.

## Public APIs

### 1. Chat Agent API

#### ChatAgentConfig
```python
class ChatAgentConfig:
    """Configuration for chat agent execution."""
    
    @classmethod
    def from_root(cls, root: str | Path) -> ChatAgentConfig:
        """Create configuration from workspace root directory."""
        pass
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        pass
```

#### run_chat_agent
```python
def run_chat_agent(
    config: ChatAgentConfig,
    task: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    budget: int | None = None,
    permission_mode: str | None = None,
    approval_handler: ApprovalHandler | None = None,
) -> RunResult:
    """Run the chat agent with given configuration and task."""
    pass
```

### 2. Approval System API

#### ApprovalManager
```python
class ApprovalManager:
    """Manages approval workflow and permission enforcement."""
    
    def __init__(
        self,
        approval_store: ApprovalStore,
        permission_mode: PermissionMode,
        jit_approval_enabled: bool = False,
    ):
        """Initialize approval manager."""
        pass
    
    def check_approval(
        self,
        request: ApprovalRequest,
    ) -> tuple[bool, str | None]:
        """Check if request is approved."""
        pass
    
    def add_approval(
        self,
        request: ApprovalRequest,
        decision: bool,
    ) -> None:
        """Add approval decision."""
        pass
```

#### ApprovalPolicy
```python
class ApprovalPolicy:
    """Policy for approval decisions."""
    
    def __init__(
        self,
        approval_store: ApprovalStore,
        permission_mode: PermissionMode,
    ):
        """Initialize approval policy."""
        pass
    
    def is_destructive_allowed(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Check if destructive operation is allowed."""
        pass
```

### 3. Workspace Tools API

#### WorkspaceToolConfig
```python
class WorkspaceToolConfig:
    """Configuration for workspace tools."""
    
    @classmethod
    def from_root(cls, root: str | Path) -> WorkspaceToolConfig:
        """Create configuration from workspace root."""
        pass
    
    @property
    def root(self) -> Path:
        """Get workspace root directory."""
        pass
```

#### Tool Registry
```python
def build_workspace_tool_registry(
    root: str | Path,
) -> ToolRegistry:
    """Build tool registry for workspace operations."""
    pass
```

#### File Operations
```python
def read_file(
    config: WorkspaceToolConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Read file content."""
    pass

def write_file(
    config: WorkspaceToolConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Write file content atomically."""
    pass

def edit_at_hash(
    config: WorkspaceToolConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Edit file at specific line with hash validation."""
    pass
```

#### Shell Operations
```python
def run_shell(
    config: WorkspaceToolConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Run shell command safely."""
    pass

def run_shell_argv(
    config: WorkspaceToolConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Run shell command with argv."""
    pass
```

### 4. Backend Systems API

#### Backend Registry
```python
class BackendRegistry:
    """Registry for backend systems."""
    
    def register_knowledge_backend(
        self,
        name: str,
        backend: KnowledgeSearchBackend,
    ) -> None:
        """Register knowledge backend."""
        pass
    
    def register_code_parse_backend(
        self,
        name: str,
        backend: CodeParseBackend,
    ) -> None:
        """Register code parse backend."""
        pass
    
    def get_knowledge_backend(
        self,
        name: str,
    ) -> KnowledgeSearchBackend | None:
        """Get knowledge backend by name."""
        pass
    
    def get_code_parse_backend(
        self,
        name: str,
    ) -> CodeParseBackend | None:
        """Get code parse backend by name."""
        pass
```

#### Backend Interfaces
```python
class KnowledgeSearchBackend(Protocol):
    """Interface for knowledge search backends."""
    
    def search(
        self,
        query: str,
        root: Path,
    ) -> list[dict[str, Any]]:
        """Search knowledge base."""
        pass

class CodeParseBackend(Protocol):
    """Interface for code parse backends."""
    
    def parse(
        self,
        path: Path,
        root: Path,
    ) -> dict[str, Any]:
        """Parse code structure."""
        pass
```

### 5. Error Handling API

#### Error Types
```python
class ToolPermissionError(Exception):
    """Raised when tool operation is not permitted."""
    pass

class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass

class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass

class BackendError(Exception):
    """Raised when backend operation fails."""
    pass
```

#### Error Context
```python
class ErrorContext:
    """Context for error reporting."""
    
    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        error: Exception,
        severity: str,
        recovery_hint: str | None = None,
    ):
        """Initialize error context."""
        pass
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        pass
```

### 6. Configuration API

#### ConfigurationLoader
```python
class ConfigurationLoader:
    """Load configuration from various sources."""
    
    def load_from_file(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """Load configuration from file."""
        pass
    
    def load_from_env(
        self,
        prefix: str = 'TEAAGENT_',
    ) -> dict[str, Any]:
        """Load configuration from environment variables."""
        pass
    
    def load_from_args(
        self,
        args: argparse.Namespace,
    ) -> dict[str, Any]:
        """Load configuration from command-line arguments."""
        pass
```

#### Configuration Schema
```python
class ConfigurationSchema:
    """Schema for configuration validation."""
    
    def register_key(
        self,
        key: str,
        type_: type,
        default: Any,
        required: bool = False,
        validator: Callable[[Any], bool] | None = None,
    ) -> None:
        """Register configuration key."""
        pass
    
    def validate(
        self,
        config: dict[str, Any],
    ) -> bool:
        """Validate configuration against schema."""
        pass
```

## Data Structures

### ApprovalRequest
```python
@dataclass
class ApprovalRequest:
    """Request for approval."""
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    content_digest: str | None = None
    destructive: bool = False
```

### RunResult
```python
@dataclass
class RunResult:
    """Result of agent execution."""
    run_id: str
    status: str
    iterations: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    error: str | None = None
```

### ToolResult
```python
@dataclass
class ToolResult:
    """Result of tool execution."""
    ok: bool
    result: Any
    error: str | None = None
```

## Usage Patterns

### 1. Running Chat Agent
```python
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent

config = ChatAgentConfig.from_root('/path/to/workspace')
result = run_chat_agent(
    config,
    task='Fix the bug in main.py',
    provider='openai',
    model='gpt-4',
    permission_mode='prompt',
)
```

### 2. Using Workspace Tools
```python
from teaagent.workspace_tools._files import (
    build_workspace_tool_registry,
    WorkspaceToolConfig,
)

config = WorkspaceToolConfig.from_root('/path/to/workspace')
registry = build_workspace_tool_registry('/path/to/workspace')

result = registry.invoke(
    'workspace_read_file',
    {'path': 'main.py'},
)
```

### 3. Managing Approvals
```python
from teaagent.approval import ApprovalManager
from teaagent.policy import ApprovalStore, PermissionMode

store = ApprovalStore('/path/to/workspace')
manager = ApprovalManager(
    store,
    PermissionMode.PROMPT,
)

approved, reason = manager.check_approval(request)
```

### 4. Using Backend Systems
```python
from teaagent.external_backends import (
    register_knowledge_backend,
    get_knowledge_backend,
)

# Register custom backend
register_knowledge_backend('my_backend', MyBackend())

# Use backend
backend = get_knowledge_backend('my_backend')
results = backend.search('query', Path('/path/to/workspace'))
```

## Error Handling Patterns

### 1. Tool Execution Errors
```python
try:
    result = registry.invoke('workspace_read_file', {'path': 'file.txt'})
except ToolPermissionError as e:
    logger.error(f'Permission denied: {e}')
except ToolExecutionError as e:
    logger.error(f'Execution failed: {e}')
```

### 2. Configuration Errors
```python
try:
    config = ChatAgentConfig.from_root('/path/to/workspace')
except ConfigurationError as e:
    logger.error(f'Invalid configuration: {e}')
```

### 3. Backend Errors
```python
try:
    results = backend.search('query', root)
except BackendError as e:
    logger.error(f'Backend error: {e}')
```

## Versioning

### API Versioning
- Major version changes indicate breaking changes
- Minor version changes indicate new features
- Patch version changes indicate bug fixes

### Deprecation Policy
- Deprecated APIs will be marked with `@deprecated` decorator
- Deprecated APIs will be removed in the next major version
- Migration guides will be provided for breaking changes

## References
- Component-specific API documentation
- Type hints in source code
- Example usage in test files
