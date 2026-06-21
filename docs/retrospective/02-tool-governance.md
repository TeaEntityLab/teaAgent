# 02 - Tool Capability & Governance Audit

> Dimension priority: **Second** | Method: cx overview / cx symbols + Read/Grep across 14+ modules and every tool registration point

## Capability Inventory (Capability | Module:Line | Maturity)

| Capability | Module:Line | Maturity | Notes |
| --- | --- | --- | --- |
| ToolRegistry registration/lookup/execution | `teaagent/tools.py:114-340` | Stable | Lookup cache <=256; `unregister` governance |
| ToolAnnotations (read_only/destructive/idempotent/stateful/security_tier) | `teaagent/tools.py:22-30` | Stable | Low/Medium/High/Critical tiers |
| ToolRateLimit (sliding window) | `teaagent/tools.py:33-48,85-111` | Stable | Per-tool, thread-safe |
| Schema validation (JSON subset) | `teaagent/schema.py:7-63` | **Beta** | Only type/properties/required; no `enum/pattern/$ref/oneOf` |
| Pre/post-tool hooks (8 events) | `teaagent/hooks.py:30-495` | Stable | Pre-hooks may veto/mutate; post-hooks may mutate results; destructive argument mutation is blocked |
| BackendRegistry (lifecycle) | `teaagent/backend_registry.py:17-123` | Stable | initialize/shutdown/check_health |
| Plugin system (entry points + manifests) | `teaagent/plugin_system.py:1-475` | Stable | RSK-10 source audit; governance rollback |
| Plugin tool governance | `teaagent/integration/plugin_governance.py:42-93` | Stable | Blocks missing schema/description or destructive+read_only |
| Tool lint (AST handler checks) | `teaagent/governance/tool_lint.py:200-323` | Stable | Flags mislabeled write/shell tools and tier mismatches |
| ApprovalBackend + 5 backends | `teaagent/approval/backend.py` | Stable | RO/WW/Prompt/Allow/Danger |
| ApprovalManager (composition) | `teaagent/approval/manager.py` | Stable | Nine-stage resolution |
| JIT approval (TTY + timeout) | `teaagent/approval/manager.py` | Stable | 60-second default; o/s/d/e |
| Multi-sig quorum (SSH signatures) | `teaagent/approval/manager.py` | Beta | FederatedSync broadcast; dev-hash fallback requires environment configuration |
| Preapproved call_id / payload digest | `teaagent/approval/manager.py` | Stable | call_id is deprecated; payload_digest preferred |
| Centralized subagent approval queue | `teaagent/subagents/_approval_queue.py:122-896` | Stable | Async+sync; batch approve/deny; cross-process |
| Redis approval queue backend | `teaagent/subagents/_approval_queue_redis_store.py:1-956` | Beta | Sentinel/ACL/SSL/network allowlist |
| JIT SSE approval server | `teaagent/jit_approval_server.py:49-445` | Beta | Loopback without authentication; 180 seconds; Bearer |
| Permission modes (5) | `teaagent/approval/manager.py` | Stable | read-only/workspace-write/prompt/allow/danger |
| Error categories (5) + DenialReasonCode (11) | `teaagent/errors.py:9-37` | Stable | TRANSIENT/MODEL_LOGIC/PERMISSION/SYSTEM/CONFIG |
| RunBudget (iterations/tool calls/cost) | `teaagent/budget.py:34-108` | Stable | `validate()` enforces >=1/>=0; phase budgets |
| BudgetMonitor (50/80/90/100%) | `teaagent/budget_monitor.py:35-189` | Stable | Monitors cost only, not iterations/tool calls |
| ScopeBudget (files/commands/risk/spend/duration) | `teaagent/scope_budget.py:17-412` | Stable | `ScopeBudgetEnforcer` |
| Automation runtime + cost caps | `teaagent/automation_limits.py:41-72` | Stable | SIGTERM on runtime cap |
| ResourceMonitor (Docker CPU/memory) | `teaagent/resource_monitor.py:52-293` | Beta | Polls docker stats |
| Runner budget enforcement | `teaagent/runner/_core.py:213-294,957-1009` | Stable | Phase 3x/iteration; cost 2x/iteration |
| AuditLogger (append-only JSONL) | `teaagent/audit.py:398-540` | Stable | fsync/file_lock/hash chain/HMAC/compliance exception |
| Audit levels L0-L3 | `teaagent/audit.py:303-353` | Stable | L3 Fernet encryption |
| Audit chain verification | `teaagent/audit_chain.py:1-532` | Stable | SHA-256/Blake3; tamper detection |
| Audit health/tail/export/viewer | Dedicated modules | Stable | health/tail/export/viewer |
| **Audit event schema (published)** | `docs/audit-event.schema.json:5-14` | **Stub** | Only 5 required fields; **omits `prev_hash/hash/chain_hmac`** |
| EventSpine -> audit bridge | `teaagent/runner/_events.py:122-174,369-401` | Stable | Maps 30+ events; critical propagation |
| Skill loader (priority directories, 32 KB cap, maximum 20) | `teaagent/skill_loader.py:45-1050` | Stable | First wins; review-gated; provenance |
| Skill review (frontmatter/AST/blocklist) | `teaagent/skill_review.py:222-242` | Stable | max_skill_md_lines=80 (warning); REFERENCE.md reminder |
| Skill lifecycle (13 states + audit) | `teaagent/skill_lifecycle.py:14-234` | Stable | Transition events |
| Skill executor (wasm/docker/subprocess) | `teaagent/skill_executor.py:1-396` | Beta | Routes through SkillRouter |
| Skill candidate workflow (install/attest) | `teaagent/skill_candidates.py:1-26+` | Beta | provenance.json; scope; attestation |
| SubagentManager (depth-limited) | `teaagent/subagents/_manager.py:1-24+` | Stable | `MAX_CHILD_PERMISSION=WORKSPACE_WRITE` |
| Subagent isolation (5 modes) | `teaagent/subagents/_isolation.py:63-403` | Stable | Docker `--network none --cap-drop ALL --read-only --user 65534` |
| Subagent batch tool (8 workers, 300 seconds) | `teaagent/subagents/_tools.py:250-497` | Stable | ThreadPool; deadline timeout |
| SwarmManager (heartbeat timeout) | `teaagent/swarm.py:380-530,726-732` | Beta | lock_timeout=60 |
| TaskCoordinator (LLM routing) | `teaagent/coordinator.py` | Beta | TaskClassification + WorkflowPlan |
| AgentFactory (prompt evolution) | `teaagent/agent_factory.py` | Beta | LLM/heuristic + hot reload |
| MCP HTTP client (filtered) | `teaagent/mcp_client.py` | Stable | Allow/deny lists; sampling; OAuth |
| MCP server (JSON-RPC stdio) | `teaagent/mcp_server.py` | Stable | `PROTOCOL_VERSION='2024-11-05'` |
| MCP tool adapter | `teaagent/mcp_tool_adapter.py:84-158` | Stable | Infers annotations; fixed output envelope |
| MCP trust policy (TTL, Fernet) | `teaagent/mcp_trust.py:186-229,318-388` | Stable | Dynamic pre-hook rereads policy on every call |
| MemoryCatalog (AbstractStore) | `teaagent/memory/catalog.py:1-62+` | Stable | add/search/delete; quarantine; TTL |
| Intent clarification (heuristic) | `teaagent/intent.py:70-185` | Beta | Five-dimensional score; threshold >0.4 |
| ChatAgent run pipeline | `teaagent/chat_agent.py:606-683` | Stable | usage_reader is the authoritative budget source |
| Externalized stores | run_store/plan_storage/session/checkpoint | Stable | JSONL+SQLite; atomic; file_lock |

## Strengths

1. **Strong ToolRegistry contract**: `tools.py:129-178` enforces five fields at registration; plugin governance and tool lint add multiple validation layers; 50+ registered tools comply.
2. **Layered approval pipeline**: backend -> path containment -> skill protection -> JIT -> preset -> scoped -> payload digest -> multi-sig -> prompt; every denial path includes a `DenialReasonCode` and an actionable hint.
3. **Layered audit + hash chain + redaction + compliance mode**: L0-L3 levels; Fernet encryption at rest; `AuditDurabilityError` is raised in compliance mode.
4. **Dense budget enforcement**: phase budgets are checked 3x/iteration, cost 2x/iteration, with hard iteration/tool-call limits; `usage_reader` supplies the authoritative total instead of trusting a mutable context key (SEC-05).
5. **Serious subagent isolation**: Docker uses `--network none --cap-drop ALL --read-only --security-opt no-new-privileges --user 65534:65534`; secret files are skipped; `directory-snapshot` explicitly states that it provides no OS isolation.
6. **Skills treated as supply-chain assets**: the loader skips skills that fail review; review checks frontmatter, line count, external references, blocklists, and AST; lifecycle records every transition as an audit event; candidates require provenance and attestation.
7. **MCP trust is evaluated at call time, not load time**: the dynamic pre-hook in `mcp_trust.py:186-229` rereads policy on every call; default TTL is 24 hours; policy is encrypted at rest with Fernet.
8. **Actionable error model**: `AgentHarnessError.hint`; `format_denial_message` generates specific remediation based on `reason_code`.

## Gaps

| ID | Severity | Summary | Evidence |
| --- | --- | --- | --- |
| G-1 | **High** | The published audit-event schema is incomplete: it requires only 5 fields and sets `additionalProperties:false`, while AuditLogger writes `prev_hash/hash/chain_hmac`; external compliance consumers validating against the schema will reject every chained event | `docs/audit-event.schema.json:5-13`; `teaagent/audit.py:473-477` |
| G-3 | **High** | The schema validator supports only a small JSON subset and does not support `enum/pattern/format/$ref/oneOf/anyOf/additionalProperties`; several tools declare schemas stricter than the validator enforces (for example, `subagent_batch` items) | `teaagent/schema.py:7-14`; `teaagent/subagents/_tools.py:398-414` |
| G-4 | Medium | `register_github_tools` defines four tools, but `_setup_tool_registry` never calls it automatically, so `github_create_pr` and related tools are unreachable in a standard run | `teaagent/github_integration.py:154`; `teaagent/chat_agent.py:500-535` |
| G-5 | Medium | `directory-snapshot` isolation is a first-class mode but provides no OS isolation; it only logs a warning, and the runner still permits it for untrusted content | `teaagent/subagents/_isolation.py:287-298` |
| G-6 | Medium | Multi-sig quorum silently falls back when `agent_id` is missing; it only calls `print()` and emits no audit event for the fallback | `teaagent/approval_manager.py:449-454` |
| G-7 | Medium | `preapproved_call_ids` is deprecated but remains functional; maintaining it alongside payload_digest increases the approval surface | `teaagent/policy.py:115-121`; `teaagent/approval_manager.py:953-968` |
| G-8 | Medium | `BudgetMonitor` monitors only cost, not iterations/tool calls, so it gives no warning as those hard limits approach | `teaagent/budget_monitor.py:74-106`; `teaagent/runner/_core.py:957,1008` |
| G-9 | Medium | The L3 audit encryption key is stored beside logs under `~/.teaagent/audit-encryption/`; this protects against copied logs but not host compromise | `teaagent/audit.py:319-321` |
| G-10 | Low | `scope_key` is not an audit concept; audit payloads use a `scope` field with values such as `call_id`/`payload_digest`, without a unified taxonomy | `teaagent/runner/_core.py:730,742` |
| G-11 | Low | `cx symbols --kind fn` without `--file` returned an error; cross-file symbol enumeration required falling back to Grep | cx v0.7.1 |
| G-12 | Low | Once the tool lookup cache reaches its 256-entry limit, new lookups are no longer cached | `teaagent/tools.py:194` |
| G-13 | Low | Skill review treats `max_skill_md_lines=80` as a warning rather than an error, so overlong skills still load | `teaagent/skill_review.py:187-193` |

> **Review correction (former G-2):** `.agents/skills` is an ignored local symlink to `/Users/teee/.agents/skills`, not a Git-tracked TeaAgent asset. Its contents cannot be used as evidence of project noncompliance. The stable G-2 identifier is intentionally retired rather than reassigned.

## AGENTS.md Rule Compliance

| Rule | Assessment | Evidence |
| --- | --- | --- |
| Tools registered through ToolRegistry | Compliant | Every registration uses `registry.register(...)`; plugins use `plugin_system.py:466` |
| All five fields present | Compliant | Enforced by `tools.py:129-141`; plugin governance blocks omissions; 50+ tools comply |
| Destructive tools require an exact-call token | **Violated** | Normal paths bind the call ID or tool-and-argument digest, but `AutoModeManager` escalates allowlisted tools to `DANGER_FULL_ACCESS` and bypasses the exact-call requirement (G1 in [01](01-security-risk.md)). |
| Tool errors are actionable and classified | Compliant | 5 `ErrorCategory` classes; 11 `DenialReasonCode` values; `hint` field; `format_denial_message` |
| Every run has iteration and tool-call limits | Compliant | `RunBudget(max_iterations=25, max_tool_calls=25)`; enforced by the runner; clamped for subagents |
| Every tool call and final result is audited | **Partial** | CLI paths record the required events (`runner/_core.py:789,824,877,508,916`), but `chat_agent.py:755` can fall back to an in-memory `AuditLogger()` with no durable trail (G4 in [01](01-security-risk.md)). |
| Harness remains thin | **Partial** | The runner remains orchestration-focused, but domain reasoning and the 4,771-line approval-queue implementation have leaked into the harness (see [03](03-architecture-quality.md), G-CRIT-1 and G-HIGH-1). |
| Prefer protocol assets; no second framework without an ADR | Compliant (with note) | MCP/Skills/Run records are complete; `agent_factory`/`coordinator`/`swarm` are exposed through ToolRegistry as tools rather than parallel frameworks |
| SKILL.md is short and uses REFERENCE.md | **Compliant** | The Git-tracked `.opencode/skill/*` files are all at most 73 lines, and `teaagent/skills/builtin/rss-summary/` is 62 lines with `REFERENCE.md` and examples. The ignored `.agents/skills` symlink is outside project scope. |

## Recommendations

### P0
- **P0-1 (fix G-1)**: Update `docs/audit-event.schema.json` to include optional `prev_hash`/`hash`/`chain_hmac` properties, or split it into a "logical event schema" and a "persisted chain entry schema." Otherwise, external compliance consumers following the current schema will reject every line written by AuditLogger.

### P1
- **P1-2 (fix G-3)**: Extend `teaagent/schema.py` to support `enum/pattern/additionalProperties/oneOf/anyOf`, closing the gap between declared and enforced contracts.
- **P1-3 (fix G-4)**: Decide whether `register_github_tools` should load automatically or be explicitly opt-in; currently four defined tools are unreachable in a standard run. Add `config.enable_github_tools` following `enable_git_tools:106`, or remove the lazy export.
- **P1-4 (fix G-6)**: When multi-sig falls back because `agent_id` is missing, emit a `multisig_fallback` audit event so misconfigured sessions can be detected after the fact.

### P2
- **P2-1 (fix G-5)**: Gate use of `directory-snapshot` for untrusted content behind an `--acknowledge-no-os-isolation` flag instead of only logging a warning.
- **P2-2 (fix G-7)**: Remove `preapproved_call_ids` after the deprecation window and standardize on payload-digest-scoped approvals.
- **P2-3 (fix G-8)**: Add iteration and tool-call monitoring alongside `BudgetMonitor` so users receive warnings before a hard `BudgetExceededError`.
- **P2-4 (fix G-10)**: Document the `scope` field taxonomy (`call_id` / `payload_digest` / `session` / `preset`) for `tool_call_approved` events.
- **P2-5 (fix G-13)**: Treat `max_skill_md_lines` violations as errors for installed skills with candidate provenance, while retaining warnings for skills under development.
