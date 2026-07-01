# ADR 0042: Shell-Mutation Reversibility Boundary (SEC-11)

## Status

Accepted — 2026-07-01

**Expiry review:** 2027-01-01 (re-score whether the default reversibility posture
for shell-heavy runs should change, and whether the `UndoJournal` fallback path
should integrate `GitBranchSandbox` transactions once the run path is unified per
ADR-0041)

## Context

SEC-11 (`docs/security/risk-register-and-threat-model-2026-06-02.md`, `H·M·6`)
states: *"`UndoJournal._PATH_WRITE_TOOLS` covers file tools only;
`workspace_run_shell_mutate` not tracked — UI shows 'undo available' but shell
side-effects are unrecoverable."* The finding conflates two questions that must
be decided separately:

1. **Can the harness reverse the *in-worktree* file effects of a shell
   mutation?** — Yes, and it already does, but only on one of two undo paths.
2. **Can the harness reverse the *out-of-worktree / external* effects of a shell
   mutation** (writes to `$HOME`, `/tmp`, system paths; network calls; database
   or remote-service state; deletions outside the tree)? — No mechanism can, and
   claiming otherwise re-creates the very "false undo safety" SEC-11 warns about.

TeaAgent ships **two** reversibility mechanisms today:

- **`GitBranchSandbox`** (`teaagent/sandbox/_git_branch.py:118`) — a
  transactional git-branch sandbox. `start()` (`:141`) creates
  `teaagent-sandbox-<run_id>`; each governed tool call is committed via a
  `GitTransactionSink` audit sink (`teaagent/cli/execution.py:216`;
  `commit_transaction()` at `:205` does `git add -A` + `git commit`);
  `rollback()`/`discard()` (`:244`, `:460`) run `git reset --hard` + `git clean
  -fd` and delete the branch. Because `git add -A` captures **every** worktree
  change — including files a shell command created or modified — this path **does
  reverse in-worktree shell mutations**.
- **`UndoJournal`** (`teaagent/run_undo.py`) — per-file before/after snapshots for
  path-write tools only (`_PATH_WRITE_TOOLS`: `workspace_write_file`,
  `workspace_apply_patch`, `workspace_edit_at_hash`). Shell-mutate tools
  (`_SHELL_MUTATE_TOOLS`: `workspace_run_shell_mutate`, `workspace_run_shell`)
  have no stable path to snapshot, so they are **never journaled**.

The live `agent undo` path already prefers the stronger mechanism:
`teaagent/cli/_handlers/_agent/preflight.py:90-114` attempts `GitBranchSandbox`
rollback **first** and only falls back to `UndoJournal` when the git sandbox is
unavailable. The git sandbox is offered by default: `--git-sandbox`
(`teaagent/cli/_agent_parsers.py:145`) plus consent-gated auto-enable
(`teaagent/cli/_handlers/_agent/run.py:335-411`, default
`git_sandbox_consent='prompt'` at `teaagent/ergonomics/workspace_defaults.py:35`).

**So the real gap is narrow and situational**: when the git sandbox is *not*
active (non-git workspace, or the operator declined consent), `agent undo` falls
back to the file-only `UndoJournal`, which cannot reverse shell mutations — yet
several **reporting** surfaces derived undo availability purely from "a journal
exists" and reported an unqualified "undo available." That unqualified claim was
the concrete SEC-11 exposure and was closed in 2026-07-01 (action S-P2-11):
`RunEvidenceSummary.rollback_shell_partial`, the run receipt's
`available (partial — shell mutations not reversed)` rendering, and
`RunStateSnapshot.undo_shell_partial` now qualify the claim, and the interactive
undo surfaces (CLI, TUI) already emit `PARTIAL_UNDO_SHELL_WARNING`
(`teaagent/run_undo.py:73`).

What remained undecided — and what this ADR settles — is the **target boundary**:
how much reversibility the harness commits to, on which path, and what it
explicitly refuses to promise.

## Decision

Ratify a **two-tier, disclosure-honest reversibility model** as the intended
SEC-11 posture, and explicitly bound it:

1. **Tier 1 — transactional reversibility (`GitBranchSandbox`).** For git
   workspaces with the sandbox active, reversal of **in-worktree** effects
   (including those produced by shell-mutating tools) is a supported guarantee,
   delivered by `git reset --hard` + `git clean -fd` on rollback. This is the
   recommended path for runs that will execute shell mutations.

2. **Tier 2 — snapshot fallback (`UndoJournal`) + mandatory disclosure.** For
   non-git workspaces or declined-consent runs, undo reverses path-write tools
   only. This path MUST disclose its partiality on **every** surface that reports
   undo/rollback availability — interactive (warning) and non-interactive
   (evidence summary, run receipt, run-state contract). No surface may report
   unqualified undo availability when a run used shell-mutating tools. This is a
   standing invariant, not a one-time fix.

3. **Out of scope by design — external side effects.** Post-hoc reversal of
   effects that escape the git worktree (writes under `$HOME`/`/tmp`/system
   paths, network and remote-service mutations, database changes, deletions
   outside the tree) is **not** a harness responsibility and MUST NOT be claimed.
   Reversibility of such effects is obtainable only by *containment before
   execution* — Docker/OS isolation (`teaagent/subagents/_isolation.py`, SEC-07
   hardening) whose container is discarded wholesale — not by an undo journal.
   Attempting selective post-hoc reversal here would reintroduce false-safety.

Consequently, SEC-11 is treated as **mitigated at its achievable ceiling**: the
achievable part (in-worktree reversal + honest disclosure of the fallback's
limits) is delivered; the unachievable part (external-effect reversal) is
documented as an explicit non-goal and routed to isolation instead.

## Rationale

- **Do not manufacture false safety.** A naive "snapshot the worktree before
  every shell call and restore on undo" would cover the same in-worktree scope
  `GitBranchSandbox` already covers, while silently missing external effects —
  the exact failure mode SEC-11 names. Honest disclosure of a partial guarantee
  is safer than a broader-looking guarantee that lies at the edges.
- **Reuse the mechanism that exists.** `GitBranchSandbox` is already wired into
  `agent run`/`agent undo` and already reverses in-worktree shell mutations.
  SEC-11 does not need a new subsystem; it needs a decided boundary and honest
  reporting — both now in place.
- **Avoid data-loss risk in the default path.** Wiring `git reset --hard` /
  `git clean -fd` semantics into the *fallback* undo (which today never destroys
  un-snapshotted files) would put user-created, un-tracked files at risk on undo.
  That is a high-risk runtime change (`docs/reviews/*-risk.md` + Human Review per
  `AGENTS.md`), and must not be smuggled in as a "reversibility improvement."
- **Thin-harness alignment.** Containment-before-execution (isolation) is the
  correct home for external-effect reversibility; the harness governs and
  discloses rather than attempting to model every possible side effect.

## Implementation

No code change lands with this ADR; it ratifies and bounds existing behavior. The
supporting code and disclosure already exist:

- Tier 1: `teaagent/sandbox/_git_branch.py:118` (`start`/`commit_transaction`/
  `rollback`/`discard`), `teaagent/cli/execution.py:216` (`GitTransactionSink`),
  `teaagent/cli/_handlers/_agent/run.py:335-411` (consent-gated auto-enable),
  `teaagent/cli/_handlers/_agent/preflight.py:90-114` (undo prefers git rollback).
- Tier 2 disclosure (action S-P2-11, commit `5316c50`):
  `teaagent/run_undo.py:73` (`PARTIAL_UNDO_SHELL_WARNING`,
  `audit_events_used_shell_mutate`), `teaagent/evidence_summary.py`
  (`rollback_shell_partial`), `teaagent/run_receipt.py` (partial rendering),
  `teaagent/integration/run_state.py` (`undo_shell_partial`).

**Gated follow-up (deferred, requires its own risk review + Human Review; do NOT
start without them):** raise Tier-2 coverage by *warning before effects occur* —
surface at run start, when a run is about to make shell mutations without an
active sandbox, so the operator can opt into the sandbox first. Any change to
default `git_sandbox_consent` or to fallback-undo destructiveness is a high-risk
runtime change and MUST be tied to the ADR-0041 governed-execution unification so
`agent run` and `SubagentManager` do not diverge.

## Consequences

- **Positive:** SEC-11 has a decided, defensible boundary; every undo-reporting
  surface is honest; no new subsystem; no data-loss risk added to the default
  path; external-effect reversibility is correctly routed to isolation.
- **Positive:** Enterprise/production claims about "undo" can now be stated
  precisely (in-worktree transactional reversal via git sandbox; disclosed
  partial otherwise; external effects require isolation).
- **Negative / accepted:** In non-git or declined-consent runs, shell mutations
  remain non-reversible; the mitigation is disclosure, not recovery. Operators
  who need reversibility for shell-heavy work must enable the git sandbox or run
  in isolation.
- **Negative / accepted:** The two-path undo (git sandbox vs. journal) persists
  until the ADR-0041 unification; documented here as intentional, not drift.

## Alternatives Considered

- **Worktree-snapshot the fallback undo and restore on undo** — rejected: same
  in-worktree scope as `GitBranchSandbox` but silently misses external effects
  (re-creates false safety), and `restore` risks destroying un-snapshotted user
  files (data loss) in the previously-non-destructive fallback path.
- **Attempt external-effect reversal (network/DB/system compensation)** —
  rejected: not generally possible; would require per-tool inverse operations the
  harness cannot know; false-safety by construction.
- **Force git sandbox on by default (remove consent prompt)** — rejected here:
  changes default run semantics (creates branches/commits, `git reset --hard` on
  rollback) and is a high-risk runtime change; deferred to the gated follow-up
  under ADR-0041 with its own risk review.
- **Leave SEC-11 as "documented, no decision"** — rejected: left the boundary and
  the reporting-honesty invariant unstated, which is how the unqualified
  "undo available" claim persisted.

## References

- SEC-11 — `docs/security/risk-register-and-threat-model-2026-06-02.md` (Part 2.1)
- Action S-P2-11 (disclosure), G-P2-6 (this ratification) — `docs/retrospective/06-action-register.md`
- ADR-0041 (execution surface unification — governed-execution layer that a future default-changing follow-up must build on)
- ADR-0020 (hardened sandbox virtualization — isolation as the external-effect containment path)
- `teaagent/sandbox/_git_branch.py`, `teaagent/run_undo.py`, `teaagent/cli/_handlers/_agent/preflight.py`, `teaagent/cli/_handlers/_agent/run.py`
