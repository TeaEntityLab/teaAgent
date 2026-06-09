# Phase 03: Competitive Analysis — Structured Devil's Advocate

**Priority:** P1
**Concept doc:** [Competitive Threat Model](../docs/architecture-reflection/04-competitive-threat-model.md)
**Estimated effort:** 2-3 sessions
**Dependencies:** None

## Objective

Formalize competitive threat modeling as a recurring practice. Produce the strongest version of each competitor's winning argument, then identify the evidence required to invalidate it. Move beyond feature-checklist comparison to strategic positioning.

## Tasks

### Task 3.1: Expand competitive threat model

- [ ] Deepen analysis for each current competitor (Claude Code, OpenCode, Codex, In-house):
  - Interview 2-3 users who chose each competitor over TeaAgent
  - Document their verbatim reasoning
  - Map each objection to a product or positioning gap
- [ ] Add "new entrant" threat scenario (what would a startup with a fresh approach look like?)
- [ ] Publish as `docs/strategy/competitive-threat-model.md`

**Verification:** Each competitor has a documented "strongest case" argument and a required response.

### Task 3.2: Build "multi-provider governance" buyer persona

- [ ] Research organizations that explicitly avoid vendor lock-in
- [ ] Document persona: title, pain points, evaluation criteria, buying process
- [ ] Create positioning document targeting this persona
- [ ] Add persona to CLAUDE.md as reference for product decisions

**Verification:** Persona document exists with sourcing evidence.

### Task 3.3: Document architectural depth argument

- [ ] Write a concise (1-page) argument: "Why governance cannot be bolted on"
- [ ] Map each governance feature (hash chain, 5-tier permissions, plan-before-write) to its architectural prerequisite
- [ ] Publish as `docs/governance/architectural-depth.md`

**Verification:** Document exists and can be referenced in competitive discussions.

### Task 3.4: Establish quarterly competitive review

- [ ] Define quarterly competitive review template:
  - What did each competitor ship last quarter?
  - What has changed in the competitive landscape?
  - Which of our assumptions need updating?
- [ ] Set calendar reminder for first review

**Verification:** First quarterly review happens within 3 months.

## Success Criteria

- [ ] Competitive threat model covers 4+ competitors with "strongest case" arguments
- [ ] Buyer persona documented with sourcing evidence
- [ ] Architectural depth argument published
- [ ] Quarterly competitive review process established

## Rollback

If threat modeling becomes too speculative:
- Restrict to "what competitors actually shipped" vs "what they might ship"
- Add "evidence required" threshold for each claim
