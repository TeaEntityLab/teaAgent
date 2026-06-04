# Pinned File Risks

| ID | Risk | Severity | Mitigation | Upstream |
|----|------|----------|------------|----------|
| PF-R-001 | Absolute path outside workspace is pinned. | High | Reject absolute paths or require explicit external approval. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (path containment) |
| PF-R-002 | `..` escapes workspace. | High | Resolve and containment-check. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) (containment boundary) |
| PF-R-003 | Symlink escapes workspace. | High | Resolve real path before accepting. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) (containment boundary) |
| PF-R-004 | Secret-name heuristic misses sensitive file. | Medium | Keep containment and explicit user review. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) |

## Required tests

- Allowed relative file.
- Missing file.
- Absolute outside path.
- Parent traversal.
- Symlink escape.
- Secret-like filename.
