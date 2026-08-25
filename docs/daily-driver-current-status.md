# Daily-Driver Current Status
# As of 2026-08-25

> **Claim class:** Current truth for daily-driver behavior (TUI, chat, agent mode,
> approval, cost, undo, resume).
>
> **Owns:** What a daily user should trust today and which surface to choose.
>
> **Does not own:** Roadmap horizon status (`roadmap-status.md`), ticket execution
> steps (`plans/ticket-plans/index.md`), or dated review evidence under
> `docs/analysis/`.
>
> **Review trigger:** TUI, chat, agent mode, approval, cost, undo, or resume behavior changes.
> **Last reviewed:** 2026-08-25 (EFX-001–003 runtime guards and providerless acceptance landed; live GitHub/browser/provider proof still missing)

This page is the short daily-use entry point for TeaAgent's TUI, TUI chat, and
agent mode. It is intentionally more practical than the audit corpus.

## First run (safe)

Safe first command: `teaagent chat` (see "Recommended today" below for safe first task).
Current status and operation guides: see the table below.
On failure: [Recovery And Continuity Guide](recovery-and-continuity-guide.md).

**Work scheduling and roadmap:** Active work is governed by
[Roadmap Status](roadmap-status.md), [Backlog Priority](backlog-priority.md), and
[DR-006](strategy/dr-006-owner-decision-2026-06-22.md). The dated 2026-06-04
daily-driver plan is historical evidence, not an active scheduling authority.

## Recommended today

| Need | Recommended surface | Why |
|------|---------------------|-----|
| Conversational local coding with cost and undo visibility | `teaagent chat` | The REPL uses the shared chat controller for result display, cost accounting, and undo journal behavior. |
| Daily cockpit with setup, preflight, runs, and approvals | `teaagent tui --setup --root .` | The TUI is useful for status and operations, with unified cost tracking via ChatSessionController. |
| Non-interactive autonomous task | `teaagent agent run "<task>"` | Best when you want audit logs, approval gates, and a run summary without a live chat loop. |
| Resume/review a known run | `teaagent agent interactive-review <run_id>` | This is the currently reliable inspection path for suspended/background-style work. |

## Solid today

- Approval governance now fail-closes GitHub/browser/MCP external mutations in prompt/read-only/workspace-write, consumes one-time JIT grants, and refuses blind redispatch of unmatched non-idempotent starts. Providerless acceptance is in `tests/acceptance/test_efx_durable_effect_flow.py`. Keep live credentials off until a live-credential dry-run exists; see "Known issues."
- `teaagent chat` prints successful task answers and no longer marks successful tasks as failures.
- `teaagent chat` `/cost` and `/budget` are wired to real session cost. Budget semantics are explicit: `None` means unlimited, while `0` is a real zero cap. Cost display labels whether the value is actual, estimated, or unavailable.
- `teaagent chat` `/undo` uses the undo journal and preserves unrelated manual edits.
- TUI setup, preflight, runs, session listing, and approval commands provide useful operational coverage.
- TUI `/cost` now accumulates via ChatSessionController (CG-11 fixed).
- TUI has adopted ChatSessionController for unified execution semantics (CG-12 fixed).
- Exception swallowing removed from ChatSessionController (CG-13 fixed).
- Failure-card matching has stopword filtering and relevance threshold (TASK-DD2-012 fixed).
- Memory and run store corruption warnings surfaced in preflight/daily (TASK-DD2-011 fixed).
- TUI ask/run/cost/undo/root/resume commands all delegate to ChatSessionController (P0-A-001). Headless command-path tests (22 tests in `test_tui_command_path.py`) verify each command goes through the controller.
- TUI undo output explicitly labels fallback: "journal undo completed", "checkpoint restore completed", or "nothing to undo" (P0-A-003).
- TUI help text includes a "TUI Command Reference" section documenting controller-backed command semantics (P0-A-004).

## Document governance

Use these when you need the rules behind status, risk, or document ownership:

- Curated docs front door: [INDEX.md](INDEX.md)
- Canonical states: [governance/document-state-model.md](governance/document-state-model.md)
- Risk to ticket to roadmap flow: [governance/risk-issue-roadmap-workflow.md](governance/risk-issue-roadmap-workflow.md)
- Document taxonomy and ownership: [governance/doc-taxonomy-and-ownership.md](governance/doc-taxonomy-and-ownership.md)
- Maintenance entry point: [governance/doc-maintenance-policy-2026-06-02.md](governance/doc-maintenance-policy-2026-06-02.md)
- Documentation operating model: [governance/documentation-operating-model-2026-06-04.md](governance/documentation-operating-model-2026-06-04.md)
- Markdown corpus review: [analysis/markdown-status-review-2026-06-02.md](analysis/markdown-status-review-2026-06-02.md)
- Documentation state review: [analysis/documentation-state-review-2026-06-04.md](analysis/documentation-state-review-2026-06-04.md)

## Current planning front door

Use [Roadmap Status](roadmap-status.md) for canonical horizon and governance-gap
status, [Backlog Priority](backlog-priority.md) for scheduling disposition, and
[DR-006](strategy/dr-006-owner-decision-2026-06-22.md) for admission rules.
Owner friction enters through the
[Operator Friction Log](work-log/operator-friction-log.md); broader held work
stays in the
[dated decision queue](specs/held-roadmap-forward-spec-index-2026-07-11.md#8-dated-decision-queue).

## Latest project-level cross-review

The newest project-level review layer fact-checks the broad "late-P0 / early-P1"
assessment and turns it into Phase 0 trust-repair work:

- Fact check: [analysis/project-state-cross-review-fact-check-2026-06-04.md](analysis/project-state-cross-review-fact-check-2026-06-04.md)
- Critical questioning: [reviews/project-state-critical-questioning-2026-06-04.md](reviews/project-state-critical-questioning-2026-06-04.md)
- Trust repair brief: [security/phase-0-trust-repair-risk-brief-2026-06-04.md](security/phase-0-trust-repair-risk-brief-2026-06-04.md)
- Governance closure report: [work-log/phase-0-governance-closure-report-2026-06-04.md](work-log/phase-0-governance-closure-report-2026-06-04.md)
- Dependency audit scope refresh: [security/dependency-audit-scope-refresh-2026-06-04.md](security/dependency-audit-scope-refresh-2026-06-04.md)
- Outlook: [strategy/phase-0-to-phase-1-outlook-2026-06-04.md](strategy/phase-0-to-phase-1-outlook-2026-06-04.md)
- Work items: [work-log/phase-0-priority-work-items-2026-06-04.md](work-log/phase-0-priority-work-items-2026-06-04.md)

## Latest documentation-state package

The current documentation optimization pass adds a curated front door, a
documentation-state review, critical questioning, an operating model, a master
plan, and a work-item ledger:

- Front door: [INDEX.md](INDEX.md)
- State review: [analysis/documentation-state-review-2026-06-04.md](analysis/documentation-state-review-2026-06-04.md)
- Critical questioning: [reviews/documentation-critical-questioning-2026-06-04.md](reviews/documentation-critical-questioning-2026-06-04.md)
- Operating model: [governance/documentation-operating-model-2026-06-04.md](governance/documentation-operating-model-2026-06-04.md)
- Master plan: [plans/documentation-optimization-master-plan-2026-06-04.md](plans/documentation-optimization-master-plan-2026-06-04.md)
- Work items: [work-log/documentation-optimization-work-items-2026-06-04.md](work-log/documentation-optimization-work-items-2026-06-04.md)

## Latest dynamic skill and long-result package

Dynamic skill generation is structurally supported but not yet proven reliable
end-to-end for daily use. The RSS failure case shows the current gap: a skill
can appear in a discoverable directory without proving reviewed install,
activation, long-source preservation, script execution, or verified summary
output.

- Audit: [analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md](analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md)
- RSS case study: [analysis/rss-failure-case-study-2026-06-05.md](analysis/rss-failure-case-study-2026-06-05.md)
- Ecosystem value map: [strategy/agent-ecosystem-core-values-2026-06-05.md](strategy/agent-ecosystem-core-values-2026-06-05.md)
- Critical questioning: [reviews/dynamic-skill-critical-questioning-2026-06-05.md](reviews/dynamic-skill-critical-questioning-2026-06-05.md)
- Architecture target: [architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md](architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md)
- Work items: [plans/dynamic-skill-and-long-result-work-items-2026-06-05.md](plans/dynamic-skill-and-long-result-work-items-2026-06-05.md)

## Latest seven-control-loop strategy package

The June 5 competitor and research pass reframes TeaAgent's next architecture
step as seven control loops: spec-first direction, dynamic workflow breadth,
goal-loop depth, model-routing cost and quality control, synthesis review,
precise memory, and human review gates. These documents are strategy and work
planning evidence only; they do not prove the runtime already implements the
full loop.

- Competitor survey: [analysis/seven-control-loops-competitor-survey-2026-06-05.md](analysis/seven-control-loops-competitor-survey-2026-06-05.md)
- Product direction: [strategy/seven-control-loops-product-direction-2026-06-05.md](strategy/seven-control-loops-product-direction-2026-06-05.md)
- Architecture map: [architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md](architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md)
- Critical questioning: [reviews/seven-control-loops-critical-questioning-2026-06-05.md](reviews/seven-control-loops-critical-questioning-2026-06-05.md)
- Work items: [plans/seven-control-loops-work-items-2026-06-05.md](plans/seven-control-loops-work-items-2026-06-05.md)

## Latest community pain-point package

The June 5 community pass records current user pain around routing opacity,
memory pollution, review cost, long-task drift, cost surprise, hook/permission
confusion, skill/MCP supply-chain risk, overeager edits, and fake success. Treat
these as roadmap pressure signals, not proof that every competitor has the same
bug or that TeaAgent has already fixed the class.

- Pain-point survey: [analysis/community-agent-pain-points-survey-2026-06-05.md](analysis/community-agent-pain-points-survey-2026-06-05.md)
- Response plan: [plans/community-pain-points-response-plan-2026-06-05.md](plans/community-pain-points-response-plan-2026-06-05.md)

## Known issues

| Issue | Practical impact | Tracking |
|-------|------------------|----------|
| Dynamic generated skills are not yet proven end-to-end. | Treat generated skills as governed candidates until a run proves activation, source preservation, and output verification. Do not rely on RSS/WebSearch skill summaries as fully reliable yet. | DSK-P0-001 through DSK-P0-004 |
| Seven-control-loop package is not daily-driver runtime proof by itself. | `docs/roadmap-status.md` owns SCL row status, while DR-006/backlog provenance keep competitor-derived SCL-P0 scheduling on hold unless owner friction evidence, governance-gap proof, or owner override promotes it. Treat completed SCL rows as control-model/docs evidence until runtime receipts prove daily behavior. | SCL-P0-001 through SCL-P0-007; DR-006 |
| Community pain-point docs are not mitigation proof by themselves. | `docs/roadmap-status.md` owns CPP row status. Daily-driver claims still need implementation receipts and tests before survey-derived pain points can be claimed fixed in user-visible behavior. | CPP-P0-001 through CPP-P0-008 |
| External-effect approval and one-time JIT guards landed; live provider proof is still missing. | Prompt/read-only/workspace-write now escalate GitHub/browser/MCP mutations; one-time grants bind payload digest and consume. Providerless acceptance exists; do not treat this as production-proven GitHub/browser safety until a live-credential dry-run exists. | EFX-002, EFX-003 |
| Interrupted mutating-tool execution is disclosed as `OUTCOME_UNKNOWN`, not settled. | Process death after mutation now leaves a checkpointed unmatched start; resume refuses blind non-idempotent redispatch. Inspect the run, workspace, and external system before any new authorized attempt. | EFX-001; [Recovery And Continuity Guide](recovery-and-continuity-guide.md#interrupted-mutating-tool-execution) |

## Recently fixed

| Fix | What changed | Tracking |
|-----|-------------|----------|
| Cost display now labels actual vs estimated vs unavailable vs unlimited. | BudgetState includes explicit `cost_state` field; TUI /cost, /budget, run summary, and evidence bundle all use the same 4 cost states consistently. UI never implies actual cost when only an estimate is available. | P0-B-001 through P0-B-003 |
| Cost state propagated to all surfaces. | RunEvidenceSummary, RunEvidenceBundle, run_summary.py, TUI /cost and /budget commands all show cost_state label with the canonical set: actual, estimated, unavailable, unlimited. | P0-B-001 |
| Cost accumulation tests added. | `tests/test_tui_cost.py` covers 4 cost states, cost/budget consistency, multi-task accumulation, evidence bundle fields, and run summary cost_state. | P0-B-002 |
| Path-scoped approval without a path now fails closed. | `p` no longer falls back to a global grant when no path can be extracted, and blank scoped patterns are rejected at the store boundary. | DS-12 / approval UX |
| Budget semantics are explicit. | `None` means unlimited, `0` is a real zero cap, and the TUI/CLI budget displays reflect that distinction. | DS-13 / budget UX |
| Explicit `--root` no longer overwritten by saved TUI state. | `_load_tui_state` condition was inverted (checked `'root' not in data` instead of finding saved root). Root restoration now guarded by `_root_explicit` flag, set by CLI entry points via `run_tui()`. | TASK-DD2-002 |
| TUI undo now uses `ChatSessionController.undo_last_run()` with checkpoint fallback. | TUI `/undo` first tries undo journal (file-level restore), falls back to git-stash checkpoint. | CG-15 / TICKET-12 |
| TUI cost display now reads from `ChatSessionController` session state (source of truth). | `_handle_cost` uses `controller.get_session_cost()` with local fallback. | CG-11 / TICKET-12 |
| Exception swallowing removed from `ChatSessionController`. | `try/except (AttributeError, TypeError): pass` blocks removed from `execute_task`. Fault-injection test added. | CG-13 / TICKET-13 |
| Redundant `audit_trail` field removed from suspension data. | `audit_trail` key removed from `suspend_to_background` and reference in `_agent.py` commented out. | CG-14 / TICKET-15 |
| TUI `/cost` and budget display now show real session cost. | TUI migrated to use `ChatSessionController` for unified cost tracking. Headless TUI path tests verify accumulation. | TASK-DD2-003 / TASK-DD2-013 |
| Failure-card matching has stopword filtering and relevance threshold. | Matching requires 2+ significant words in common to avoid false positives from unrelated tasks. | TASK-DD2-012 |
| Memory and run store corruption warnings surfaced. | `health_report()` methods track corrupt entries; preflight/daily show warnings for degraded state. | TASK-DD2-011 |
| Headless TUI path tests hardened. | Tests now drive through actual command paths (cost, root, initial task, undo, approvals) rather than helper functions. | TASK-DD2-013 |
| REPL suspend→resume round-trip restored. | `suspend_to_background()` records `run_started` before `session_suspended`, so `teaagent agent resume <run_id>` can recover the task; `test_repl_suspend_resume_roundtrip` covers the path. | TICKET-16 Phase 2 |
| TUI `session clear` now clears persisted chat messages. | The command empties the active session's `messages` list, saves it, and reports an error when no active session exists. | TUI session UX |
| Run evidence summaries surfaced in agent mode payload. | `run_evidence` field added to agent run output with commands, tests, approvals, gaps. | — |
| Updated daily-driver status docs. | Removed stale known issues, added recently-fixed section. | — |
| TUI/CLI semantic parity (P0-A). | Headless command-path tests (22 tests) verify ask/run/cost/undo/root/resume delegate to ChatSessionController. TUI undo output labels journal vs checkpoint fallback. Help text includes controller-backed command reference. | P0-A-001, P0-A-002, P0-A-003, P0-A-004 |

## Do not rely on yet

- Do not use `teaagent agent run --background <run_id>` to resume; it can treat the id as a new task argument.
- Do not treat a successful docs-only check as proof that active runtime paths were tested.
- Do not treat newly landed stop-gaps as release-ready until the active command path is tested.
- Do not treat a loaded skill as proof that the skill was used or that the final
  artifact was source-backed.
- Do not treat the seven-control-loop strategy or work-item package as runtime
  proof, or as permission to schedule legacy-competitive work without the DR-006
  gates: owner friction evidence, governance-gap proof, or owner override.
- Do not treat community pain-point docs as mitigation evidence. Use
  `docs/roadmap-status.md` for row state, then require implementation/test
  receipts before claiming daily-driver behavior is fixed.
- Do not treat EFX-001–003 unit/integration guards as production-proven GitHub,
  browser, or other live-provider safety. Keep those integrations disabled or
  remove ambient credentials until acceptance-tier evidence exists.
- Do not treat an unmatched mutating start as settled. Resume refuses blind
  non-idempotent redispatch and surfaces `OUTCOME_UNKNOWN`; inspect the run,
  workspace, and external system before any new authorized attempt.


## 2026-06-25 review note

CG-16 test-harness work (TUI de-mock slices, `test_tui.py` doctor GraphQLite stub,
runner tool-decision split) does **not** change user-visible daily-driver behavior.
Evidence: `pytest tests/test_tui*.py tests/tui/ tests/test_tui_command_path.py -q`.

## Read next

- Known daily-use caveats: [daily-driver-known-issues-2026-06-01.md](daily-driver-known-issues-2026-06-01.md)
- Command cookbook: [guides/daily-driver-command-cookbook-2026-06-02.md](guides/daily-driver-command-cookbook-2026-06-02.md)
- Guide index: [guides/daily-driver-guide-index-2026-06-02.md](guides/daily-driver-guide-index-2026-06-02.md)
- TUI guide: [tui-daily-driver-guide.md](tui-daily-driver-guide.md)
- TUI chat reference: [tui-chat-reference.md](tui-chat-reference.md)
- Agent mode guide: [agent-mode-operator-guide.md](agent-mode-operator-guide.md)
- Troubleshooting: [daily-driver-troubleshooting.md](daily-driver-troubleshooting.md)
- Reliability scorecard: [reliability/daily-driver-reliability-scorecard-2026-06-02.md](reliability/daily-driver-reliability-scorecard-2026-06-02.md)
- Complete risk/ROI work plan: [plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md](plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md)
- Full review index: [analysis/daily-driver-review-INDEX-2026-06-01.md](analysis/daily-driver-review-INDEX-2026-06-01.md)
