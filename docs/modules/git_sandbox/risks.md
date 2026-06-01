# Git Sandbox Risks

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| GS-R-001 | Original branch lost before merge/discard. | High | Preserve sandbox object or rehydrate full state. |
| GS-R-002 | Dirty workspace stash restored at wrong time. | High | Explicit resolution state machine. |
| GS-R-003 | Branch named with pending id but evidence uses final id. | Medium | Persist mapping in run evidence. |
| GS-R-004 | Docs say opt-in while runtime starts sandbox. | Medium-high | Align help, docs, and defaults. |

## Human review gate

Any change to git sandbox defaults, branch naming, merge behavior, or stash restoration
requires human review.
