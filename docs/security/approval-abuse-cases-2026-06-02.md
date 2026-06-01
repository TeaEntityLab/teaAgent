# Approval Abuse Cases
# 2026-06-02

Abuse cases for approval UX and matching.

## Abuse case A-001: Broad grant by missing path

The prompt cannot extract a path and falls back to broad tool approval.

Required defense:

- Reject missing path for write/destructive tools.
- Ask for explicit global approval only through a scary, separate path.

## Abuse case A-002: Directory grant disguised as file grant

The prompt displays `docs/foo.md` but stores `docs/**`.

Required defense:

- Store grant type.
- Display grant type.
- Test matcher against sibling files.

## Abuse case A-003: Reused approval after task changes

An approval from a previous task remains valid for a new task with different intent.

Required defense:

- Bind approval to run id and call id.
- Revoke on task or run boundary where appropriate.

## Abuse case A-004: Approval laundering through resume

A resumed run uses stale approval state without making continuity visible.

Required defense:

- Persist approval state in run evidence.
- Show pending/used approvals on resume.

## Abuse case A-005: Human cannot understand the operation

The prompt has exact data but too much noise.

Required defense:

- One-line operation summary.
- Exact path.
- Expandable raw input.
- Clear approve/reject choices.
