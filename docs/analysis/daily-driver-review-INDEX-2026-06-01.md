# Daily-Driver Review Package — Master Index
# 2026-06-01

A single entry point to the 2026-06-01 review of teaagent's daily surfaces
(TUI, `teaagent chat`, agent mode). Read in this order.

## Read order

1. **`daily-driver-code-grounded-ux-findings-2026-06-01.md`** *(analysis)*
   The centerpiece. 8 code-level findings (CG-01…CG-08) with `file:line` evidence and
   severity. Start here — it's the *what's broken now*.
2. **`competitive-feedback-refresh-2026-06-01.md`** *(analysis)*
   Sourced June-1 delta vs the May-31 survey. Why the findings matter competitively.
3. **`daily-driver-hardening-plan-2026-06-01.md`** *(plans)*
   Phased fix plan (P0-1…P2-1) with falsifiable acceptance tests.
4. **`daily-driver-risk-register-2026-06-01.md`** *(analysis)*
   Product risks (PR-1…PR-6) + execution risks (ER-1…ER-6), rollback, review gate.
5. **`daily-driver-persona-journey-maps-2026-06-01.md`** *(specs)* — fills F-ECO-002.
6. **`operator-cockpit-contract-2026-06-01.md`** *(specs)* — fills F-ECO-010.
7. **`run-evidence-bundle-spec-2026-06-01.md`** *(specs)* — fills F-ECO-011.
8. **`permission-mode-risk-decision-table-2026-06-01.md`** *(analysis)* — fills F-ECO-013.

## Extended ecosystem specs (added on request, code-grounded)

14. **`ide-desktop-surface-plan-2026-06-01.md`** *(specs)* — fills F-ECO-004.
15. **`mcp-trust-onboarding-journey-2026-06-01.md`** *(specs)* — fills F-ECO-008.
16. **`automation-lifecycle-spec-2026-06-01.md`** *(specs)* — fills F-ECO-012.
17. **`provider-resilience-playbook-2026-06-01.md`** *(specs)* — fills F-ECO-009.
18. **`repo-map-benchmark-corpus-2026-06-01.md`** *(specs)* — fills F-ECO-005.
19. **`subagent-parent-review-workflow-2026-06-01.md`** *(specs)* — fills F-ECO-006.
20. **`extension-activation-explainability-2026-06-01.md`** *(specs)* — fills F-ECO-007.

## Reconsideration & execution layer

21. **`daily-driver-findings-second-pass-2026-06-01.md`** *(analysis)* — re-audit:
    new findings CG-09/CG-10, severity re-exam, completeness audit, residual risks R-1…R-5.
22. **`daily-driver-execution-readiness-2026-06-01.md`** *(plans)* — dev/test mechanics,
    per-ticket DoD + implementation pointers, and the **spec-level risk register SR-1…SR-11**.

## Consolidation / log layer

9. **`daily-driver-recommendation-log-2026-06-01.md`** — every finding, rec, judgment,
   research signal, decision, assumption (the "log everything" deliverable).
10. **`daily-driver-open-decisions-2026-06-01.md`** — maintainer decision register (DQ-1…).
11. **`daily-driver-assumptions-and-nongoals-2026-06-01.md`** — AS-1…, NG-1….
12. **`daily-driver-traceability-matrix-2026-06-01.md`** — finding→fix→test→theme→gap.
13. **`daily-driver-backlog-2026-06-01.md`** *(plans)* — flat, ticket-style backlog.

## Relationship to the May-31 corpus

This package **builds on** and does not replace:
- `agent-market-ux-survey-2026-05-31.md` (themes UX-F1…UX-F8)
- `agent-ecosystem-daily-use-gap-review-2026-05-31.md` (gaps F-ECO-001…F-ECO-014)
- `agent-competitive-risks-2026-05-31.md`, `competitor-community-feedback-synthesis-2026-05-31.md`
- `plans/ux-improvement-roadmap-2026-05-31.md`, `plans/competitive-positioning-plan-2026-05-31.md`

The May-31 work was **doc-level**; this package is **code-level + consolidation**.

## ID namespaces (so cross-references are unambiguous)

| Prefix | Meaning | Defined in |
|--------|---------|-----------|
| CG-## | code-grounded finding | findings doc |
| P0/P1/P2-# | fix/plan item | hardening plan |
| PR-# / ER-# | product / execution risk | risk register |
| D-# | research delta signal | competitive refresh |
| SPEC-* | design spec | recommendation log §3 |
| J-# | judgment | recommendation log §4 |
| DQ-# | decision needed | open-decisions |
| AS-# / NG-# | assumption / non-goal | assumptions-and-nongoals |
| UX-F# | survey theme | May-31 survey |
| F-ECO-### | ecosystem gap | May-31 gap review |

## One-paragraph executive summary

teaagent's governance foundation is strong and remains its differentiator, but its
daily-driver surfaces carry two P0 correctness defects — the chat REPL reports every
task as failed and never shows the answer (CG-01), and its `/undo` can destroy
unrelated uncommitted work (CG-02) — plus fabricated cost displays (CG-03) on a theme
competitors now win on. Root cause is two divergent chat implementations (CG-05). Fix
Phase 0 first (small, high-impact), unify behind a shared controller, then deliver the
four design specs that close the still-open ecosystem gaps (journeys, cockpit, evidence
bundle, risk-mode table).
</content>
