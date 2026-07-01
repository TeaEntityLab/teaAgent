# 05 - AGENTS.md Rule Compliance Matrix

> **Last reviewed:** 2026-06-30 (targeted: ADR-0041 Phase 2 D4 thin-harness row; last full DR-003 refresh 2026-06-22).
> Rule-by-rule comparison of `AGENTS.md` against evidence from the four audit dimensions.
> Ratings: **Compliant / Partial / Violated**. Every row includes evidence as `file_path:line_number`.

## Architecture

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Keep the harness thin: orchestration, tool governance, state boundaries, audit, and validation belong here; domain reasoning belongs in the model or skills." | **Partial** | Governance spine is in-repo (`runner/_core.py`, `approval/`, `audit.py`). Domain reasoning remains in `teaagent/domain/` (**2,781 LOC** measured 2026-06-30: `issue_intake.py` 961, `workflow_engine.py` 768, `agent_factory.py` 436, `coordinator.py` 409, `intent.py` 207); `swarm.py` (~1,059 LOC) and the decomposed approval hybrid store (`subagents/_hybrid_store_*.py`) add product surface. **ADR-0041 Phase 2 (behavior-preserving thinning, increment 1)** relocated the LLM-path *prompt reasoning* out of Python into reviewed skill assets under `teaagent/skills/builtin/` (`task-classification/`, `agent-prompt-authoring/`), loaded via `teaagent/domain/_prompt_assets.py`, with byte-identity tests (`tests/test_prompt_assets.py`); the tested deterministic heuristics and their fallbacks deliberately stay in the harness (LLM-ifying them would regress behavior and fail gate D2), so measured LOC is roughly flat and the rating remains **Partial**. See [ADR-0041 §2.3](../adr/0041-execution-surface-unification-and-harness-thinning.md) and [harness-first-direction-2026-06-13.md](../strategy/harness-first-direction-2026-06-13.md) — thin harness is a **target invariant**, not current truth. |
| "Treat thin harness as a **target invariant for new work**, not a claim about current code size." | **Compliant** | Stated in `AGENTS.md` (2026-06-22) and ratified in [harness-first-direction-2026-06-13.md](../strategy/harness-first-direction-2026-06-13.md) §6. Event-spine migration (TASK-006) is the planned remediation path. |
| "Prefer protocol assets over vendor-specific assets: MCP-style tool metadata, Skills, and portable run records." | **Compliant** | MCP: `mcp_server.py:PROTOCOL_VERSION='2024-11-05'`; `mcp_tool_adapter.py` consumes MCP manifests as `ToolDefinition`. Skills: `skill_loader.py` + provenance via `skill_review.py`. Run records: hash-chained `audit.py`, `run_receipt.py`, `run_evidence.py`. Vendor adapters isolated in `llm/_adapters.py` and optional `managed_runtime.py`. |
| "Do not add a second agent framework without an ADR." | **Compliant (literally)** | ADRs 0019, 0022, 0028, 0029, and **0040** cover swarm/subagents/tournament and shared budget/audit/approval invariants across `AgentRunner` and `SubagentManager`. Dual execution loops remain a **maintainability debt** despite ADR coverage. |

## Tool Governance

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Tools must be registered through `ToolRegistry`." | **Compliant** | `teaagent/tools.py:114` — single registration path; workspace, git, browser, MCP, plugins all use `registry.register(...)`. |
| "Each tool requires a name, description, input schema, output schema, and annotations." | **Compliant** | `register()` validates required fields (`tools.py:129-165`); `governance/tool_lint.py` provides deeper linting. |
| "In `read-only`, `workspace-write`, and `prompt` modes, destructive tools must not run unless an approval token is present for that exact tool call." | **Compliant** | `ApprovalManager.assert_allowed()` enforces JIT/store/scoped/payload-digest binding (`approval/manager.py:847-978`); `tests/test_approval_token_exactness.py`. `AllowBackend` / `DangerFullAccessBackend` are not used in these three modes. |
| "In `allow` and `danger-full-access`, destructive tools may proceed under the declared mode with audit; those modes are owner-chosen widenings, not silent bypasses." | **Compliant** | `PermissionModeEnforcer.check()` returns `None` (allowed) for `ALLOW` and `DANGER_FULL_ACCESS` (`approval/manager.py:269-273`); decisions are still audited on the runner path. Documented in `docs/USAGE.md` permission matrix. |
| "Side effects in production runs must route through a governed path so `ApprovalPolicy` runs before `ToolRegistry.execute()`." | **Partial** | Runner path: `AgentRunner._execute_tool_decision()` → `assert_allowed()` → `registry.execute()` (`runner/_core.py:718-819`). **Gap:** `ToolRegistry.execute()` has no built-in approval gate; direct callers can bypass policy (`tools.py:215-323`). |
| "Tool errors must be actionable and classified." | **Compliant** | `DenialReasonCode`, `AgentHarnessError.hint`, `format_denial_message` (`errors.py`, `approval/manager.py`). |

## Runtime Safety

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Every run must have an iteration limit and a tool-call limit." | **Compliant** | `RunBudget` defaults 25/25 (`budget.py:45-47`); enforced in `runner/_core.py`; subagents clamp (`subagents/_manager.py:52-58`). |
| "Every tool call and final result must be recorded in the audit log." | **Compliant** | CLI/runner paths record full lifecycle. Library path defaults to durable JSONL via `RunStore` (`chat_agent.py:779-782`); `no_audit=True` is explicit opt-out with stderr warning (`tests/test_chat_agent_library_audit.py`). |
| "Long-lived state must be externalized; in-memory runner state is temporary only." | **Compliant** | RunStore, approval presets, checkpoint store, audit JSONL; per-run ephemeral state in `RunContext` / `JITApprovalState`. |

## Skills

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Keep `SKILL.md` short and route details into `REFERENCE.md` or examples." | **Compliant** | `skill_review.py` enforces `max_skill_md_lines=80`; tracked `.opencode/skill/*` within limit. |
| "Treat skills as reviewed supply-chain assets, not casual prompt snippets." | **Compliant** | `skill_loader.py` skips failed review; `skill_lifecycle.py` audit transitions; candidate provenance in `skill_candidates.py`. |

## Auto-Mode (formerly G1 — resolved)

| Prior finding | Current rating | Evidence |
| --- | --- | --- |
| Auto-mode escalated to `DANGER_FULL_ACCESS`, bypassing exact-call tokens | **Resolved → Compliant** | `AutoModeManager.get_auto_approve_policy()` preserves parent `permission_mode` and uses payload-scoped `preapproved_payload_digests` (`runner/_auto_mode_manager.py:52-78`). Tests: `tests/test_auto_mode_authority_audit.py` (no escalation, `authority_type='auto_mode'` audit events). |

## Cross-Dimension Compliance Summary

| Section | Rules | Compliant | Partial | Violated |
| --- | --- | --- | --- | --- |
| Architecture | 4 | 3 | 1 | 0 |
| Tool Governance | 6 | 5 | 1 | 0 |
| Runtime Safety | 3 | 3 | 0 | 0 |
| Skills | 2 | 2 | 0 | 0 |
| **Total** | **15** | **13** | **2** | **0** |

## Conclusion (2026-06-22)

- **No rules are Violated** after `AGENTS.md` reconciliation and verification against current tests.
- **Two Partial ratings remain systemic**:
  1. **Thin harness** — domain/swarm/hybrid-store surface exceeds target invariant; migration tracked via ADR-0041 (Phase 2 increment 1 relocated LLM prompt reasoning to reviewed skill assets; tested deterministic logic retained), harness-first §6, and TASK-006.
  2. **Governed path** — approval is enforced at `AgentRunner`, not inside `ToolRegistry.execute()`; defense-in-depth gap for direct registry callers.
- **Prior P0 auto-mode violation is closed** — update [01-security-risk.md](01-security-risk.md) G1 status when that chapter is next refreshed.
- **Prior library-audit partial is closed** — `chat_agent` durable audit default verified by `tests/test_chat_agent_library_audit.py`.

## Changelog

| Date | Change |
| --- | --- |
| 2026-06-30 | ADR-0041 Phase 2 D4: thin-harness row updated with measured domain LOC (2,781) and the behavior-preserving prompt-asset relocation (increment 1); rating stays Partial. |
| 2026-06-22 | DR-003: Re-rated destructive-tool rule (mode-relative); added thin-harness target + governed-path rows; closed auto-mode and library-audit gaps per current code/tests. |
| (prior) | Original matrix rated auto-mode Violated and library audit Partial. |
