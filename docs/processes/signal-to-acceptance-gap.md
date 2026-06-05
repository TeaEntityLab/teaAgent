# Signal-to-Acceptance-Gap Process

**Status:** Active process
**Frequency:** Per signal (continuous), reviewed quarterly
**Owner:** TBD
**Last reviewed:** 2026-06-05

## Purpose

Convert external signals — competitor feature launches, community pain points,
ecosystem shifts, user feedback — into actionable acceptance gaps that are
traceable, triaged, and either filed as roadmap work or explicitly deferred.

This process enforces the principle that community feedback is signal, not fact
(see [TeaAgent Product Principles](../strategy/teaagent-product-principles-2026-06-04.md)).

## Signal Sources

| Source | Monitoring process | Confidence guidance |
|---|---|---|
| Competitor changelogs / releases | [OpenCode Gap Watch](opencode-gap-watch.md), quarterly survey | Medium — feature exists but adoption unknown |
| Community discussions (Reddit, Discord, HN) | [Community Presence](community-presence.md) | Low — sentiment can be loud but unrepresentative |
| GitHub issues (TeaAgent or competitors) | Issue tracker, gap-watch scripts | Medium — structured but self-selecting |
| DeepWiki / documentation comparison | `scripts/refresh_agent_readme_survey.md` | High — verifiable feature inventory |
| Direct user feedback | Support channels, daily-driver sessions | Medium-High — real usage but small sample |
| Ecosystem announcements (MCP, ACP, A2A specs) | Spec-watch, protocol changelogs | High — authoritative spec changes |

## Process

### Phase 1: Signal Capture

For each external signal:

1. **Record** — Date, source URL, verbatim claim or feature description.
2. **Classify** — Source type (competitor, community, ecosystem, user).
3. **Assign confidence** — Low / Medium / High based on verifiability and
   source authority.
4. **Cross-reference** — Check whether TeaAgent already addresses the capability
   (via different surface, different scope, or architectural choice).

Artifact: raw signal entry in the monitoring process doc or a dated survey.

### Phase 2: Gap Triage

For each signal that represents a genuine gap:

1. **Map to use-case** — Find or create a row in `docs/use-cases.md`.
   If the signal maps to an existing use-case, note it as a new sub-capability.
2. **Assess severity** — Score based on:
   - **User impact**: How many daily-driver workflows are affected?
   - **Trust risk**: Does the gap weaken governance, audit, or safety?
   - **Competitive urgency**: Is a competitor gaining adoption because of this?
3. **Assign priority** — P0 (trust/safety), P1 (daily workflow), P2 (ecosystem/niche).
4. **Propose response**:
   - **File acceptance gap** — Create a ticket with acceptance criteria.
   - **Defer with rationale** — Document why this gap is not acted on now.
   - **Already covered** — Note how existing TeaAgent capability addresses it
     and close the signal.

Artifact: triaged entry with priority, severity rationale, and response decision.

### Phase 3: Acceptance Gap Filing

For signals promoted to acceptance gaps:

1. **Create a ticket** — Use the project ticket format. Label with source signal
   and date.
2. **Write acceptance criteria** — What must be true for this gap to be closed?
   Prefer testable, falsifiable criteria.
3. **Link to use-case matrix** — Add a row to `docs/use-case-matrix.md` with
   `Covered = no` and the ticket reference.
4. **Add to roadmap** — If P0/P1, add a roadmap row with owner, confidence,
   and next gate.
5. **Record in backlog** — Add to `docs/backlog-priority.md` with the signal
   source and priority tier.

Artifact: ticket + use-case-matrix row + roadmap row (if applicable).

### Phase 4: Quarterly Review

During the [quarterly refresh process](../release-checklist.md#quarterly-refresh-process-p2-c):

1. Review all signals captured since the last quarter.
2. Verify that deferred gaps still have valid rationale.
3. Promote any deferred gaps whose competitive urgency increased.
4. Close any gaps where the competitor feature was removed or where TeaAgent
   gained equivalent capability through other work.
5. Update confidence levels based on new evidence.

## Signal Confidence Rubric

| Confidence | Criteria | Example |
|---|---|---|
| **High** | Authoritative spec change, verified feature in competitor release notes, or DeepWiki source comparison | MCP spec adds a new transport; competitor ships documented approval gates |
| **Medium** | Credible community report with linked evidence, or competitor feature announced but not independently verified | Reddit thread with linked commit showing competitor undo support |
| **Low** | Unsourced community sentiment, feature request without evidence, or unverifiable claim | "Everyone is asking for X" without links or counts |

## Traceability Rules

- Every signal that reaches Phase 3 must be traceable from signal source →
  use-case row → ticket → roadmap row.
- Deferred signals must have a dated rationale and a re-evaluation trigger
  (e.g., "revisit if competitor ships approval gates").
- Closed signals that were dismissed because "already covered" must cite the
  specific TeaAgent capability that covers them.
- The quarterly refresh checklist in `docs/release-checklist.md` gates the
  signal-to-gap pipeline.

## Related Documents

- [TeaAgent Product Principles](../strategy/teaagent-product-principles-2026-06-04.md)
- [Release Checklist](../release-checklist.md)
- [OpenCode Gap Watch](opencode-gap-watch.md)
- [Community Presence](community-presence.md)
- [Use Cases](../use-cases.md)
- [Use Case Matrix](../use-case-matrix.md)
- [Backlog Priority](../backlog-priority.md)
