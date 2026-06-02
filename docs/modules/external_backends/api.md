# external_backends — Public API Reference

## Data Models

### `BackendConfig`
| Field | Type | Description |
|---|---|---|
| `root` | `Path` | Workspace root used by backend operations. |
| `timeout` | `int` | Timeout in seconds for backend calls. |
| `max_retries` | `int` | Retry budget for adapter operations. |
| `additional_config` | `dict[str, Any] | None` | Backend-specific optional configuration. |

### `BackendRegistry`
| Field | Type | Description |
|---|---|---|
| `_knowledge_backends` | `dict[str, Any]` | Registered knowledge adapters. |
| `_code_parse_backends` | `dict[str, Any]` | Registered code-parse adapters. |
| `_initialized` | `bool` | Lifecycle state after initialize/shutdown. |

## Functions

### `register_knowledge_backend(name: str, backend: KnowledgeSearchBackend) -> None`
**Location**: `teaagent/external_backends.py:106`
**Pre-condition**: Non-empty name and protocol-compatible backend.
**Post-condition**: Registers backend in default registry under `name`.

### `get_knowledge_backend(name: str) -> KnowledgeSearchBackend`
**Location**: `teaagent/external_backends.py:110`
**Pre-condition**: Backend has been registered.
**Post-condition**: Returns backend or raises `ValueError` if unknown.

### `register_code_parse_backend(name: str, backend: CodeParseBackend) -> None`
**Location**: `teaagent/external_backends.py:114`
**Pre-condition**: Non-empty name and protocol-compatible backend.
**Post-condition**: Registers code-parse backend in default registry.

### `get_code_parse_backend(name: str) -> CodeParseBackend`
**Location**: `teaagent/external_backends.py:118`
**Pre-condition**: Backend has been registered.
**Post-condition**: Returns backend or raises `ValueError` if unknown.

### `get_default_backend_registry() -> BackendRegistry`
**Location**: `teaagent/backend_registry.py:116`
**Pre-condition**: None.
**Post-condition**: Returns process-global lifecycle-aware backend registry.
