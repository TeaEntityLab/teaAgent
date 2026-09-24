---
feature: mcp-surface
source_commit: a91f1dc2
last_verified_at: 2026-09-24
verification_status: failed
known_findings: [F-1]
covers:
  - teaagent/mcp_server.py
  - teaagent/mcp_http/
  - teaagent/mcp_trust.py
  - teaagent/cli/_handlers/_mcp.py
  - teaagent/cli/_handlers/_mcp_trust.py
drive:
  - id: tests
    expect: MCP server/HTTP/trust/error-contract test set passes (~89 tests, ~25s)
    run: |
      cd "$REPO"
      "$P" -m pytest -q tests/test_mcp_server.py tests/test_mcp_http.py \
        tests/test_mcp_trust.py tests/test_dogfood_mcp_errors_g27_g35.py
  - id: stdio-protocol
    expect: initialize answers serverInfo teaagent; tools/list returns the same tool count as `tool list`; unknown tool is -32602; unknown method is -32601
    run: |
      printf '%s\n' \
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
        '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"no_such_tool","arguments":{}}}' \
        '{"jsonrpc":"2.0","id":4,"method":"nope"}' | "$T" mcp serve --root . > frames.jsonl 2> /dev/null
      "$P" - frames.jsonl "$("$T" tool list --root . | jget 'd["count"]')" <<'PY'
      import json, sys
      f = {x['id']: x for x in map(json.loads, open(sys.argv[1]))}
      assert f[1]['result']['serverInfo']['name'] == 'teaagent'
      assert len(f[2]['result']['tools']) == int(sys.argv[2])
      assert f[3]['error']['code'] == -32602
      assert f[4]['error']['code'] == -32601
      PY
  - id: http-auth-and-session
    expect: with --auth-token, POST /mcp without bearer is 401; initialize returns an Mcp-Session-Id header; a later request without it is 400
    run: |
      port=$((20000 + RANDOM % 20000))
      "$T" mcp serve --http --port "$port" --auth-token vtok --root . > server.log 2>&1 &
      pid=$!; trap 'kill $pid 2> /dev/null' EXIT
      for _ in $(seq 40); do curl -s -o /dev/null "http://127.0.0.1:$port/mcp" && break; sleep 0.25; done
      u="http://127.0.0.1:$port/mcp"; j='Content-Type: application/json'
      init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
      [ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$u" -H "$j" -d "$init")" = 401 ]
      curl -s -D headers.txt -o /dev/null -X POST "$u" -H 'Authorization: Bearer vtok' -H "$j" -d "$init"
      grep -qi '^mcp-session-id: ' headers.txt
      [ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$u" -H 'Authorization: Bearer vtok' -H "$j" -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')" = 400 ]
---

# MCP surface

`teaagent mcp serve` exposes the workspace tool pack
(`build_workspace_tool_registry`) to MCP clients over stdio JSON-RPC
(`serve_mcp_stdio`, `teaagent/mcp_server.py`) or Streamable HTTP
(`serve_mcp_http`, `teaagent/mcp_http/__init__.py`). `teaagent mcp trust`
manages the trust policy for *remote* MCP servers consumed by agent runs
(`teaagent/mcp_trust.py`).

## Entry points

| Surface | Command |
|---|---|
| stdio | `teaagent mcp serve --root .` (one JSON-RPC request per stdin line) |
| HTTP | `teaagent mcp serve --http --port 7330 --auth-token TOKEN --root .` → `POST/GET/DELETE /mcp` |
| Methods | `initialize`, `tools/list`, `tools/call` |
| Trust | `teaagent mcp trust …` |

## Observable outcomes (healthy product)

- Protocol errors are JSON-RPC error frames (-32601 unknown method, -32602 invalid params / unregistered tool, -32603 internal); the server keeps serving.
- HTTP: default bind 127.0.0.1; `--auth-token` enforces `Authorization: Bearer`; every request after `initialize` must echo `Mcp-Session-Id`.

## Known finding F-1 — `tools/call` is ungoverned (open, owner ruling required)

Observed at `a91f1dc2`, stdio and HTTP: `tools/call` for a destructive tool
(`workspace_write_file`) **executes immediately**. `_call_tool` calls
`registry.execute(name, arguments)` with no `ApprovalPolicy`, no permission
mode (`mcp serve` has no `--permission-mode` flag), and writes **no audit
event**. This contradicts:

- `AGENTS.md` Tool Governance: destructive tools must not run in
  `read-only`/`workspace-write`/`prompt` without an approval token, and direct
  `ToolRegistry.execute()` without policy context is unsupported.
- `AGENTS.md` Runtime Safety: every tool call must be audited.
- `docs/api/mcp-api.md` § Trust Model, which says the server applies approval
  policy, returns `-32001` on denial, and accepts `--permission-mode`.

`git log -S` finds no commit that ever added policy to `mcp_server.py`, so
this is not a regression from an earlier governed state. Oracle check
`A5-mcp-destructive-call-governed` in `verify/acceptance.yaml` is
`known_failing` on F-1. Do **not** add a drive item that asserts the current
ungoverned behavior; the owner decides between gating the server (product fix)
or rewriting the documented trust model (doc fix).

## Failure paths

| Symptom | Likely class |
|---|---|
| destructive `tools/call` executes | known finding F-1 (report as KNOWN, not new) |
| destructive `tools/call` now denied with -32001 | F-1 fixed → acceptance reports XPASS; update this file and F-1 status (doc drift) |
| `curl` connection refused on the HTTP item | harness: port collision or slow start; rerun |

## Evidence

`verify/checks/drive.sh mcp-surface`; `verify/checks/acceptance.sh` (A5 XFAIL).
