# Risk Report — `GitBranchSandbox.keep()` restores original branch

**Date:** 2026-09-14 · **Scope:** `teaagent/sandbox/_git_branch.py` `keep()` only
**High-risk path touched:** `teaagent/sandbox/_git_branch.py` (sandbox lifecycle)

## What changes

`keep()` previously popped the auto-stash but never ran
`git checkout <original_branch>`, so a headless run's `keep` resolution left
the working tree checked out on the sandbox branch. The next run then created
a nested sandbox whose `original_branch` was the prior sandbox, not `main`
(observed live: `teaagent-sandbox-d78f…` recorded `original_branch:
teaagent-sandbox-bd0b…`).

`keep()` now `git checkout`s back to `_original_branch` before popping the
stash, matching `merge()`/`rollback()`/`discard()`, while still preserving the
sandbox branch (not deleted) for review.

## Risk assessment

- **Blast radius:** one method on the sandbox lifecycle. `merge`, `rollback`,
  and `discard` already switch back; `keep` was the only path that did not.
- **Failure mode:** if the checkout fails (e.g., dirty tree blocking the
  switch), `keep()` now returns `success=False` with an error instead of
  silently stranding HEAD — a louder, safer failure than the prior silent
  mis-branch. The sandbox branch is still preserved for manual recovery.
- **Backward compatibility:** callers that relied on HEAD staying on the
  sandbox branch after `keep()` would now find HEAD on the original branch.
  No caller depends on the stranded state — it was the bug.
- **Rollback:** revert the hunk; `keep()` returns to leaving HEAD on the
  sandbox branch (reintroducing the nesting bug).

## Decision

Proceed. The change makes `keep()` consistent with every other resolution and
fixes a real dogfooding-observed defect (nested sandboxes, stranded HEAD).
