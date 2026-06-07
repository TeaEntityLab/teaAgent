# Tool Authoring Guide

All tools must be registered through `ToolRegistry`.

## Contract

Each tool requires:

- `name`: stable machine-readable identifier.
- `description`: concise behavior summary for model prompts and MCP metadata.
- `input_schema`: JSON-schema-like object schema.
- `output_schema`: JSON-schema-like object schema.
- `annotations`: `ToolAnnotations(read_only, destructive, idempotent, stateful)`.
- `handler`: pure Python callable accepting `dict[str, Any]` and returning JSON-serializable data.

## Minimal Example

```python
from teaagent.tools import ToolAnnotations, ToolRegistry

registry = ToolRegistry()
registry.register(
    name="example_uppercase",
    description="Uppercase one string.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    output_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    annotations=ToolAnnotations(read_only=True, idempotent=True),
    handler=lambda args: {"text": args["text"].upper()},
)
```

## Rules

- Mark any filesystem write, network mutation, shell mutation, or state change as `destructive=True`.
- Stateful tools that mutate process-local caches must set `stateful=True` and either `destructive=True` or `idempotent=True`; otherwise `tool_lint` emits `stateful_without_governance`.
- Keep tool errors actionable. Raise `ValueError` with a corrective message for model-correctable errors.
- Return only JSON-serializable values.
- Bound all external work with timeouts and byte limits.
- Do not read secrets unless the tool is explicitly designed for secret handling and redaction is reviewed.

## Tests

Add tests that cover:

- Valid input and output shape.
- Invalid input classification.
- Permission behavior when `destructive=True`.
- Audit redaction for sensitive arguments and results.

---

## Plugin Tutorial: Custom Plugin in 10 Minutes (DOC-004)

### 1. Scaffold

```bash
mkdir -p .teaagent/plugins/hello-plugin
```

### 2. `plugin.json`

```json
{"name": "hello-plugin", "version": "0.1.0", "commands": ["hello"]}
```

### 3. Command handler (`.teaagent/plugins/hello-plugin/commands.py`)

```python
def hello_command(args):
    print('Hello from plugin')
    return 0
```

### 4. Verify

```bash
teaagent plugin list
```

### Extension points

| Extension | Purpose |
|-----------|---------|
| Commands | CLI subcommands |
| Agents | Subagent YAML/JSON defs |
| Hooks | Pre/post run lifecycle |
| MCP | External tool servers |

See `docs/plugin-skill-catalog.md` for the full catalog.
