# Daily-Driver Review Package — Master Index
# 2026-06-01

A single entry point to the 2026-06-01 review of teaagent's daily surfaces
(TUI, `teaagent chat`, agent mode). Read in this order.

## Document governance

This package is historical evidence plus active indexes. When dated review files
disagree, use the active status ledgers and the governance rules below:

1. **`../governance/document-state-model.md`** *(governance)*
   Canonical states for findings, risks, tickets, roadmap rows, and archived docs.
2. **`../governance/risk-issue-roadmap-workflow.md`** *(governance)*
   Pipeline from finding/risk capture to ticket, roadmap, evidence, and supersession.
3. **`../governance/doc-taxonomy-and-ownership.md`** *(governance)*
   Document type ownership and source-of-truth rules.
4. **`markdown-status-review-2026-06-02.md`** *(analysis)*
   `cx`/repo review of the Markdown corpus and recommended consolidation policy.

## 2026-06-02 expansion after further code improvements

These files are the newest layer. They preserve the June 1 evidence but reclassify
newly patched behavior as verify/close where appropriate, and add fresh risk items from
the June 2 review.

1. **`../daily-driver-current-status.md`** *(user guide)*
   Short daily-use front door for TUI, TUI chat, and agent mode.
2. **`daily-driver-new-code-facts-and-risks-2026-06-02.md`** *(analysis)*
   New working-tree facts: chat positional task forwarding and TUI cost stop-gap are
   partially fixed; root, controller parity, lifecycle wording, and new RL risks remain.
3. **`daily-driver-new-risk-log-2026-06-02.md`** *(analysis)*
   RL-NEW-01..05: dry-run writes, context-pack truth label, pinned-file containment,
   corrupt state visibility, and failure-card matching.
4. **`daily-driver-advice-and-recommendation-ledger-2026-06-02.md`** *(analysis)*
   June 2 advice/recommendation/thought ledger.
5. **`daily-driver-decision-log-2026-06-02.md`** *(analysis)*
   Decisions DQ-2026-001..018 for root, cost, lifecycle, approval, and cleanup.
6. **`../plans/daily-driver-implementation-sequencing-board-2026-06-02.md`** *(plans)*
   Current implementation order and parallel lanes.
7. **`../plans/daily-driver-regression-test-matrix-2026-06-02.md`** *(plans)*
   Test matrix for trust-sensitive daily-driver behavior.
8. **`../plans/ticket-plans/index.md`** *(plans)*
   Ticket index now includes TASK-DD2-003..014.
9. **`../architecture/daily-driver-state-and-lifecycle-map-2026-06-02.md`** *(architecture)*
   State/lifecycle map for root, cost, approvals, run records, undo, and audit evidence.
10. **`../reviews/daily-driver-docs-package-review-2026-06-02.md`** *(review)*
    Review of the documentation package itself and its saturation risk.

## 2026-06-02 additional guide/module supplement

This supplement makes the June 2 findings easier to use day to day.

1. **`../guides/daily-driver-guide-index-2026-06-02.md`** *(guides)*
   Entry point for command cookbook, TUI/chat recipes, approval recipes, and recovery.
2. **`../modules/daily-driver-module-map-2026-06-02.md`** *(modules)*
   Maps daily risks to TUI, run store, git sandbox, context pack, and pinned-file docs.
3. **`daily-driver-more-docs-log-2026-06-02.md`** *(analysis)*
   Logs the extra docs pass, advice MD-001..010, and docs-expansion risks.
4. **`../plans/daily-driver-verification-backlog-2026-06-02.md`** *(plans)*
   Backlog of the highest-value verification work created by the June 2 docs.
5. **`../governance/daily-driver-release-gates-2026-06-02.md`** *(governance)*
   Release blockers and proof requirements for daily-driver claims.
6. **`../reliability/daily-driver-reliability-scorecard-2026-06-02.md`** *(reliability)*
   Conservative readiness scores by area.
7. **`../security/daily-driver-safety-boundaries-2026-06-02.md`** *(security)*
   Safety boundaries for root, approval, pinned files, cost, undo, evidence, and sandbox.

## 2026-06-01 second-pass after improvements: read these first

These files are the newest layer of the daily-driver review. They incorporate the
latest code improvements and the parallel second-pass audits, and should be read before
the earlier same-day refresh documents.

1. **`daily-driver-second-pass-after-improvements-2026-06-01.md`** *(analysis)*
   Current fixed/still-active/new facts after the latest code changes.
2. **`../plans/daily-driver-second-pass-task-plan-2026-06-01.md`** *(plans)*
   Reviewable task queue for the newly discovered risks.
3. **`daily-driver-verification-gap-audit-2026-06-01.md`** *(analysis)*
   Where current tests prove behavior, and where they only cover helpers or smoke paths.
4. **`daily-driver-ux-contract-drift-2026-06-01.md`** *(analysis)*
   User-facing words, flags, and displays that currently drift from runtime behavior.

## 2026-06-01 late refresh: read these next

The files below supersede stale parts of the earlier same-day package. Some earlier
findings were fixed or shifted to different runtime paths; the current risks now center
on chat task entry, TUI cost accounting, git-sandbox defaults, lifecycle wording, and
runtime/test path divergence.

1. **`daily-driver-current-truth-audit-2026-06-01.md`** *(analysis)*
   Current code truth table: active, fixed, stale, and shifted findings.
2. **`daily-driver-risk-register-refresh-2026-06-01.md`** *(analysis)*
   Updated risk register based on current code review and parallel UX/repo audits.
3. **`daily-driver-popular-agent-feedback-survey-2026-06-01.md`** *(analysis)*
   Current market/forum feedback survey and competitive daily-use lessons.
4. **`daily-driver-agent-market-source-map-2026-06-01.md`** *(analysis)*
   Source map for official docs, issue/forum signals, volatile facts, and product notes.
5. **`daily-driver-ux-survey-tui-chat-agent-2026-06-01.md`** *(analysis)*
   UX journey and severity survey for TUI, TUI chat, CLI chat, and agent mode.
6. **`daily-driver-defeat-modes-2026-06-01.md`** *(analysis)*
   Failure modes where TeaAgent can technically work but lose daily-user trust.
7. **`../plans/daily-driver-usefulness-master-plan-2026-06-01.md`** *(plans)*
   Phased plan for making the project daily-useful.
8. **`../plans/daily-driver-stability-test-plan-2026-06-01.md`** *(plans)*
   Test strategy and readiness gates.

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
23. **`daily-driver-third-pass-postfix-audit-2026-06-01.md`** *(analysis)* — **READ THIS
    FOR CURRENT TRUTH.** After the `ChatSessionController` batch landed: CG-01/02/03(REPL)/
    04/06/07/09/10 FIXED; new findings CG-11…CG-16 (TUI never adopted the controller →
    `/cost` $0.00, undo divergence, a test masking the bug). Tickets 12-15 in the backlog.

## Post-fix layer (third pass — TUI not yet on the controller)

24. **`daily-driver-tui-controller-migration-spec-2026-06-01.md`** *(specs)* — how to
    migrate the TUI onto `ChatSessionController` without regressing (capability gap,
    minimal additive controller changes, parity contract, risks MR-1…MR-5).
25. **`daily-driver-surface-parity-matrix-2026-06-01.md`** *(analysis)* — REPL vs TUI vs
    agent, behavior-by-behavior; makes CG-12 legible (3 ❌ rows = the bugs).
26. **`daily-driver-tui-postfix-execution-sheets-2026-06-01.md`** *(plans)* — per-ticket
    DoD + exact file:line for TICKET-12…15 (incl. the 1-line cost stop-gap 12a).
27. **`daily-driver-test-integrity-audit-2026-06-01.md`** *(analysis)* — the
    inject-the-state-you-assert anti-pattern (CG-16), grounded instances, the rule.
28. **`daily-driver-third-pass-thought-log-2026-06-01.md`** *(analysis)* — complete
    "log everything" for this pass: TP-OBS / TP-J / TP-REC / TP-AS / TP-DQ / R-6…R-8.

## Consolidation / log layer

9. **`daily-driver-recommendation-log-2026-06-01.md`** — every finding, rec, judgment,
   research signal, decision, assumption (the "log everything" deliverable).
10. **`daily-driver-open-decisions-2026-06-01.md`** — maintainer decision register (DQ-1…).
11. **`daily-driver-assumptions-and-nongoals-2026-06-01.md`** — AS-1…, NG-1….
12. **`daily-driver-traceability-matrix-2026-06-01.md`** — finding→fix→test→theme→gap.
13. **`daily-driver-backlog-2026-06-01.md`** *(plans)* — flat, ticket-style backlog.

## Fourth-pass: agent-mode surface (newly reviewed)

29. **`daily-driver-agent-mode-suspension-audit-2026-06-01.md`** *(analysis)* — audits the
    non-interactive agent path + the suspend→resume round-trip. Findings AG-01…AG-04: the
    REPL advertises `resume`/`--background`/`interactive-review` but only review works;
    `resume` errors, `--background` runs the id as a literal task. Agent-mode *governance*
    (scoped approvals, plan gate, auto-compact) verified solid. → TICKET-16.

## Consolidation & QA layer (fifth pass)

30. **`daily-driver-findings-status-ledger-2026-06-01.md`** *(analysis)* — **single
    authoritative status page** for CG-01…CG-17 + AG-01…AG-04 (status/ticket/test/evidence).
31. **`daily-driver-acceptance-test-catalog-2026-06-01.md`** *(plans)* — every named test:
    exists / missing / misleading. Surfaced CG-17 + 5 unguarded shipped fixes.
32. **`../processes/daily-driver-manual-qa-smoke.md`** *(processes)* — human smoke
    checklist with observable expected results per finding/surface.

## Repo-convention artifacts (this review, filed in the project's own dirs)

- **`../adr/0025-chat-session-controller-unification.md`** — ADR for the controller
  decision, honestly marked *Implemented (Partial — REPL done, TUI pending)*.
- **`../processes/postfix-reaudit-process.md`** — reusable re-audit procedure that caught
  the partial application + masking test; run it after any fix batch lands.

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
| DQ-2026-### | June 2 decision needed | daily-driver-decision-log-2026-06-02 |
| AS-# / NG-# | assumption / non-goal | assumptions-and-nongoals |
| UX-F# | survey theme | May-31 survey |
| F-ECO-### | ecosystem gap | May-31 gap review |
| CF-### | June 2 code fact | daily-driver-new-code-facts-and-risks-2026-06-02 |
| RL-NEW-## | June 2 new risk | daily-driver-new-risk-log-2026-06-02 |
| ADV-### | June 2 advice item | daily-driver-advice-and-recommendation-ledger-2026-06-02 |
| MD-### | June 2 more-docs advice item | daily-driver-more-docs-log-2026-06-02 |

## One-paragraph executive summary

teaagent's governance foundation is strong and remains its differentiator, but the
current daily-driver risks have shifted. Controller-backed chat fixed several earlier
defects, while the active high-risk queue is now: `teaagent chat <task>` can accept and
drop the task, TUI cost/budget state is not wired to real run cost, agent mode can
auto-start a git sandbox despite `--git-sandbox` reading as opt-in, background/suspend
copy is contradictory, and tests/docs can cover stale paths. Fix the command grammar and
shared state model first, then harden the TUI cockpit and permission/recovery stories.
