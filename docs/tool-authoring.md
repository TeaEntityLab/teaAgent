# Tool Authoring Guide

All tools must be registered through `ToolRegistry`.

## Contract

Each tool requires:

- `name`: stable machine-readable identifier.
- `description`: concise behavior summary for model prompts and MCP metadata.
- `input_schema`: JSON-schema-like object schema.
- `output_schema`: JSON-schema-like object schema.
- `annotations`: `ToolAnnotations(read_only, destructive, idempotent)`.
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
