# Documentation Maintenance Policy
# 2026-06-02

Policy for keeping the daily-driver documentation useful instead of merely large.

## Front door

The current front door is:

- `docs/daily-driver-current-status.md`
- `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`
- `docs/plans/ticket-plans/index.md`

## Update rules

- Add a dated layer for new audits.
- Do not rewrite historical findings into a false timeline.
- Add supersession notes when code changes alter an old finding.
- Mark items as active, partially fixed, verify/close, fixed, or superseded.
- Link docs to tests or tickets when possible.

## When to add a new doc

Add a doc when it:

- Helps a daily user choose a command.
- Converts a risk into a ticket.
- Defines a cross-ticket contract.
- Records a decision.
- Provides verification procedure.

Do not add a doc just to restate an existing finding.

## Staleness review

Review current-status and known-issues docs after every change to:

- TUI cost.
- TUI root.
- Chat initial task.
- Approval scope.
- Resume/background wording.
- Undo behavior.
- Run evidence.
