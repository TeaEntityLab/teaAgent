# Run Store Module Risks

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| RS-R-001 | Corrupt JSONL is silently filtered. | Medium-high | Surface degraded health. |
| RS-R-002 | Suspended run lacks task context. | High | Write run-start/context before advertising resume. |
| RS-R-003 | Review and resume use different assumptions. | Medium | Define lifecycle contract. |
| RS-R-004 | Audit evidence is hard to connect to final answer. | Medium | Improve run evidence guide and summaries. |

## Test requirements

- Malformed run file produces warning.
- Valid run still appears.
- Suspended run can be inspected.
- Resumable run has task and observations.
