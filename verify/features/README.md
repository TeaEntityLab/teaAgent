# Feature map index

Each feature file starts with YAML front matter read by `verify/checks/*.sh`:

| Key | Meaning |
|---|---|
| `feature` | file stem |
| `source_commit` | product commit the file was last verified against |
| `last_verified_at` | UTC date of that verification |
| `verification_status` | `passed` · `failed` (requires `known_findings`) · `unverified` |
| `known_findings` | open finding ids below that this feature exposes |
| `covers` | product paths whose change makes the file stale |
| `drive` | list of `{id, expect, run}`; `run` is bash executed in a fresh scratch workspace after `source verify/checks/lib.sh; enter_scratch` |

| Feature | Status | Drive items |
|---|---|---|
| [governed-tool-execution](governed-tool-execution.md) | passed | tests, tool-contracts, read-only-blocks-write, prompt-pauses-unapproved-write, scoped-digest-exactness, approve-and-resume, presets-deny-beats-allow, plan-gate |
| [run-lifecycle](run-lifecycle.md) | passed | tests, offline-run-completes, iteration-cap, tool-call-cap, runs-list-and-replay, undo-restores |
| [audit-evidence](audit-evidence.md) | passed | tests, lifecycle-events-recorded, chain-verify-and-tamper, denial-explained |
| [mcp-surface](mcp-surface.md) | passed | tests, stdio-protocol, http-auth-and-session, destructive-call-governed, preset-digest-and-mode-authorize, workspace-write-refused |
| [operator-cli](operator-cli.md) | passed | tests, init-non-tty-requires-provider, init-fake, doctor-selftest, read-only-surfaces |

## Findings

None open. Resolved (G-P2-20, 2026-09-24; found by this map at `a91f1dc2`):

| Id | Severity | Finding | Fix | Guard |
|---|---|---|---|---|
| F-1 | high | `mcp serve` `tools/call` ran destructive tools with no `ApprovalPolicy`, no permission mode, and no audit event (stdio and HTTP), contradicting `AGENTS.md` Tool Governance and Runtime Safety. | `MCPGovernance` (policy + run log) is required by every MCP entry point; `--permission-mode`, `--approve-scoped`; `workspace-write` refused. Risk report `docs/reviews/mcp-server-governance-2026-09-24-risk.md` | oracle A5; mcp-surface drive items; `tests/test_mcp_server.py` |
| F-2 | medium | `h4_governance_shadow` receipts kept raw `content`/`command` arguments under `payload.context.arguments`. | `redact_audit_value` redacts any nested `arguments` dict | oracle A6; `tests/test_audit.py::test_nested_tool_arguments_are_redacted_like_top_level` |
| F-3 | low | `approval approve <call_id> --resume` printed the inert `--approve-call-id` deprecation notice. | resume namespace passes `approve_call_id=[]` | governed-tool-execution `approve-and-resume` |
| F-4 | low | `CONTRIBUTING.md` installed a nonexistent `oauth` extra. | installs `.[dev]` | — |

A new finding gets the next id, a row here, and (when it breaks an oracle
invariant) `status: known_failing` + `finding:` on the oracle check until fixed.

## Not mapped (no drive coverage here)

TUI (`teaagent tui`), chat REPL, gateway (Telegram/Slack/Discord), cloud/background
runners, consensus/swarm/subagents, OAuth 2.1/DPoP for MCP HTTP, control-plane
server, memory/skills lifecycle, release evidence tooling, VS Code extension,
real LLM providers. Their tests exist under `tests/`; a green sweep says nothing
about them.
