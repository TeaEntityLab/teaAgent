# Parallel Phase 0 Implementation Report
# 2026-06-04

## Purpose

This report records the current project state after a documentation-led review
and five parallel implementation lanes. It is intentionally practical: it
connects what the documents said, what the code now does, what remains risky,
and which work items should be done next.

The main operating principle for this pass was safety first. Daily usability
matters, but a daily-driver agent is only useful if its approval, memory,
session, and documentation contracts are hard to misunderstand.

## Source Documents Reviewed

Primary source-of-truth documents:

- `docs/daily-driver-current-status.md`
- `docs/work-log/phase-0-priority-work-items-2026-06-04.md`
- `docs/security/phase-0-trust-repair-risk-brief-2026-06-04.md`
- `docs/reviews/project-state-critical-questioning-2026-06-04.md`
- `docs/roadmap-status.md`
- `docs/plans/ticket-plans/index.md`
- `docs/plans/ticket-plans/inline-todos.md`

Module-level documents used as consistency checks:

- `docs/modules/approval_manager/spec.md`
- `docs/modules/policy/api.md`
- `docs/modules/runner/api.md`
- `docs/modules/runner/risks.md`
- `docs/modules/memory/spec.md`
- `docs/modules/memory/api.md`
- `docs/modules/memory/inspection.md`
- `docs/modules/memory/risks.md`

## Parallel Work Lanes

| Lane | Focus | Main outcome |
| --- | --- | --- |
| Lane 1 | Chat REPL suspension UX | Removed stale resume instructions from `/background` output and added regression assertions. |
| Lane 2 | TUI session clear | Made `session clear` clear persisted session state, not only the in-memory list. |
| Lane 3 | Memory catalog cache correctness | Added metadata-based invalidation so external file updates refresh cached memory entries. |
| Lane 4 | Docs validation governance | Added roadmap-status validation for H0 documentation-current-truth/doc-vs-HEAD guard references. |
| Lane 5 | Approval full-access gate | Made `allow_all_destructive` inert in prompt mode; legitimate bypass callers must promote to an explicit broad permission mode. |

## Current Implementation Facts

### Approval and permission boundary

- `allow_all_destructive=True` is no longer enough to bypass destructive
  approval in `prompt` mode.
- `full_access_acknowledged=True` is now metadata, not authority.
- Chat destructive mode maps the explicit `--allow-destructive` user flag to
  `PermissionMode.DANGER_FULL_ACCESS`.
- Auto mode returns a `danger-full-access` approval policy and is still scoped
  by `AutoModeGuard`.
- `PermissionMode.ALLOW` and `PermissionMode.DANGER_FULL_ACCESS` remain broad
  modes; they must be treated as deliberate trust-boundary changes.

### Approval authority naming

- The canonical approval authority remains
  `teaagent.approval_manager.ApprovalManager`.
- The runner-local helper is now documented and guarded as
  `RunnerApprovalCoordinator`, reducing the chance that future agents patch the
  wrong approval class.

### Memory authority

- `teaagent.memory.catalog` is the canonical implementation.
- `teaagent.memory` and `teaagent.memory_legacy` re-export the same classes for
  compatibility.
- A regression test now proves that the package export, public memory package,
  canonical module, and legacy import path resolve to the same `MemoryCatalog`.

### Daily-driver UX

- TUI `session clear` now persists the cleared session.
- Chat `/background` no longer prints a stale direct `teaagent resume` command
  that did not match the actual background-review path.
- Full REPL suspend-to-resume rehydration remains open. The current fix is an
  honesty repair, not full continuity.

### Documentation governance

- Roadmap validation now checks that H0 claim/risk hygiene remains connected to
  documentation-current-truth and doc-vs-HEAD guard work.
- Current-state docs were updated to distinguish fixed daily-driver issues from
  historical evidence.
- Historical docs were not deleted. The preferred pattern is supersession plus
  a current front door, not erasing audit trails.

## Critical Reflections

### The project is useful, but its usefulness depends on trust clarity

TeaAgent already has enough harness, tool governance, TUI/CLI surface area,
audit logging, and tests to be useful for daily local workflows. The risk is not
that the project lacks features. The risk is that users and future agents cannot
quickly tell which features are safe, current, and supported.

The highest-leverage work is therefore not more surface area. It is reducing the
number of hidden trust paths.

### High test count is not enough

The test suite is large, but the approval-gate change shows why intent matters.
A test can preserve a dangerous behavior if it was written around legacy output.
Security-sensitive tests should assert the desired contract, not only the old
contract.

Rule for future work:

- For safety behavior, ask: "Would this test fail if a caller silently gained
  more authority than the UI says?"
- For daily UX behavior, ask: "Would this test fail if the UI tells the user to
  do something that does not actually work?"
- For docs governance, ask: "Would this check fail if a current-status document
  drifted away from HEAD?"

### `danger-full-access` is a product feature and a product liability

The project needs an escape hatch for trusted automation. Removing
`danger-full-access` would make some real workflows worse. The better design is
to make entry explicit, auditable, visually obvious, and hard to persist by
accident.

The remaining risk is not the existence of the mode. The remaining risk is mode
ceremony: how users enter it, how long it lasts, how it is logged, and how it is
displayed in CLI/TUI/chat.

### Documentation has shifted from "missing" to "governance-heavy"

The documentation corpus is strong. The problem is now discovery and state
authority. A maintainer should not need to read ten dated reviews to learn
whether a P0 item is still open.

Recommended pattern:

- Dated review documents stay immutable except for supersession notes.
- Current truth lives in canonical status documents.
- Execution truth lives in ticket plans and indexes.
- Risk truth lives in risk registers plus module `risks.md` files.
- Roadmap truth lives in `docs/roadmap-status.md`.
- Validation scripts guard the front doors.

## Risk Register Delta

| Risk | Before this pass | Current state | Residual risk |
| --- | --- | --- | --- |
| Prompt-mode destructive bypass | Active critical risk | Fixed and regression-guarded | Broad modes still need ceremony/audit UX. |
| Duplicate approval manager naming | Active high risk | Fixed and regression-guarded | Future helpers must not reuse authority class names. |
| Policy/approval import boundary | Historical high risk | Import-order tests pass | Keep shared helpers outside both modules. |
| Memory canonical source split | Historical medium risk | Fixed by re-export structure and regression test | Do not add behavior to `memory_legacy.py`. |
| TUI `session clear` persistence | UX correctness gap | Fixed and tested | Broader TUI persistence parity still needs journey tests. |
| Chat `/background` stale instruction | UX honesty gap | Fixed and tested | Full resume rehydration remains open. |
| Optional dependency audit | Open | Not changed in this pass | Needs separate base/dev/optional audit policy. |
| Coverage omit governance | Open | Not changed in this pass | Needs owner/reason/return milestone ledger. |

## Follow-Up Closure Note

Later on 2026-06-04, the two open governance items above were closed:

- `docs/governance/coverage-omit-ledger.md` now includes every
  `pyproject.toml` coverage omit pattern with owner, reason, risk, return
  milestone, and smoke-test candidate.
- `scripts/validate_docs_consistency.py` now fails when the coverage omit
  ledger drifts from `pyproject.toml`.
- `docs/security/dependency-audit-policy.md` and
  `.github/workflows/security.yml` now split base, dev/lockfile, and
  optional-extra dependency audits.
- The base PR gate no longer uses unscoped `pip-audit --skip-editable`, which
  could audit packages from the runner or audit-tool environment instead of the
  TeaAgent base dependency surface.

## Prioritized Work List

### P0 - next safety and stability work

1. Add a full-access entry ceremony and audit event.
   - Why: current code gates prompt-mode bypass, but broad mode entry still
     needs stronger operator evidence.
   - Acceptance: enabling `danger-full-access` emits a hash-chained event with
     mode, caller surface, workspace, and confirmation source.
   - ROI: high. It turns a necessary escape hatch into an accountable action.

2. Add an auto-mode policy restoration test.
   - Why: runner risk RUN-R-001 still documents in-place policy replacement.
   - Acceptance: a test proves the runner does not retain auto-mode
     `danger-full-access` policy after auto mode ends, or the design formally
     documents that auto mode is run-lifetime only.
   - ROI: high. It guards a trust-boundary persistence bug.

3. Convert coverage omit smoke candidates into direct tests.
   - Why: the omit ledger now exists; the next risk is letting smoke candidates
     remain indirect forever.
   - Acceptance: each omitted security- or UX-sensitive path has direct smoke
     coverage or a documented non-testable rationale.
   - ROI: high. It prevents silent decay in security-relevant modules.

4. Resolve optional-extra audit findings by extra.
   - Why: audit lanes are now separated, but optional ecosystems are real attack
     surface once enabled.
   - Acceptance: each optional-extra vulnerability has fix, upstream wait,
     mitigation, or release-blocking decision with owner and date.
   - ROI: high. It avoids both false panic and false confidence.

5. Assign or close proposed ADRs.
   - Why: proposed decisions with no owner become architectural fog.
   - Acceptance: each proposed ADR has owner, due date, and status transition.
   - ROI: medium-high. It reduces future planning ambiguity.

### P1 - daily-driver product work

6. Finish chat background resume rehydration.
   - Why: the current fix stops misleading the user; it does not complete the
     continuity promise.
   - Acceptance: a backgrounded chat can be resumed with provider/model/root,
     messages, cost, and approval context restored or explicitly unavailable.
   - ROI: high for daily usage.

7. Add CLI/TUI parity journey tests for session, cost, approval, undo, and
   memory.
   - Why: individual fixes can still leave cross-surface drift.
   - Acceptance: one acceptance flow exercises equivalent state across CLI and
     TUI.
   - ROI: high for user trust.

8. Add a generated docs front door.
   - Why: current docs are valuable but too numerous for quick navigation.
   - Acceptance: `docs/INDEX.md` links current status, risk, roadmap, ticket
     index, ADRs, module docs, and historical evidence.
   - ROI: medium-high. It helps both humans and agents.

9. Add smoke tests for remaining coverage-omitted packages.
   - Why: "not covered" should never mean "not even importable".
   - Acceptance: each omitted package has a smoke test or documented non-test
     rationale.
   - ROI: medium.

10. Add mode-state UX indicators in TUI/chat.
    - Why: users should always know when they are in a broad permission mode.
    - Acceptance: TUI/chat headers or status panels show permission mode,
      broad-mode warning, and approval policy source.
    - ROI: medium-high for safety and confidence.

## Cost-Effectiveness Assessment

Highest ROI work:

- Approval mode entry/audit ceremony.
- Auto-mode restoration contract.
- Direct smoke tests for omitted trust-sensitive modules.
- Optional-extra dependency remediation.
- Chat resume rehydration.

Lower ROI until P0 is stable:

- New provider surfaces.
- New plugin ecosystems.
- More competitive positioning documents without freshness automation.
- Large UI redesigns that do not clarify trust state.

The project should spend the next sprint reducing hidden state and stale claims,
not expanding the number of ways to run agents.

## Questions Future Reviewers Should Ask

1. Can a user tell, before a tool call, whether the call can mutate the
   workspace?
2. Can an audit reviewer prove who or what enabled broad permission mode?
3. Can a future agent find the current status of a risk without reading dated
   historical layers?
4. Can the test suite fail for the most dangerous trust regressions, not merely
   for output formatting changes?
5. Can optional dependencies be enabled without silently changing the security
   profile?
6. Can TUI chat, CLI chat, and agent mode share enough state that users do not
   feel punished for switching surfaces?

## Verification Expectations

For this pass, minimum verification should include:

- Focused approval-gate tests.
- TUI session persistence tests.
- Chat suspend/background output tests.
- Memory catalog tests.
- Docs consistency tests.
- Roadmap-status validation.
- Lint.
- Full pytest run when local runtime permits.

If a future environment cannot run the full suite, the final report must name
the blocked command, the environment reason, and the highest-risk unverified
surface.
