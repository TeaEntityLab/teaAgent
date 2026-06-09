# Phase 06: Data Flywheel — Turn Usage Signals into Product Improvement
Last updated: 2026-06-09

**Priority:** P2
**Concept doc:** [Defensibility & Moat Analysis](../architecture-reflection/07-defensibility-moat-analysis.md)
**Estimated effort:** 4-6 sessions
**Dependencies:** Phase 04 (PMF telemetry infra)

## Objective

Build the data flywheel that turns user behavior signals into systematic product improvement. Move from an engineering-oriented feedback loop (bug→fix→learn) to a product-oriented one (usage→insight→improvement→more usage).

## Tasks

### Task 6.1: Aggregate feature usage patterns from RunStore

- [ ] Build queryable view over RunStore audit logs:
  - Most-called tools (read_file vs write_file vs shell vs search)
  - Permission mode distribution
  - Task completion rate by type
  - Error rate by tool
- [ ] Generate weekly usage report (automated)
- [ ] Publish internal dashboard (CLI-readable)

**Verification:** Weekly report produces actionable insights (e.g., "write_file errors increased 20%").

### Task 6.2: Build aggregate failure pattern analysis

- [ ] Classify failure types from RunStore error events:
  - Tool execution errors
  - Permission enforcement errors
  - Budget/limit errors
  - Provider API errors
- [ ] Identify top 3 failure patterns per week
- [ ] Auto-create GitHub issues for recurring patterns
- [ ] Link to memory catalog failure cards

**Verification:** Recurring failure pattern → auto-created issue with stack trace.

### Task 6.3: Implement config drift detection

- [ ] Track permission mode configuration over time (from RunStore)
- [ ] Detect when users downgrade from higher to lower permission mode
- [ ] Flag when safety defaults are overridden
- [ ] Generate weekly "governance health" report

**Verification:** Report identifies users who downgraded from `prompt` to `allow` mode (potential risk).

### Task 6.4: Build "TeaAgent in production" case study template

- [ ] Create template for user stories:
  - Problem before TeaAgent
  - Setup and onboarding experience
  - Permission mode choices and rationale
  - Integration with existing tools
  - Measurable outcomes
- [ ] Publish first case study (can be dogfooding/self-hosted initially)
- [ ] Create submission process for external users to contribute case studies

**Verification:** Case study template exists. First (internal) case study published.

### Task 6.5: Create behavior dashboard (founder-facing)

- [ ] Build CLI command: `teaagent insights usage-report`
- [ ] Show: active users, task volume, error rates, feature adoption trends
- [ ] Show: week-over-week and month-over-month comparisons
- [ ] Output: human-readable (terminal table) + JSON (for scripting)

**Verification:** `teaagent insights usage-report` produces actionable data.

## Success Criteria

- [ ] Weekly usage report automated from RunStore data
- [ ] Top 3 failure patterns identified per week with auto-created issues
- [ ] Config drift detection produces governance health report
- [ ] First case study published (internal or external)
- [ ] `teaagent insights usage-report` CLI command functional

## Rollback

If data flywheel features create too much noise:
- Reduce auto-issue creation to only Critical/High severity patterns
- Make usage report opt-in rather than default
