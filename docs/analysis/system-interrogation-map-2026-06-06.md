# System Interrogation Map - TeaAgent
# 2026-06-06

> **Claim class:** Evidence snapshot and critical-question map.
>
> **Purpose:** Record the public, reviewable questioning structure behind the
> June 6, 2026 multi-angle TeaAgent system review.
>
> This document is not a private chain-of-thought transcript. It preserves the
> concrete questions, evidence handles, inferences, counterarguments, and work
> directions that maintainers can audit without depending on private reasoning.

---

## Inputs

Local evidence:

- [System Critical Review Package](system-critical-review-2026-06-06-INDEX.md)
- [Engineering Architecture Critique](engineering-architecture-critique-2026-06-06.md)
- [Multi-Agent Coordination Critique](multi-agent-coordination-critique-2026-06-06.md)
- [User Experience and Conversation Patterns](user-experience-and-conversation-patterns-2026-06-06.md)
- [Risk and Trust Model Critique](risk-and-trust-model-critique-2026-06-06.md)
- [Performance and Observability Critique](performance-and-observability-critique-2026-06-06.md)
- [Integration and Extensibility Critique](integration-and-extensibility-critique-2026-06-06.md)
- [Deployment and Operations Readiness](deployment-and-operations-readiness-2026-06-06.md)
- [Competitor Self-Comparison Matrix](competitor-self-comparison-matrix-2026-06-06.md)
- [System Improvement Work Directions](../plans/system-improvement-work-directions-2026-06-06.md)

External source refresh used for competitive framing on 2026-06-06:

- OpenAI Codex help and product updates.
- Anthropic Claude Code extension and subagent documentation.
- GitHub Copilot cloud agent documentation.
- OpenCode, Aider, Cline, Cursor, Kiro, Devin, OpenHands, Jules, Windsurf/Cascade, and Roo Code official or upstream documentation.

---

## Executive Question Set

| Angle | Skeptical question | Best-supported answer | Confidence | Follow-up |
| --- | --- | --- | --- | --- |
| Engineering architecture | Is TeaAgent still a thin governed harness? | Partly. The runner/tool/audit spine is coherent, but the surrounding feature surface is broad enough to behave like a framework. | High | WS0, WS5 |
| Runtime state | Is the run protocol explicit enough to extend safely? | No. The mutable `context` dict is a hidden API between runner, decision engine, cost, observations, and summaries. | High | WS5-001 |
| Resource lifecycle | Can long-lived sessions run without accumulating hidden state? | Not confidently. Approval-policy executors, audit event lists, run indexes, and approval queues have growth or lifecycle risks. | Medium-high | WS3, WS4 |
| Remote multi-agent | Can the current subagent system support remote teams? | No. It is useful for local, single-process delegation but lacks durable queues, hard global budgets, crash recovery, and safe default write isolation. | High | WS2 |
| Shared workspace writes | What happens when parallel children write the same file? | Current evidence points to undefined last-writer behavior in shared isolation; no conflict guard is documented as default. | High | WS2-001 |
| Conversation UX | Does a normal developer know what is happening during a run? | Only if they already know TeaAgent's command model. Progress, approvals, undo scope, and run receipts are not legible enough by default. | High | WS1 |
| Approval UX | Is governance visible at the moment users make risky decisions? | Partly. Approval primitives exist, but call IDs and JSON are the main user-facing units too often. | High | WS1-002 |
| Trust claims | Are audit and sandbox claims proportionate? | They are meaningful for local governance, but not enough for broad enterprise, multi-tenant, or sandbox-complete claims. | High | WS0, WS3 |
| Observability | Can an operator diagnose a stuck or expensive run quickly? | Not yet. Audit logs are rich, but live latency, queue, cost, and durability health are not surfaced as first-class run state. | Medium-high | WS4 |
| Integration | Are extension points mature enough to expand aggressively? | Tools and providers are relatively strong; approval strategies, run services, storage, and event streams need clearer contracts. | Medium-high | WS5 |
| Documentation governance | Do docs clarify maturity or create claim drift? | Both. The dated evidence trail is valuable, but current truth must be curated to avoid stale competitor and maturity claims. | High | WS0, WS6 |
| Competitive position | Where can TeaAgent win without copying everyone? | Governance-as-a-layer: local-first, provider-agnostic, audit/cost/approval/run-evidence control. | Medium-high | WS6 after WS1/WS3 proof |

---

## Angle-by-Angle Interrogation

### 1. Engineering Architecture

Critical questions:

- What is the smallest stable core that must remain trustworthy?
- Which modules are part of the harness spine, and which are experimental product surface?
- Which internal protocols are typed contracts, and which are implicit dict keys or ambient context variables?
- Which resources are created per run, per session, or globally, and who shuts them down?
- Which test families validate behavior instead of mocks around behavior?
- Which features should be deleted, quarantined, or labeled experimental before more integrations are added?

Evidence handles:

- The runner accepts a decision callback and delegates tools through the registry.
- Audit logging, tool schemas, permissions, budgets, and run stores are real first-class primitives.
- The architecture critique identifies the mutable run `context` dict, broad `chat_agent.py` wiring, unmanaged executor lifecycle, and large CLI/TUI surfaces as coupling risks.

Inference:

TeaAgent should treat "thin harness" as a target invariant, not a current blanket claim. The safest formulation is "TeaAgent has a governed harness spine with broad alpha product experiments around it."

Work direction:

- Define subsystem maturity labels.
- Extract a typed run-service contract.
- Replace implicit context keys with a typed intermediate.
- Separate product surfaces from the runner/tool/audit spine.

### 2. Remote and Local Multi-Agent Coordination

Critical questions:

- Who owns the global budget when a parent delegates to children?
- What is the default write isolation for a child agent, and is shared workspace mutation ever implicit?
- What happens if a child hangs, the parent crashes, or the approval bridge loses its event loop?
- Can a child spawn more children without an explicit global recursion guard?
- Are `SubagentManager`, team orchestration, and `SwarmManager` one concept or multiple competing concepts?
- What state must survive process restart before the system may claim remote readiness?

Evidence handles:

- Local subagent, batch, team, isolation, diff capture, lineage, and approval queue code exists.
- Default or common local execution paths are still in-process and thread-based.
- The critique identifies no batch-level timeout on one path, in-process approval queue state, weak budget inheritance, shared-isolation race risk, and parallel orchestration layers.

Inference:

The current multi-agent system is valuable as local bounded delegation. It should not be described as remote-team-ready until durable coordination, isolation, budget inheritance, and failure semantics are enforced.

Work direction:

- Make shared isolation explicit or gated.
- Add hard deadlines and cancellation for batch execution.
- Propagate parent budget envelopes.
- Add durable approval queue state.
- Unify swarm and subagent orchestration semantics.

### 3. General User Conversation Experience

Critical questions:

- Can a first-time user tell whether the agent is thinking, waiting for approval, running tools, or stuck?
- Does the user see what will be changed before approving a risky tool call?
- Are "run", "session", "task", "background", "resume", "checkpoint", and "undo" used consistently?
- Does the default interactive surface speak human first and JSON second?
- Is cost shown as actual, estimated, unknown, or local-provider non-billable?
- Can the user recover without knowing internal run IDs or call IDs?

Evidence handles:

- CLI, TUI, and chat surfaces exist and have substantial command coverage.
- The UX analysis identifies JSON-heavy TUI output, multiple chat paths, approval-by-call-ID friction, background/resume vocabulary ambiguity, and non-default progress visibility.
- Active finding ledgers show many daily-driver defects were fixed, which means the critique must distinguish current open risks from already closed June 1 defects.

Inference:

TeaAgent's user experience is powerful for operators but still exposes too much internal control-plane vocabulary. Governance will not feel like a benefit until it is packaged as readable run receipts, approval summaries, progress state, and recovery affordances.

Work direction:

- Add default run receipts.
- Add approval by numbered, readable pending action.
- Show progress summaries by default for interactive runs.
- Preserve JSON for scripting, but add human-first TUI display paths.

### 4. Security, Trust, and Claim Proportionality

Critical questions:

- Which trust guarantees are hard enforcement, and which are best-effort logging?
- What happens when audit disk writes fail?
- Is audit encryption described in terms of the threat model it actually covers?
- Are generated or plugin tools governed with the same schema, annotation, and approval requirements as first-party tools?
- Which prompt-injection boundaries are enforced by code, and which are only documented behavior?
- Which security claims require compliance mode before they can be advertised?

Evidence handles:

- Tool schemas, approval modes, audit chain verification, read-only gates, and plugin governance tests exist.
- The risk critique flags audit durability, key locality, legacy chain compatibility, plugin trust, and sandbox wording as areas where claims can outrun implementation.

Inference:

TeaAgent's trust story is real but must be stated precisely. The strongest claim is "auditable local governance." The unsafe claim is "complete production sandbox or enterprise compliance platform."

Work direction:

- Add claim classes for security guarantees.
- Add fatal audit failure mode for compliance runs.
- Add strict chain verification mode for new logs.
- Keep prompt-injection boundaries explicit and tested.

### 5. Operations, Observability, and Long-Run Behavior

Critical questions:

- Can operators see queue depth, latency, cost burn, audit health, and disk growth without reading raw JSONL?
- Are metrics emitted from the same source of truth as audit events?
- What happens after thousands of runs in the same workspace?
- Which cleanup, rotation, and archival jobs are required but not yet built?
- Which warnings are fatal in compliance mode?

Evidence handles:

- Audit logs, run stores, traces, acceptance gates, and operations documentation exist.
- The performance and operations critiques identify gaps around live metrics, disk growth, run-index scaling, and external collector assumptions.

Inference:

TeaAgent has more operational documentation than many alpha projects, but it still needs productized run observability. Audit logs should become an operator-facing receipt and metrics layer, not only forensic raw material.

Work direction:

- Add run-level latency and cost summaries.
- Expose approval queue depth and audit durability health.
- Add redacted audit-tail and run-health commands.
- Define retention and rotation expectations.

### 6. Integration and Extensibility

Critical questions:

- Is there one canonical run contract for CLI, TUI, tests, plugins, and future IDE/server adapters?
- Can an external surface subscribe to events without depending on internal audit object layout?
- Are storage backends, approval strategies, and provider adapters separable?
- Are plugin tools rejected early when metadata or annotations are unsafe?
- Are MCP, skills, plugins, subagents, hooks, and providers documented as separate concepts with different trust boundaries?

Evidence handles:

- Tool registration and provider adapter interfaces are relatively clean.
- CLI/TUI/chat setup still duplicates orchestration concerns.
- Plugin governance recently became stricter, which improves safety but increases the need for explicit extension contracts.

Inference:

The next integration work should not add another surface first. It should define the event, run, storage, and approval contracts that stop every new surface from reimplementing policy.

Work direction:

- Define `AgentService` or equivalent.
- Define stable event stream schema.
- Inject approval strategy as an interface.
- Align plugin discovery with registry governance.

### 7. Documentation and Roadmap Governance

Critical questions:

- Which document is current truth, and which is dated evidence?
- Are old competitor facts, test counts, provider counts, and maturity claims explicitly superseded?
- Does every roadmap row have owner, status, exit criteria, and evidence?
- Are analysis documents creating new work that is not routed into a plan?
- Can a future maintainer find the current answer without reading every dated review?

Evidence handles:

- `docs/INDEX.md`, generated docs inventory, documentation operating model, active findings ledger, and ticket plans provide a governance framework.
- The corpus is large enough that discoverability is itself a product risk.

Inference:

Documentation is a competitive advantage only if it reduces ambiguity. Without claim classes and front-door links, it can accidentally preserve stale claims as if they were current truth.

Work direction:

- Keep dated snapshots.
- Add supersession notes when facts drift.
- Maintain package indexes.
- Regenerate docs inventory after adding files.
- Run docs consistency checks after governance-sensitive edits.

### 8. Competitive Positioning

Critical questions:

- Which competitor advantages are stable product shape, and which are volatile marketing facts?
- Which lanes should TeaAgent avoid because incumbents already own them?
- Which TeaAgent strengths are visible in the user experience, not only in code?
- Which claims require same-day official-source refresh before reuse?
- Does TeaAgent compare itself to every major competitor on the same axis, or only on axes where it looks good?

Evidence handles:

- Current source-backed competitor matrix covers terminal, IDE, cloud, and governed-orchestration competitors.
- Official docs confirm broad market movement toward remote/cloud agents, IDE surfaces, plan/spec workflows, subagents, hooks, permissions, MCP, and PR workflows.
- TeaAgent's local evidence supports governance, audit, cost, permission, provider, tool-registry, and skill/plugin aspirations.

Inference:

TeaAgent should not chase "fastest IDE assistant" or "hosted teammate" first. Its defensible position is a governed, local-first, provider-agnostic harness that can export evidence for teams that need control.

Work direction:

- Make governance visible through receipts and dashboards.
- Avoid volatile star/pricing/model rankings.
- Treat remote agent UX as a benchmark, not a current claim.
- Refresh competitor facts from official docs before public positioning updates.

---

## Cross-Cutting Failure Assumptions

| Assumption to challenge | Failure if false | Required guard |
| --- | --- | --- |
| Users will read docs before running commands. | Users choose unsafe or confusing modes, then blame the product. | Human-readable defaults and inline help. |
| Shared local execution is acceptable for child agents. | Parallel writes race or destroy user work. | Safer isolation default or explicit shared-mode gate. |
| Audit failures can be best-effort. | Compliance users believe records exist when disk writes failed. | Fatal compliance mode and health receipts. |
| Cost estimates are accurate enough. | Budget trust collapses when providers report differently or not at all. | Cost-state taxonomy and honest labels. |
| Dated docs are self-explanatory. | Old competitor or status claims are reused as current truth. | Claim classes, supersession notes, and current indexes. |
| More features improve competitiveness. | Surface sprawl hides the strongest governance differentiator. | Maturity labels and integration contracts before expansion. |

---

## Evidence-to-Work Trace

| Evidence cluster | Main inference | Workstream |
| --- | --- | --- |
| Mutable context, broad chat wiring, executor lifecycle, monolithic handlers | The harness spine needs sharper contracts. | WS5, WS0 |
| Shared isolation, missing batch timeout, in-memory approvals, budget gaps | Local delegation must be bounded before remote claims. | WS2 |
| JSON-heavy TUI, call-ID approvals, ambiguous background/resume, non-default progress | Governance must be visible and understandable. | WS1 |
| Audit disk failure behavior, key locality, legacy chain compatibility | Trust claims need modes and precise wording. | WS3 |
| Raw audit logs, weak live metrics, run-index growth | Operators need run-health and retention surfaces. | WS4 |
| Stale competitive facts risk, large dated docs corpus | Docs need claim-class and refresh discipline. | WS0, WS6 |

---

## Rejected Shortcuts

| Shortcut | Why rejected |
| --- | --- |
| Add more remote-agent marketing before hardening local multi-agent state. | It would convert known local risks into a credibility failure. |
| Hide complexity by removing governance controls from the UX. | Governance is the product wedge; the fix is better presentation, not weaker controls. |
| Treat every dated analysis document as current truth. | Dated evidence is useful only when front-door docs clarify status. |
| Chase exact competitor star counts and pricing tables. | They are volatile and distract from durable capability comparison. |
| Add another UI surface before defining `AgentService` and event-stream contracts. | It would duplicate policy wiring and increase drift. |

---

## Unknowns

| Unknown | Why it matters | How to reduce uncertainty |
| --- | --- | --- |
| Real external user tolerance for governance-first friction | Determines whether the product wedge is strong enough. | Run first-use studies with security, platform, and solo CLI personas. |
| Actual cost-estimation accuracy by provider | Determines how strong budget guarantees can be. | Add provider-labeled cost telemetry and compare estimates to reported usage. |
| Multi-agent write-conflict frequency in realistic tasks | Determines default isolation tradeoff. | Add adversarial batch-write tests and manual team-task trials. |
| Whether teams want local-first governance more than hosted async PR flow | Determines GTM focus. | Interview regulated/platform teams before building cloud surfaces. |
| Which extension surfaces external users will actually adopt | Determines whether MCP, plugin, CLI, TUI, or IDE should get next investment. | Instrument local use and collect explicit feedback through docs/examples. |

