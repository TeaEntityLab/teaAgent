# Seven Control Loops Work Items - 2026-06-05

## Purpose

This ledger turns the seven-control-loop strategy into concrete tasks. It
extends, not replaces, the dynamic skill and roadmap ledgers.

Canonical states follow `docs/governance/document-state-model.md`.

## Work Item Ledger

| ID | Priority | State | Control loop | Work item | Owner surface | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| SCL-P0-001 | P0 | Complete | Spec-first | Add spec binding to high-risk runs. | plan gate / runner | High-risk mutating run records `spec_id` and `spec_hash` or explicit exemption. |
| SCL-P0-002 | P0 | Complete | Spec-first | Add repository grounding check for specs. | docs/specs / plan gate | Spec-to-plan transition records files searched and assumptions confirmed. |
| SCL-P0-003 | P0 | Complete | Dynamic workflow | Link dynamic skill lifecycle work as first H3 proof. | skills | DSK-P0 items remain the first ecosystem-trust spine. |
| SCL-P0-004 | P0 | Complete | Loop / goal | Define persisted goal record. | run store / context bus | Goal links objective, spec, tasks, runs, blockers, cost, review, and evidence. |
| SCL-P0-005 | P0 | Complete | Model routing | Add `model_route` audit receipt. | model routing / budget | Run evidence records requested model, resolved model, route reason, policy source, estimate, and actual cost. |
| SCL-P0-006 | P0 | Complete | Synthesis review | Define synthesis review artifact. | subagents / review | Review findings have state, severity, evidence path, and false-positive handling. |
| SCL-P0-007 | P0 | Complete | Human review | Define human review gate packet. | approval / policy | Irreversible paths expose spec, diff, tools, cost, tests, risks, and rollback. |
| SCL-P1-001 | P1 | Complete | Precise memory | Add typed memory metadata. | memory | Memory entries have scope, owner, source run, freshness, TTL, confidence, and review state. |
| SCL-P1-002 | P1 | Complete | Precise memory | Add memory quarantine/promote flow. | memory / CLI | Agent-written durable memory requires review before project-wide use. |
| SCL-P1-003 | P1 | Complete | Loop / goal | Add `teaagent goal status`. | CLI / run store | CLI shows objective, active phase, cost, blockers, and next gate. |
| SCL-P1-004 | P1 | Complete | Model routing | Add role routing tests. | tests / model routing | Plan, execution, review, and security roles resolve expected model classes. |
| SCL-P1-005 | P1 | Complete | Synthesis review | Add high-risk review requirement. | runner / governance | High-risk goal cannot close without synthesis review or documented waiver. |
| SCL-P1-006 | P1 | Complete | Human review | Attach gate packet to skill install and memory promotion. | skills / memory / approval | Risky persistence changes cannot proceed without review packet. |
| SCL-P2-001 | P2 | Complete | All loops | Add TUI control cockpit. | TUI | TUI summarizes spec, goal, model, memory, review, and gates for active run. |
| SCL-P2-002 | P2 | Complete | All loops | Add release evidence bundle. | release / docs | Release bundle includes seven-loop evidence status. |
| SCL-P2-003 | P2 | Complete | All loops | Add control-loop freshness validator. | docs validation | Current docs fail if roadmap rows omit control-loop links or status. |

## P0 Execution Detail

### SCL-P0-001: Spec binding

Implementation intent:

- Treat spec-first as a run contract for risky work.

Acceptance:

- A high-risk mutating run without spec or exemption fails before write.
- A small typo-style run can carry `spec_exemption: small_clear_task`.
- Run summary prints the bound spec path and hash.

### SCL-P0-004: Goal record

Minimum fields:

- `goal_id`
- `objective`
- `status`
- `spec_id`
- `spec_hash`
- `task_ids`
- `run_ids`
- `cost_cents`
- `memory_ids`
- `review_ids`
- `human_gate_ids`
- `blockers`
- `next_gate`

Acceptance:

- A multi-run task can be inspected without replaying the full chat transcript.

### SCL-P0-005: Model route receipt

Minimum fields:

- `requested_provider`
- `requested_model`
- `resolved_provider`
- `resolved_model`
- `role`
- `routing_reason`
- `policy_source`
- `estimated_cost_cents`
- `actual_cost_cents`
- `fallback_used`

Acceptance:

- A reviewer can explain why a model was used and how much it cost.

### SCL-P0-006: Synthesis review artifact

Minimum fields:

- `review_id`
- `target_run_id`
- `target_goal_id`
- `reviewer_role`
- `model_route_id`
- `files_reviewed`
- `commands_reviewed`
- `tests_reviewed`
- `findings`
- `residual_risk`
- `recommended_gate_state`

Finding states:

- `proposed`
- `verified`
- `rejected`
- `false_positive`
- `needs_human`
- `fixed`
- `superseded`

Acceptance:

- A review can fail because it lacks enough evidence.

### SCL-P0-007: Human review gate packet

Minimum fields:

- `gate_id`
- `risk_reason`
- `irreversible_action`
- `spec_hash`
- `diff_summary`
- `tool_calls`
- `model_routes`
- `cost_summary`
- `tests`
- `review_findings`
- `rollback_path`
- `approver`
- `decision`

Acceptance:

- The human sees the evidence before approving.

## Test Plan

| Test | Layer | Why |
| --- | --- | --- |
| High-risk run requires spec or exemption | Acceptance | Proves spec-first is a gate. |
| Model route receipt emitted | Unit/acceptance | Proves routing is auditable. |
| Goal status survives multiple runs | Integration | Proves depth is durable. |
| Review artifact rejects insufficient evidence | Unit | Proves synthesis review is not prose theater. |
| Agent-written memory starts quarantined | Acceptance | Proves memory drift control. |
| Human gate packet required for skill install | Acceptance | Proves irreversible persistence gate. |
| TUI shows seven-loop summary | Headless TUI | Proves daily-user visibility. |

## Roadmap Mapping

| Work IDs | Roadmap horizon |
| --- | --- |
| SCL-P0-001, SCL-P0-002 | H0/H1 |
| SCL-P0-003 | H3 |
| SCL-P0-004, SCL-P1-003 | H4 |
| SCL-P0-005, SCL-P1-004 | H5 |
| SCL-P0-006, SCL-P1-005 | H5 |
| SCL-P1-001, SCL-P1-002 | H2/H5 |
| SCL-P0-007, SCL-P1-006 | H0/H3/H6 |

## Definition Of Done

The seven-control-loop system is credible when:

- Every loop has at least one receipt type.
- Every loop has a failure state.
- Every loop has at least one acceptance test.
- The current status page names unimplemented loops honestly.
- The roadmap links each loop to an owner surface.

## Immediate Sequence

1. Keep DSK-P0 dynamic skill work as the first ecosystem-trust implementation.
2. Add `model_route` receipt because it is narrow and high ROI.
3. Add spec binding for high-risk writes.
4. Add goal record after spec binding is stable.
5. Add synthesis review artifact and human gate packet.
6. Add memory quarantine/promote after gate packet shape exists.

## Community Pain Overlay

The community pain-point survey adds a user-facing pressure layer over this
ledger. It should be used when deciding which receipt work lands first:

- Routing opacity and cost surprise strengthen the case for `SCL-P0-005`.
- Long-task drift strengthens the case for `SCL-P0-004`.
- Memory pollution and memory poisoning strengthen the case for `SCL-P1-001`
  and `SCL-P1-002`, possibly pulling a minimal quarantine rule into P0.
- Review cost and repeated findings strengthen the case for `SCL-P0-006`.
- Hook and permission confusion strengthen the case for `SCL-P0-007`.
- Skill/MCP supply-chain risk strengthens the case for `DSK-P0-001` through
  `DSK-P0-004`.
- Overeager edits strengthen the case for spec binding and intent-drift gates.

See `docs/analysis/community-agent-pain-points-survey-2026-06-05.md` and
`docs/plans/community-pain-points-response-plan-2026-06-05.md`.

## Notes

- Do not implement all seven loops as a monolithic refactor.
- Do not add a new runtime framework.
- Do not treat docs as closure evidence for runtime behavior.
- Do not let model self-report satisfy receipt requirements.
