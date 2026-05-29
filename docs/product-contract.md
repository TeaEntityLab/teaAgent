# TeaAgent Product Contract

Last updated: 2026-05-28

## What TeaAgent Is

TeaAgent is a **governance-first coding-agent harness** for autonomous development tasks.

- **Local-first by default** — runs against a workspace root with explicit permission modes.
- **Provider-adapter based** — connects to LLM providers; it is not a model framework.
- **Tool-boundary centered** — all side effects flow through `ToolRegistry`, `ApprovalPolicy`, and workspace tools.
- **Audit-first** — every iteration, tool call, approval decision, and final result is recorded in per-run JSONL.
- **Permission-mode enforced** — `read-only`, `workspace-write`, `prompt`, `allow`, and `danger-full-access` are first-class.

Core execution path:

```text
ModelDecisionEngine → AgentRunner → ToolRegistry → ApprovalPolicy → Workspace Tools → AuditLogger / RunStore
```

## What TeaAgent Is Not

- Not a generic no-code agent builder.
- Not a drop-in replacement for LangChain, LangGraph, or CrewAI orchestration models.
- Not a fully autonomous production deployer by default.
- Not a complete sandbox guarantee unless Code Mode container backend or git/worktree isolation is configured.
- Not enterprise-proven by community adoption alone — maturity labels apply per feature ([maturity-matrix.md](maturity-matrix.md)).

## Primary User Outcomes

1. **Inspect a repo safely** — read-only analysis with audit trail.
2. **Make bounded code changes** — hash-anchored edits, protected paths, optional plan binding (`--from-plan`, `--require-plan`).
3. **Approve destructive actions** — prompt-mode HITL with scoped approvals and JIT TTY prompts.
4. **Replay and recover** — run store, undo journal, `teaagent runs trace|export|replay`.
5. **Extend with guardrails** — plugins, MCP, skills under manifest and policy gates.

## Competitive Positioning

For developers who want coding-agent automation with **strict tool governance, auditability, and permission boundaries** — not maximum agent orchestration surface area.

Differentiators:

- Tool contract lint (`teaagent tool lint`)
- Permission matrix enforcement (see `tests/policy/test_permission_matrix.py`)
- Audit completeness checks (`teaagent runs export`)
- Plan-before-write opt-in (`--require-plan`)
- Validation profiles (`--validate` + `--validation-profile`)

## Release Expectations

Before claiming a feature **Stable**, it must have:

- Documented CLI or API entry point
- Acceptance or integration test reference in [maturity-matrix.md](maturity-matrix.md)
- Known failure modes listed in [threat-model.md](threat-model.md) when security-relevant
