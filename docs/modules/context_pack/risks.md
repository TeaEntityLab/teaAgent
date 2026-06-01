# Context Pack Risks

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| CP-R-001 | `read_only` label overclaims no side effects. | Medium-high | Pass caller flag or rename field. |
| CP-R-002 | Context pack construction initializes local state. | Medium | Thread readonly through helpers. |
| CP-R-003 | Candidate files include surprising paths. | Medium | Keep path resolution contained and auditable. |

## Review questions

- What does `read_only` mean in this artifact?
- Can building the pack write files?
- Does preflight/daily output describe that correctly?
