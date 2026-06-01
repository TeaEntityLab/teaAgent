# Daily-Driver Human Review Gates
# 2026-06-02

Some daily-driver changes are reversible code edits but still deserve human review
because they change trust, authority, or recovery semantics.

## Gate table

| Gate | Required when | Reviewer question |
|------|---------------|-------------------|
| HR-001 Root authority | Changing root persistence or `--root` precedence. | Can a user predict the repository being modified? |
| HR-002 Approval scope | Changing approval prompts, path scope, or defaults. | Is the approval exact enough for write/destructive tools? |
| HR-003 Cost semantics | Changing cost display, budget display, or cap behavior. | Does the UI avoid false precision? |
| HR-004 Undo/recovery | Changing undo, checkpoint, stash, or restore behavior. | Can unrelated manual edits be preserved? |
| HR-005 Lifecycle wording | Changing background/suspend/resume/review commands. | Do words map to runtime state? |
| HR-006 Stale path deletion | Removing old chat or TUI paths. | Do tests prove the replacement path? |
| HR-007 Git sandbox defaults | Changing whether sandbox starts by default. | Is branch/worktree state predictable? |
| HR-008 Provider spend | Changing provider/model defaults or cost caps. | Can users bound spend? |

## Rollback expectations

Each gated change should include:

- Before behavior.
- After behavior.
- User-visible migration note.
- Test proving the new behavior.
- Manual smoke step if interactive.
- Rollback command or revert plan.

## Review shortcuts to reject

- "The docs explain it" without runtime enforcement.
- "The test passes" when the test bypasses the public path.
- "The command name is close enough" for lifecycle changes.
- "The approval is safe because it is local" without path scope.

## Approval wording rule

For trust-sensitive changes, a reviewer should be able to answer:

1. What can happen?
2. Where can it happen?
3. Who allowed it?
4. How can it be undone?
5. What evidence proves it happened?
