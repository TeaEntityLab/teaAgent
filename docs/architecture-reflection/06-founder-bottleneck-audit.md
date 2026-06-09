# 06: Founder Bottleneck Audit

> **Core question:** Which workflows stall when the founder is unavailable for a week?
> **Priority:** P2 — important for Launch stage readiness, not blocking pre-PMF.
> **Last reviewed:** 2026-06-09
> **Depends on:** [01-founder-playbook-reflection.md](01-founder-playbook-reflection.md) (Learning 6)
> **Work plan:** [Phase 05: Founder Systematization](../../plans/phase-05-founder-systematization.md)

## Problem Statement

The Founder's Playbook describes the transition from "doing the work" to "designing the systems that do the work" as the hardest transition in the startup lifecycle. The risk is missing this transition entirely — staying in builder mode while the organization stalls.

TeaAgent's current state:

> 203 source files, 332 test files, 29 ADRs, 1 month, 1 primary contributor.

This is a classic founder-coded project. The architecture is sophisticated, but the decision-making is centralized. The test is simple: **what happens when the founder is unavailable for one week?**

## The Bottleneck Test

For each workflow below, answer:

1. **Who else can do it?** (Is the knowledge documented? Is the tooling accessible?)
2. **What's the fallback if the founder doesn't respond?** (Escalation path?)
3. **What breaks silently?** (No one notices until it's too late?)

### Workflow Inventory

| # | Workflow | Founder-Dependent? | Documentation | Fallback | Silent Breaks |
|---|----------|-------------------|---------------|----------|---------------|
| 1 | Architecture decisions (new features) | ✅ Yes — only founder has full context | ADRs exist but cover decisions retroactively | No defined architecture review process | Wrong design choices compound |
| 2 | PR review / merge approval | ✅ Yes — sole reviewer | Coding standards exist in ruff/mypy config | PRs pile up, velocity drops | Code quality degrades |
| 3 | Bug triage & prioritization | 🟡 Partial | Issue templates exist | Automated, but no prioritization without founder | Low-priority bugs accumulate |
| 4 | Release engineering | ✅ Yes — only founder knows the pipeline | build/release scripts exist | No one knows the full release flow | Releases stall |
| 5 | CI/CD failure response | ✅ Yes — only founder understands CI | CI config exists | CI stays red until founder returns | Broken builds compound |
| 6 | User support (GitHub issues) | 🟡 Partial | Some docs, SUPPORT.md | Responses delayed | User frustration |
| 7 | Roadmap prioritization | ✅ Yes — only founder has the vision | Roadmap is implicit | No roadmap = no direction | Feature drift |
| 8 | Security incident response | ✅ Yes — only founder knows the infra | SECURITY.md exists but no runbook | Nothing happens | Escalation delay |
| 9 | Dependency updates | ❌ Automated | Dependabot/Renovate config | Auto-updates with CI checks | Breaking changes may slip |
| 10 | Provider integration (new LLM) | 🟡 Partial | Provider adapter pattern documented | New providers wait | Time-to-integrate increases |
| 11 | Community engagement | ✅ Yes — only founder responds | No community guidelines | Silence | Community atrophy |
| 12 | Documentation updates | 🟡 Partial | Docs exist but founder-driven | Docs go stale | Knowledge decay |

### High-Risk Workflows

The three workflows with the highest "breaks silently" impact:

#### 1. Architecture Decisions (Workflow 1)

**Why it's high-risk:** Without the founder's full context, a new contributor or AI agent will make locally-optimal decisions that drift from the architectural vision. ADRs are written *after* decisions, not *before* — they document, not guide.

**Intervention:**
- Define an Architecture Review Board (ARB) process, starting with a single additional reviewer
- Create ADR template that must be filled *before* implementation (not after)
- Document the "architectural guardrails" in CLAUDE.md that constrain decisions

#### 2. CI/CD & Release (Workflows 4-5)

**Why it's high-risk:** When CI breaks and the founder isn't available, every subsequent PR builds on a broken foundation. Release pipeline knowledge is entirely in the founder's head.

**Intervention:**
- Document release pipeline as a runbook (step-by-step, including rollback)
- Create a CI failure response checklist
- Cross-train at least one other person on the release flow

#### 3. Bug Triage & Prioritization (Workflow 3)

**Why it's high-risk:** Without founder triage, all bugs look equal. Critical security bugs get the same attention as cosmetic issues.

**Intervention:**
- Define automated severity classification (keyword-based, user-impact heuristics)
- Create a severity matrix with documented response SLAs
- Establish a "no founder needed" triage process for common bug types

## Systematization Roadmap

### Phase 1: Document the Invisible (P1)

These are workflows where the process exists but is undocumented:

| Action | Workflow | Output |
|--------|----------|--------|
| Write release runbook | 4 | `RELEASE.md` with step-by-step, rollback, verification |
| Write CI failure runbook | 5 | `docs/operations/ci-failure-response.md` |
| Create severity classification guide | 3 | `docs/operations/severity-matrix.md` |
| Document architecture review process | 1 | `docs/operations/architecture-review.md` |

**Estimated effort:** 2-3 focused sessions.

### Phase 2: Distribute Authority (P1-P2)

These are workflows where authority must be delegated, not just documented:

| Action | Workflow | Mechanism |
|--------|----------|-----------|
| Add secondary PR reviewer | 2 | GitHub CODEOWNERS with second reviewer |
| Create triage team (2-3 trusted contributors) | 3 | GitHub issue routing + defined SLA |
| Establish architecture review partner | 1 | Regular architecture sync with technical advisor |
| Deploy automation for common decisions | 3 | AI-based issue classification |

### Phase 3: Measure & Iterate (P2)

Track whether systematization is working:

| Metric | Current Baseline | Target |
|--------|-----------------|--------|
| PR merge latency (founder available) | TBD | <24h |
| PR merge latency (founder unavailable) | TBD | <48h (same as available) |
| Issues triaged within 48h | TBD | >80% |
| Releases per week without founder intervention | 0 | >50% |
| CI red-to-green recovery time (no founder) | TBD | <2h |

## The "One Week Absence" Drill

A practical test to validate systematization:

> At a random date in the next 3 months, the founder will be unreachable for 7 consecutive days. Before this drill, document what should and should not happen.

**Checklist:**
- [ ] Any contributor can run the release pipeline
- [ ] CI failures have a documented response workflow
- [ ] PRs are reviewed by ≥1 non-founder within 48h
- [ ] Security reports trigger automated notification to a second responder
- [ ] User issues are acknowledged within 24h (even if unresolved)
- [ ] The roadmap is documented enough that one week of work doesn't diverge

## Success Criteria

- [ ] Release pipeline documented with step-by-step runbook
- [ ] CI failure response documented with severity-based SLAs
- [ ] ≥1 non-founder can perform a release
- [ ] Issue triage is partially automated (severity classification, routing)
- [ ] Architecture decisions have a pre-implementation review process
- [ ] "One week absence" drill passes with no critical workflow failure

## References

- Founder's Playbook Learning 6: "Founder Transitions from Doer to System Designer"
- GitHub CODEOWNERS pattern
- [Architecture documentation](./README.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md) — existing contribution guidelines
