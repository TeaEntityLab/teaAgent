# Phase 04: PMF Measurement Framework

**Priority:** P1
**Concept doc:** [PMF Measurement Framework](../docs/architecture-reflection/05-pmf-measurement-framework.md)
**Estimated effort:** 3-5 sessions
**Dependencies:** Phase 02 (scope clarity before measuring)

## Objective

Implement the measurement framework that separates genuine product-market fit from vanity signals. Establish activation/retention baselines from existing data, instrument collection for forward-looking metrics, and define decision criteria for PMF assessment.

## Tasks

### Task 4.1: Establish baselines from existing RunStore data

- [ ] Query existing RunStore for historical usage patterns
  - Unique run IDs per time period
  - Distribution: read-only vs write tasks
  - Permission mode frequency
  - Error rates and failure types
- [ ] Publish baseline metrics report
- [ ] Define "current activated user" based on existing data patterns

**Verification:** Baseline report published with actual numbers, not targets.

### Task 4.2: Instrument opt-in telemetry

- [ ] Add `--telemetry` flag to `teaagent setup` and `teaagent run`
- [ ] Define anonymous telemetry payload:
  - Task type (read-only/write/plan)
  - Permission mode used
  - Completion time (seconds)
  - Error type (if any)
  - OS/platform
- [ ] Implement opt-in prompt on first run
- [ ] Add `teaagent telemetry status` and `teaagent telemetry disable` commands
- [ ] Document data collection practices in PRIVACY.md

**Verification:** Fresh install → first run → opt-in prompt → telemetry flowing.

### Task 4.3: Implement cohort tracking

- [ ] Define cohort windows: Day 0, Day 1, Day 7, Day 14, Day 30, Day 90
- [ ] Implement Day 0/1/7/30/90 retention computation from RunStore data
- [ ] Generate weekly retention report (automated, CLI-readable)
- [ ] Define initial retention targets (update after baseline)

**Verification:** Weekly retention report runs without manual intervention.

### Task 4.4: Add post-task feedback prompt (opt-in)

- [ ] Design ≤3 question survey:
  1. "Did this task accomplish what you wanted?" (yes/no/partially)
  2. "How satisfied are you with the result?" (1-5)
  3. "May we follow up via email?" (opt-in email field, optional)
- [ ] Implement as optional prompt after `teaagent run` completion
- [ ] Store responses in anonymized format

**Verification:** Post-task prompt appears correctly. Response rate >10%.

### Task 4.5: Define PMF decision criteria

- [ ] Document Sean Ellis test protocol (survey questions, cohort selection, timing)
- [ ] Define "effort test" signal (push vs pull engagement ratio)
- [ ] Document PMF decision framework (all targets met / partial / not met)
- [ ] Schedule quarterly PMF review

**Verification:** PMF decision document exists with clear pass/fail criteria.

## Success Criteria

- [ ] Baseline metrics published from existing RunStore data
- [ ] Opt-in telemetry implemented with privacy documentation
- [ ] Weekly retention report automated
- [ ] Post-task feedback prompt collecting responses
- [ ] PMF decision criteria documented with pass/fail thresholds

## Rollback

If telemetry is rejected by community:
- Keep RunStore-based analysis only (no telemetry)
- Use qualitative signals (GitHub issues, survey) instead of quantitative
