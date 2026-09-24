---
feature: mcp-surface
source_commit: ba6009df
last_verified_at: 2026-09-24
verification_status: passed
covers:
  - teaagent/mcp_server.py
  - teaagent/mcp_http/
  - teaagent/mcp_trust.py
  - teaagent/cli/_handlers/_mcp.py
  - teaagent/cli/_handlers/_mcp_trust.py
  - teaagent/cli/_mcp_parsers.py
  - teaagent/integration/run_contract.py
drive:
  - id: tests
    expect: MCP server/HTTP/trust/error-contract/governance test set passes (~93 tests, ~25s)
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
  - id: destructive-call-governed
    expect: "default (prompt) mode denies an unapproved write with -32001 and writes nothing; the run log .teaagent/runs/mcp-*.jsonl records tool_call_requested then tool_call_blocked, ends with run_completed, and its chain verifies"
    run: |
      printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"workspace_write_file","arguments":{"path":"mcp.txt","content":"y"}}}' \
        | "$T" mcp serve --root . > frame.json 2> /dev/null
      jget 'd["error"]["code"]' < frame.json | grep -qx -- -32001
      [ ! -e mcp.txt ]
      log=$(ls .teaagent/runs/mcp-*.jsonl)
      "$P" -c 'import json,sys; print([json.loads(l)["event_type"] for l in open(sys.argv[1])])' "$log" \
        | grep -qx "\['run_started', 'tool_call_requested', 'tool_call_blocked', 'run_completed'\]"
      "$T" audit verify "$(basename "$log" .jsonl)" --root . --ci | jget 'd["status"]' | grep -qx valid
  - id: preset-digest-and-mode-authorize
    expect: "a `approval grant` preset allows writes under its glob only; an --approve-scoped digest allows its exact call; --permission-mode allow runs the write; read-only denies"
    run: |
      call() { printf '{"jsonrpc":"2.0","id":%s,"method":"tools/call","params":{"name":"workspace_write_file","arguments":{"path":"%s","content":"y","create_dirs":true}}}\n' "$1" "$2"; }
      "$T" approval grant workspace_write_file --path-glob 'ok/**' --scope session --root . > /dev/null
      { call 1 ok/a.txt; call 2 b.txt; } | "$T" mcp serve --root . > frames.jsonl 2> /dev/null
      [ -e ok/a.txt ] && [ ! -e b.txt ]
      digest=$("$P" -c "from teaagent.policy import compute_scoped_payload_digest as c; print(c('workspace_write_file', {'path': 'b.txt', 'content': 'y', 'create_dirs': True}))")
      call 3 b.txt | "$T" mcp serve --root . --approve-scoped "workspace_write_file:$digest" > /dev/null 2>&1
      [ -e b.txt ]
      call 4 c.txt | "$T" mcp serve --root . --permission-mode read-only > frame.json 2> /dev/null
      jget 'd["error"]["code"]' < frame.json | grep -qx -- -32001; [ ! -e c.txt ]
      call 5 c.txt | "$T" mcp serve --root . --permission-mode allow > /dev/null 2>&1
      [ -e c.txt ]
  - id: workspace-write-refused
    expect: "`mcp serve --permission-mode workspace-write` exits 2 before serving (the mode depends on a bound plan MCP cannot provide) and opens no run log"
    run: |
      rc=0; echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | "$T" mcp serve --root . --permission-mode workspace-write > out.txt 2> err.txt || rc=$?
      [ "$rc" = 2 ]; grep -q 'workspace-write' err.txt
      ! ls .teaagent/runs/mcp-*.jsonl > /dev/null 2>&1
---

# MCP surface

`teaagent mcp serve` exposes the workspace tool pack
(`build_workspace_tool_registry`) to MCP clients over stdio JSON-RPC
(`serve_mcp_stdio`, `teaagent/mcp_server.py`) or Streamable HTTP
(`serve_mcp_http`, `teaagent/mcp_http/__init__.py`). Every `tools/call` goes
through `MCPGovernance` (workspace `ApprovalPolicy` + run log).
`teaagent mcp trust` manages the trust policy for *remote* MCP servers
consumed by agent runs (`teaagent/mcp_trust.py`). Contract:
`docs/api/mcp-api.md`.

## Entry points

| Surface | Command / symbol |
|---|---|
| stdio | `teaagent mcp serve --root .` (one JSON-RPC request per stdin line) |
| HTTP | `teaagent mcp serve --http --port 7330 --auth-token TOKEN --root .` → `POST/GET/DELETE /mcp` |
| Governance flags | `--permission-mode {read-only,prompt,allow,danger-full-access}` (default: workspace config, else prompt), `--approve-scoped TOOL:SHA256` |
| Library | `MCPGovernance.for_workspace(root, permission_mode=…, transport=…)`; `handle_mcp_request(registry, request, governance=…)` |
| Methods | `initialize`, `tools/list`, `tools/call` |
| Trust (remote servers) | `teaagent mcp trust {list,inspect,allow,deny,revoke,audit}` |

## Observable outcomes (healthy product)

- Protocol errors are JSON-RPC error frames (-32601 unknown method, -32602 invalid params / unregistered tool, -32603 internal); the server keeps serving.
- A destructive `tools/call` runs only under `allow`/`danger-full-access`, a matching approval preset, or a matching `--approve-scoped` digest; otherwise `-32001`. A deny preset wins in every mode. No interactive prompt exists over MCP.
- Each server process writes one chained run log `.teaagent/runs/mcp-<hex>.jsonl` (`origin: mcp`); arguments and results are redacted.
- HTTP: default bind 127.0.0.1; `--auth-token` enforces `Authorization: Bearer`; every request after `initialize` must echo `Mcp-Session-Id`.

## Failure paths

| Symptom | Likely class |
|---|---|
| destructive `tools/call` executes without mode/preset/digest | product regression (AGENTS.md Tool Governance; oracle A5) |
| a `tools/call` leaves no `tool_call_*` event in the mcp run log | product regression (AGENTS.md Runtime Safety) |
| `curl` connection refused on the HTTP item | harness: port collision or slow start; rerun |
| `mcp serve` exits 2 in a workspace whose config default is `workspace-write` | healthy: pass `--permission-mode` explicitly |

## History

F-1 (2026-09-24, `a91f1dc2`): `tools/call` ran destructive tools with no
policy and no audit. Fixed under G-P2-20; risk report
`docs/reviews/mcp-server-governance-2026-09-24-risk.md`.

## Evidence

`verify/checks/drive.sh mcp-surface`; `verify/checks/acceptance.sh` (A5).
