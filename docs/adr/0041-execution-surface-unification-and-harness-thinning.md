# ADR 0041: Execution Surface Unification and Harness Thinning

## Status

Proposed — 2026-06-30

**Target architecture decision.** This ADR defines a phased migration with
acceptance gates at each step. It is **not** authorization for a single
big-bang refactor. Implementation lands incrementally; each phase must pass
its gate before the next phase begins.

Extends ADR-0040 (shared-invariant contract) and addresses the remaining
G-HIGH-2 thin-harness deviation documented in
`docs/retrospective/03-architecture-quality.md` and the partial-compliance row
in `docs/retrospective/05-compliance-matrix.md`.

## Context

### Dual execution surfaces duplicate governance

Two execution frameworks remain in production:

1. **Primary runner** — `teaagent/runner/_core.py` (`AgentRunner`): the
   canonical agent loop. It owns budget enforcement (`_core.py:957–1060`,
   `_assert_cost_budget`, `_check_phase_budget`), audit emission via
   `EventSpine` → audit bridge (`runner/_events.py`, `register_audit_consumer`),
   and the nine-stage tool authorization pipeline (`_authorize_tool_call`,
   `RunnerApprovalCoordinator` in `runner/_approval_manager.py`,
   `ApprovalPolicy.assert_allowed`).
2. **Second framework** — `teaagent/subagents/_manager.py:205–538`
   (`SubagentManager.run_subagent`) and `teaagent/swarm.py` (swarm
   orchestration): recursive child runners that build their own config,
   approval handler (`_build_approval_handler` → centralized queue per
   ADR-0022), budget clamp (`_resolve_budget_limits`, `_resolve_child_cost_cap`),
   and audit logger (`RunStore.audit_logger`), then delegate to
   `run_chat_agent` (`_manager.py:457–465`).

ADR-0040 accepted the dual-framework design and introduced a
`SharedInvariantContract` in `teaagent/runner/_invariants.py` plus static
import gates (`scripts/validate_runner_invariants.py`) and unit tests
(`tests/runner/test_runner_invariants.py`). That work makes divergence
**detectable** but does not yet **define governance once**:

- `AgentRunner` embeds budget, approval, and audit orchestration inline in
  `_core.py` (~1,100+ lines).
- `SubagentManager` re-implements budget resolution, approval-handler
  selection, RBAC pre-checks, and audit setup before calling
  `run_chat_agent`, which itself re-enters the primary runner path with a
  separately constructed config.
- The live differential test described in ADR-0040 §2 (identical scenario
  through both paths with matching evidence bundles) is **not yet landed**.
  Equivalence is enforced structurally (import gate), not by a shared
  callable layer both surfaces invoke.

This doubles the correctness surface for the five governance loops in
ADR-0009 (tool governance, plan binding, audit, memory hygiene, swarm
hardening): a policy change in budget thresholds, approval stages, or audit
event shape must be applied in two places or silently diverge.

ADR-0025 established the pattern for chat surfaces: one
`ChatSessionController` instead of parallel REPL/TUI execution paths. The
execution-framework split is the same class of problem at the runner layer.

ADR-0029 deferred a third consensus surface rather than shipping parallel
authority paths. This ADR applies the same discipline: **do not add a third
execution framework** to solve unification.

### Harness-thinness deviation: domain reasoning in-repo

`AGENTS.md:5` states the target invariant:

> Keep the harness thin: orchestration, tool governance, state boundaries,
> audit, and validation belong here; domain reasoning belongs in the model or
> skills.

`AGENTS.md:6` clarifies this is a **target invariant for new work**, not a
claim about current size (`docs/strategy/harness-first-direction-2026-06-13.md`).

Despite action register item A-P1-1 (marked done for relocation into
`teaagent/domain/`), **~2,777 lines** of domain reasoning remain in the
harness package:

| Module | LOC | Domain responsibility |
| --- | ---: | --- |
| `teaagent/domain/issue_intake.py` | 943 | Issue parsing, ambiguity classification, plan extraction |
| `teaagent/domain/workflow_engine.py` | 748 | Multi-step workflow execution, validation profiles, polish mode |
| `teaagent/domain/agent_factory.py` | 444 | LLM-driven agent prompt evolution and dynamic plugin creation |
| `teaagent/domain/coordinator.py` | 434 | Task classification, routing, workflow plan generation |
| `teaagent/domain/intent.py` | 207 | Ambiguity scoring, clarification heuristics (`clarify_task`) |

`teaagent/domain/intent.py:3–4` explicitly documents that domain reasoning
lives here. Root modules are compatibility shims (ADR-0030), but the
reasoning itself is still Python in the harness tree—not skills or model
prompts. `workflow_engine.py` and `coordinator.py` call `LLMAdapter`
directly for classification, plan generation, and self-correction—product
logic that `docs/retrospective/03-architecture-quality.md:186` recommends
moving to skills or the model.

`docs/retrospective/05-compliance-matrix.md:11` rates thin-harness as
**Partial** because of this surface plus swarm/hybrid-store product code.

## Decision

**Do not add a third agent framework.** Unify governance through a shared
layer and thin the harness through a separate, paced domain migration.

### Phase 1 — Shared governed-execution layer (execution surfaces)

Extract a single **governed-execution invariant layer**—tool authorization,
approval gating, audit emission, and budget enforcement—that both
`AgentRunner` and `SubagentManager` (and any future orchestrator such as
`SwarmManager`) **call**, not re-implement.

#### 1.1 Module boundary

Introduce `teaagent/runner/_governed_execution.py` (name may vary; location
under `teaagent/runner/` keeps ADR-0040's contract co-located):

- **`GovernedExecutionContext`** — holds `RunBudget`, `ApprovalPolicy`,
  `AuditLogger`, `EventSpine`, workspace root, and lineage metadata.
- **`authorize_tool_call(...)`** — single implementation of the pipeline
  currently in `AgentRunner._authorize_tool_call` (file policy, auto-mode,
  payload-digest preapproval, `ApprovalPolicy.assert_allowed`, JIT handler).
- **`enforce_budget(...)`** — iteration, tool-call, phase, and cost checks
  currently spread across `_check_phase_budget`, `_assert_cost_budget`, and
  the main loop guard in `_core.py`.
- **`emit_run_lifecycle(...)`** — wraps `EventSpine` emission and audit
  bridge registration so subagent spawns cannot construct a parallel audit
  path.

`AgentRunner` becomes a thin orchestration shell: decide → call governed
layer → dispatch tools. `SubagentManager.run_subagent` constructs a
`GovernedExecutionContext` (with child budget clamped per MA-03) and passes
it into the same layer before `run_chat_agent`, rather than duplicating
handler wiring in `_build_approval_handler` / `_build_subagent_config`.

#### 1.2 Contract evolution

`teaagent/runner/_invariants.py` (`SharedInvariantContract` from ADR-0040)
remains the evidence schema. Phase 1 **implements** the contract instead of
only asserting import paths. `scripts/validate_runner_invariants.py` gains a
check that `_manager.py` and `_core.py` import from `_governed_execution`
rather than duplicating `ApprovalPolicy.assert_allowed` call sites.

#### 1.3 Phase 1 acceptance gate

All must pass before Phase 2 starts:

| Gate | Evidence |
| --- | --- |
| **G1 — Shared layer exists** | Met: `teaagent/runner/_governed_execution.py` exported; `AgentRunner` delegates **both** budget enforcement (cost/phase/warnings) and **authorization** (`authorize_tool_call`: spine gate, auto-mode scoping, payload-digest preapproval, approval-policy decision) to it |
| **G2 — Subagent path uses layer** | Met: `SubagentManager` constructs context via shared helpers; no parallel `assert_allowed` in `_manager.py`; budget clamp single-sourced via `compute_clamped_budget` (gated) |
| **G3 — Live differential** | Met: `TestLiveDifferential` runs an identical tool+budget scenario through `AgentRunner` and `SubagentManager.run_subagent`; `assert_budget_invariant`, `assert_audit_invariant`, `assert_approval_invariant` pass on collected evidence |
| **G4 — CI green** | Met: `validate_runner_invariants.py` exit 0; full suite green after the bare-assert guard fix — 6561 collected, 6547 passed / 14 skipped / 0 failed across both the non-slow tier (`-m "not nightly and not slow"`) and the nightly/slow tier (`-m "nightly or slow"`); acceptance tier unchanged |
| **G5 — No third framework** | Met: import graph shows no new execution-loop package; single run loop in `_core.py`; subagents/swarm delegate through `run_chat_agent` |

#### 1.4 Phase 1 rollback

If G3 or G4 fails after partial landing:

1. Revert the delegating commits in `AgentRunner` / `SubagentManager` (keep
   `_governed_execution.py` behind a feature flag or on a branch).
2. ADR-0040 static gates remain the authority baseline.
3. File a blocking note in `docs/retrospective/06-action-register.md` citing
   the failing gate; do not start Phase 2.

#### 1.5 Phase 1 progress (2026-06-30)

Behavior-preserving slices landed (2026-06-30):

- **Budget clamp single-sourced.** `subagents/_manager._resolve_budget_limits`
  delegates to canonical `runner/_invariants.compute_clamped_budget` instead of a
  hand-kept `min(child, parent)` mirror. Delegation test:
  `tests/runner/test_runner_invariants.py::TestBudgetInvariant`
  `::test_resolve_budget_limits_delegates_to_canonical_clamp`.
- **G2-budget static gate.** `scripts/validate_runner_invariants.py` now fails if
  `_manager.py` stops importing/calling `compute_clamped_budget` (regression lock
  for the slice above), alongside the existing approval/audit import gates.
- **G3 live differential test landed.** `TestLiveDifferential` runs an
  identical-shape scenario through `AgentRunner` (direct) and
  `SubagentManager.run_subagent` (via the `subagent` tool) and asserts
  `assert_audit_invariant`, `assert_audit_events_match`, `assert_approval_invariant`,
  and `assert_budget_invariant` on evidence collected from both surfaces.
- **G1 budget enforcement extracted.** `runner/_governed_execution.py` now owns
  per-iteration budget enforcement (`enforce_cost_budget` / `enforce_phase_budget`
  / `enforce_budget_warnings`), a verbatim behavior-preserving move from `_core.py`;
  `AgentRunner` delegates to it. The §1.2 import gate in
  `scripts/validate_runner_invariants.py` requires `_core.py` to use the layer.
  Risk report: `docs/reviews/a-p1-3-governed-execution-risk.md`; unit tests:
  `tests/runner/test_governed_execution.py`.
- **G1 authorization extracted.** `runner/_governed_execution.authorize_tool_call`
  now owns the per-tool-call approval pipeline (file-policy + spine permission
  gates, auto-mode scoping with `ApprovalPolicy` reassignment, preapproved
  payload-digest checks, `assert_allowed`, and approval-request handling), a
  verbatim `self`->`runner` move from `_core.py`; `AgentRunner._authorize_tool_call`
  delegates to it. The §1.2 G1 gate now also requires `_core.py` to call
  `authorize_tool_call`. Risk report:
  `docs/reviews/a-p1-3-authorization-extraction-risk.md`; delegation test:
  `tests/runner/test_governed_execution.py::test_authorize_tool_call_delegates_to_shared_layer`.

**All Phase-1 gates are met (2026-06-30).** **G1** — the shared
governed-execution layer owns both the budget and authorization dimensions, with
the static gate (`validate_runner_invariants.py`) locking both delegations.
**G2** — the budget clamp is single-sourced via `compute_clamped_budget`. **G3** —
the live differential test passes on both surfaces. **G4** — after the
bare-assert guard fix, the entire suite is green: 6561 collected, 6547 passed /
14 skipped / 0 failed across the non-slow tier (6208 passed / 14 skipped) and the
nightly/slow tier (339 passed). The sole pre-fix failure was a bare-assert guard
count that drifted when the env-lock work added a self-consistency invariant;
that guard was reviewed and corrected (test-only, isolated). **G5** — the import
graph shows no new execution-loop package; the single run loop remains in
`_core.py` and subagents delegate through `run_chat_agent`. Phase 2 (domain
reasoning migration) remains
**unauthorized** pending an explicit decision.

### Phase 2 — Domain reasoning migration (harness thinning)

Migrate domain reasoning out of `teaagent/domain/` toward **skills** (for
reviewed, reusable procedures) and **model prompts** (for classification /
plan generation), leaving the harness as orchestration and governance only.

Priority order (highest harness coupling first):

1. **`intent.py`** — ambiguity heuristics → skill (`skills/intent-clarification/`
   or equivalent) + thin harness wrapper that invokes the skill tool.
2. **`coordinator.py`** — task classification / workflow plan generation →
   model-structured output via skill prompt; harness retains only routing
   hooks.
3. **`agent_factory.py`** — prompt evolution → skill-owned templates;
   harness registers plugins, does not generate prompts.
4. **`workflow_engine.py`** — step validation and polish loops → skill
   procedures; harness retains `UndoJournal` / audit wiring only.
5. **`issue_intake.py`** — issue parsing and ambiguity reports → skill +
   optional GitHub tool; harness retains intake API boundary.

Each module migrates independently. `teaagent/domain/*.py` become shims
(ADR-0030 pattern) until callers move, then are deleted.

#### 2.1 Phase 2 acceptance gate (per module)

| Gate | Evidence |
| --- | --- |
| **D1 — Caller inventory** | `rg` / import-graph shows zero production imports of the module from harness orchestration code (runner, subagents, swarm, cli handlers) except the compat shim |
| **D2 — Skill or prompt asset** | New or updated `SKILL.md` + tests proving the behavior previously in the Python module |
| **D3 — LOC budget** | Cumulative `teaagent/domain/` LOC decreases by ≥25% per migrated module; target ≤500 LOC total residual (orchestration types only) |
| **D4 — Compliance matrix** | `docs/retrospective/05-compliance-matrix.md` thin-harness row updated to **Compliant** or **Partial** with measured LOC |

#### 2.2 Phase 2 rollback (per module)

If D2 or D4 regresses:

1. Restore the `teaagent/domain/<module>.py` implementation from the shim.
2. Disable the skill default in config; document in the module's SKILL.md as
   `experimental — unwired` (ADR-0029 precedent).
3. Do not migrate the next module until the failing module's gate is green
   again.

### Explicit non-decisions

- **Fold `SubagentManager` into `runner/` now** — remains gated by ADR-0040
  §4 fold criterion (two release cycles of machine-checked invariants + swarm
  scheduler expressible as runner primitive).
- **Add a third framework** (workflow engine runtime, separate child-process
  runner, etc.) — prohibited without a new ADR; this ADR satisfies unification
  by extraction, not addition.
- **Big-bang delete of `teaagent/domain/`** — rejected; phased per-module
  migration only.

## Rationale

- **One safety contract, many orchestrators.** Swarm/tournament semantics
  (ADR-0028) and centralized subagent approval (ADR-0022) are valuable
  product surfaces; the failure mode is duplicated **governance**, not
  duplicated **loops**. A shared governed-execution layer gives ADR-0009's
  five loops a single implementation anchor.
- **ADR-0040 is necessary but insufficient.** Import-path gates catch gross
  divergence; they do not prevent subtle budget-threshold or audit-payload
  drift when logic is copy-pasted across `_core.py` and `_manager.py`.
- **Domain code in harness violates the stated north star.** Relocating to
  `teaagent/domain/` satisfied A-P1-1's letter (namespace separation) but not
  `AGENTS.md:5`'s spirit. Skills are reviewed supply-chain assets; keeping
  ~2.7k LOC of LLM prompts and heuristics in Python makes the harness a
  product runtime, not a governance shell.
- **Phased gates match harness-first direction.** `docs/strategy/harness-first-direction-2026-06-13.md` §2 non-goals explicitly forbid a big-bang runner rewrite; behavior-preserving steps with acceptance green are required.

## Implementation

Planned artifacts (none required for ADR acceptance; tracked when Phase 1
starts):

| Artifact | Phase |
| --- | --- |
| `teaagent/runner/_governed_execution.py` | 1 |
| Refactor `teaagent/runner/_core.py` to delegate | 1 |
| Refactor `teaagent/subagents/_manager.py` to delegate | 1 |
| `tests/runner/test_governed_execution_differential.py` | 1 |
| Extend `scripts/validate_runner_invariants.py` | 1 |
| `skills/*/SKILL.md` + migration per `teaagent/domain/*` | 2 |
| Update `docs/architecture/execution-frameworks.md` | 1 |
| Update `docs/retrospective/05-compliance-matrix.md` | 2 |

## Consequences

### Positive

- Tool authorization, approval, audit, and budget are defined **once**;
  policy changes land in one module and apply to primary and subagent runs.
- Live differential tests replace structural-only equivalence for governance.
- Domain reasoning becomes portable skill assets, aligning code with
  `AGENTS.md:5` and reducing harness gravity (`docs/strategy/harness-first-direction-2026-06-13.md` G4).
- Clear rollback at each phase limits blast radius.

### Negative

- Phase 1 is a non-trivial refactor of `_core.py` and `_manager.py` with
  regression risk despite gates.
- Phase 2 requires skill authoring and test investment per module; total
  calendar time spans multiple release cycles.
- Residual `teaagent/domain/` shims add temporary indirection until callers
  migrate.

### Migration

- **Phase 1:** behavior-preserving extraction; no user-visible CLI changes
  expected.
- **Phase 2:** module-by-module; owners may need to enable new skills
  explicitly during transition.

## Alternatives Considered

- **Fold subagent path into `AgentRunner` immediately** — rejected; same
  rationale as ADR-0040 (swarm/tournament regression risk, fold criterion not
  met).
- **Leave ADR-0040 static gates as sufficient** — rejected; does not reduce
  duplicated implementation or satisfy live differential equivalence.
- **Move domain to `teaagent/domain/` only (status quo)** — rejected; namespace
  move without skills/model migration does not satisfy thin-harness target.
- **Introduce a third "unified runner" framework** — rejected; violates
  `AGENTS.md:8` and repeats the dual-framework mistake at larger scale.

## References

- `AGENTS.md:5–8` — thin harness, governed path, no second framework without ADR
- `docs/strategy/harness-first-direction-2026-06-13.md` — north star, no big-bang rewrite
- `docs/retrospective/03-architecture-quality.md` (G-HIGH-2)
- `docs/retrospective/05-compliance-matrix.md` (thin-harness partial row)
- `docs/retrospective/06-action-register.md` (A-P1-1, A-P1-3)
- `teaagent/runner/_core.py` — primary runner governance
- `teaagent/runner/_invariants.py` — ADR-0040 shared-invariant contract
- `teaagent/subagents/_manager.py:205–538` — second framework entry point
- `teaagent/domain/` — domain reasoning modules (~2,777 LOC)
- ADR-0009 (5-loop governance system)
- ADR-0025 (chat session controller unification precedent)
- ADR-0029 (defer parallel authority / consensus surfaces)
- ADR-0040 (second-framework shared invariants)
