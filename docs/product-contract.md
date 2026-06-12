# TeaAgent Product Contract

> **Last reviewed:** 2026-06-13
> **Review trigger:** Persona framing, external-adoption claims, or strategic positioning changes.
> **Direction record:** [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md)

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

## Primary User (Owner-Operator)

**The owner-operator** is a single person who is simultaneously the maintainer, daily user, and governance auditor of his own runs. This is TeaAgent's current and validated persona.

Core interactions:

1. **Inspect a repo safely** — read-only analysis with audit trail.
2. **Make bounded code changes** — hash-anchored edits, protected paths, optional plan binding (`--from-plan`, `--require-plan`).
3. **Approve destructive actions** — prompt-mode HITL with scoped approvals and JIT TTY prompts.
4. **Replay and recover** — run store, undo journal, `teaagent runs trace|export|replay`.
5. **Extend with guardrails** — plugins, MCP, skills under manifest and policy gates.

## Differentiators (Owner-Operator Scope)

For a maintainer operating his own governance harness with **strict tool governance, auditability, and permission boundaries** in a local-first context.

Evidence-backed capabilities:

- Tool contract lint (`teaagent tool lint`)
- Permission matrix enforcement (see `tests/policy/test_permission_matrix.py`)
- Audit completeness checks (`teaagent runs export`)
- Plan-before-write opt-in (`--require-plan`)
- Validation profiles (`--validate` + `--validation-profile`)

## Future Goals (Aspirational)

These personas and use cases are **not current capabilities** and appear here to document forward direction. They may become evidence-backed in a future release, but no present-tense claim is made.

- **Ordinary developer daily driver** — simplifying friction for non-auditor users
- **Team operator** — multi-user approval workflows and delegated governance
- **Enterprise deployment** — federated multi-agent runs, policy auditing, hosted dashboards

## Release Expectations

Before claiming a feature **Stable**, it must have:

- Documented CLI or API entry point
- Acceptance or integration test reference in [maturity-matrix.md](maturity-matrix.md)
- Known failure modes listed in [threat-model.md](threat-model.md) when security-relevant

## Claim Traceability

Top-10 product claims are tracked with evidence commands and acceptance test references in
[docs/architecture/claim-to-test-traceability-matrix.md](architecture/claim-to-test-traceability-matrix.md).
Claims without a test reference must be labelled **roadmap**, not current capability.
The matrix is validated by `tests/acceptance/test_claim_traceability.py`.
