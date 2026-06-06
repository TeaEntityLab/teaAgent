# System Review Workstream Traceability - TeaAgent
# 2026-06-06

> **Claim class:** Plan and traceability matrix.
>
> **Purpose:** Connect the June 6 critical review package to concrete workstreams,
> acceptance criteria, validation evidence, and competitor pressure.
>
> This is an execution companion to
> [System Improvement Work Directions](system-improvement-work-directions-2026-06-06.md).
> Use that file for the workstream backlog and this file to understand why each
> workstream exists and how to prove it moved the system.

---

## Traceability Matrix

| Evidence source | Critical finding | Competitor / market pressure | Workstream | Proof of movement |
| --- | --- | --- | --- | --- |
| [Engineering Architecture Critique](../analysis/engineering-architecture-critique-2026-06-06.md) | The runner spine is coherent, but product wiring and implicit context keys create a framework-like coupling surface. | Claude Code and Devin/Cascade present clearer extension taxonomies and workflow layers. | WS0, WS5 | Maturity map plus typed run-service/event-stream contract tests. |
| [Engineering Architecture Critique](../analysis/engineering-architecture-critique-2026-06-06.md) | Resource lifecycle risks exist in approval policy, audit event retention, run indexes, and queues. | Hosted/IDE products hide operational state; TeaAgent must be more honest and inspectable. | WS3, WS4 | Run-health command, audit durability mode, retention/rotation policy, targeted tests. |
| [Multi-Agent Coordination Critique](../analysis/multi-agent-coordination-critique-2026-06-06.md) | Local subagents are not remote-team-ready because queues, budgets, isolation, and crash recovery are incomplete. | Cursor, Kiro, Codex, Copilot, Devin, and Jules normalize remote async work. | WS2 | Batch deadline, child budget inheritance, isolation gate, global depth/concurrency tests. |
| [User Experience and Conversation Patterns](../analysis/user-experience-and-conversation-patterns-2026-06-06.md) | Governance exists but is hard to understand during normal conversation. | Cline Plan/Act, Cursor modes, Aider git simplicity, and Codex/Copilot status surfaces reduce cognitive load. | WS1 | Human-readable receipt, readable approval selectors, progress summaries, cost-state labels. |
| [Risk and Trust Model Critique](../analysis/risk-and-trust-model-critique-2026-06-06.md) | Audit and sandbox claims must be proportionate to actual failure behavior. | OpenHands sandbox vocabulary and enterprise competitor audit/control surfaces set expectations. | WS0, WS3 | Claim-class docs, fatal compliance audit mode, strict chain verification, prompt-injection boundary tests. |
| [Performance and Observability Critique](../analysis/performance-and-observability-critique-2026-06-06.md) | Operators lack first-class live visibility into cost, latency, queue depth, and audit durability. | Hosted tools surface status and collaboration logs by default. | WS4 | Run metrics receipt, audit tail, approval queue age/depth, disk-growth warnings. |
| [Integration and Extensibility Critique](../analysis/integration-and-extensibility-critique-2026-06-06.md) | Extension points are promising but policy setup is duplicated across surfaces. | Claude Code/OpenCode/Cascade package skills, hooks, MCP, and agents with clearer boundaries. | WS5 | Shared `AgentService`, event stream, approval strategy, storage contracts, plugin metadata tests. |
| [Competitive Claim Audit](../analysis/competitive-claim-audit-2026-06-06.md) | Volatile competitive claims must not leak into current-truth docs. | Market moves quickly; stale positioning damages credibility. | WS0, WS6 | Same-day source refresh rule, supersession notes, matrix update, docs consistency check. |
| [System Interrogation Map](../analysis/system-interrogation-map-2026-06-06.md) | The review questions cut across modules and must not remain prose-only. | Competitors package workflow clarity as product. | WS0-WS6 | Each major question maps to backlog row, acceptance gate, or explicit non-goal. |

---

## Workstream Cards

### WS0 - Claim Hygiene and Maturity Boundaries

Target outcome:

- A maintainer can tell whether a claim is current truth, dated evidence, plan,
  reference, governance rule, or user guide.
- Public-facing positioning cannot accidentally reuse stale competitor facts or
  alpha/beta implementation claims.

First slice:

1. Add subsystem maturity labels for runner, tools, approval, audit, providers,
   chat, TUI, subagents, memory, plugins, and remote orchestration.
2. Add supersession notes to volatile competitor and maturity snapshots.
3. Update release checklist language for enterprise, remote-ready, and sandbox-complete claims.

Validation:

```bash
python3 scripts/validate_docs_consistency.py
python3 scripts/detect_stale_plans.py
```

### WS1 - Run Receipt and Conversation Trust

Target outcome:

- A normal developer can understand what happened in a run without reading JSONL,
  source code, or internal call IDs.

First slice:

1. Define a receipt schema with goal, provider/model, mode, budget, approvals,
   tools, files, tests, audit path, cost state, resume/checkpoint state, and
   warnings.
2. Add a CLI/TUI display path for the latest run receipt.
3. Convert approval display from call-ID-first to numbered pending actions.

Validation:

```bash
python3 -m pytest tests/test_run_receipt.py tests/test_tui.py -q
python3 -m pytest tests/acceptance -q
```

### WS2 - Multi-Agent Safety and Coordination

Target outcome:

- Local delegation is bounded by time, budget, depth, concurrency, approval
  durability, and safe workspace ownership before any remote claim is made.

First slice:

1. Add batch-level timeout and partial-result reporting.
2. Enforce global depth/concurrency regardless of named subagent definition.
3. Make shared write isolation explicit or gated.
4. Propagate parent budget envelopes to children.

Validation:

```bash
python3 -m pytest tests/test_subagent.py tests/test_subagent_batch.py tests/test_subagent_isolation.py -q
python3 -m pytest tests/test_subagent_approval_queue_integration.py -q
```

### WS3 - Audit, Security, and Budget Integrity

Target outcome:

- Trust guarantees are mode-specific, testable, and honest about failure behavior.

First slice:

1. Add compliance-mode fatal audit durability behavior.
2. Add strict audit-chain verification for new logs.
3. Expand prompt-injection, schema, approval-token, and path-containment tests.
4. Define cost state taxonomy in user-visible receipts.

Validation:

```bash
python3 -m pytest tests/test_audit.py tests/test_audit_chain.py tests/test_security_fixes.py -q
python3 -m pytest tests/test_governance_adversarial_runtime.py -q
```

### WS4 - Observability and Operations

Target outcome:

- Operators can diagnose run state, queue state, cost burn, audit durability, and
  retention risk from product commands.

First slice:

1. Emit per-run latency buckets for LLM, tool, approval, audit write, and storage.
2. Add `approval queue` age/depth display.
3. Add redacted audit-tail and run-health commands.
4. Document retention and rotation expectations.

Validation:

```bash
python3 -m pytest tests/test_run_evidence.py tests/test_audit_events.py -q
teaagent selftest --root .
```

### WS5 - Integration and Extension Boundaries

Target outcome:

- CLI, TUI, tests, plugins, and future IDE/server adapters use one run contract
  and one approval/event/storage vocabulary.

First slice:

1. Define an `AgentService` or equivalent run setup boundary.
2. Define a stable event stream contract that does not require direct audit
   object coupling.
3. Inject approval strategy and storage interfaces.
4. Keep plugin-provided tools under the same metadata and approval governance as
   first-party tools.

Validation:

```bash
python3 -m mypy teaagent/
python3 -m pytest tests/test_plugins.py tests/test_tool_registry.py tests/test_cli_tui_surface_parity.py -q
```

### WS6 - Competitive Positioning and Developer Relations

Target outcome:

- TeaAgent's market story is narrow, defensible, and backed by product-visible
  proof rather than prose.

First slice:

1. Refresh competitor matrix from official docs.
2. Add a governance-first README section only after WS1/WS3 proof is visible.
3. Publish "when not to use TeaAgent" and persona guides with current caveats.
4. Convert current claims into examples, demos, and receipt screenshots.

Validation:

```bash
python3 scripts/refresh_competitive_docs.py --check
python3 scripts/validate_docs_consistency.py
```

---

## Gate Dependencies

| Gate | Blocks | Exit condition |
| --- | --- | --- |
| Claim hygiene gate | Public README positioning, release notes, competitive pages | Claim classes and volatile-source rules are linked from docs front doors. |
| Conversation trust gate | Developer daily-driver claims | Run receipt, readable approvals, progress summary, and cost-state labels exist and are tested. |
| Multi-agent safety gate | Remote/team-agent claims | Batch timeout, budget inheritance, isolation gate, depth/concurrency limits, durable approvals. |
| Compliance trust gate | Enterprise/compliance claims | Fatal audit durability mode, strict chain verification, documented non-goals, security tests. |
| Integration contract gate | New IDE/server/plugin surfaces | Shared run service, event stream, approval strategy, storage interfaces. |

---

## Decision Backlog

| Decision | Owner surface | Default recommendation | Revisit trigger |
| --- | --- | --- | --- |
| Should shared subagent isolation remain the default? | Subagents / workspace safety | No; make it explicit or gate it. | After concurrent-write tests and migration impact review. |
| Should TeaAgent build hosted remote agents now? | Product strategy | No; finish local safety and observability gates first. | After WS2 and WS4 are verified. |
| Should JSON remain the TUI default? | TUI / user experience | No for human TTY sessions; keep JSON as explicit/scripted format. | After receipt/text output design. |
| Should audit disk failures be fatal by default? | Security / operations | Fatal in compliance mode, warning in normal local mode. | After operator mode taxonomy is documented. |
| Should new integrations use direct `run_chat_agent()` calls? | Integration architecture | No; define a shared run service first. | When WS5 first slice lands. |
| Should public docs claim enterprise readiness? | Documentation / release | No. | After compliance gate, certification evidence, and deployment proof exist. |

---

## Acceptance Definition for This Traceability Layer

- Every major June 6 critique angle maps to at least one workstream.
- Every workstream names product-visible proof, not only implementation chores.
- Competitive pressure is used to prioritize, not to justify copying.
- Remote, enterprise, and sandbox claims are blocked by explicit gates.
- Validation commands are concrete and runnable in the repo.

