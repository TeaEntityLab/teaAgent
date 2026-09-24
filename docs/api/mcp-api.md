# MCP Server API Specification

**Protocol version:** `2024-11-05`  
**Transports:** stdio JSON-RPC 2.0 (one request per line) · Streamable HTTP (`--http`)  
**Entry point:** `teaagent mcp serve`  
**Source:** `teaagent/mcp_server.py`, `teaagent/mcp_http/__init__.py`, `teaagent/tools.py`

Every statement below is exercised by `verify/features/mcp-surface.md` or
`tests/test_mcp_server.py` / `tests/test_mcp_http.py`.

---

## Starting the server

```bash
teaagent mcp serve --root /path/to/project                          # stdio
teaagent mcp serve --http --port 7330 --auth-token "$TOKEN" --root .  # Streamable HTTP
```

stdio reads requests from stdin and writes responses to stdout. HTTP details
(`POST/GET/DELETE /mcp`, `Mcp-Session-Id`, bearer/OAuth auth, loopback default)
are in [docs/cli.md § MCP Server](../cli.md#mcp-server).

| Flag | Meaning |
|---|---|
| `--root` | Workspace served and governed (default `.`) |
| `--permission-mode` | `read-only`, `prompt`, `allow`, `danger-full-access` (default: workspace config, else `prompt`). `workspace-write` is refused (exit 2): it depends on a bound plan, which MCP clients cannot provide |
| `--approve-scoped TOOL:SHA256` | Preapprove one exact call by payload digest (repeatable); digest = `teaagent.policy.compute_scoped_payload_digest(tool_name, arguments)` |

---

## Methods

| Method | Result |
|---|---|
| `initialize` | `{"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "teaagent", "version": "0.1.0"}}` |
| `tools/list` | `{"tools": [{"name", "description", "inputSchema", "annotations"}]}` |
| `tools/call` | `{"content": [{"type": "text", "text": "<JSON result>"}], "isError": false}` |

Requests without an `id` (notifications) get no response. Any other method is
`-32601`. The server exposes no resources.

`annotations` in `tools/list`:

```json
{"readOnlyHint": true, "destructiveHint": false, "idempotentHint": true, "statefulHint": false}
```

These describe the local tool pack. The server's own approval decision uses
the registry's annotations, never client-supplied hints.

### Errors

| Condition | Frame |
|---|---|
| Unknown method | JSON-RPC error `-32601` |
| `tools/call` without string `name` / object `arguments`, or unregistered tool | JSON-RPC error `-32602` |
| Denied by the approval policy (see Trust Model) | JSON-RPC error `-32001`, message names the rule |
| Tool raised (validation failure, missing file, rate limit from `ToolRateLimit`) | result with `isError: true` and the error text |
| Unexpected failure inside one request | JSON-RPC error `-32603`; the server keeps serving |

---

## Trust Model

Every `tools/call` passes the workspace `ApprovalPolicy` before
`ToolRegistry.execute()`, the same policy `teaagent run` uses (AGENTS.md Tool
Governance). There is no interactive prompt over MCP (stdio owns the terminal
streams; HTTP has no operator), so a destructive tool runs only when:

1. `--permission-mode allow` or `danger-full-access`, **or**
2. an approval preset in `.teaagent/approvals.json` allows it (`teaagent approval grant …`), **or**
3. its payload digest matches an `--approve-scoped` value.

A matching deny preset (`teaagent approval deny …`) blocks the call in every mode, including `allow`.

`read-only` blocks every destructive tool. `prompt` without a matching preset
or digest denies with `-32001`. `--approve-call-id` does not exist here and is
inert elsewhere. JSON-RPC request ids are client-chosen and never grant approval.

### Audit

Each server process writes one hash-chained run log,
`.teaagent/runs/mcp-<hex>.jsonl` (`origin: mcp`): `run_started` at startup,
then per call `tool_call_requested` followed by `tool_call_blocked`, or by
`tool_call_started` and `tool_call_completed` / `tool_call_failed`;
`run_completed` on clean shutdown. Tool arguments and results are redacted
like any run log. Verify with `teaagent audit verify mcp-<hex> --root . --ci`.

Library callers construct the same binding explicitly:

```python
from teaagent import MCPGovernance, PermissionMode, handle_mcp_request

governance = MCPGovernance.for_workspace(
    root, permission_mode=PermissionMode.PROMPT, transport='embedded'
)
response = handle_mcp_request(registry, request, governance=governance)
governance.close()
```

---

## Consuming remote MCP servers

`teaagent mcp trust {list,inspect,allow,deny,revoke,audit}` manages the trust
policy for **remote** MCP servers whose tools an agent run consumes; it does
not affect this server.

```bash
teaagent mcp trust allow --tools search fetch --server my-server --root .
teaagent mcp trust inspect --server my-server --root .
```
