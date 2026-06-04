# Git Sandbox Risks

| ID | Risk | Severity | Mitigation | Upstream |
|----|------|----------|------------|----------|
| GS-R-001 | Original branch lost before merge/discard. | High | Preserve sandbox object or rehydrate full state. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) |
| GS-R-002 | Dirty workspace stash restored at wrong time. | High | Explicit resolution state machine. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| GS-R-003 | Branch named with pending id but evidence uses final id. | Medium | Persist mapping in run evidence. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) |
| GS-R-004 | Docs say opt-in while runtime starts sandbox. | Medium-high | Align help, docs, and defaults. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) |

## Human review gate

Any change to git sandbox defaults, branch naming, merge behavior, or stash restoration
requires human review.
