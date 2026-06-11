# Intent Reassessment and Governance Worklist - 2026-06-11

Status: captured from reflective-dispatch / reflective-handoff-retro session  
Scope: docs-first intent review, test and architecture critique, competitor cross-check, follow-up work list  
Risk level: low, read-only analysis converted into a durable project artifact  
Human review required: before public positioning claims, dependency changes, or large architecture extraction

## Goal

Preserve the 2026-06-11 reflective review so future work does not lose the core insight:

TeaAgent is not primarily "another coding agent." The stronger product intent is a local-first, provider-agnostic, governance-centered agent harness that makes every material model/tool/workspace action inspectable through receipts.

The practical question is therefore not "can it edit code?" but:

- Why was this action allowed?
- Which policy, approval, and budget boundary applied?
- Which tool calls happened?
- What changed in the workspace?
- What evidence proves completion?
- What can be undone or audited later?
- Which claims are supported by current evidence?

## Current State

The docs and implementation point in the same broad direction:

- Product contract: local-first, provider-adapter based, tool-boundary centered, audit-first, permission-mode enforced.
- Runtime path: `ModelDecisionEngine -> AgentRunner -> ToolRegistry -> ApprovalPolicy -> workspace tools -> AuditLogger / RunStore`.
- Governance primitives exist in code: tool schemas, annotations, destructive/read-only semantics, approval policy, budget monitor, audit events, hash/HMAC audit chain, run store, evidence summaries, undo/show flows.
- Acceptance coverage is broad, especially around workspace tools, permissions, policy-as-code, audit, run evidence, TUI/CLI flows, and daily-driver behavior.

The strongest remaining concern is not "missing feature surface." It is evidence integrity:

- Docs are supposed to be the control plane, but some test-count and evidence claims have drifted.
- Acceptance tests often validate harness plumbing with fake adapters or synthetic audit events, which is useful but not sufficient proof of real model behavior.
- `AgentRunner` is carrying many governance responsibilities, which supports the product direction but risks violating the "thin harness" principle.
- Competitors now expose many of the same vocabulary items: plan mode, approval mode, MCP, skills, hooks, subagents, worktrees, cloud/background tasks, and enterprise policy controls.

## Decisions Made

1. Position TeaAgent around auditable governance, not generic coding-agent capability.
2. Treat "receipts before rhetoric" as the main product wedge.
3. Treat docs as part of the runtime control surface, not marketing collateral.
4. Prefer hard, replayable claims over broad claims such as "safer," "enterprise-ready," or "unique."
5. Prioritize end-to-end evidence completeness over adding more surface features.
6. Use competitor comparison to narrow TeaAgent's claims, not to imitate every product surface.

## Assumptions

- The repo remains local-first and CLI/TUI-centered unless a future decision record explicitly changes that.
- Provider-agnostic means governance semantics must remain stable even when model providers differ.
- Fake-adapter tests are valuable for deterministic harness verification, but they must be complemented by adversarial behavior and real-path evidence tests.
- Public positioning should be dated and sourced because agent products are changing quickly.

## Evidence Reviewed

Local project evidence:

- `README.md`
- `docs/product-contract.md`
- `docs/use-cases.md`
- `docs/use-case-matrix.md`
- `docs/acceptance.md`
- `docs/roadmap-status.md`
- `docs/run-evidence-and-audit-guide.md`
- `docs/architecture.md`
- `docs/strategy/teaagent-product-principles-2026-06-04.md`
- `docs/strategy/malleable-governed-agent-harness-2026-06-03.md`
- `docs/strategy/competitive-analysis-and-positioning-2026-06-06.md`
- `docs/strategy/seven-control-loops-product-direction-2026-06-05.md`
- `docs/analysis/competitive-claim-audit-2026-06-06.md`
- `docs/analysis/seven-control-loops-competitor-survey-2026-06-05.md`
- `docs/reviews/seven-control-loops-critical-questioning-2026-06-05.md`
- `governance/README.md`
- `governance/framework/GOVERNED-AGENTIC-ENGINEERING.md`
- `teaagent/runner/_core.py`
- `teaagent/tools.py`
- `teaagent/approval/policy.py`
- `teaagent/audit.py`
- `teaagent/chat_agent.py`
- `tests/acceptance/test_docs_acceptance_count_accuracy.py`
- `tests/acceptance/test_first_hour_e2e_flow.py`
- `tests/acceptance/test_policy_as_code_flow.py`
- `tests/acceptance/test_plan_mode_read_only_flow.py`
- `tests/acceptance/test_run_evidence_summary_flow.py`
- `tests/acceptance/test_security_read_only_gate_flow.py`
- `tests/acceptance/test_workspace_edit_flow.py`

External evidence refreshed during the prior review:

- Claude Code docs: overview, permission modes, enterprise / third-party deployment.
- OpenAI Codex docs: overview, CLI, sandboxing, permissions, agent approvals and security.
- OpenCode docs: overview, permissions, agents.
- Aider docs: git integration, lint/test, repo map.
- Cline docs: overview, approvals, IDE / Kanban / enterprise surfaces.
- Kiro docs: specs, steering, hooks.
- Devin docs: autonomous software engineer workflow and task model.
- OpenHands docs: local / cloud / SDK / CLI architecture.

Relevant external research signals noted:

- Behavior-driven testing for AI coding agents: repository-grounded fuzzing can expose agent failures that happy-path tests miss.
- Overeager coding agents: permissive agents can exceed requested scope; this is directly relevant to TeaAgent's permission and plan gates.
- Large-scale agentic PR studies: useful as market context, but not enough to justify product claims without project-local evidence.

## Commands / Tests Run

These were used as evidence during the review:

```bash
python3 -m pytest tests/acceptance --collect-only -q
```

Result: succeeded; 621 acceptance tests collected.

```bash
python3 scripts/validate_docs_consistency.py
```

Result: failed. Reported risk register evidence coverage at 24/29 rows, ticket index evidence coverage at 21/21 rows, and test quality audit failure because full pytest collection failed.

```bash
python3 -m pytest tests --collect-only -q
```

Result: failed. Full test collection reached 5987 collected tests before one collection error: `tests/test_cli_fuzz_parsers.py` imports `hypothesis`, which was unavailable in the current environment.

```bash
python3 scripts/audit_test_quality.py --tests-dir tests/acceptance --format markdown --fail-on none
```

Result: succeeded. Reported 621 collected acceptance nodes, 123 test files, 612 test functions, 1832 assertions, 20 tests with weak patterns, 54 total mock calls, and 3 high-risk no-assertion files.

## Critical Findings

### F1 - Docs Control Plane Drift

Severity: high  
Theme: evidence integrity

`docs/acceptance.md` has a current headline aligned with the acceptance collection count, but the same file still contains stale prose referencing 446 acceptance tests. `docs/roadmap-status.md` records another dated snapshot with 628 passed tests. These can all be explainable snapshots, but the docs do not currently make the distinction obvious enough.

Why it matters:

If docs are the control plane, stale evidence inside docs is not cosmetic. It weakens the central claim that TeaAgent is governed by verifiable receipts.

Likely repair:

- Make all test-count claims explicitly dated and scoped.
- Extend the docs acceptance-count guard to detect stale count prose anywhere in the document, not just the first headline marker.
- Add a "current vs historical snapshot" convention for roadmap evidence.

### F2 - Test Breadth Is Strong, But Evidence Is Often Synthetic

Severity: high  
Theme: test adequacy

The acceptance suite is broad and valuable. However, many important flows use fake adapters, fixture-created audit streams, or helper-level checks. This is good for deterministic harness coverage, but it cannot be the only proof of real agent behavior.

Examples:

- `test_first_hour_e2e_flow.py` is strong because it exercises edit, local pytest, show, and undo. It still uses `FakeAdapter` and `--skip-plan-check`.
- `test_run_evidence_summary_flow.py` validates evidence parsing and structure, but uses constructed audit events.
- Security and read-only gate tests cover important helpers and audit events, but should be complemented by full runner paths.

Likely repair:

- Keep fake-adapter tests as deterministic contract tests.
- Add a smaller set of hostile/adversarial behavior tests for over-scope edits, unauthorized tool calls, fake completion, cost-boundary violations, and plan bypass attempts.
- Add at least one evidence-completeness test generated from a real first-hour path.

### F3 - AgentRunner Is Becoming the Governance Gravity Well

Severity: medium-high  
Theme: architecture boundary

`AgentRunner` currently coordinates many concerns: plugin discovery/loading, budget monitoring, context compaction, phase tracking, plan validation, proof-of-use, JIT approval, file policy, tool calls, audit logging, and auto-mode behavior.

Why it matters:

This supports TeaAgent's governance goal, but it risks turning the thin harness into a dense god object. The more governance becomes centralized in one runtime class, the harder it becomes to prove, test, and reuse each control loop independently.

Likely repair:

- Do not start with a large rewrite.
- First produce a control-loop ownership map.
- Then extract only the most stable boundaries: plan/spec gate, budget gate, evidence recorder, approval gate, context compaction gate.

### F4 - Plan/Spec Gate Is Product-Critical But Not Yet Proven as a Daily Path

Severity: high  
Theme: product contract

Docs emphasize spec-first and governance loops. Yet the first-hour flow currently uses `--skip-plan-check`. That may be appropriate for testing a specific path, but it cannot be the flagship proof of governed execution.

Likely repair:

- Add a first-hour governed path without `--skip-plan-check`.
- Assert the generated or selected plan/spec artifact.
- Assert that plan validation appears in audit/run evidence.
- Assert that a failed or missing plan blocks execution with an actionable reason.

### F5 - Competitor Vocabulary Has Converged

Severity: medium  
Theme: positioning

Competitors now commonly expose plan modes, permission modes, MCP, hooks, skills, subagents, cloud/background execution, worktrees, and enterprise controls. TeaAgent should not compete by claiming these words alone.

Likely repair:

- Make claims narrower and stronger:
  - local-first governance harness
  - provider-agnostic policy and audit semantics
  - run receipts and evidence bundles
  - cost/approval/tool-call traceability
  - docs-as-control-plane claim hygiene
- Avoid claims like:
  - only agent with governance
  - more secure than competitors
  - enterprise-ready without deployment evidence
  - hosted autonomous teammate unless remote execution is hardened and verified

## Socratic Questions

1. If docs are a control plane, what should happen when a doc claim and a test result disagree?
2. Which claims should be impossible to merge without a current evidence receipt?
3. Does TeaAgent prove "the model behaved safely," or only that "the harness can block scripted unsafe behavior"?
4. Which tests would fail if a model tried to edit more files than requested?
5. Which tests would fail if a model claimed completion without running the required verification?
6. Which tests would fail if cost was unknown but the UI implied a precise spend?
7. Does the first-hour experience teach the user governance, or does governance appear mainly in docs and edge cases?
8. Where is the single best receipt that explains one complete run from prompt to file diff to test result to undo?
9. Which `AgentRunner` responsibility would be easiest to prove if extracted?
10. Which `AgentRunner` responsibility would be most dangerous to extract too early?
11. If OpenCode, Claude Code, and Codex all have permissions, what exact receipt can TeaAgent show that they do not emphasize?
12. If Aider wins on git simplicity, how can TeaAgent make undo/evidence feel equally simple instead of bureaucratic?
13. If Kiro wins on spec-first UX, how can TeaAgent make spec gates runtime-enforced rather than merely documented?
14. If Devin/OpenHands win on remote parallel work, should TeaAgent compete there now or explicitly defer it?
15. What is the smallest demo that proves the whole product thesis in under five minutes?

## Work List

### W1 - Fix Docs Evidence Drift

Priority: P0  
Owner surface: docs / validation  
Rationale: Docs are part of the governance surface. Stale evidence undermines the product thesis.

Tasks:

- Update `docs/acceptance.md` so historical and current test-count claims are unambiguous.
- Extend `tests/acceptance/test_docs_acceptance_count_accuracy.py` or add a companion test that scans for stale acceptance-count prose throughout the document.
- Clarify `docs/roadmap-status.md` snapshot semantics: date, command, scope, commit, current-vs-historical meaning.
- Re-run docs consistency validation.

Acceptance criteria:

- `python3 -m pytest tests/acceptance/test_docs_acceptance_count_accuracy.py -q` passes.
- `python3 scripts/validate_docs_consistency.py` no longer fails on stale doc-count confusion or test collection setup.
- All test-count claims in docs include scope and date.

### W2 - Restore Full Test Collection

Priority: P0  
Owner surface: test environment / dependencies  
Rationale: Validation tooling cannot be trusted if full collection fails before tests run.

Tasks:

- Decide whether `hypothesis` is a required development dependency.
- If yes, add it to the appropriate dev dependency manifest.
- If no, gate or skip `tests/test_cli_fuzz_parsers.py` with an explicit reason.
- Re-run full collection.

Acceptance criteria:

- `python3 -m pytest tests --collect-only -q` completes without collection errors.
- The dependency decision is documented in the relevant dependency or testing doc.

### W3 - Add Governed First-Hour E2E

Priority: P0  
Owner surface: acceptance tests / CLI runtime  
Rationale: The flagship daily path should prove plan/spec governance, not bypass it.

Tasks:

- Add a first-hour e2e variant without `--skip-plan-check`.
- Assert plan/spec artifact presence or explicit selected plan.
- Assert plan validation audit evidence.
- Assert workspace edit, local test execution, show/evidence summary, and undo.
- Include a negative case where missing plan blocks execution with an actionable error.

Acceptance criteria:

- The new test fails if plan validation is skipped silently.
- The new test fails if run evidence lacks plan/spec status.
- The new test remains deterministic, likely through a fixture model, but validates the real gate path.

### W4 - Add Receipt Completeness Contract

Priority: P0  
Owner surface: audit / run evidence / acceptance  
Rationale: TeaAgent's moat is receipts; receipts need a single strong contract.

Tasks:

- Define the minimum complete receipt for a run:
  - prompt or task summary
  - model/provider identifier
  - permission mode
  - budget estimate and actual/unknown status
  - approval decisions
  - tool calls and classifications
  - file diffs
  - verification commands and results
  - final result
  - undo/recovery pointer
- Add a test that asserts a real run produces all required fields.
- Distinguish synthetic receipt parser tests from runtime-produced receipt tests.

Acceptance criteria:

- A single command can produce a human-readable evidence bundle for one complete local run.
- The acceptance test fails if any required receipt field disappears.

### W5 - Create Control-Loop Ownership Map

Priority: P1  
Owner surface: architecture docs / runner internals  
Rationale: Before refactoring, clarify which control loop owns which decision.

Tasks:

- Map existing responsibilities in `AgentRunner`.
- Define ownership for:
  - approval gate
  - budget gate
  - plan/spec gate
  - tool governance gate
  - audit/evidence recorder
  - context compaction gate
  - plugin loading boundary
  - final result validation
- Identify which boundaries are stable enough to extract.
- Identify which should remain in `AgentRunner` for now.

Acceptance criteria:

- A doc exists under `docs/architecture/` or `docs/analysis/` with control-loop input/output/failure semantics.
- No code extraction begins until the map identifies the first narrow extraction.

### W6 - Extract One Narrow Runner Boundary

Priority: P1  
Owner surface: runner / tests  
Dependency: W5  
Rationale: Reduce `AgentRunner` density without causing a broad refactor.

Candidate first extractions:

- Plan/spec gate evaluator.
- Receipt completeness builder.
- Budget decision adapter.
- Approval decision recorder.

Acceptance criteria:

- One responsibility moves behind a clear interface.
- Existing runner behavior remains unchanged.
- Tests cover success, block, and audit/evidence paths for the extracted boundary.

### W7 - Add Adversarial Over-Scope Tests

Priority: P1  
Owner surface: acceptance / adversarial tests  
Rationale: Competitor research and agent-behavior studies show scope creep and over-eager execution as real risks.

Tasks:

- Create tests where the model tries to:
  - edit an unrequested file
  - run an unauthorized command
  - claim completion without verification
  - exceed tool-call limits
  - ignore a read-only or plan-only mode
  - bury a destructive action inside a benign-looking step
- Assert block reasons are actionable and audited.

Acceptance criteria:

- At least one adversarial test fails on each of: unauthorized write, unauthorized shell command, missing verification, and scope expansion.
- Audit log records the blocked intent and boundary reason.

### W8 - Improve Test Quality Queue

Priority: P1  
Owner surface: tests  
Rationale: The quality audit found weak patterns and no-assertion tests.

Tasks:

- Repair high-risk no-assertion tests:
  - `tests/acceptance/test_github_integration_flow.py`
  - `tests/acceptance/test_hook_lifecycle_flow.py`
  - `tests/acceptance/test_headless_tui.py`
- Review the 20 weak-pattern tests reported by `audit_test_quality.py`.
- Decide which construction-only tests should become behavior tests and which should remain construction tests with explicit naming.

Acceptance criteria:

- `python3 scripts/audit_test_quality.py --tests-dir tests/acceptance --format markdown --fail-on none` reports no high-risk no-assertion files.
- Weak patterns are either fixed or explicitly justified.

### W9 - Refresh Competitive Claims With Dated Evidence

Priority: P1  
Owner surface: strategy docs / claim hygiene  
Rationale: Competitors are moving quickly; stale claims can become false within weeks.

Tasks:

- Update competitive docs to avoid uniqueness claims unless directly sourced and dated.
- Separate capabilities by surface:
  - local CLI
  - IDE
  - cloud/background
  - enterprise/admin
  - open-source/self-hosted
  - provider/model flexibility
- Use TeaAgent's own verified capabilities as the comparison baseline.

Acceptance criteria:

- Competitive docs distinguish evidence, inference, and positioning.
- Claims have dates and source links.
- Unsafe phrases such as "only," "more secure," or "enterprise-ready" are removed or backed by precise evidence.

### W10 - Build a Five-Minute Proof Demo Script

Priority: P2  
Owner surface: product / docs / CLI  
Rationale: The project thesis needs a compact demo that proves governance without requiring a reader to inspect the whole repo.

Demo should show:

1. A user asks for a small code change.
2. TeaAgent selects/validates a plan or explains why one is needed.
3. It requests or records approvals according to policy.
4. It edits a file.
5. It runs verification.
6. It emits an evidence summary with budget/tool/file/test receipts.
7. It shows undo/recovery.

Acceptance criteria:

- Demo can be run locally from a clean checkout.
- Demo output includes the evidence bundle path.
- Demo does not depend on a paid live provider unless a fake-provider mode is explicitly labeled.

### W11 - Define Provider-Agnostic Governance Contract

Priority: P2  
Owner surface: provider adapters / docs / tests  
Rationale: Provider-agnostic is only meaningful if governance semantics survive provider differences.

Tasks:

- Define which fields every provider adapter must expose or mark unknown:
  - model id
  - provider id
  - token usage
  - estimated cost
  - actual cost if available
  - tool-call representation
  - refusal/error class
  - streaming support
- Add tests for unknown cost and partial usage metadata.

Acceptance criteria:

- Unknown cost is never presented as actual cost.
- Provider adapters have a shared governance metadata contract.

### W12 - Add Claim-to-Test Traceability

Priority: P2  
Owner surface: docs / tests  
Rationale: If "receipts before rhetoric" is real, product claims should point to tests or evidence bundles.

Tasks:

- Create or extend a traceability matrix linking:
  - product claim
  - source doc
  - acceptance test
  - evidence command
  - current status
- Start with the top 10 claims:
  - local-first
  - provider-agnostic
  - permission modes
  - policy-as-code
  - cost boundary
  - audit log
  - run evidence
  - undo/recovery
  - plan/spec gate
  - docs-as-control-plane

Acceptance criteria:

- Each top claim has at least one evidence command or explicit gap.
- Claims without evidence are labeled as roadmap, not current capability.

## Suggested Execution Order

1. W2 - Restore full test collection.
2. W1 - Fix docs evidence drift.
3. W4 - Add receipt completeness contract.
4. W3 - Add governed first-hour e2e.
5. W8 - Repair high-risk test quality findings.
6. W5 - Create control-loop ownership map.
7. W6 - Extract one narrow runner boundary.
8. W7 - Add adversarial over-scope tests.
9. W9 - Refresh competitive claims.
10. W12 - Add claim-to-test traceability.
11. W10 - Build five-minute proof demo script.
12. W11 - Define provider-agnostic governance contract.

## Risks

- Over-refactoring risk: extracting runner boundaries before W5 could create churn without improving proof.
- Over-documentation risk: adding more strategy docs without validation will worsen the control-plane drift.
- Competitor-chasing risk: copying cloud/team/IDE surfaces too early could dilute the local governance wedge.
- Test theater risk: adding more fake-adapter tests without adversarial real-path checks may inflate counts without increasing confidence.
- Claim risk: public language can become stale quickly because Claude Code, Codex, OpenCode, Cline, Kiro, Devin, and OpenHands are changing rapidly.

## Trust Boundaries / External Data

- Competitor facts are time-sensitive. Treat the external survey as current to 2026-06-11 only.
- External docs describe vendor claims and product surfaces; they do not prove comparative security.
- Research papers and benchmarks can motivate test design, but TeaAgent claims still need repo-local evidence.
- Fake adapter behavior is controlled evidence for the harness, not proof of live model behavior.

## Blockers

- Full test collection currently fails without `hypothesis`.
- Docs consistency validation currently fails.
- Some acceptance quality findings remain unresolved.
- The review did not run the full test suite; it used collection and quality-audit commands.

## Acceptance Criteria For This Artifact

This artifact is sufficient if a future agent can:

- Reconstruct the product thesis.
- See the major evidence-backed concerns.
- Identify the next P0 work without rereading the whole conversation.
- Distinguish local evidence from external competitor evidence.
- Convert work items into tickets or implementation plans.

## Do Not Do

- Do not claim TeaAgent is uniquely governed without dated competitor evidence.
- Do not treat acceptance test count as quality by itself.
- Do not start a broad `AgentRunner` rewrite before mapping control-loop ownership.
- Do not replace deterministic fake-adapter tests; complement them with adversarial and real-path tests.
- Do not present unknown provider cost as actual spend.
- Do not publish competitor comparisons without source dates and capability-surface distinctions.

## Human Review Required

Human review is recommended before:

- Publishing competitive positioning.
- Adding or removing development dependencies.
- Performing a broad runner refactor.
- Changing permission or approval defaults.
- Claiming enterprise readiness, production security, or hosted autonomous execution.

## Next Recommended Action

Start with W2 and W1 together:

1. Restore full test collection by resolving the `hypothesis` dependency decision.
2. Fix docs evidence drift so acceptance counts and roadmap snapshots are scoped, dated, and validated.

These are the best first moves because they repair the evidence foundation before adding more governance features.
