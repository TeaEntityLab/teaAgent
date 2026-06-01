# Daily-Driver Review Checklist
# 2026-06-02

Reviewer checklist for daily-driver PRs.

## Scope

- Does the PR touch TUI, chat, agent mode, approval, cost, root, undo, resume, memory, or run-store behavior?
- Are docs and tests in the same PR when user-visible behavior changes?
- Is the change small enough to reason about?

## Tests

- Does at least one test drive the active command path?
- Does any test inject the state it claims to prove?
- Is there a negative test for misuse?
- Is manual smoke required?

## UX

- Does the user see a clear result or clear refusal?
- Are lifecycle words accurate?
- Are errors actionable?
- Are known limitations honest?

## Safety

- Are approval scopes exact?
- Is workspace root unambiguous?
- Is undo/recovery scope visible?
- Are pinned/context files contained?

## Evidence

- Can the final claim be traced to run/audit/test evidence?
- Are "not tested" gaps named?
- Is the known-issues page updated if needed?
