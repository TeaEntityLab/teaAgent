# 05: PMF Measurement Framework

> **Core question:** What metrics separate genuine product-market fit from vanity signals for TeaAgent?
> **Priority:** P1 — necessary before scaling user acquisition.
> **Last reviewed:** 2026-06-09
> **Depends on:** [01-founder-playbook-reflection.md](01-founder-playbook-reflection.md) (Learning 5)
> **Work plan:** [Phase 04: PMF Framework](../../plans/phase-04-pmf-framework.md)

## Problem Statement

The Founder's Playbook warns that early traction is not product-market fit. Launch energy comes from transient forces (friends, investors' portfolio companies, Hacker News spikes) that cannot predict what happens at week 6 or week 12.

The playbook prescribes:

> "在釋出前就設好 retention 基準、activation 標準、第 7 天與第 30 天目標；並先定義『偽陽性』長什麼樣。"

TeaAgent's current state:

| Measurement | Status |
|-------------|--------|
| Engineering maturity matrix | ✅ Excellent |
| Market-facing metrics | ❌ None |
| Sean Ellis test | ❌ Not conducted |
| Retention/activation baselines | ❌ Not defined |
| User onboarding time tracking | ❌ Not instrumented |
| "Pseudopositive" definitions | ❌ Not documented |

## Framework Design

### Metric Hierarchy

```
            Product-Market Fit
         /          |          \
   Retention     Revenue     Referral
   (stickiness)  (willingness (advocacy)
                  to pay)
       |            |            |
   Activation    Unit Econ   Net Promoter
   Time-to-value CAC/LTV    Sean Ellis (>40%)
   Day 7/30       Payback     Organic growth
                  period      rate
```

### Tier 1: Activation Metrics (Pre-PMF Gate)

These measure whether a new user reaches the "aha moment" — the point where they experience TeaAgent's core value.

| Metric | Definition | Target | Collection Method |
|--------|-----------|--------|-------------------|
| Time to first task | Minutes from install to first `teaagent run` completion | ≤5 min (golden path) | CLI telemetry (`--telemetry`) |
| Time to first governance win | Minutes from install to first `--permission-mode` experience | ≤10 min | CLI telemetry |
| Setup completion rate | % of installs that complete `teaagent setup` | ≥70% | CLI telemetry |
| First task success rate | % of first `teaagent run` attempts that succeed | ≥80% | RunStore data |
| Day 1 activation | User completes ≥2 non-trivial tasks on first day | TBD after baseline | RunStore data |

**Pseudopositive definitions:**
- User runs `teaagent --help` and never executes a task → not activated
- User completes setup but never runs a task → not activated
- User runs only trivial tasks (single-command) without governance exploration → partial activation

### Tier 2: Retention Metrics (PMF Signal)

| Metric | Definition | Initial Target | Update Cadence |
|--------|-----------|---------------|----------------|
| Day 7 retention | % of activated users who run ≥1 task on day 7 | TBD (industry benchmark: 30-40%) | Weekly |
| Day 30 retention | % of activated users who run ≥1 task in days 15-30 | TBD (benchmark: 20-30%) | Monthly |
| Weekly active users | Users with ≥1 task completion in a week | TBD | Weekly |
| Task frequency | Mean tasks per active user per week | TBD | Weekly |
| Power user ratio | % of users with ≥5 tasks/week | TBD | Weekly |

**Retention quality signals:**
- *Good retention*: User returns because of habit/workflow integration
- *Bad retention*: User returns because of bugs/errors requiring re-run
- *Fake retention*: User returns due to founder's personal nudging

**Pseudopositive definitions:**
- "Registered" ≠ "retained" — registration without repeat usage is noise
- "High day-1 activity" that drops to zero by day 7 → not PMF
- Activity driven by the founder's personal follow-ups → not PMF

### Tier 3: Revenue/Commitment Metrics (PMF Confirmation)

| Metric | Definition | Initial Target | Notes |
|--------|-----------|---------------|-------|
| Willingness to pay | % of day-30 retained users who would pay for TeaAgent | TBD | Survey-based |
| Sean Ellis score | % of active users saying "very disappointed" if TeaAgent disappeared | ≥40% | Required by playbook |
| Paid conversion rate | % of users who upgrade from free to paid | TBD | Post-monetization |
| Referral rate | % of new users who joined via existing user referral | TBD | Organic growth signal |

**Pseudopositive definitions:**
- "Would pay" survey answers ≠ actual payment (say/do gap)
- Non-binding intent-to-pay is not revenue
- Referral from founder's personal network is not organic growth

### Tier 4: Qualitative Signals (Context for Metrics)

These cannot be reduced to numbers but are essential for interpreting the quantitative data:

| Signal | Collection Method | What It Reveals |
|--------|-------------------|-----------------|
| User verbatim ("I wish it could...") | CLI feedback prompt, TUI | Feature gaps, onboarding friction |
| Support request patterns | Issue tracker categorization | UX failures, documentation gaps |
| Reinstall/re-engage triggers | RunStore event analysis | What brings users back |
| Silent abandonment patterns | Last-run timestamps | Where users exit without feedback |
| Competitor switching | Survey | Positioning clarity |

## Baseline Collection

Before interpreting any metric, establish baselines from current data:

### Step 1: RunStore Audit (Existing Data)

The RunStore already contains per-run data. Even without explicit telemetry, we can extract:

- Number of unique run IDs per time period
- Distribution of task types (read-only vs write)
- Frequency of permission mode usage
- Error rates and failure patterns

**Action:** Query the existing RunStore to establish pre-framework baselines.

### Step 2: Define Cohort Windows

| Cohort | Definition | Why |
|--------|-----------|-----|
| Day 0 | First run completion | Activation start |
| Day 1 | 24-48h after first run | Initial re-engagement |
| Day 7 | 7±1 days after first run | Early retention |
| Day 14 | 14±2 days | Mid retention |
| Day 30 | 30±3 days | PMF signal |
| Day 90 | 90±7 days | Habit formation |

### Step 3: Instrument Collection

**Non-invasive** (no new user-facing features):
- Parse RunStore JSONL for task metadata
- Add optional anonymous ping on `teaagent setup` completion
- Use existing audit events for workflow patterns

**Light-weight** (minimal UX change):
- Post-task completion survey prompt (≤3 questions, opt-in)
- Optional `--telemetry` flag for anonymous usage stats
- Email-based day-7/day-30 check-in (opt-in)

## Measuring "Effort Test" (Playbook's Alternative to Sean Ellis)

The Founder's Playbook suggests a less survey-dependent signal:

> "PMF 前 retention 靠創辦人英雄式硬撐，PMF 後產品開始自己拉動用戶——當動作從『推』變『拉』，是真實改變最清楚的訊號。"

**Implementation:**
- Track source of each user re-engagement:
  - *Push*: Founder email, manual outreach, feature announcement
  - *Pull*: User-initiated CLI run, scheduled task, habit-driven usage
- Target: ≥70% of weekly active usage should be "pull" within 3 months

## Decision Framework

```
Data collected → Compare to PMF targets
     |
     ├── All targets met → [PMF Confirmed] → Move to Launch/Scale focus
     |
     ├── Some targets met → [Partial Fit] → Identify weakest metric, iterate
     |                                       → Set re-evaluation date
     |
     └── No targets met → [No PMF Yet]
                          → Diagnostic: is it retention, activation, or wrong segment?
                          → Option A: Adjust product (onboarding/feature focus)
                          → Option B: Adjust segment (who needs this most?)
                          → Option C: Pivot (evidence suggests different problem)
```

## Implementation Plan

### Phase 1: Baseline (This week)
- [ ] Query existing RunStore for historical usage patterns
- [ ] Define current "activated user" based on existing data
- [ ] Publish baseline metrics as a one-time report

### Phase 2: Instrument (Next 2 weeks)
- [ ] Add optional telemetry flag (`--telemetry`)
- [ ] Implement day-0/day-7/day-30 cohort tracking
- [ ] Add post-task feedback prompt (opt-in, ≤3 questions)

### Phase 3: Measure (Ongoing)
- [ ] Weekly retention report (automated from RunStore)
- [ ] Monthly Sean Ellis survey (email-based, targeted)
- [ ] Quarterly PMF review against targets

## Risks

| Risk | Mitigation |
|------|-----------|
| Metrics create perverse incentives | Measure outcomes, not proxy metrics; review quarterly for gaming |
| Telemetry becomes privacy concern | Make telemetry opt-in, document data practices transparently |
| Small sample size pre-PMF | Use qualitative signals to supplement small-n quantitative data |
| Founder biases metric interpretation | External advisor reviews PMF assessment quarterly |

## References

- Founder's Playbook Learning 5: "Early Traction Is Not PMF"
- Sean Ellis: "The Startup Pyramid" (Sean Ellis test methodology)
- [Maturity Matrix](../maturity-matrix.md) — engineering readiness vs. market readiness
- [RunStore architecture](../../README.md#architecture) — existing data collection infrastructure
