# Daily-Driver Complete Work Plan: Risk, Feasibility, and ROI

Date: 2026-06-04

## Purpose

This document turns the current evidence corpus into a prioritized execution plan for making TeaAgent more useful as a daily agent harness across TUI mode, TUI chat mode, CLI chat, and agent mode.

It uses four inputs:

1. repository evidence from current docs, tests, and code paths
2. high-risk findings from the daily-driver and security review corpus
3. competitor signals from Pi, OpenCode, Claude Code, Codex, Aider, and OpenHands
4. investment judgment: risk reduction, feasibility, user value, and strategic return

The plan favors work that makes TeaAgent boringly trustworthy before work that only makes it broader.

## Decision Thesis

TeaAgent should invest first in **trust-path coherence**.

The project already has a strong governance identity: permissions, audit, budgets, undo, run evidence, skills, MCP, and multi-agent workflows. The next value jump does not come from adding another large feature family. It comes from ensuring that daily users can predict what the agent will do, what it cost, what it changed, how to undo it, and which run record proves it.

The most cost-effective path is:

1. close surface drift on TUI/CLI chat semantics
2. make cost, undo, root, approvals, and resume honest across surfaces
3. harden evidence and trust boundaries
4. simplify first-hour guidance
5. expand ecosystem features only after the trust path is stable

## Scoring Model

| Field | Meaning |
|---|---|
| User value | How much this improves daily use, onboarding, or confidence. |
| Risk reduction | How much this reduces data loss, wrong-repo work, false state, cost surprise, or governance bypass. |
| Strategic leverage | How much this strengthens TeaAgent's differentiation against competitors. |
| Feasibility | How likely the work is to land safely with current code and tests. |
| Effort | Rough implementation size. |
| ROI | Combined return after considering value, risk reduction, leverage, feasibility, and effort. |

Qualitative scores:

| Score | Meaning |
|---|---|
| Very high | Do first unless blocked. |
| High | Important and worth scheduling soon. |
| Medium | Valuable after the trust path is stable. |
| Low | Keep as backlog or opportunistic cleanup. |

## Priority Stack

| Priority | Workstream | ROI | Risk | Feasibility | Why this rank |
|---|---|---|---|---|---|
| P0-A | TUI / CLI semantic parity | Very high | High | Medium-high | Same command must mean same trust semantics across daily surfaces. |
| P0-B | Cost and budget truth | Very high | High | High | Fake or stale cost is a direct trust failure and relatively bounded to verify. |
| P0-C | Undo and recovery honesty | Very high | High | Medium | Recovery confusion can damage user work; wording and behavior must align. |
| P0-D | Root and approval-scope truth | Very high | Critical | Medium-high | Wrong repo or broad approval is the shortest path to severe user harm. |
| P1-A | Resume/background lifecycle repair | High | High | Medium | Run ids should be durable continuity handles, not confusing strings. |
| P1-B | Run evidence and audit completeness | High | High | Medium | TeaAgent's differentiation depends on evidence that users can inspect. |
| P1-C | Controller persistence error handling | High | Medium-high | High | Silent persistence failure undermines undo and run history. |
| P1-D | First-hour onboarding and recovery copy | High | Medium | High | Low-cost improvement that makes the existing system usable faster. |
| P2-A | MCP, skills, and subagent trust hardening | High | Critical | Medium | Essential before ecosystem expansion; higher blast radius and more moving parts. |
| P2-B | Docs as control plane | Medium-high | Medium | High | Keeps the large corpus useful and reduces future drift. |
| P2-C | Competitor refresh loop | Medium | Medium | High | Maintains strategy quality but does not fix runtime trust by itself. |
| P3-A | Breadth expansion and packaging | Medium | Medium | Medium | Valuable after the daily-driver trust path is no longer noisy. |

## Workstream Plans

### P0-A: TUI / CLI Semantic Parity

**Goal:** The TUI, TUI chat, CLI chat, and agent mode should share the same meaning for task execution, cost, undo, root, approval, resume, and run evidence.

**Evidence**

- `ChatSessionController` exists to unify result handling, cost tracking, and undo.
- The TUI still has local state and fallback mechanisms that can diverge from controller truth.
- Prior audits repeatedly found that tests can pass while active interactive paths remain untested.

**Feasibility**

Medium-high. The shared controller already exists, so the work is mostly migration, tests, and wording cleanup rather than new architecture.

**Risks**

- TUI tests may assert helper state instead of command-path behavior.
- Migrating too much at once could obscure regressions.
- Fallback checkpoint restore may still be needed, so wording must be explicit.

**ROI**

Very high. This is the work that turns TeaAgent from "many capable surfaces" into "one coherent operator experience".

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P0-A-001 | Add or refresh headless command-path tests for TUI `ask`, `run`, `/cost`, `/undo`, `root`, and `resume`. | Tests fail if the TUI bypasses shared state or injects the asserted state directly. |
| P0-A-002 | Move remaining TUI task execution semantics behind controller-owned state where practical. | Cost, observations, final answer, and undo state come from one source. |
| P0-A-003 | Keep fallback behavior explicit. | Output says whether journal undo or checkpoint restore was used. |
| P0-A-004 | Update help text and daily-driver docs after behavior is proven. | Docs and active command behavior agree. |

### P0-B: Cost and Budget Truth

**Goal:** No daily surface should show a fake zero, stale local value, or unverified cost claim.

**Evidence**

- Cost display was a repeated daily-driver finding.
- Recent fixes improved controller-backed cost state, but docs still warn against treating helper-only tests as proof.
- Competitor feedback repeatedly shows cost surprise as a user trust issue.

**Feasibility**

High. The scope is bounded: shared controller state, run result cost fields, display formatting, and regression tests.

**Risks**

- Some adapters may not provide reliable cost.
- A single session may combine estimated and actual values.
- Budget caps may still use zero to mean "unlimited", which must be explicit.

**ROI**

Very high. Users immediately notice cost displays, and accurate cost is one of TeaAgent's strongest governance promises.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P0-B-001 | Define display states: actual, estimated, unavailable, unlimited cap. | UI never implies actual cost when it only has estimate or no value. |
| P0-B-002 | Add tests for task-driven TUI cost accumulation. | Running a mocked task with known cost changes `/cost` through the active command path. |
| P0-B-003 | Align `/budget`, run summary, and evidence bundle terminology. | Same run shows the same cost and cap semantics across surfaces. |
| P0-B-004 | Update current-status and known-issues docs after tests pass. | No stale warning remains for a fixed path. |

### P0-C: Undo and Recovery Honesty

**Goal:** Users should know exactly what will be undone, which mechanism is used, and whether unrelated manual work is safe.

**Evidence**

- CLI chat moved to journal-based undo.
- TUI still has checkpoint fallback behavior.
- Prior reviews treat undo ambiguity as a data-loss risk.

**Feasibility**

Medium. The behavior exists but must be made visible and tested across fallback paths.

**Risks**

- Journal undo and checkpoint restore have different blast radii.
- Deleting stale undo journals or checkpoint refs incorrectly can remove recovery evidence.
- Over-simplified wording can hide real mechanism differences.

**ROI**

Very high. Recovery is a core trust promise and a direct differentiator from lighter agents.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P0-C-001 | Add undo preview or mechanism label before restore where feasible. | User can see journal versus checkpoint scope before or immediately after action. |
| P0-C-002 | Add regression tests for journal undo and checkpoint fallback. | Both paths are covered and named in output. |
| P0-C-003 | Update recovery docs with mechanism-specific language. | Docs stop using one generic "undo" for multiple blast radii. |
| P0-C-004 | Ensure run evidence records undo availability and outcome. | Evidence bundle can answer "was this reversible?". |

### P0-D: Root and Approval-Scope Truth

**Goal:** The agent must operate in the intended workspace and approval scope must be understandable before destructive work.

**Evidence**

- Stale root state was a red-team scenario and a high-priority daily-driver risk.
- Approval without path scope weakens the governance story.
- Wrong-repo work and over-broad approval are high-impact failures.

**Feasibility**

Medium-high. Root precedence is relatively bounded; approval scope may require more review.

**Risks**

- Persisted TUI state can conflict with explicit command arguments.
- Broad tool approvals may be legitimate in advanced workflows but dangerous as accidental defaults.
- Changing approval prompts can affect tests and user muscle memory.

**ROI**

Very high. These are small surfaces with large blast radius.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P0-D-001 | Keep explicit root stronger than saved state and test it. | Saved root A cannot override explicit root B. |
| P0-D-002 | Reject or clearly classify empty path-scoped approvals. | No ambiguous path grant silently becomes broad approval. |
| P0-D-003 | Surface active root and approval scope in cockpit and run evidence. | User can inspect both without reading logs. |
| P0-D-004 | Add examples to the permission playbook. | Common approval scenarios show exact scope and safe alternative. |

### P1-A: Resume and Background Lifecycle Repair

**Goal:** `resume`, `attach`, `background`, `suspend`, and `interactive-review` should have distinct behavior and wording.

**Evidence**

- Existing docs warn that some lifecycle copy is ahead of implementation.
- Agent-mode run ids should become durable continuity handles.
- Competitors increasingly support long-running tasks and background workflows.

**Feasibility**

Medium. Some work is copy and command grammar; full resume requires state correctness.

**Risks**

- A command may look like resume but start a new task.
- Storing enough state for resume may expose privacy or stale-authority questions.
- Approval continuity across resume needs careful policy design.

**ROI**

High. This supports daily use and agent mode without adding a new feature category.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P1-A-001 | Remove or correct commands that imply background execution when only suspension exists. | Help text no longer suggests unsupported lifecycle behavior. |
| P1-A-002 | Make `agent run --background <run_id>` refuse with a helpful hint if that is not the resume path. | Run ids are not treated as fresh tasks. |
| P1-A-003 | Define resume state contract. | A run record states whether it is resumable, review-only, or archived. |
| P1-A-004 | Add acceptance around suspend to review to resume or refusal. | User sees clear state transitions. |

### P1-B: Run Evidence and Audit Completeness

**Goal:** Every meaningful run should answer what happened, what changed, what was approved, what it cost, what was tested, and what remains uncertain.

**Evidence**

- The strategic direction is "malleable workflows with receipts".
- Existing docs already treat run evidence as a differentiator.
- Security review found audit integrity and completeness risks.

**Feasibility**

Medium. Some evidence fields exist; completeness and presentation need hardening.

**Risks**

- Audit logs can be too raw for daily users.
- Over-promising "tamper evidence" without strong key management can mislead.
- Sensitive data redaction must remain conservative.

**ROI**

High. Evidence is TeaAgent's product moat.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P1-B-001 | Define a run evidence completeness checklist. | Successful, failed, cancelled, and pending-approval runs all have expected evidence fields. |
| P1-B-002 | Add `verified`, `claimed`, `not_tested`, and `known_failure` categories to user-facing summaries where missing. | Final output does not blur proof levels. |
| P1-B-003 | Add audit completeness checks to post-run or validation workflow. | Missing critical events are surfaced. |
| P1-B-004 | Keep redaction tests near evidence rendering. | Sensitive values do not leak through summaries. |

### P1-C: Controller Persistence Error Handling

**Goal:** Persistence and undo-journal save failures should not be silently swallowed as mock-only errors.

**Evidence**

- `ChatSessionController` currently catches `AttributeError` and `TypeError` around store and undo persistence.
- Prior docs classify this as a recoverability risk.

**Feasibility**

High. This is a narrow code path with clear tests.

**Risks**

- Existing tests may rely on permissive mock behavior.
- Surfacing errors too aggressively may break otherwise successful chat runs.

**ROI**

High. Low-to-medium effort, strong improvement to recoverability honesty.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P1-C-001 | Replace broad mock-detection catches with explicit test/mocking seams or classified warnings. | Real persistence failures are visible. |
| P1-C-002 | Add tests for store save failure and undo save failure. | Failure produces actionable output or structured evidence. |
| P1-C-003 | Update risk docs after behavior is proven. | CG-13 moves to verify/close or fixed. |

### P1-D: First-Hour Onboarding and Recovery Copy

**Goal:** A new daily user should reach a safe first success without reading the full architecture.

**Evidence**

- Existing docs call out first-hour e2e and actionable recovery as productization gaps.
- Competitor docs lead with short setup and first command flows.
- TeaAgent's docs corpus is deep enough that entry points matter.

**Feasibility**

High. Mostly docs, help text, and acceptance alignment.

**Risks**

- Simplifying copy can accidentally overclaim stability.
- Guide updates can drift unless linked to active status docs.

**ROI**

High. High user value for low implementation cost.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P1-D-001 | Update the current-status front door with the new complete plan link. | Users can find the recommended roadmap from the daily entry point. |
| P1-D-002 | Keep setup, first read-only run, first chat run, and recovery commands in one path. | First-hour guide does not require reading analysis docs. |
| P1-D-003 | Add common error recovery examples. | Provider missing, read-only write block, budget exceeded, undo unavailable, and approval blocked have next actions. |

### P2-A: MCP, Skills, and Subagent Trust Hardening

**Goal:** Ecosystem expansion should not weaken TeaAgent's governance story.

**Evidence**

- The module risk index lists MCP tool injection, native skill execution, and subagent isolation risks.
- Pi's ecosystem shows that bolt-on permissions fragment quickly.
- TeaAgent differentiates by making governance first-party.

**Feasibility**

Medium. The work touches multiple trust boundaries and needs careful tests.

**Risks**

- Tightening defaults can break existing user workflows.
- MCP and skills may have different trust models and cannot be treated identically.
- Subagent isolation changes can be platform-dependent.

**ROI**

High, but after P0/P1 daily trust repairs. This is strategic hardening before broader ecosystem growth.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P2-A-001 | Enforce MCP trust expiry at call time. | Expired trust entries cannot authorize tools. |
| P2-A-002 | Make skill isolation downgrade visible. | User can see when WASM/Docker isolation is unavailable and native execution is used. |
| P2-A-003 | Harden subagent approval inheritance and workspace copy rules. | Child agents do not silently inherit unsafe authority or copy secrets. |
| P2-A-004 | Add security review checklist entries for extension changes. | Future PRs have a clear trust-boundary gate. |

### P2-B: Docs As Control Plane

**Goal:** Keep the documentation corpus navigable, truthful, and execution-oriented.

**Evidence**

- The docs package review explicitly warns that more docs can hide implementation work.
- The governance docs now define status, ownership, and evidence-to-principle policy.
- Dated docs are valuable but can conflict without supersession rules.

**Feasibility**

High. This is mostly disciplined editing and validation.

**Risks**

- New docs can multiply faster than readers can use them.
- Index edits can become stale if not validated.

**ROI**

Medium-high. Strong leverage for maintainer continuity, but does not directly repair runtime behavior.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P2-B-001 | Add supersession notes to high-traffic outdated docs. | Reader can tell current truth from history. |
| P2-B-002 | Keep the plan index, review index, and current-status page connected. | No new major plan is orphaned. |
| P2-B-003 | Add a monthly docs drift review checklist. | Evidence docs either point to current truth or remain clearly archival. |

### P2-C: Competitor Refresh Loop

**Goal:** Maintain external awareness without becoming reactive.

**Evidence**

- Competitor survey and Pi review both influenced the current strategic direction.
- Agent products move quickly, so static comparison ages fast.

**Feasibility**

High, if kept bounded.

**Risks**

- Community feedback can overrepresent power users.
- The project may copy surface features instead of extracting durable lessons.

**ROI**

Medium. Useful for strategy; not a replacement for local evidence.

**Concrete tasks**

| Task | Description | Acceptance |
|---|---|---|
| P2-C-001 | Refresh official docs and release-note signals quarterly. | Date and source boundary are explicit. |
| P2-C-002 | Keep community feedback labeled as signal, not fact. | Strategy docs distinguish evidence from sentiment. |
| P2-C-003 | Convert new signals into acceptance gaps only when they affect daily use. | No roadmap churn from novelty alone. |

### P3-A: Breadth Expansion and Packaging

**Goal:** Expand only after the daily trust path is stable.

**Candidate areas**

- session branching
- skill development loop
- richer session viewer
- desktop/client-server packaging
- hosted/background task guides
- broader provider handoff workflows

**Feasibility**

Medium. Some foundations already exist, but each area could expand scope quickly.

**Risks**

- Breadth can hide trust drift.
- Packaging work can dominate without improving core usefulness.
- New surfaces create new parity obligations.

**ROI**

Medium now, higher after P0/P1 are done.

## Recommended Execution Order

### Phase 0: Two-week trust repair batch

1. P0-B cost and budget truth
2. P0-A TUI / CLI semantic parity
3. P0-C undo and recovery honesty
4. P0-D root and approval-scope truth
5. P1-C controller persistence error handling

**Exit criteria**

- `tests/test_tui.py`, chat CLI tests, and docs consistency checks pass.
- Active daily surfaces no longer show misleading cost, undo, root, or approval state.
- Current-status docs match runtime behavior.

### Phase 1: Evidence and lifecycle batch

1. P1-A resume/background lifecycle repair
2. P1-B run evidence and audit completeness
3. P1-D first-hour onboarding and recovery copy
4. P2-B docs as control plane

**Exit criteria**

- Run ids have clear states: resumable, review-only, pending approval, failed, completed, archived.
- User-facing summaries distinguish verified from claimed behavior.
- A new user can follow the first-hour path without reading the audit corpus.

### Phase 2: Ecosystem hardening batch

1. P2-A MCP, skills, and subagent trust hardening
2. P2-C competitor refresh loop
3. targeted P3-A expansion only after explicit review

**Exit criteria**

- Extension and MCP trust behavior is enforced and visible.
- Subagent authority and isolation are bounded.
- New ecosystem work has an explicit governance and receipt plan.

## Work That Should Wait

| Work | Wait condition |
|---|---|
| Full desktop/client-server packaging | Wait until TUI/CLI daily parity is stable. |
| Large new agent framework or orchestration layer | Avoid unless an ADR proves existing primitives cannot support the need. |
| Large visual TUI redesign | Wait until state correctness is boring. |
| Aggressive skill marketplace work | Wait until skill trust, isolation, and provenance are stronger. |
| Hosted/cloud task expansion | Wait until local run evidence and lifecycle states are clear. |

## Risk Review

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Docs grow faster than implementation | Medium | Medium-high | Every new plan must create tasks or acceptance checks. |
| TUI parity work becomes broad rewrite | Medium | High | Slice by behavior: cost, undo, root, resume, approval. |
| Cost source remains adapter-dependent | Medium | High | Label actual/estimated/unavailable states explicitly. |
| Undo cleanup deletes recovery data | Low-medium | High | Add tests before changing journal/checkpoint lifecycle. |
| Approval tightening breaks advanced workflows | Medium | Medium | Separate accidental broad grants from explicit global/tool grants. |
| MCP/skill hardening breaks ecosystem compatibility | Medium | Medium-high | Add migration docs and compatibility tests. |
| Competitor chasing dilutes identity | Medium | Medium | Require every competitor lesson to map to TeaAgent principles. |

## ROI Reflection

The highest ROI work is not the flashiest work. It is the work that prevents users from asking:

- Which repo did it touch?
- What did this cost?
- Can I undo it safely?
- Why was this tool allowed?
- Is this run actually resumable?
- What evidence proves the final answer?

Every time TeaAgent answers one of those questions clearly, the project becomes more valuable than a raw agent wrapper. Every time it answers vaguely, the governance story weakens.

## Definition of Done For This Plan

The plan is considered actionable when:

1. each P0/P1 workstream has at least one concrete testable task
2. priority order reflects risk, feasibility, and ROI
3. high-risk items have human review gates
4. docs indexes point to this plan
5. future maintainers can trace each priority to repository evidence

## Source Documents

- [docs/analysis/teaagent-evidence-ledger-2026-06-04.md](../analysis/teaagent-evidence-ledger-2026-06-04.md)
- [docs/analysis/competitor-signal-survey-2026-06-04.md](../analysis/competitor-signal-survey-2026-06-04.md)
- [docs/strategy/teaagent-product-principles-2026-06-04.md](../strategy/teaagent-product-principles-2026-06-04.md)
- [docs/strategy/daily-driver-roadmap-rationale-2026-06-04.md](../strategy/daily-driver-roadmap-rationale-2026-06-04.md)
- [docs/reviews/daily-driver-critique-and-counterarguments-2026-06-04.md](../reviews/daily-driver-critique-and-counterarguments-2026-06-04.md)
- [docs/work-log/roadmap-work-items-2026-06-04.md](../work-log/roadmap-work-items-2026-06-04.md)
- [docs/plans/daily-driver-implementation-sequencing-board-2026-06-02.md](daily-driver-implementation-sequencing-board-2026-06-02.md)
- [docs/plans/daily-driver-usefulness-master-plan-2026-06-01.md](daily-driver-usefulness-master-plan-2026-06-01.md)
