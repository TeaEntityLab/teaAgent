---
type: guide
audience: developer
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# Tool Development Guide

How to build safe, auditable tools for TeaAgent.

All tools must be registered through `ToolRegistry`. The registry enforces schema validation,
annotation governance, and audit redaction at every call site. Nothing executes outside it.

**Related docs:**
- [Tool authoring quick-reference](../tool-authoring.md) — contract summary
- [Integration guide](integration-guide.md) — registering tools and packaging plugins
- [Approval policy design](approval-policy-design.md) — when your tool needs approval

---

## Core Contract

Every tool requires five fields and a handler:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Stable machine-readable identifier (snake_case) |
| `description` | `str` | Concise behaviour summary — shown to the model and in MCP metadata |
| `input_schema` | `dict` | JSON Schema object describing accepted arguments |
| `output_schema` | `dict` | JSON Schema object describing the returned structure |
| `annotations` | `ToolAnnotations` | Safety flags (see below) |
| `handler` | `Callable[[dict], Any]` | Pure Python callable; must return JSON-serialisable data |

### ToolAnnotations

```python
from teaagent.tools import ToolAnnotations

@dataclass(frozen=True)
class ToolAnnotations:
    read_only: bool = False      # No writes of any kind (filesystem, network, state)
    destructive: bool = False    # Writes or mutations — requires approval token
    idempotent: bool = False     # Same input → same output; safe to retry
    stateful: bool = False       # Mutates process-local caches or in-memory state
```

**Governance rules** (enforced by `tool_lint`):

- `destructive=True` → approval token required before execution (default policy)
- `stateful=True` and not `destructive=True` and not `idempotent=True` → `stateful_without_governance` lint error
- A tool cannot be both `read_only=True` and `destructive=True`

---

## Minimal Example: Read-Only Tool

```python
from teaagent.tools import ToolAnnotations, ToolRegistry

registry = ToolRegistry()

registry.register(
    name="get_env_var",
    description="Read a single environment variable by name. Returns empty string if unset.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Environment variable name"},
        },
        "required": ["name"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "set": {"type": "boolean"},
        },
        "required": ["value", "set"],
    },
    annotations=ToolAnnotations(read_only=True, idempotent=True),
    handler=lambda args: {
        "value": __import__("os").environ.get(args["name"], ""),
        "set": args["name"] in __import__("os").environ,
    },
)
```

---

## Minimal Example: Destructive Tool

```python
import os
from teaagent.tools import ToolAnnotations, ToolRegistry

registry = ToolRegistry()

def _write_config(args: dict) -> dict:
    path = args["path"]
    content = args["content"]

    # Validate path is within expected boundaries
    if ".." in path or path.startswith("/"):
        raise ValueError(f"Path '{path}' must be a relative path within the workspace")
    if len(content) > 1_000_000:
        raise ValueError("content exceeds 1 MB limit")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"written": len(content)}

registry.register(
    name="write_config_file",
    description="Write a configuration file. Requires approval for destructive operations.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path within workspace"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
    output_schema={
        "type": "object",
        "properties": {"written": {"type": "integer"}},
        "required": ["written"],
    },
    annotations=ToolAnnotations(destructive=True, idempotent=False),
    handler=_write_config,
)
```

---

## Error Handling

### Model-correctable errors → `ValueError`

Raise `ValueError` with a corrective message when the model provided invalid input
and can retry with better arguments:

```python
def handler(args: dict) -> dict:
    if not args["sql"].strip().upper().startswith("SELECT"):
        raise ValueError(
            "Only SELECT statements are allowed. "
            "Rewrite your query to use SELECT."
        )
    # ... execute
```

The runner surfaces `ValueError` text back to the model as a tool error observation.

### Non-recoverable errors → standard exceptions

For infrastructure failures (network down, file system error), raise a standard
exception. The runner will log it to the audit trail and treat the tool call as failed.

### Timeouts and byte limits

Always bound external work:

```python
import httpx

def handler(args: dict) -> dict:
    resp = httpx.get(args["url"], timeout=10)
    resp.raise_for_status()
    body = resp.text[:100_000]   # cap at 100 KB
    return {"body": body}
```

---

## Output Requirements

- **JSON-serialisable only.** `datetime`, `Path`, custom objects — convert them to strings/dicts.
- **No secrets in output.** Audit logs capture tool outputs. The audit module redacts
  known patterns (`Bearer …`, `sk-…`, JWTs, AWS access keys) but you should not rely on this
  as the primary guard.
- **Match the declared `output_schema`.** Schema validation runs after every call.

---

## Sensitive Arguments and Audit Redaction

The audit system automatically redacts values matching these key names:
`api_key`, `authorization`, `credential`, `password`, `secret`, `token`
and argument keys: `command`, `content`, `new`, `old`.

For additional redaction, use `RedactionConfig`:

```python
from teaagent.redaction import RedactionConfig

config = RedactionConfig(
    extra_keys={"private_key", "ssn"},
    extra_patterns=[r"\b[0-9]{9}\b"],  # SSN pattern
)
```

Pass the config to `AuditLogger` at construction time.

---

## Stateful Tools

Tools that mutate process-local caches must declare `stateful=True` and either
`destructive=True` (requires approval) or `idempotent=True` (no approval needed but retries are safe):

```python
_cache: dict = {}

def _cache_set(args: dict) -> dict:
    _cache[args["key"]] = args["value"]
    return {"ok": True}

registry.register(
    name="cache_set",
    description="Set a key in the in-process cache.",
    input_schema={...},
    output_schema={...},
    annotations=ToolAnnotations(stateful=True, destructive=True),
    handler=_cache_set,
)
```

---

## Rate Limiting

For tools that call external APIs, declare a `ToolRateLimit` to prevent budget overruns:

```python
from teaagent.tools import ToolRateLimit

registry.register(
    name="send_email",
    # ...
    rate_limit=ToolRateLimit(calls_per_minute=10, burst=3),
)
```

---

## MCP Metadata

`ToolRegistry.mcp_metadata()` returns the full tool list in MCP-compatible format.
The server (`teaagent mcp serve`) exposes this automatically.

To inspect registered tools:

```python
for meta in registry.mcp_metadata():
    print(meta["name"], "-", meta["description"])
```

---

## Testing Your Tool

Minimum test coverage:

```python
import pytest
from teaagent.tools import ToolRegistry, ToolAnnotations
from teaagent.errors import ToolPermissionError

@pytest.fixture
def registry():
    r = ToolRegistry()
    r.register(
        name="my_tool",
        description="...",
        input_schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]},
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: {"result": args["x"].upper()},
    )
    return r

def test_valid_input(registry):
    result = registry.call("my_tool", {"x": "hello"})
    assert result == {"result": "HELLO"}

def test_invalid_input_raises(registry):
    with pytest.raises(Exception):   # schema validation error
        registry.call("my_tool", {})  # missing required "x"

def test_destructive_requires_approval(registry):
    # Register a destructive version and verify it raises without a token
    registry.register(
        name="destructive_tool",
        description="...",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {},
    )
    with pytest.raises(ToolPermissionError):
        registry.call("destructive_tool", {})  # no approval token
```

---

## Checklist Before Shipping

- [ ] `name` is stable snake_case (renaming breaks recorded runs)
- [ ] `description` accurately describes what the tool **does** (not what it is)
- [ ] `input_schema` uses `required` for all mandatory fields
- [ ] `output_schema` matches what `handler` actually returns
- [ ] `destructive=True` for any filesystem write, network mutation, or shell command
- [ ] `ValueError` raised with corrective text for model-correctable errors
- [ ] External calls are bounded by timeouts and byte caps
- [ ] No raw secrets in output fields
- [ ] Tests cover: valid input, invalid input, permission behavior, audit redaction

---

## See Also

- [Examples — custom tool](examples/custom_tool.py)
- [Plugin development](integration-guide.md#4-plugin-development) — packaging as an entry-point plugin
- [Approval policy design](approval-policy-design.md) — when and how destructive tools get approved
