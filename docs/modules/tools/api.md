# tools — Public API Reference

## `ToolAnnotations` (frozen dataclass)
```python
@dataclass(frozen=True)
class ToolAnnotations:
    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    stateful: bool = False
    security_tier: str = 'Medium'  # 'Low' | 'Medium' | 'High' | 'Critical'
```

## `ToolRateLimit` (frozen dataclass)
```python
@dataclass(frozen=True)
class ToolRateLimit:
    max_calls: int
    window_seconds: float = 60.0
```

## `ToolDefinition` (frozen dataclass)
```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]    # JSON Schema (type: object)
    output_schema: dict[str, Any]   # JSON Schema (not enforced at runtime)
    annotations: ToolAnnotations
    handler: ToolHandler            # Callable[[dict], dict]
    rate_limit: Optional[ToolRateLimit] = None
    capability_manifest: Optional[dict[str, Any]] = None

    def get_security_tier(self) -> str
    # Returns: 'Low' | 'Medium' | 'High' | 'Critical'
    # Priority: capability_manifest['security_tier'] > annotation derivation
```

## `ToolRegistry`

### `register`
```python
def register(
    self,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    handler: ToolHandler,
    *,
    annotations: ToolAnnotations = ToolAnnotations(),
    rate_limit: Optional[ToolRateLimit] = None,
    capability_manifest: Optional[dict[str, Any]] = None,
) -> None
```
- **Pre**: `name` must not already be registered.
- **Post**: Tool is callable via `call(name, arguments)`.

### `call`
```python
def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]
```
- **Pre**: Tool `name` registered; `arguments` must pass `input_schema` validation.
- **Post**: Returns handler result (possibly modified by post-hooks).
- **Raises**: `ToolExecutionError` (unknown tool, rate limit exceeded), `ToolValidationError` (schema mismatch), `HookError` (pre-hook veto).

### `get`
```python
def get(self, name: str) -> Optional[ToolDefinition]
```
Returns the `ToolDefinition` or `None`.

### `list_tools`
```python
def list_tools(self) -> list[ToolDefinition]
```
All registered tools.

### `attach_hooks`
```python
def attach_hooks(self, hook_registry: HookRegistry) -> None
```
Associates a `HookRegistry` with this tool registry. All subsequent `call()` invocations use the hooks.

---

## Type Alias

```python
ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]
```
