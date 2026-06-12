# Intent Critical Review and Worklist - 2026-06-12

> **Claim class:** dated reflective research/review artifact, not stable
> product truth and not a public competitor claim.
>
> **Scope:** TeaAgent at `d736a1b` on 2026-06-12, docs-first intent review,
> test/architecture critique, same-day official-source competitor skim, and a
> follow-up work list.
>
> **Complements:** [Intent Reassessment and Governance Worklist
> 2026-06-11](intent-reassessment-and-worklist-2026-06-11.md),
> [Intent Verification Delta 2026-06-12](intent-verification-delta-2026-06-12.md),
> and [Claim-to-Test Traceability Matrix](../architecture/claim-to-test-traceability-matrix.md).
>
> **Human review required before:** public market claims, branch-protection
> changes, policy/RBAC enforcement flips, destructive repo hygiene, or any
> production/enterprise posture claim.

---

## 1. Dispatch Result

The user request was routed through `reflective-dispatch` as:

- **Primary mode:** `reflective-research` because the task starts from docs,
  needs current external competitor evidence, and asks for source-grounded
  synthesis.
- **Critique lens:** `reflective-review` because the task asks to Socratically
  challenge current tests and architecture rather than merely summarize them.
- **Artifact shape:** `reflective-spec-plan` style because the requested
  output is durable thinking plus a work list.
- **Strictness:** L5. The project thesis is governance-sensitive; claims need
  dated evidence, explicit confidence, and a clear evidence/inference split.

Research question:

> Starting from the docs, what is TeaAgent trying to prove, what do the tests
> and architecture actually prove or fail to prove, how does competitor
> convergence change the thesis, and what work should follow?

## 2. Direct Recommendation

Keep the product thesis narrow and hard:

> TeaAgent should be a local-first, provider-agnostic governance harness for
> agentic coding work, where every material model decision, tool call, approval,
> file mutation, cost boundary, and completion claim can be explained by a
> durable receipt.

Do **not** compete on vocabulary alone. "Permissions," "plan mode,"
"subagents," "hooks," "MCP," "worktrees," "background agents," and "enterprise
controls" are now common market vocabulary. TeaAgent's defensible lane is not
that it has these words; it is that it can make the control path auditable,
local, reproducible, and claim-tested.

The next quality bar is therefore not "add another agent feature." It is:

1. Make the docs gate environment-stable and hard to bypass.
2. Remove deprecated approval paths from flagship proof tests.
3. Resolve current-truth contradictions across dated review files, generated
   artifacts, and front-door docs.
4. Prove at least one real-path/live-provider governed run without weakening
   local-first and provider-agnostic semantics.
5. Continue narrow runner extractions only where they improve control-loop
   testability; avoid a broad rewrite.

## 3. Evidence Map

### Local docs reviewed

- `README.md`
- `docs/INDEX.md`
- `docs/product-contract.md`
- `docs/daily-driver-current-status.md`
- `docs/roadmap-status.md`
- `docs/plans/work-direction-execution-index-2026-06-10.md`
- `docs/analysis/intent-reassessment-and-worklist-2026-06-11.md`
- `docs/analysis/intent-verification-delta-2026-06-12.md`
- `docs/analysis/competitor-analyses-vs-self-consolidation-2026-06-10.md`
- `docs/analysis/competitor-self-comparison-matrix-2026-06-06.md`
- `docs/analysis/competitor-survey-moratorium-2026-06-10.md`
- `docs/analysis/eval-gate-competitor-absence-2026-06-10.md`
- `docs/architecture/control-loop-ownership-map-2026-06-11.md`
- `docs/architecture/claim-to-test-traceability-matrix.md`
- `docs/testing/test-quality-standards.md`
- `docs/processes/quarterly-competitor-refresh.md`

### Local implementation and tests sampled

- `teaagent/runner/_core.py`
- `teaagent/runner/_plan_validator.py`
- `teaagent/runner/_approval_manager.py`
- `teaagent/tools.py`
- `teaagent/audit.py`
- `teaagent/approval/policy.py`
- `teaagent/cli/__init__.py`
- `teaagent/ergonomics/workspace_defaults.py`
- `tests/acceptance/test_first_hour_e2e_flow.py`
- `tests/acceptance/test_docs_acceptance_count_accuracy.py`
- `tests/acceptance/test_claim_traceability.py`

### Verification commands run during this review

System Python path:

```bash
python3 scripts/validate_docs_consistency.py
```

Result: failed because pytest collection failed. Follow-up collection showed
`tests/test_cli_fuzz_parsers.py` imports `hypothesis`, which is unavailable in
the system Python 3.14 environment. Collection reached 6052 tests before the
single import error.

Repository venv path:

```bash
.venv/bin/python scripts/validate_docs_consistency.py
```

Result: passed. Reported risk register evidence coverage 24/29 rows (82%) and
ticket index evidence coverage 21/21 rows (100%).

Focused docs/claim checks:

```bash
.venv/bin/python -m pytest tests/acceptance/test_docs_acceptance_count_accuracy.py tests/acceptance/test_claim_traceability.py -q
```

Result: 19 passed.

Acceptance collection:

```bash
.venv/bin/python -m pytest tests/acceptance --collect-only -q
```

Result: 646 tests collected.

Acceptance quality audit:

```bash
.venv/bin/python scripts/audit_test_quality.py --tests-dir tests/acceptance --format markdown --fail-on none
```

Result: 646 collected test nodes, 126 test files, 629 test functions, 98
docstrings, 1905 assertions, 17 weak-pattern flags, 0 skip decorators, 58 mock
calls, and no high-risk no-assertion files.

Full acceptance tier:

```bash
python3 scripts/run_acceptance_tier.py --tier all
```

Result: 646 passed, 8 warnings. The warnings are deprecation warnings from
`preapproved_call_ids` in flagship acceptance paths.

### Same-day external source skim

This was a bounded same-day official-source skim, not a full market survey.
Use it for internal direction only; refresh same-day before public use.

- Claude Code overview and security/permission docs:
  - `https://docs.anthropic.com/en/docs/claude-code/overview`
  - `https://docs.anthropic.com/en/docs/claude-code/security`
  - `https://code.claude.com/docs/en/permission-modes`
- OpenAI Codex docs:
  - `https://developers.openai.com/codex/`
  - `https://developers.openai.com/codex/concepts/sandboxing`
  - `https://developers.openai.com/codex/permissions`
  - `https://developers.openai.com/codex/agent-approvals-security`
  - `https://developers.openai.com/codex/enterprise/governance`
- OpenCode docs:
  - `https://opencode.ai/docs`
  - `https://opencode.ai/docs/permissions`
- Aider docs:
  - `https://aider.chat/docs/`
- Cline docs:
  - `https://docs.cline.bot/`
- Kiro docs:
  - `https://kiro.dev/docs/`
  - `https://kiro.dev/docs/specs/`
- Devin docs:
  - `https://docs.devin.ai/`
- OpenHands docs:
  - `https://docs.openhands.dev/overview/introduction`

## 4. Re-Derived Intent

### Evidence

The docs repeatedly converge on a governance-first contract:

- `README.md` frames TeaAgent as a local harness, not a generic hosted coding
  agent clone.
- `docs/product-contract.md` defines the key invariants: local-first,
  provider-adapter based, tool-boundary centered, audit-first, permission-mode
  enforced, bounded runs, and human approval for destructive operations.
- `docs/architecture/claim-to-test-traceability-matrix.md` turns product
  claims into claim/test/evidence rows.
- `docs/analysis/intent-reassessment-and-worklist-2026-06-11.md` already
  names the central product question: can every material action be explained
  by a receipt?
- `docs/analysis/intent-verification-delta-2026-06-12.md` shows the project
  spent a full review cycle not chasing feature breadth, but repairing false
  evidence, config precedence, agent-contribution gates, and verification
  drift.

### Inference

The project goal is not "build the most capable coding agent." It is "build
the smallest useful governed agent harness whose claims can be audited."

That implies a stricter definition of product progress:

- A new feature is progress only if its authority, audit, rollback, cost, and
  evidence semantics are clear.
- A doc update is product work when it changes a claim users rely on.
- A passing test count is not enough; the proof must cover the path a user or
  future agent would actually follow.
- An architecture extraction is useful only if it makes a control loop more
  independently testable or less bypassable.

## 5. Findings

### F1 - The docs gate is green only on the repo venv path

Severity: P0 for developer trust, P1 for product behavior.

The validator passes under `.venv/bin/python` and fails under system `python3`
because the system environment lacks `hypothesis`. This is not a product
runtime failure, but it is a control-plane portability failure: the front-door
validation command in `docs/INDEX.md` says `python3 scripts/validate_docs_consistency.py`.

Why it matters:

If docs are treated as a control plane, the gate should fail with a clear
bootstrap/dependency message or select the project venv consistently. A gate
that means "green if you guessed the right interpreter" is weaker than the
project thesis requires.

### F2 - Flagship proof paths still exercise a deprecated approval mechanism

Severity: P0/P1.

The full acceptance tier passes, but eight warnings come from
`preapproved_call_ids` deprecation in high-value acceptance paths including
first-hour and run-evidence proofs.

Why it matters:

Flagship tests teach future maintainers what "the real path" is. If those
tests continue to use a deprecated approval shortcut, the proof path and the
target architecture slowly diverge.

### F3 - Current-truth documents still have status tension

Severity: P1.

`docs/analysis/intent-verification-delta-2026-06-12.md` says WDG-003
suite-summary refresh remains open after the sixth pass, while
`docs/plans/work-direction-execution-index-2026-06-10.md` marks WDG-003 in the
closed/ongoing set. The tension may be explainable by timing, but it is still
a contradiction a future agent could misread.

Why it matters:

The product thesis depends on claim hygiene. A work item cannot be both closed
and open without a dated supersession note that names the exact remaining gap.

### F4 - Acceptance coverage is broad, but not yet enough real-path proof

Severity: P1.

The acceptance suite is now broad and green. It also still relies heavily on
deterministic adapters, fixture-created evidence, and harness-level assertions.
That is good for contract tests. It is not sufficient as the only proof of
real model behavior, live-provider variance, or agent overreach.

Why it matters:

Competitors are also adding approval and plan workflows. TeaAgent's stronger
claim must be that its receipts survive realistic agent behavior, not only
well-shaped fake decisions.

### F5 - The architecture is improving, but `AgentRunner` remains a gravity well

Severity: P1/P2.

The runner has already started shedding stable pieces such as plan validation
and approval handling. The remaining core still owns many concerns: iteration,
tool execution, policy evaluation, approval requests, budget monitoring,
context compaction, audit events, phase state, and final result handling.

Why it matters:

Centralization is useful while semantics are still forming, but it becomes a
testability risk once the semantics stabilize. The right next extraction is
not a sweeping rewrite; it is a narrow extraction of control loops that need
independent proof.

### F6 - Competitor convergence narrows TeaAgent's public claims

Severity: P1 for positioning.

Official docs now show overlapping primitives across the market:

- Claude Code: permissions, plan mode, auto mode, MCP, skills, hooks, and
  subagent behavior.
- OpenAI Codex: sandbox profiles, approvals, network/domain policies,
  subagents, skills, hooks, enterprise analytics, and compliance export.
- OpenCode: provider flexibility plus allow/ask/deny permission rules.
- Cline: IDE-integrated approval workflows, Kanban/parallel work, and
  enterprise controls.
- Kiro: spec artifacts, steering, hooks, task waves, and MCP.
- Devin and OpenHands: cloud/self-hosted workflows, integrations, teams,
  budgeting, or RBAC surfaces.
- Aider: terminal pair programming with git, lint/test, and many providers.

Why it matters:

TeaAgent should not claim uniqueness for "has permissions" or "has specs."
It should claim only what its receipts prove: local/provider-agnostic
governance, claim-to-test hygiene, run evidence, and potentially an
operator-auditable eval gate if the live-fire proof is completed.

### F7 - Risk coverage is reported but not yet tightened

Severity: P2.

The validator reports risk register evidence coverage at 24/29 rows (82%) but
still exits green under the venv. That may be the intended threshold, but the
five unverified rows should not disappear into a passing command.

Why it matters:

The project is trying to train future agents to respect evidence. A green
command with an embedded partial-coverage warning should create a visible work
item or a documented threshold rationale.

## 6. Competitor Cross-Check

This table records internal positioning implications from official docs as of
2026-06-12. It is not a public comparison matrix.

| Product | Official-doc signal | Implication for TeaAgent |
| --- | --- | --- |
| Claude Code | Terminal/IDE/browser/desktop surfaces; permissions, plan mode, auto mode, MCP, skills, hooks, agent teams/background agents; sandbox and explicit approvals. | Do not claim permissions, plan mode, skills, hooks, or subagents as unique. Prove stricter receipt semantics and local policy clarity. |
| OpenAI Codex | OS-enforced sandbox, permission profiles, network/domain controls, approvals, subagents, skills, hooks, governance analytics, compliance API. | Codex sets a strong sandbox/governance benchmark. TeaAgent's lane is open/local/provider-agnostic receipts, not broader enterprise surface. |
| OpenCode | Provider flexibility, `/init` project instructions, permission config with allow/ask/deny and granular patterns. | Provider-agnostic and permission-config language is shared. TeaAgent needs better evidence bundles, not just similar knobs. |
| Aider | Terminal pair programming, git workflow, lint/test integration, many providers. | Aider remains a simplicity benchmark. TeaAgent should not let governance ceremony obscure first-hour usefulness. |
| Cline | IDE approval workflow, SDK/CLI/Kanban, parallel per-card worktrees, enterprise controls. | TeaAgent currently loses IDE-native and multi-lane ergonomics; compete on auditable local governance first. |
| Kiro | Specs use `requirements.md`, `design.md`, and `tasks.md`; task waves follow dependency graphs. | Spec-first is not unique. TeaAgent must prove that plan/spec gates are enforceable and receipt-backed. |
| Devin | Cloud software-engineer workflow, Slack/Teams/web/IDE/CLI handoffs, explicit completion criteria and verification. | TeaAgent should not chase hosted async by default; it should make local governance receipts more credible than cloud delegation logs. |
| OpenHands | Local, cloud, self-host, SDK, RBAC/permissions, usage reporting, budgeting, scalable agent orchestration. | Enterprise and orchestration surfaces are crowded. TeaAgent's wedge remains small, inspectable, and portable. |

## 7. Socratic Questions

These questions are intentionally sharper than a normal roadmap. They are
designed to catch self-deception before it becomes a product claim.

1. If the docs validator only passes under the right interpreter, is it a gate
   or an environment-sensitive ritual?
2. Should `docs/INDEX.md` publish commands that are known to fail on this
   machine's system Python, or should the commands bootstrap/select the repo
   environment?
3. If flagship acceptance tests use deprecated approval paths, which path are
   we really teaching future agents to preserve?
4. What exact test would fail if a model falsely claimed it had run tests?
5. What exact test would fail if a model edited a second file outside the
   approved plan?
6. What exact test would fail if a provider adapter dropped cost metadata?
7. Which current claim would be embarrassing if copied into a public README
   tomorrow?
8. Are the five unverified risk-register rows intentionally below threshold,
   or are they hidden debt inside a green command?
9. If WDG-003 is both closed and still open depending on the document, which
   source should a future agent trust?
10. What is the minimum receipt a new contributor should see within five
    minutes to understand TeaAgent's difference?
11. Would a skeptical user care more about "646 acceptance tests" or one
    replayable evidence bundle from a realistic run?
12. Which `AgentRunner` responsibility would be safest to extract next because
    its contract is already stable?
13. Which `AgentRunner` responsibility should **not** be extracted yet because
    the semantics are still moving?
14. If competitors all have plan/spec modes, what exactly does TeaAgent's
    plan/spec gate prevent that theirs may not?
15. If competitors all have approval prompts, what exactly does TeaAgent's
    approval receipt preserve that theirs may not?
16. Does the eval gate fail red on a seeded behavioral regression, or only in
    unit tests of the gate machinery?
17. Would a live provider conformance run expose anything the fake adapter can
    never expose?
18. Are generated docs artifacts part of the truth pipeline or optional
    reports? If they are truth, why can they go stale repeatedly?
19. What is the smallest change that would make branch protection enforce the
    project thesis rather than merely document it?
20. Which competitor capability should TeaAgent deliberately refuse because it
    would dilute the local governance harness?

## 8. Work List

| ID | Priority | Work item | Acceptance gate |
| --- | --- | --- | --- |
| IR-2026-06-12-001 | P0 | Make docs validation environment-stable. Either venv-select, bootstrap-check, or emit a precise missing-dev-dependency error before pytest collection. | `python3 scripts/validate_docs_consistency.py` gives an actionable deterministic result on a clean checkout; `.venv/bin/python scripts/validate_docs_consistency.py` still passes. |
| IR-2026-06-12-002 | P0 | Migrate flagship proof flows off `preapproved_call_ids` and onto scoped payload-digest approvals. | Full acceptance tier passes with no `preapproved_call_ids` deprecation warnings in first-hour, five-minute proof, or run-evidence paths. |
| IR-2026-06-12-003 | P0 | Resolve WDG-003 status conflict and suite-summary truth. | `intent-verification-delta`, `work-direction-execution-index`, generated suite summary, and docs index agree on whether WDG-003 is open, partial, or fixed; stale generated artifact fixture fails validation. |
| IR-2026-06-12-004 | P1 | Refresh `daily-driver-current-status.md` if the 06-12 governance batch changed user-visible daily behavior. | Daily-driver doc has a 2026-06-12 review note or an explicit "no behavior change" note with evidence command. |
| IR-2026-06-12-005 | P1 | Turn the 24/29 risk-register evidence coverage into explicit tracked work. | The five unverified rows are named in a ledger with owner/status, or the threshold rationale is documented and tested. |
| IR-2026-06-12-006 | P1 | Add one realistic governed run proof beyond fake-adapter determinism. | A live-provider or replayed-real-provider gated smoke either passes with a receipt bundle or skips only with explicit env-gate rationale; no network call happens unless opted in. |
| IR-2026-06-12-007 | P1 | Run eval-gate live-fire. | A seeded conversational regression makes the eval/release gate red end-to-end, with the red proof recorded. |
| IR-2026-06-12-008 | P1 | Burn down acceptance weak-pattern flags. | `audit_test_quality.py` shows fewer than 10 weak-pattern flags, with all remaining flags documented as acceptable. |
| IR-2026-06-12-009 | P2 | Continue narrow runner extraction. | One stable control loop, preferably receipt completeness or approval digest recording, is extracted with no behavior change and focused tests. |
| IR-2026-06-12-010 | P2 | Update competitor refresh policy after this same-day skim. | The moratorium/quarterly-refresh docs say when same-day official-source refresh is required before public claims. |
| IR-2026-06-12-011 | P2 | Dogfood TeaAgent governance on a TeaAgent repo change. | One repo change is run through TeaAgent itself and a sanitized receipt bundle is linked from `docs/demo/`. |
| IR-2026-06-12-012 | P2 | Audit stash/branch hygiene. | Old agent-created stashes/branches are inventoried; destructive cleanup is gated by human review; future runs cannot stash the harness repo unintentionally. |

Suggested order:

1. IR-001, because every docs/control-plane claim depends on deterministic
   validation.
2. IR-002 and IR-003, because they touch flagship proof credibility.
3. IR-005 and IR-007, because they turn "green but partial" into explicit
   red/green criteria.
4. IR-006 and IR-011, because they provide the realistic proof competitors
   cannot be answered with rhetoric.
5. IR-009 after the proof path is stable enough to avoid refactoring a moving
   target.

## 9. Claim Ledger

| Claim | Status | Evidence | Open constraint |
| --- | --- | --- | --- |
| TeaAgent's thesis is governance-first, local-first, and provider-agnostic. | Strong | README, product contract, claim matrix, 06-11/06-12 intent docs. | Keep public language scoped to receipt-backed capabilities. |
| Acceptance suite is currently green. | Strong for venv/current tier | Full acceptance tier: 646 passed, 8 warnings. | Warnings use deprecated approval path. |
| Docs consistency is green. | Conditional | `.venv/bin/python scripts/validate_docs_consistency.py` passes. | System `python3` path fails due missing dev dependency. |
| Competitor vocabulary has converged on permissions/specs/hooks/subagents. | Strong as internal same-day skim | Official docs skim on 2026-06-12. | Refresh same-day before publication. |
| TeaAgent has a unique public eval-gate advantage. | Not yet claimable | Existing `eval-gate-competitor-absence` doc plus current work list. | Needs live-fire red proof and same-day competitor refresh. |
| `AgentRunner` extraction should continue. | Inference | Runner size/responsibility sampling plus control-loop map. | Extract only stable control loops with tests. |

## 10. Sufficiency Gate

This artifact is sufficient for internal planning because it:

- starts from current docs rather than from a new feature wish list;
- distinguishes verified commands from inference;
- records the system-Python validator failure instead of smoothing it over;
- uses official competitor docs only for current external facts;
- converts critique into work items with acceptance gates.

It is **not** sufficient for:

- public competitor positioning;
- claims that TeaAgent has a market-unique eval gate;
- enforcement-mode or branch-protection changes;
- destructive cleanup of stashes/branches.

Those require human review and fresh evidence at the point of action.

