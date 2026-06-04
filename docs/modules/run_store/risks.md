# Run Store Module Risks

| ID | Risk | Severity | Mitigation | Upstream |
|----|------|----------|------------|----------|
| RS-R-001 | Corrupt JSONL is silently filtered. | Medium-high | Surface degraded health. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) (audit integrity) |
| RS-R-002 | Suspended run lacks task context. | High | Write run-start/context before advertising resume. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (run state durability; DS-04) |
| RS-R-003 | Review and resume use different assumptions. | Medium | Define lifecycle contract. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| RS-R-004 | Audit evidence is hard to connect to final answer. | Medium | Improve run evidence guide and summaries. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (audit completeness) |

## Test requirements

- Malformed run file produces warning.
- Valid run still appears.
- Suspended run can be inspected.
- Resumable run has task and observations.
