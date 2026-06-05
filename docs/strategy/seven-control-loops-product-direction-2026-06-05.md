# Seven Control Loops Product Direction - 2026-06-05

## Purpose

This strategy turns seven current agent-system themes into TeaAgent's product
direction. It builds on "malleable workflows with receipts" and makes the
control architecture explicit.

## North Star

TeaAgent should become a governed daily-driver agent harness where every form of
agent power has a corresponding control loop and receipt.

The control loops are:

| Control loop | What it controls | User trust question |
| --- | --- | --- |
| Spec-first | Direction | Did the agent build the right thing? |
| Dynamic workflow | Breadth | Can the agent gain new capabilities safely? |
| Loop / goal | Depth | Can the agent persist through hard work without drifting? |
| Model routing | Cost and quality | Did the right model do the right job at the right price? |
| Synthesis review | Truth | Did an independent review separate real findings from plausible claims? |
| Precise memory | Cross-session drift | Did the agent remember the right things and forget or quarantine the wrong things? |
| Human review gate | Irreversible risk | Did a human endorse the risky action with enough evidence? |

## Why This Matters Now

Agent products are no longer only competing on model capability. They are
competing on control systems:

- Spec Kit and Kiro make specs visible artifacts.
- Cline and OpenCode separate planning, building, subagents, and permissions.
- Pi and Codex make dynamic skills/extensions central to product value.
- Claude Code and Copilot add separate review agents.
- Claude, Kiro, and Codex all expose some form of persistent memory or steering.
- Recent research warns that agents can over-expand scope and misinfer least
  privilege.

TeaAgent should respond by making control loops first-class.

## Product Principle 1: Every Power Needs A Receipt

If a feature gives the agent more power, it must also generate a receipt:

| Power | Receipt |
| --- | --- |
| Write files | Diff, approval, pre-image, rollback path |
| Use skill | Skill source, activation cause, used-for-output evidence |
| Route model | Requested model, resolved model, reason, cost |
| Continue goal | Goal state, active tasks, blockers, context health |
| Read memory | Memory ID, scope, provenance, freshness |
| Promote memory | Human/review attestation and source run |
| Review output | Finding state, severity, verification, false-positive status |

No receipt means no trust claim.

## Product Principle 2: Spec-First Is A Control Surface, Not A Ritual

Spec-first should not mean writing docs before every typo fix. It should mean
that high-risk or ambiguous work has an explicit direction artifact before
mutating tools are allowed.

TeaAgent default:

- Small, obvious changes can proceed with an inline task summary.
- Multi-file, destructive, security-sensitive, or long-horizon work needs a spec
  or plan hash.
- The spec must name acceptance criteria and non-goals.
- The run must record which spec hash it implemented.

## Product Principle 3: Dynamic Workflow Is Allowed Through Quarantine

Users should be able to teach TeaAgent new skills, tools, and workflows from
inside a session. That is part of the product. But dynamic capability should not
silently become trusted memory.

TeaAgent default:

- Dynamic skills become candidates.
- Dynamic tools require schemas and risk annotations.
- Dynamic workflow changes are reviewed before persistent activation.
- Active skill directories are protected unless a development override is set.

## Product Principle 4: Goals Are State Machines

Hard work should be represented as a goal object, not a fragile conversation.

A goal should know:

- Objective.
- Bound spec.
- Task list.
- Current phase.
- Runs attached to it.
- Cost and token usage.
- Evidence artifacts.
- Memory entries created.
- Review gates passed.
- Blockers and next gate.

This is how TeaAgent can support long difficult tasks without relying on a
single context window.

## Product Principle 5: Model Routing Is A Budget Policy

Model routing should not be a hidden implementation detail. It controls money,
quality, and latency.

TeaAgent default:

- Plan/review/security/high-risk work can choose stronger models.
- Exploration and low-risk formatting can choose cheaper/faster models.
- Routing decisions are recorded.
- Policy can constrain allowed providers and models.
- Users can inspect model spend by role and task type.

## Product Principle 6: Review Is A Separate System

Synthesis review should not be the original agent saying "looks good." It should
be a separate pass with a different prompt, possibly a different model, and a
different evidence contract.

TeaAgent default:

- Reviewer has read-only permissions by default.
- Reviewer cites files, tests, docs, and sources.
- Reviewer classifies findings as verified, suspected, false positive, or needs
  human judgment.
- Reviewer cannot approve irreversible changes alone.

## Product Principle 7: Memory Is Scoped Evidence

Memory is dangerous when it becomes a vague pile of context. It is valuable when
it is precise, scoped, sourced, and reviewable.

TeaAgent default:

- Project rules belong in committed guidance docs.
- Session learnings belong in run-linked memory.
- Agent-written durable memory starts in quarantine unless low-risk.
- Memory has owner, source run, freshness, scope, and revocation path.
- Memory used in a run is recorded.

## Product Principle 8: Human Review Gates Must Be Cheap To Perform

Human review is necessary for irreversible risk, but bad review UX creates
rubber-stamp approvals. The system must prepare the evidence.

Gate packet:

- Spec hash.
- Diffs.
- Tool call list.
- Approval history.
- Model routing and cost.
- Tests and lint results.
- Review findings.
- Unresolved risks.
- Rollback path.

The human should decide, not reconstruct.

## Integration With Existing TeaAgent Thesis

Existing thesis:

> Malleable workflows with receipts.

Updated thesis:

> Malleable workflows with receipts, governed by seven control loops.

This keeps the project direction stable while making the control system more
explicit.

## Prioritized Adoption

### P0: Make Control Visible

- Add cross-loop docs and roadmap rows.
- Make current gaps explicit.
- Record which modules own each control.

### P1: Bind Spec, Goal, Review, And Memory

- Add goal object.
- Bind run to spec hash.
- Add synthesis review artifact.
- Add memory provenance and quarantine.

### P2: Optimize Cost And Dynamic Breadth

- Add role-based model routing receipts.
- Add dynamic workflow test harness.
- Add TUI control cockpit.

## What TeaAgent Should Not Copy

- Do not copy full-power extension systems without first-party governance.
- Do not copy memory systems that treat generated memory as always trusted.
- Do not copy review agents that add cost without producing closure evidence.
- Do not copy spec-first workflows that do not bind to repository facts.
- Do not copy model routing that is invisible to users.

## Product Differentiation

Competitors increasingly provide one or two strong loops:

- Kiro: strong spec loop.
- Pi: strong dynamic workflow loop.
- Codex: strong long-running multi-agent loop.
- Cline/OpenCode: clear mode and model routing controls.
- Claude/Copilot: strong review loop.
- Claude/Kiro/Codex: memory and steering.

TeaAgent's opportunity is to integrate all seven as one inspectable harness.

## Success Criteria

TeaAgent can claim this direction is real when a complex run can show:

1. The spec or exemption that controlled direction.
2. The dynamic skills/tools used and their governance state.
3. The goal state and loop history.
4. The model routing decisions and cost.
5. The synthesis review result.
6. The memory read/write/promote events.
7. The human review gate packet for risky actions.

## Bottom Line

The next product leap is not a larger feature list. It is tighter control over
agent autonomy. The seven loops give TeaAgent a way to expand capability while
making each expansion easier to inspect, review, and trust.
