# Risk Report — govern and audit `mcp serve` `tools/call`; redact nested tool arguments

**Date:** 2026-09-24 · **Action:** G-P2-20 (verification-map findings F-1, F-2)
**High-risk paths touched:** `teaagent/audit.py` (redaction). Governance-sensitive, not on the list: `teaagent/mcp_server.py`, `teaagent/mcp_http/__init__.py`, `teaagent/cli/_handlers/_mcp.py`, `teaagent/cli/_mcp_parsers.py`, `teaagent/integration/run_contract.py`.

## Goal

Close two gaps the verification map recorded as `known_failing` oracles:

- **F-1** `teaagent mcp serve` executed any registered tool, including
  `workspace_write_file` / `workspace_run_shell`, straight through
  `ToolRegistry.execute()` with no `ApprovalPolicy`, no permission mode, and no
  audit event (stdio and HTTP). `git log -S` shows it was never governed.
- **F-2** `h4_governance_shadow` receipts stored raw `content` / `command`
  tool arguments under `payload.context.arguments`; `redact_audit_payload`
  only redacted a top-level `arguments` key.

## Authority / ruling

F-1 had two candidate fixes: gate the server, or rewrite
`docs/api/mcp-api.md` to describe an ungoverned server. The second violates
`AGENTS.md` Tool Governance ("side effects … must route through a governed
path so `ApprovalPolicy` runs before `ToolRegistry.execute()`; direct
`ToolRegistry.execute()` without policy context is unsupported") and Runtime
Safety ("every tool call … recorded in the audit log"). The repo's own
operating rules therefore decide it: gate the server. No owner-discretion
choice is being made on the owner's behalf.

## What changes

- `MCPGovernance` (`teaagent/mcp_server.py`) binds one server process to the
  workspace `ApprovalPolicy` (built by the shared `build_approval_policy`, same
  presets / multisig / workspace containment as `teaagent run`) and a
  hash-chained run log `.teaagent/runs/mcp-<hex>.jsonl`.
  `handle_mcp_request`, `serve_mcp_stdio`, `build_mcp_http_server`,
  `serve_mcp_http` now **require** `governance=`; no ungoverned entry point remains.
- `tools/call`: `tool_call_requested` → `ApprovalPolicy.assert_allowed` →
  `tool_call_blocked` + JSON-RPC `-32001`, or `tool_call_started` → execute →
  `tool_call_completed` / `tool_call_failed`.
- JIT prompting is disabled (`RunSetupRequest.enable_jit_prompt=False`): stdio
  owns the terminal streams and HTTP has no operator.
- `mcp serve --permission-mode` (default workspace config, else `prompt`) and
  `--approve-scoped TOOL:SHA256`. `workspace-write` is refused with exit 2: on
  `run` it is safe only because PLAN_GATE binds a plan; MCP clients cannot
  bind one, so the mode would mean "write anything".
- `redact_audit_value` applies tool-argument redaction to any nested
  `arguments` dict; the top-level special case in `redact_audit_payload`
  folds into it (same output).

## Threat model / failure modes

| Threat | Before | After |
|---|---|---|
| Any MCP client (IDE, browser page allowed by `--allowed-origin`, compromised local process on loopback) writes files / runs shell | executes | denied unless mode/preset/digest authorizes |
| Client forges JSON-RPC id to reuse an approval | n/a | ids only correlate audit events; approval binds payload digest, presets, or mode |
| Client hints (`destructiveHint`) lie | n/a (client hints never consulted) | unchanged: server uses registry annotations |
| MCP tool effects invisible to audit / undo review | yes | every call in a chained run log |
| Audit log leaks file bodies / shell commands via shadow receipts | yes | redacted |

Failure modes introduced: an MCP client that previously wrote files now gets
`-32001` (intended, fail-closed); operators opt in via `--permission-mode
allow` or narrow presets. A workspace whose config default is
`workspace-write` must pass `--permission-mode` explicitly for `mcp serve`.
The VS Code extension launches `mcp serve --http` without a mode, so its
destructive calls are denied until presets or `allow` are configured.

## Sink inventory

Workspace files and shell (fronted by `ApprovalPolicy`); audit log (redacted);
no new outbound, credential, memory, or permission sinks.

## Dry-run / verification

- `tests/test_mcp_server.py`: prompt and read-only deny + audit + no file;
  preset allows only the matching path; allow mode records the full lifecycle
  and the chain verifies; CLI refuses `workspace-write`.
- `tests/test_audit.py::test_nested_tool_arguments_are_redacted_like_top_level`
  fails on the previous `audit.py` and passes now.
- `verify/acceptance.yaml` A5/A6 flip from `known_failing` to `expected_pass`.

## Rollback

Revert the commit. The `governance=` parameter removal restores the old
signatures; nothing is migrated on disk (run logs are append-only files).

## Human review

Public API change (`handle_mcp_request` & co. now require `governance=`) and
an intentional behavior change for MCP clients. Flagged in CHANGELOG.

## Go / No-go

Go: the change moves an unsupported, ungoverned side-effect path under the
existing policy engine without widening any authority.
