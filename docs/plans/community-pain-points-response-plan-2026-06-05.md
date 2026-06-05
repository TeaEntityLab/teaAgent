# Community Pain Points Response Plan - 2026-06-05

## Purpose

This plan turns the community pain-point survey into concrete TeaAgent work. It
does not replace the seven-control-loop ledger. It explains why the current
highest-ROI work is user-visible control-plane evidence rather than more agent
surface area.

Primary evidence: `docs/analysis/community-agent-pain-points-survey-2026-06-05.md`.

## Strategy

The next work should optimize for trust closure:

1. Can the user see what influenced the agent?
2. Can the user see what the agent spent?
3. Can the user see whether a skill/tool/review actually ran?
4. Can the user see which memory or spec shaped the answer?
5. Can the user reject risky persistence or irreversible action with enough
   evidence?

If a feature does not improve one of those answers, defer it until Phase 1.

## Work Item Ledger

| ID | Priority | State | Pain addressed | Work item | Owner surface | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| CPP-P0-001 | P0 | Complete | Routing opacity, cost surprise | Add route evidence panel to run summary. | model routing / run evidence | Summary shows requested/resolved model, role, reason, fallback, and cost. |
| CPP-P0-002 | P0 | Complete | Long-task drift | Add goal checkpoint receipt. | runner / run store | Long task records objective, accepted plan/spec, current task, blockers, and next gate. |
| CPP-P0-003 | P0 | Complete | Memory pollution | Add memory write quarantine rule for agent-created project memory. | memory / approval | Agent-created durable project memory is pending review by default. |
| CPP-P0-004 | P0 | Complete | Review cost/noise | Add review artifact minimum schema. | review / subagents | Review cannot close without evidence paths, findings state, and residual risk. |
| CPP-P0-005 | P0 | Complete | Hook/permission confusion | Add approval authority receipt. | approval / audit | Every approved risky action records approving mechanism and exact scope. |
| CPP-P0-006 | P0 | Complete | Skill/MCP supply chain | Add dynamic asset provenance summary. | skills / MCP / audit | Run evidence shows loaded skills/MCP servers, source path, trust state, and revocation status. |
| CPP-P0-007 | P0 | Complete | Fake success | Add proof-of-use requirement for skill-backed outputs. | skills / runner | A skill-backed final answer links source artifact, command/tool call, output hash, and verification. |
| CPP-P0-008 | P0 | Complete | Overeager edits | Add intent-drift pre-write check for high-risk runs. | plan gate / policy | New files or broad edits outside accepted scope require explicit gate packet. |
| CPP-P1-001 | P1 | Complete | Review cost/noise | Add review repeat suppression. | review / evidence | Re-review identifies repeated findings and marks superseded or still-active state. |
| CPP-P1-002 | P1 | Complete | Cost surprise | Add phase budget thresholds. | budget / model routing | Plan, execute, review, and synthesis phases can warn or stop separately. |
| CPP-P1-003 | P1 | Complete | Context rot | Add context pressure score. | context bus / TUI | TUI shows stale files, token pressure, large artifacts, memory count, and compaction risk. |
| CPP-P1-004 | P1 | Complete | Memory poisoning | Add untrusted-source memory tests. | tests / memory | Web/tool/MCP output cannot become project memory without review. |
| CPP-P1-005 | P1 | Complete | Spec process overhead | Add risk-adaptive spec exemption UX. | plan gate / CLI | Low-risk tasks can proceed with explicit exemption receipt and no heavy spec ceremony. |
| CPP-P2-001 | P2 | Complete | Cross-agent observability | Add control-plane cockpit. | TUI | One panel summarizes route, memory, review, skill, spec, goal, approval, and cost. |

## Priority Rationale

### P0 first

P0 work is selected because it reduces real trust loss without requiring a new
agent framework:

- Route receipts are narrow and directly address cost/routing confusion.
- Goal checkpoints reduce long-session drift before more background automation.
- Memory quarantine prevents a class of future cross-session failures.
- Review artifacts make synthesis review inspectable rather than prose theater.
- Approval authority receipts protect TeaAgent's strongest differentiator.
- Dynamic asset provenance extends the skill lifecycle work already planned.
- Proof-of-use fixes the RSS failure class.
- Intent-drift checks address overeager agent behavior before broader autonomy.

### P1 next

P1 work improves ergonomics and scale:

- Repeat suppression keeps review from becoming noise.
- Phase budgets make spend predictable.
- Context pressure scoring makes long runs visible before they fail.
- Memory poisoning tests harden the new memory lifecycle.
- Spec exemptions prevent governance from becoming friction for tiny tasks.

### P2 later

P2 work turns the control plane into a polished daily-driver experience after
the receipt objects exist.

## Acceptance Test Plan

| Work item | Suggested test |
| --- | --- |
| CPP-P0-001 | `test_model_route_receipt_in_run_summary` |
| CPP-P0-002 | `test_long_goal_checkpoint_survives_resume` |
| CPP-P0-003 | `test_agent_memory_write_starts_pending_review` |
| CPP-P0-004 | `test_review_artifact_rejects_missing_evidence` |
| CPP-P0-005 | `test_approval_authority_receipt_exact_scope` |
| CPP-P0-006 | `test_dynamic_asset_provenance_in_run_evidence` |
| CPP-P0-007 | `test_skill_backed_output_requires_proof_of_use` |
| CPP-P0-008 | `test_intent_drift_blocks_out_of_scope_write` |
| CPP-P1-001 | `test_review_repeat_findings_marked_superseded` |
| CPP-P1-002 | `test_phase_budget_threshold_stops_review_fanout` |
| CPP-P1-003 | `test_context_pressure_score_lists_sources` |
| CPP-P1-004 | `test_untrusted_tool_output_cannot_promote_memory` |
| CPP-P1-005 | `test_low_risk_spec_exemption_receipt` |

## Integration With Seven Control Loops

| Community pain work | Existing seven-control work |
| --- | --- |
| CPP-P0-001 | SCL-P0-005 |
| CPP-P0-002 | SCL-P0-004 |
| CPP-P0-003 | SCL-P1-001, SCL-P1-002 |
| CPP-P0-004 | SCL-P0-006 |
| CPP-P0-005 | SCL-P0-007 |
| CPP-P0-006 | DSK-P0-001, DSK-P0-002, SCL-P0-003 |
| CPP-P0-007 | DSK-P0-003, DSK-P0-004 |
| CPP-P0-008 | SCL-P0-001, SCL-P0-002, SCL-P0-007 |

## Documentation Updates Required During Implementation

- Update `docs/daily-driver-current-status.md` when a pain point becomes fixed
  or verified.
- Update `docs/roadmap-status.md` when any CPP item moves out of Proposed.
- Update the relevant module `risks.md` when memory, model routing, approval,
  skill, or review ownership changes.
- Add evidence links to the run/test names in this plan when tests land.

## Risks

- A route receipt can become another wall of text if not summarized well.
- Memory quarantine can frustrate users if promotion UX is too slow.
- Review artifacts can create process drag if every small task needs them.
- Intent-drift gates can block useful refactors if scope language is too
  brittle.
- Cost estimates can be misleading when providers expose incomplete usage data.

## Decision

Adopt the community pain points as a control-plane roadmap overlay, not as a
request to add more autonomous features immediately. TeaAgent should first make
existing autonomy observable, reviewable, budgeted, and reversible.
