# Phase 05: Founder Systematization — Reduce Single-Point-of-Failure Risk
Last updated: 2026-06-09

**Priority:** P2
**Concept doc:** [Founder Bottleneck Audit](../architecture-reflection/06-founder-bottleneck-audit.md)
**Estimated effort:** 4-6 sessions (spread across 2-3 weeks)
**Dependencies:** Phase 01 (CLAUDE.md), Phase 02 (scope clarity)

## Objective

Systematize the three highest-risk workflows that currently depend entirely on the founder: architecture decisions, CI/release engineering, and bug triage. Ensure the project can survive a 1-week founder absence without critical workflow failure.

## Tasks

### Task 5.1: Document release pipeline

- [ ] Write `RELEASE.md` at project root with:
  - Prerequisites (access, credentials, permissions)
  - Step-by-step release workflow
  - Rollback procedure for each step
  - Verification checklist (what must be checked post-release)
- [ ] Include: version bump, CHANGELOG update, build, test, tag, publish
- [ ] Cross-train one additional person on the release flow

**Verification:** A non-founder can perform a dry-run release following the document.

### Task 5.2: Create CI failure response runbook

- [ ] Write `docs/operations/ci-failure-response.md`:
  - Common failure modes and their symptoms
  - Step-by-step diagnostic workflow
  - Escalation criteria (what requires founder input)
  - Rollback procedure for CI config changes
- [ ] Add auto-response to common failure patterns (if feasible)

**Verification:** CI failure → non-founder can diagnose and fix common cases.

### Task 5.3: Implement issue triage automation

- [ ] Define severity matrix:
  - Critical (data loss, security, broken for all users)
  - High (broken for some users, no workaround)
  - Medium (broken for some users, workaround exists)
  - Low (cosmetic, nice-to-have)
- [ ] Implement keyword-based severity auto-classification (GitHub Actions)
- [ ] Define SLA per severity: Critical <4h, High <24h, Medium <72h, Low <2w
- [ ] Create triage team of 2-3 trusted contributors
- [ ] Document triage process in CONTRIBUTING.md

**Verification:** New issue → auto-classified → routed with SLA.

### Task 5.4: Establish architecture review process

- [ ] Define pre-implementation ADR requirement for significant changes
- [ ] Create ADR template that must be filled *before* coding
- [ ] Identify architecture review partner (technical advisor or co-contributor)
- [ ] Set regular architecture sync cadence
- [ ] Document process in `docs/operations/architecture-review.md`

**Verification:** Next significant feature has a pre-implementation ADR.

### Task 5.5: Plan "1-week absence" drill

- [ ] Set a date within 3 months for the founder to be unreachable for 7 days
- [ ] Create checklist of what must be in place before the drill
- [ ] Define success criteria for the drill
- [ ] Schedule post-drill retrospective

**Verification:** Drill date set. Pre-drill checklist items tracked.

## Success Criteria

- [ ] Release runbook documented, non-founder can execute
- [ ] CI failure runbook documented, common failures resolvable by non-founder
- [ ] Issue triage partially automated with severity classification
- [ ] ADRs written pre-implementation for significant changes
- [ ] "1-week absence" drill scheduled within 3 months

## Rollback

If systematization becomes overhead that slows development:
- Automate only the highest-frequency workflows
- Keep ADR pre-implementation as "recommended" not "required" initially
