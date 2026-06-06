# System Review Reasoning Ledger - TeaAgent
# 2026-06-06

> **Purpose:** Record the public reasoning path behind the June 6, 2026
> multi-angle system review.
>
> This is not a private chain-of-thought transcript. It is a reviewable ledger of
> questions, evidence, inferences, counterarguments, and work directions that can
> be audited by maintainers.

---

## Method

1. Read the repository operating instructions, documentation index, and current
   dated review package.
2. Inspected the existing June 6 analysis drafts for engineering architecture,
   multi-agent coordination, conversation UX, risk, deployment, integration,
   performance, and competitive positioning.
3. Checked code anchors at HEAD `ad5e2d7` for runner behavior, approval policy,
   audit logging, subagent management, TUI/chat commands, tool registry, provider
   adapters, run storage, plugin discovery, and memory catalog boundaries.
4. Refreshed competitor context from official or upstream documentation where
   possible.
5. Separated stable evidence from inference, volatile claims, and unknowns.
6. Converted the critique into workstreams instead of treating it as a single
   abstract improvement request.

---

## Core Critical Questions

### Q1. Is TeaAgent still a thin governed harness, or has it become a broad agent framework?

**Evidence**

- `pyproject.toml` marks the package as `Development Status :: 3 - Alpha`.
- The repository contains hundreds of Python files and broad optional extras for
  TUI, code analysis, OAuth, telemetry, GraphQLite, and developer tooling.
- `teaagent/runner/_core.py` owns the central agent loop, phase budget checks,
  tool approval transitions, and final result handling.
- Chat and TUI behavior still reach across cost state, command dispatch,
  compacting, approvals, and background/session semantics.

**Inference**

TeaAgent has a credible governed-harness core, but the surrounding product
surface is already broad enough that users may experience it as a general agent
framework. That is not automatically wrong, but it makes the "thin harness"
claim fragile unless the stable core, experimental features, and integration
surfaces are explicitly labeled.

**Counterargument**

An alpha system often needs broad experiments before the durable architecture is
obvious. Prematurely narrowing the surface could discard useful discoveries.

**Work Direction**

Define a stable-core boundary and maturity labels for runner, audit, approval,
tools, providers, subagents, TUI, memory, plugins, and remote orchestration.

---

### Q2. Can the current multi-agent model support remote or high-concurrency teams?

**Evidence**

- `teaagent/subagents/_types.py` defaults subagent isolation to `shared`.
- `teaagent/subagents/_manager.py` caps child permission at `workspace-write`,
  but some validation is tied to resolved subagent definitions and local
  execution assumptions.
- `teaagent/subagents/_tools.py` uses batch execution with `as_completed(...)`
  and no obvious batch-level timeout at the coordination layer.
- `teaagent/subagents/_approval_queue.py` stores approval queues in process
  memory.
- `teaagent/swarm.py` implements another coordination path with its own
  executor and timeout model.
- Competitors with explicit remote/delegated workflows emphasize sandboxes,
  sessions, pull requests, branch isolation, spec context, or hosted task
  execution.

**Inference**

The current design is useful for local bounded delegation, but it should not be
marketed as remote-team-ready. Remote multi-agent work needs durable queues,
stronger isolation defaults, inherited budget envelopes, bounded batch
deadlines, explicit workspace ownership, and one coordination contract rather
than parallel orchestration systems.

**Counterargument**

TeaAgent's local-first posture can be a deliberate differentiator. It does not
need to copy cloud agents to be valuable.

**Work Direction**

Keep local-first as the default, but harden the multi-agent contract before
adding remote claims: safer default isolation, durable approval state, global
depth/concurrency gates, explicit budget inheritance, and a clear manager
unification plan.

---

### Q3. Would a normal developer understand what the agent is doing during a conversation?

**Evidence**

- The TUI exposes many commands, including approval, compaction, cost, background
  handling, and session controls.
- Approval flows can require users to reason about tool call IDs or internal
  execution state.
- Background/suspension wording is easy to misread as live remote execution even
  when the implementation is checkpoint-oriented.
- Cost is visible, but cost state is partly session/controller dependent.

**Inference**

The conversation surface is powerful for expert operators, but daily users need
more legible receipts, progress language, and approval prompts. The biggest UX
gap is not command availability; it is making state transitions explain
themselves without requiring the user to learn implementation vocabulary.

**Counterargument**

Advanced CLI/TUI users tolerate complexity when the system is transparent and
scriptable.

**Work Direction**

Add a human-readable run receipt, default progress summaries, approval by
readable selectors, clearer background/resume language, and a consolidation plan
for overlapping chat surfaces.

---

### Q4. Are the trust and security claims proportionate to the implementation?

**Evidence**

- `teaagent/approval_manager.py` has named permission modes and path checks for
  destructive operations.
- `teaagent/tools.py` requires registered tools with schemas and annotations.
- `teaagent/audit.py` records events and includes chain integrity checks, but it
  can cool down disk write failures and retain events in memory.
- `teaagent/audit_chain.py` preserves compatibility for legacy chain reset
  lines.
- The project is explicitly alpha.

**Inference**

TeaAgent has meaningful trust primitives for a local single-user harness, but it
should avoid broad enterprise or multi-tenant security claims. The current trust
story is strongest when framed as auditable local governance, not as a complete
production sandbox.

**Counterargument**

The presence of audit, schema, approval, and permission concepts gives TeaAgent a
stronger foundation than many lightweight agent tools.

**Work Direction**

Introduce claim classes for trust guarantees, fail loudly on audit durability in
compliance mode, add strict chain verification for new logs, broaden path/schema
containment tests, and document explicit non-goals.

---

### Q5. Where does TeaAgent plausibly beat competitors?

**Evidence**

- Official competitor documentation highlights strong surfaces for IDE use,
  hosted cloud delegation, PR workflows, spec-first development, Docker
  sandboxes, terminal simplicity, or mode-based tool governance.
- TeaAgent's distinctive assets are local provider independence, explicit tool
  schemas, audit logs, approval policy concepts, budget controls, MCP-style
  registry structure, skill/plugin aspirations, and documentation-heavy
  governance.

**Inference**

TeaAgent should not try to win the first impression against IDE-native or hosted
cloud products. It can credibly compete where teams need a local-first,
provider-agnostic, inspectable harness with governance and audit as first-class
features.

**Counterargument**

Governance is only compelling if the daily experience is not frustrating. A tool
that is safer but harder to use will still lose many users.

**Work Direction**

Turn governance into an operator-visible product artifact: a run receipt that
shows goal, model/provider, budget, tools, approvals, files touched, tests run,
audit path, cost, and resume state.

---

### Q6. Are the current documents clarifying maturity or hiding it?

**Evidence**

- The repository contains many dated analysis, review, plan, and strategy files.
- `docs/INDEX.md` intentionally acts as the curated front door rather than an
  exhaustive file list.
- The June 6 review drafts were substantial, but some competitive tables included
  volatile market data that needs same-day refresh before reuse.

**Inference**

The documentation corpus is a strength if it clearly distinguishes canonical
truth from dated reasoning. It becomes a liability when old competitor facts,
aspirational claims, and current implementation evidence appear side by side
without freshness rules.

**Counterargument**

Dated documents are valuable precisely because they preserve reasoning trails
and expose how conclusions changed.

**Work Direction**

Keep dated reasoning trails, but add package indexes, source-backed matrices,
reasoning ledgers, supersession notes, and validation checks for current-truth
links.

---

## Open Questions

| Question | Why It Matters | Current Status |
| --- | --- | --- |
| Which surfaces are considered supported for daily users today? | Sets release claims and support burden. | Partially answered by daily-driver docs; needs alignment with June 6 critique. |
| Should remote agents be a product goal or an explicit non-goal for Phase 0/1? | Determines whether to invest in durable queues and sandbox orchestration now. | Unresolved; current code should stay local-first until hardened. |
| What is the minimum trust receipt that makes TeaAgent visibly different? | Converts hidden governance into user value. | Proposed in work directions; not implemented here. |
| Which competitor facts must be refreshed on every positioning update? | Prevents stale star/pricing/model claims. | Source-backed matrix now records the rule. |
| Which audit failures must become fatal in compliance mode? | Separates best-effort local logging from real governance claims. | Needs engineering design and tests. |

---

## Review Outcome

The strongest near-term direction is not "add more agent features." It is to
make the existing governance visible, bounded, and pleasant:

1. Correct maturity and competitor claims.
2. Give every run a readable receipt.
3. Harden local multi-agent execution before remote claims.
4. Make audit and approval guarantees explicit and testable.
5. Keep integrations pluggable, but define stable contracts before expanding
   plugin surface area.
6. Treat documentation as a product surface with current-truth indexes and dated
   evidence trails.
