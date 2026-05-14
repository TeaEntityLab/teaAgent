# Acceptance Coverage

TeaAgent acceptance tests live under `tests/acceptance/` and verify user-facing
workflows rather than isolated primitives.  Integration tests live under
`tests/integration/` and verify cross-component interactions.

Run acceptance tests:

```bash
python3 -m pytest tests/acceptance
```

Run integration tests:

```bash
python3 -m pytest tests/integration
```

---

## Acceptance Flows (tests/acceptance/)

### Original Flows

| File | Story | Key assertions |
|---|---|---|
| `test_daily_cli.py` | Daily CLI read-only workflow | `agent preflight`, `agent run`, `agent show`, audit persistence, run-level audit summary |
| `test_daily_tui.py` | Daily TUI workflow | chat mode, memory injection, progress streaming, agent answer persistence in session history |
| `test_mcp_client_flow.py` | MCP client compatibility | bearer auth, session lifecycle, `tools/list`, `tools/call`, session close |
| `test_a2a_federation_flow.py` | A2A federation | remote discovery, partial endpoint failure, capability routing, delegation, context forwarding, agent trace metadata |
| `test_managed_runtime_flow.py` | Managed runtime | tool metadata context construction, workspace/request context forwarding, persisted managed task audit events, result trace metadata |
| `test_ultrawork_flow.py` | Long-running worker | background worker start, list, show, log tail, and stop lifecycle |
| `test_workspace_edit_flow.py` | Workspace edit | hash-anchored read/edit, git status, test command execution, git diff inspection, final diff summary |
| `test_live_provider_conformance_flow.py` | Live provider conformance | provider checks skipped unless explicit env gate set, preventing accidental live API calls in CI |
| `test_model_smoke_gating_flow.py` | Hosted-provider smoke | `model smoke --live-env-var` skips live adapter calls unless CI explicitly sets the gate |

### New Flows — Added in this Sprint

#### Cost & Token Tracking

**File:** `test_cost_tracking_flow.py`

**Story (AC-NEW-7):** *As a user, I want to see live token usage and estimated
cost after a run so that I can track spending and tune my budget limits.*

| Assertion | Details |
|---|---|
| `RunResult.cost_cents >= 0.0` | Present on all terminal statuses |
| `RunResult.input_tokens` accumulated | Summed across all LLM calls in the run |
| `RunResult.output_tokens` accumulated | Summed across all LLM calls in the run |
| `run_completed` audit event carries cost fields | `cost_cents`, `input_tokens`, `output_tokens` |

---

#### Graceful Cancel

**File:** `test_cancel_flow.py`

**Story (AC-NEW-5):** *As a developer, I want to interrupt a running agent using
a cancel token so that long-running tasks can be stopped cleanly without
corrupting state.*

| Assertion | Details |
|---|---|
| `cancel_token.set()` stops the run | Status is `failed:system` |
| `run_started` still in audit log | No corruption on cancel |
| Cancel token set from a different thread | Thread-safe via `threading.Event` |
| Un-set cancel token runs normally | No performance penalty when not cancelled |
| `ChatAgentConfig.cancel_token` wired end-to-end | Flows from config → runner |

---

#### Remote MCP Tool Consumption

**File:** `test_remote_mcp_consumption_flow.py`

**Story (AC-NEW-9):** *As a platform engineer, I want to connect TeaAgent to a
remote MCP server and have its tools appear in the tool registry, with approval
rules applied uniformly.*

| Assertion | Details |
|---|---|
| All remote tools registered | Names match MCP `tools/list` response |
| Annotations inferred from MCP hints | `readOnlyHint`, `destructiveHint` |
| `name_prefix` filter works | Only matching tools are registered |
| `ToolRateLimit` applied uniformly | All remote tools share the same quota |
| Remote tool callable via `ToolRegistry.execute` | Proxied through `MCPHTTPClient` |

---

#### Skill Discovery and Injection

**File:** `test_skill_install_flow.py`

**Story (AC-NEW-10):** *As a platform engineer, I want to install skills into
`.opencode/skill/<name>/SKILL.md` and have them automatically injected into the
agent system prompt.*

| Assertion | Details |
|---|---|
| Skill content in system prompt | After `run_chat_agent` with skill installed |
| Multiple skills all present | All discovered skills injected |
| No `Skills:` section when empty | Clean prompt when no skills installed |
| Project skill overrides user skill | First-wins deduplication by name |
| Skill reaches `ModelDecisionEngine` system prompt | End-to-end via stub adapter assertion |

---

#### Policy-as-Code Deny Rules

**File:** `test_policy_as_code_flow.py`

**Story (AC-NEW-14):** *As a security lead, I want a `policy.yaml` deny-rule
that blocks specific tool calls regardless of permission mode.*

| Assertion | Details |
|---|---|
| `policy.yaml` loaded from workspace root | `load_file_policy(root)` finds it |
| Matching rule blocks the tool call | Runner status is `failed:*` |
| Non-matching tools not affected | Read-only tools pass through |
| Rules fire in `danger-full-access` mode | File policy is independent of `PermissionMode` |
| `argument_pattern` + `tool_pattern` combined | Glob matching on both axes |

---

#### Webhook Audit Event Delivery

**File:** `test_webhook_audit_flow.py`

**Story (AC-NEW-12):** *As a fleet operator, I want to subscribe to audit events
via webhook so my SIEM receives every important event in real time.*

| Assertion | Details |
|---|---|
| `run_started` and `run_completed` delivered | During a full `run_chat_agent` call |
| HMAC-SHA256 signature verifiable | `X-TeaAgent-Signature-256` header |
| Event filter restricts delivery | Only whitelisted `event_type` values sent |
| Webhook failure does not abort run | Unreachable endpoint silently ignored |

---

#### Error Remediation Hints

**File:** `test_error_remediation_flow.py`

**Story (AC-NEW-2):** *As a user with a misconfigured environment, I want error
messages to include actionable remediation hints.*

| Assertion | Details |
|---|---|
| `BudgetExceededError` has hint about limits | Default hint mentions `max_iterations` |
| `ToolPermissionError` has hint about mode | Default hint mentions `allow`/`permission` |
| `ToolExecutionError` has workspace hint | Default hint mentions workspace/command |
| `RunCancelledError` has resume hint | Default hint mentions `agent resume` |
| Hints appear in `str()` output | `→` separator injected by `__str__` |
| Custom hints override defaults | `hint=` kwarg takes precedence |

---

#### Audit Log Integrity

**File:** `test_audit_chain_integrity_flow.py`

**Story (AC-NEW-13):** *As a security lead, I want the audit JSONL log to be
verifiable so that tampering is detectable.*

| Assertion | Details |
|---|---|
| Every JSONL line is valid JSON | Parseable individually |
| Event IDs are unique within a run | No duplicates across events |
| Sensitive values redacted in persisted log | `content` argument not in raw file |
| Disk log matches in-memory events | Event types in same order |
| Audit files have restricted permissions | Not world-readable (mode ≤ 0o600) |

---

## Integration Tests (tests/integration/)

| File | Coverage |
|---|---|
| `test_runner_cost_tracking.py` | `RunResult` cost fields + audit event fields (IT-1) |
| `test_cancel_token.py` | Cancel token — pre-cancel, mid-run, thread-safe (IT-2) |
| `test_tool_rate_limit.py` | Sliding-window quota, concurrency safety, expiry (IT-3) |
| `test_mcp_tool_adapter.py` | `register_mcp_tools` discovery, annotations, filter (IT-4) |
| `test_skill_loader.py` | `load_skills` discovery, dedup, cap, prompt injection (IT-5) |
| `test_audit_sink_isolation.py` | Crashing sink does not propagate or block other sinks (IT-6) |
| `test_file_policy.py` | `DenyRule` matching, `FilePolicy.assert_allowed`, runner wiring (IT-7) |
| `test_webhook_sink.py` | HTTP delivery, HMAC, filter, failure suppression (IT-8) |
| `test_error_hints.py` | All error classes have default hints, `str()` rendering (IT-9) |
| `test_subagent_budget_inheritance.py` | Subagent depth limit, error dict, registry guard (IT-10) |
| `test_run_resume_checkpoint.py` | Checkpoint save on tool completion, pending-approval, SQLite round-trip, obs replay (IT-11) |
| `test_destructive_approval_lifecycle.py` | Pause → approve → resume; deny path; auto-approve handler; read-only block (IT-12) |
| `test_streaming_tool_calls.py` | `on_chunk` callbacks, audit events, token accumulation (IT-13) |
| `test_schema_migration_live.py` | Migration ordering, idempotency, data survival, version tracking (IT-14) |
| `test_dpop_replay_concurrency.py` | Concurrent JTI consume: exactly one success; expiry reset (IT-15) |

---

## Next User Stories

The following stories are specified and prioritised but do not yet have
acceptance tests.  Each maps to a Review gap analysis recommendation.

| ID | Story | Priority |
|---|---|---|
| AC-NEW-1 | `teaagent init` first-time wizard | P2 |
| AC-NEW-3 | Workspace profile (`.teaagent/profile.toml`) | P2 |
| AC-NEW-4 | Interactive diff preview + inline y/n approval | P0 |
| AC-NEW-6 | `teaagent run undo <run_id>` workspace rollback | P2 |
| AC-NEW-8 | Desktop/webhook notification on ultrawork completion | P2 |
| AC-NEW-11 | A2A delegation carries `traceparent` header | P1 |
| AC-NEW-15 | Configurable PII redaction categories | P2 |
| AC-NEW-16 | HTTPS_PROXY / CA bundle / mTLS "just works" | P2 |
| AC-NEW-17 | `teaagent upgrade` schema migration dry-run preview | P2 |
| AC-NEW-18 | Graceful degradation when disk fills mid-run | P2 |
| AC-NEW-19 | `teaagent run export / import` | P2 |
| AC-NEW-20 | Local model (Ollama/vLLM) with full governance | P2 |
| AC-NEW-21 | `teaagent eval run <suite>` with HTML report | P2 |
| AC-NEW-22 | `teaagent benchmark` latency/cost regression tracking | P2 |
