# Pinned File Risks

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| PF-R-001 | Absolute path outside workspace is pinned. | High | Reject absolute paths or require explicit external approval. |
| PF-R-002 | `..` escapes workspace. | High | Resolve and containment-check. |
| PF-R-003 | Symlink escapes workspace. | High | Resolve real path before accepting. |
| PF-R-004 | Secret-name heuristic misses sensitive file. | Medium | Keep containment and explicit user review. |

## Required tests

- Allowed relative file.
- Missing file.
- Absolute outside path.
- Parent traversal.
- Symlink escape.
- Secret-like filename.
