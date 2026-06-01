# Operator Trust Model
# As of 2026-06-02

TeaAgent should earn trust by making important facts consistent across surfaces. A
daily user should not need to know which internal controller path produced a result.

## Trust-sensitive facts

| Fact | Why it matters | Required property |
|------|----------------|-------------------|
| Task submitted | User must know whether work started. | Execute or reject; never silently drop. |
| Run state | User must know whether work is running, suspended, failed, or complete. | Lifecycle words map to real runtime state. |
| Cost | User must understand spend and budget pressure. | Display derives from real ledger. |
| Approval | User grants authority to a specific action. | Exact tool, input, path, and call id. |
| Undo scope | User risks losing manual work. | Scope is visible before destructive recovery. |
| Root | User expects work in the selected repo. | Explicit CLI root beats stale saved state. |
| Evidence | User needs proof after a run. | Claims link to audit events, diffs, and tests. |

## Permission modes

Permission modes should be explained as authority boundaries:

- Read-only or inspect modes are for discovery.
- Prompt modes are for unfamiliar or risky work.
- Auto-approval modes are for trusted, bounded tasks.
- Path-scoped approval should be preferred over broad approval.

## Approvals

Approval UX must preserve four things:

1. The exact tool call.
2. The exact path or resource scope.
3. The exact run and approval id.
4. The record that the user approved it.

Empty path scope, broad grants, or ambiguous messages should be treated as release
blockers for daily-driver trust.

## Audit logs

Audit logs are the project differentiator only if they are easy to connect to the
operator story:

- Start event: what was asked.
- Tool event: what authority was used.
- Approval event: who allowed what.
- Result event: what changed.
- Verification event: what proved it.

## Cost

Cost display is trust-sensitive because wrong zeros are more harmful than missing
numbers. A missing value says "unknown"; `$0.00` says "free."

Rule: when cost is not wired, show "unknown" or link to the run summary instead of a
decorative zero.

## Undo

Undo should be described by mechanism and scope:

- "Undo last run's touched files" for undo journal.
- "Restore checkpoint" for checkpoint/stash recovery.
- "Manual git revert" for human-selected changes.

Do not use the same command label for different scopes without a warning.

## Evidence bundles

An evidence bundle should distinguish:

- Claimed: what the agent says it did.
- Observed: what audit logs and diffs show.
- Verified: what tests, smoke checks, or human review proved.
- Not tested: what still relies on assumption.

## Known trust gaps

- TUI cost can display false zero.
- TUI undo and REPL undo can differ.
- Some lifecycle wording advertises resume/background behavior ahead of implementation.
- Some tests verify helper behavior rather than the active user path.

These are not just bugs; they are trust bugs.
