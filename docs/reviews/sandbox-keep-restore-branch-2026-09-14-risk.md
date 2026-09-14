# Risk Report — sandbox `keep()` + headless resolution restore original branch

**Date:** 2026-09-14 · **Scope:** `teaagent/sandbox/_git_branch.py` `keep()` + `teaagent/cli/_handlers/_agent/sandbox_resolution.py` headless path
**High-risk paths touched:** `teaagent/sandbox/_git_branch.py`, `teaagent/cli/_handlers/_agent/sandbox_resolution.py` (sandbox lifecycle)

## What changes

`keep()` previously popped the auto-stash but never ran
`git checkout <original_branch>`, so a headless run's `keep` resolution left
the working tree checked out on the sandbox branch. The next run then created
a nested sandbox whose `original_branch` was the prior sandbox, not `main`
(observed live: `teaagent-sandbox-d78f…` recorded `original_branch:
teaagent-sandbox-bd0b…`).

`keep()` now `git checkout`s back to `_original_branch`, then squash-merges
the sandbox branch and `git reset`s so the agent's changes land as
uncommitted edits in the working tree. HEAD returns to the original branch
(no nesting) while the work stays visible for review/undo — the first-hour
acceptance test depends on the changes being present after a headless run.

The headless path in `resolve_git_sandbox_after_run` compounded this: it
recorded `resolution='keep'` in the audit trail but never invoked
`sandbox.keep()`, so the branch was never restored even after `keep()` was
fixed. It now calls `sandbox.keep()` and records the real result (success +
error), so the audit event reflects what actually happened.

## Risk assessment

- **Blast radius:** one method on the sandbox lifecycle. `merge`, `rollback`,
  and `discard` already switch back; `keep` was the only path that did not.
  The squash-merge applies the same diff `merge` would, just uncommitted.
- **Failure mode:** if the checkout or squash-merge fails (e.g., a real merge
  conflict with the restored stash), `keep()` returns `success=False` with an
  error instead of silently stranding HEAD — a louder, safer failure. The
  sandbox branch is still preserved for manual recovery.
- **Backward compatibility:** callers that relied on HEAD staying on the
  sandbox branch after `keep()` now find HEAD on the original branch with the
  changes applied uncommitted. No caller depended on the stranded state — it
  was the bug. The visible-changes behavior matches the acceptance test's
  contract.
- **Rollback:** revert the hunk; `keep()` returns to leaving HEAD on the
  sandbox branch (reintroducing the nesting bug).

## Decision

Proceed. The change makes `keep()` consistent with every other resolution and
fixes a real dogfooding-observed defect (nested sandboxes, stranded HEAD).
