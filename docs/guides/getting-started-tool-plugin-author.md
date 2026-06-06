# Getting Started — Tool / Plugin Author

> **Last reviewed:** 2026-06-06
> **Persona:** Developer extending TeaAgent with tools or entry-point plugins

Extensions must pass **ToolRegistry governance**: schemas, annotations, approval
semantics, and audit compatibility.

## Quick tool (in-repo)

See [Tool Development](tool-development.md) and [Integration Guide § Tools](integration-guide.md).

Minimum contract:

- `input_schema` / `output_schema` — JSON Schema objects
- `annotations` — `read_only`, `destructive`, etc.
- Handler that raises clear errors (surfaced as `ToolExecutionError`)

```bash
python3 -m pytest tests/test_ws3_schema_path_containment.py -q
```

## Plugin package (entry point)

```toml
[project.entry-points."teaagent.tools"]
my_tools = "my_package.tools:register"
```

`load_plugins()` runs governance lint on newly registered tools. Invalid plugins
are rolled back and marked failed.

```python
from teaagent.integration import validate_plugin_tools
from teaagent.tools import ToolRegistry

registry = ToolRegistry()
# ... register tools ...
report = validate_plugin_tools(registry, tool_names=["my_tool"])
assert not report.blocked, report.to_dict()
```

## Governance checklist

| Requirement | Why |
| --- | --- |
| Object input/output schemas | Runner validation + MCP export |
| Correct `destructive` / `read_only` | ApprovalPolicy routing |
| Non-empty description | Operator transparency |
| Pass `lint_registry()` | Catches annotation contradictions |

## Integration contracts (WS5)

- Shared run setup: `teaagent.integration.prepare_agent_run`
- Storage adapters: `storage_bundle_for_workspace`
- Doc: [integration-contracts.md](../governance/integration-contracts.md)

## Examples

- [examples/plugin_skeleton/](examples/plugin_skeleton/)
- [tool-authoring.md](../tool-authoring.md)
