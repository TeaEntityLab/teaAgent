# Documentation Maintenance Policy
# 2026-06-02

Policy for keeping the daily-driver documentation useful instead of merely large.

This file is the short entry point. Detailed rules live in:

- [Document State Model](document-state-model.md)
- [Risk Issue Roadmap Workflow](risk-issue-roadmap-workflow.md)
- [Documentation Taxonomy And Ownership](doc-taxonomy-and-ownership.md)
- [Documentation Operating Model](documentation-operating-model-2026-06-04.md)

## Front door

The current front door is:

- `docs/INDEX.md`
- `docs/daily-driver-current-status.md`
- `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`
- `docs/plans/ticket-plans/index.md`
- `docs/roadmap-status.md`

## Update rules

- Add a dated layer for new audits.
- Do not rewrite historical findings into a false timeline.
- Add supersession notes when code changes alter an old finding.
- Mark items with the canonical states in `document-state-model.md`.
- Link docs to tests or tickets when possible.
- Keep one active source of truth for each status question.
- Label volatile facts with date, command, commit, and scope.
- Treat stable current-truth docs as product surfaces.

## When to add a new doc

Add a doc when it:

- Helps a daily user choose a command.
- Converts a risk into a ticket.
- Defines a cross-ticket contract.
- Records a decision.
- Provides verification procedure.
- Records a dated evidence snapshot that should not be mixed into current truth.

Do not add a doc just to restate an existing finding.

## When to update instead of adding

Update an existing entry point when the change affects:

- Current user-facing truth.
- Active finding status.
- Ticket execution order.
- Roadmap state.
- Module ownership.
- Security, stability, or approval claims.

## Staleness review

Review current-status and known-issues docs after every change to:

- TUI cost.
- TUI root.
- Chat initial task.
- Approval scope.
- Resume/background wording.
- Undo behavior.
- Run evidence.

## Verification

After governance-sensitive docs edits, run:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

Use `cx overview docs --limit 100` or heading searches when checking whether new
governance docs are discoverable.
