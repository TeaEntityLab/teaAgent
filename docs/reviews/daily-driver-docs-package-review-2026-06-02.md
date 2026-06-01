# Daily-Driver Docs Package Review
# 2026-06-02

This review looks at the documentation package itself as a product surface.

## Findings

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| DOC-001 | Medium | The audit corpus is thorough but hard for a daily user to enter. | Keep [../daily-driver-current-status.md](../daily-driver-current-status.md) as the front door. |
| DOC-002 | Medium | Historical findings can appear contradictory after fixes land. | Add supersession notes and index ordering after each pass. |
| DOC-003 | High | Docs can overstate implementation if ADR/status pages are not updated after partial fixes. | Keep ADR-0025 partial until TUI parity is tested. |
| DOC-004 | Medium | Ticket plans exist for many risks but not all newer DD2 risks. | Add one small plan per trust-sensitive gap. |
| DOC-005 | Medium | User guides and maintainer audits were blended. | Keep operator guides short and move code-grounded evidence into analysis docs. |
| DOC-006 | Low | "More docs" can become a substitute for code. | Use each new doc to create a test, ticket, or decision. |

## Strengths

- The package has strong code-grounded evidence.
- Risk IDs and ticket IDs make cross-reference possible.
- Manual QA smoke explicitly captures interactive failures that CI missed.
- The project already has ADR, process, plan, analysis, and spec directories.

## Remaining gaps

- A single generated dashboard of current active vs fixed findings would help.
- Some user-facing docs still need update discipline after fixes land.
- Agent mode continuity needs a concrete run-store proof doc after TICKET-16.
- Approval scope behavior needs a concise user-facing example set.

## Recommendation

Treat docs as a living daily-driver control plane:

1. Current status tells users what to do today.
2. Known issues tells users what not to trust.
3. Ticket plans tell maintainers what to fix next.
4. Test matrix tells reviewers what proof is missing.
5. Review index preserves history without making it the entry point.

## Review decision

The docs package is useful, but its next quality jump depends on code fixes and
verification evidence. Continue writing docs only when they reduce operator ambiguity or
convert risk into executable work.
