# System Improvement Work Directions - TeaAgent
# 2026-06-06

> **Status:** Proposed execution backlog derived from the June 6, 2026
> multi-angle critical review package.
>
> **Scope:** Engineering architecture, remote/local multi-agent behavior,
> conversation UX, trust/security posture, observability, integration contracts,
> documentation governance, and competitive positioning.
>
> **Traceability companion:** Use
> [System Review Workstream Traceability](system-review-workstream-traceability-2026-06-06.md)
> to map each workstream to the evidence source, competitor pressure, proof of
> movement, and validation gate.

---

## Priority Stack

| Priority | Theme | Reason |
| --- | --- | --- |
| P0 | Claim hygiene and data-loss prevention | Prevents overpromising and protects audit/trust claims. |
| P1 | Conversation trust | Converts internal governance into user-visible confidence. |
| P1 | Multi-agent safety | Required before remote, parallel, or team-oriented claims. |
| P1 | Observability and cost clarity | Makes long-running agent behavior diagnosable. |
| P2 | Integration boundaries | Reduces framework sprawl and stabilizes extension points. |
| P2 | Documentation governance | Keeps dated reasoning useful without becoming stale truth. |
| P3 | Competitive positioning | Turns strengths into market language after the product proof exists. |

---

## Critical Question Routing

| Critical question | Primary evidence | Workstream |
| --- | --- | --- |
| What exactly is stable core versus alpha/beta/experimental surface? | Engineering architecture critique and documentation operating model | WS-0 |
| Can a normal developer understand a run without reading JSONL or call IDs? | User experience and conversation patterns analysis | WS-1 |
| Can local subagents run safely under time, budget, depth, and isolation limits? | Multi-agent coordination critique | WS-2 |
| What trust claims are hard guarantees, and what is best-effort? | Risk and trust model critique | WS-3 |
| Can operators diagnose cost, latency, queue depth, audit health, and retention? | Performance and observability critique | WS-4 |
| Can integrations reuse policy instead of duplicating it? | Integration and extensibility critique | WS-5 |
| Which competitor claims are safe to reuse? | Competitor self-comparison matrix and competitive claim audit | WS-6 |

---

## WS-0 - Claim Hygiene And Maturity Boundaries

**Goal:** Ensure public and internal claims match current implementation.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS0-001 | Define claim classes for docs: current truth, dated evidence, proposal, aspiration, and non-goal. | Governance doc updated; new/changed analysis docs label their claim class. |
| WS0-002 | Add supersession notes to older competitor and architecture docs that contain volatile facts. | Stale star counts, pricing, model availability, or adoption claims point to a refresh source. |
| WS0-003 | Create a maturity map for runner, tools, approval, audit, providers, chat, TUI, subagents, memory, and plugins. | Each subsystem has `stable`, `beta`, `alpha`, or `experimental` status plus owner and verification gate. |
| WS0-004 | Add a release-note rule that forbids enterprise, remote-ready, or sandbox-complete claims without explicit evidence. | Documentation checklist includes prohibited claim examples and required proof links. |

---

## WS-1 - Run Receipt And Conversation Trust

**Goal:** Make every agent run understandable to a normal developer.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS1-001 | Implement a human-readable run receipt. | Receipt includes goal, provider/model, budget, tools used, approvals, files touched, tests run, cost, audit path, and resume/checkpoint state. |
| WS1-002 | Replace raw approval-ID-first UX with readable selectors. | User can approve by numbered pending action with tool name, reason, path summary, risk class, and expiry. |
| WS1-003 | Add default progress summaries for long runs. | TUI/CLI shows current phase, last tool, next intended action, elapsed time, and budget remaining. |
| WS1-004 | Consolidate chat surface semantics. | CLI, TUI, and controller share command definitions or a documented translation layer. |
| WS1-005 | Repair background/resume vocabulary. | Documentation and UI distinguish checkpointed suspension, resumable session, and live background execution. |
| WS1-006 | Add conversation UX acceptance tests. | Tests cover approval display, cost display, compact/resume wording, and receipt generation. |

---

## WS-2 - Multi-Agent Safety And Coordination

**Goal:** Keep local delegation useful while preparing for remote-safe designs.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS2-001 | Change or gate default subagent isolation. | Shared workspace is explicit; safer isolated mode is available and documented. |
| WS2-002 | Add batch-level timeout and cancellation to subagent batch execution. | Batch calls stop at configured deadline and report partial results without hanging. |
| WS2-003 | Propagate budget envelopes to child agents. | Child runs inherit max iterations, max tool calls, cost budget, and elapsed-time budget unless explicitly narrowed. |
| WS2-004 | Enforce global depth and concurrency controls independent of subagent definition lookup. | Recursive or definitionless child launches cannot bypass depth/concurrency policy. |
| WS2-005 | Replace process-only approval queues with a durable coordination abstraction. | Local implementation may remain file-backed, but the interface supports recovery and remote orchestration. |
| WS2-006 | Produce an orchestration unification design for subagents and swarm. | One document names the canonical manager, compatibility path, and migration tests. |
| WS2-007 | Define remote multi-agent non-goals for Phase 0/1. | Docs state which remote claims are intentionally unsupported until safety gates pass. |

---

## WS-3 - Audit, Security, And Budget Integrity

**Goal:** Make trust guarantees explicit, testable, and proportionate.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS3-001 | Add compliance mode for fatal audit durability failures. | In compliance mode, audit disk write failure stops the run instead of silently continuing in memory. |
| WS3-002 | Add strict audit-chain verification for new logs. | New strict mode rejects legacy reset lines unless compatibility mode is requested. |
| WS3-003 | Expand schema and path-containment tests. | Tests cover generated tools, nested schemas, symlinks, destructive tools, and workspace escape attempts. |
| WS3-004 | Define cost state taxonomy. | Docs and tests distinguish estimated, provider-reported, pending, and unknown cost. |
| WS3-005 | Add prompt-injection boundary documentation and tests. | Tool outputs, skills, memory, and repository docs have documented trust boundaries. |
| WS3-006 | Add approval-token exactness tests for destructive tools. | Destructive call cannot reuse stale or mismatched approval token. |

---

## WS-4 - Observability And Operations

**Goal:** Make agent runs diagnosable without reading raw logs by hand.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS4-001 | Record LLM, tool, approval, and audit latency metrics. | Metrics are available per run and summarized in the run receipt. |
| WS4-002 | Expose approval queue depth and age. | CLI/TUI can show pending approvals with age, risk, and expiry. |
| WS4-003 | Record audit durability health. | Operators can see disk write failures, cooldown status, and chain verification status. |
| WS4-004 | Add an audit tail command. | Command shows recent events with redaction and clear event classification. |
| WS4-005 | Add config lint for unsafe combinations. | Lint warns about permissive tool settings, missing audit path, shared subagent isolation, and unclear provider cost policy. |

---

## WS-5 - Integration And Extension Boundaries

**Goal:** Preserve provider/plugin flexibility without uncontrolled framework growth.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS5-001 | Define an `AgentService` or equivalent run contract. | CLI, TUI, plugins, and tests invoke a shared run setup path rather than duplicating orchestration. |
| WS5-002 | Define a stable event stream contract. | Consumers can subscribe to run events without depending on internal audit object layout. |
| WS5-003 | Inject approval strategy as an interface. | CLI, TUI, test, and future remote approval flows use the same strategy boundary. |
| WS5-004 | Define storage interfaces for runs, approvals, memory, and audit. | Local default remains simple; remote-safe backends can be added without changing runner logic. |
| WS5-005 | Align plugin discovery with tool registry governance. | Plugin-provided tools must satisfy schema, annotation, approval, and audit requirements. |

---

## WS-6 - Competitive Positioning And Developer Relations

**Goal:** Explain TeaAgent's real advantage only after it is visible in the product.

| ID | Work Item | Acceptance Criteria |
| --- | --- | --- |
| WS6-001 | Write a governance-first README section. | Public docs explain TeaAgent as a local-first governed harness, not a generic IDE/cloud agent clone. |
| WS6-002 | Write a trust and audit whitepaper. | Document includes exact guarantees, non-goals, failure behavior, and verification commands. |
| WS6-003 | Establish a quarterly competitor refresh process. | Source-backed matrix is refreshed from official docs; volatile metrics are timestamped or omitted. |
| WS6-004 | Add persona-specific getting-started guides. | At minimum: solo CLI user, team operator, tool/plugin author, and security reviewer. |
| WS6-005 | Publish a comparative "when not to use TeaAgent" page. | Honest non-fit scenarios include IDE-first teams, hosted cloud delegation needs, and zero-config beginner workflows. |

---

## Suggested Sequencing

1. WS0 claim hygiene and maturity labels.
2. WS1 run receipt MVP.
3. WS3 audit durability and strict claim gates.
4. WS2 batch timeout, budget inheritance, and isolation policy.
5. WS4 observability commands.
6. WS5 integration contracts.
7. WS6 positioning refresh.

---

## Definition Of Done For This Backlog

- New claims have evidence links and claim classes.
- Daily users can understand what happened in a run without reading source code.
- Local multi-agent execution has bounded time, budget, depth, and approval
  behavior.
- Audit failures are visible and fatal when the chosen mode requires it.
- Competitor comparisons use official/upstream sources and avoid stale volatile
  metrics.
- Docs index points to the current package instead of forcing readers to infer
  which dated file is authoritative.

---

## Stop Conditions

Do not pursue remote multi-agent product claims until WS2 safety gates pass. Do
not market enterprise-grade audit or sandbox guarantees until WS3 gates pass. Do
not expand plugin or provider surfaces until WS5 contracts are clear enough to
avoid duplicating runner policy in every integration.
