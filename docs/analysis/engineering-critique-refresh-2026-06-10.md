# Engineering Architecture Critique — Refresh
# 2026-06-10

> **Claim class:** Dated evidence package.
> **Anchor:** TeaAgent at commit `8fcd781` (HEAD on 2026-06-10).
> **Refreshes:** [Engineering Architecture Critique (2026-06-06)](engineering-architecture-critique-2026-06-06.md), which was anchored at `ad5e2d7`.
> **Method:** Git delta analysis (`ad5e2d7..HEAD`: 81 commits, ~75,010 insertions / ~11,839 deletions across 694 files), import-graph wiring checks on new modules, and spot reads of changed subsystems. Full reasoning trace: [System Review Reasoning Ledger (2026-06-10)](system-review-reasoning-ledger-2026-06-10.md).

---

## Verdict

The four days since the last review delivered real closures of previously named
debts (TUI monolith decomposition, audit integrity P0s, subagent isolation
default, batch timeout, durable approval backend interface) **and** introduced a
new, larger instance of the project's recurring failure mode: a ~12,000-line
H4/H5/H6 component drop whose governance and eval modules are not imported by
any production code path. The codebase is accumulating verified-but-unwired
capability faster than it integrates it, and the canonical status document
already disagrees with the commit log about what is done.

---

## What Improved Since 2026-06-06 (Evidence)

| 06-06 finding | Status at `8fcd781` | Evidence |
| --- | --- | --- |
| Monolithic TUI entry point (~1,000+ line `tui/__init__.py`) | **Resolved.** `tui/__init__.py` is now 36 lines; logic split into `core.py`, `state.py`, `rendering.py`, `_commands.py`, `_setup.py`, cockpit modules (4,301 lines total across the package). | `teaagent/tui/` package listing; `wc -l` |
| Silent audit disk-write failures, HMAC key fragility, legacy chain resets | **Resolved at P0 level.** Commit `5d1c25f` (P0 audit integrity), key-save OSError now warns, strict-chain work tracked in roadmap critical-path table. | `git log`; `docs/roadmap-status.md` critical-path table |
| Default subagent isolation `shared` (WS2-001) | **Resolved.** Shared workspace now requires explicit `isolation='shared'`; worktree default on git workspaces; env override with warning on non-git workspaces. | `teaagent/subagents/_isolation.py:26-60` |
| Subagent batch had no timeout (WS2-002) | **Resolved.** `DEFAULT_SUBAGENT_BATCH_TIMEOUT_SECONDS = 300`. | `teaagent/subagents/_isolation.py:19` |
| Process-only approval queues (WS2-005) | **Interface landed.** `teaagent/coordination/approval_backend.py` defines a durable file-backed default with snapshot recovery and a `remote` extension point. | Module docstring and `BACKEND_FILE` / `BACKEND_REMOTE` constants |
| No run receipt (WS1-001) | **Resolved and wired.** `teaagent/run_receipt.py` is imported by CLI run/runs handlers and TUI commands. | Import grep across `teaagent/cli/_handlers/`, `teaagent/tui/_commands.py` |
| Approval-ID-first UX (WS1-002) | **Resolved.** Numbered destructive-approval selectors are listed as supported in the non-goals doc and unified queue contract (`5ea042f`). | `docs/strategy/remote-multi-agent-non-goals-2026-06-06.md` "Supported today" |
| No mutation gate for trust modules | **Resolved.** A2 permission binding (`7c83e01`) and A3 nightly mutation smoke (`35c7cb0`) with registry tests. | `.github/workflows/nightly-mutation.yml`, `scripts/run_mutation_smoke.py` |

This is genuine engineering progress, and it tracked the WS1/WS2/WS3 backlog
from the 06-06 package almost line-by-line. The backlog mechanism works.

---

## New Findings (2026-06-10)

### ENG-R1 — H4/H5 component clusters are implemented but unwired (High)

Commit `fe2a881` added ~12,188 lines: `rbac.py`, `policy_engine.py`,
`policy_routing.py`, `consensus_validation.py`, `eval_suite.py`,
`release_gate.py`, `scope_creep.py`, `prompt_regression.py`,
`repo_map_benchmark.py`, `context_health.py` extensions, cockpit screens, and a
full `update/` package, plus 291 tests.

Import-graph check at HEAD:

- The **H4 governance cluster** (`rbac`, `policy_engine`, `policy_routing`,
  `consensus_validation`) is imported **only by other members of the same
  cluster**. Nothing in `runner/`, `approval/`, `subagents/`, `gateway/`,
  `cli/`, or `_lazy_exports.py` references it.
- The **H5 eval cluster** (`eval_suite`, `release_gate`, `scope_creep`,
  `prompt_regression`, `repo_map_benchmark`) likewise only imports within
  itself. No script under `scripts/` and no workflow under
  `.github/workflows/` invokes `release_gate` or `eval_suite`.
- Only `tui/cockpit_data_sources.py` → `tui/__init__.py` (H4-001 cockpit) is
  wired into a user-reachable surface.

Consequence: the commit message claim "Implement Horizon H4, H5, and H6 core
components" is true at the component level and **untrue at the system level**.
RBAC does not protect any real agent action; the policy engine governs no real
route; the release gate gates no release. The 291 tests verify islands.

This is the same shape as earlier findings about parallel approval/plugin
systems, now at horizon scale. Component-first development is a defensible
strategy **only if** the unwired state is explicitly labeled and the wiring is
a tracked, gated work item. Today neither is true.

### ENG-R2 — Canonical status document contradicts the commit log (High)

`docs/roadmap-status.md` ("Canonical source of truth", last updated 2026-06-07)
lists H4, H5, H6 as **Pending** and M4/M5/M6 as **Pending**, while commits
`f2c835a`, `4e0a9e9`, `111c61c`, `fe2a881` claim H4/H5/H6 implementation. It
also lists horizons H2 and H3 as **Pending** while their exit milestones M2 and
M3 are marked **Complete** in the same file. Given ENG-R1, "Pending" is
arguably the *more* accurate label for H4–H6 — but the document and the commit
history now tell opposite stories, and the merge gate
(`scripts/validate_docs_consistency.py`) did not catch it because it validates
internal doc consistency, not doc-vs-code wiring.

### ENG-R3 — Root-module sprawl continues (Medium)

`teaagent/` now contains **183 top-level modules** (444 `.py` files
package-wide, up from ~366 on 06-06). The new H4/H5 modules were added at the
root rather than into the existing `governance/`, `consensus/`, or
`coordination/` packages — three of which already exist and have overlapping
names with the new files (`teaagent/consensus/` vs
`teaagent/consensus_validation.py`, `teaagent/governance/` vs
`teaagent/policy_engine.py`). The 06-06 finding about duplicate/parallel
systems is reproducing.

### ENG-R4 — Review capacity vs. change velocity (Medium)

81 commits and a net +63k lines in four days, including two commits above
10k lines each. The A1–A3 governance gates (spec quality gate, permission
binding, mutation smoke) cover L3 trust modules only; nothing gates "new
subsystem must be wired or labeled experimental." Velocity at this rate makes
the dated-review process (this package) the only integration check, and it is
manual.

### ENG-R5 — Test suite scale (Low, watch)

Roadmap claims 4,758 tests passing at H1 completion (06-07); the 06-04 memory
recorded 3,355. The suite grew ~40% in three days. A full re-run was started
for this review (result recorded in the
[package index](system-critical-review-2026-06-10-INDEX.md)). At this growth
rate, suite runtime and flake management become engineering constraints of
their own; there is no tiering (smoke/full) in the default developer loop yet.

---

## Standing Findings Carried Forward (Unresolved)

- Mutable run `context` dict in the runner remains.
- `AgentService` shared run contract (WS5-001) exists as
  `integration/run_contract.py` but CLI/TUI convergence on it is partial.
- Stable event-stream contract (WS5-002) not yet observed as a consumer-facing
  interface.
- Provider cost-state taxonomy (WS3-004) partially addressed via receipts; the
  estimated-vs-reported distinction still leaks to users in places.

---

## Engineering Recommendations (feed into work directions)

1. **Wire-or-quarantine rule:** every new module must either be reachable from
   a production entry point (CLI, TUI, runner, gateway, CI) or carry an
   explicit `experimental — unwired` label in module docstring and roadmap.
   Add a validator that diffs `teaagent/*.py` against the import graph from
   entry points and fails on unlabeled islands. This converts ENG-R1/R2 from a
   recurring manual finding into a gate.
2. **Pick the canonical home** for policy/consensus/governance code and fold
   the new root modules in (or re-export and deprecate). Stop root growth at
   183.
3. **Tier the test suite** (smoke / full / nightly-mutation) before it crosses
   ~6k tests.
4. **Status truth:** roadmap-status updates must accompany any commit whose
   message claims a horizon/milestone, enforced by a commit-message↔roadmap
   consistency check.
