# Daily-Driver Current Status
# As of 2026-06-04

This page is the short daily-use entry point for TeaAgent's TUI, TUI chat, and
agent mode. It is intentionally more practical than the audit corpus.

## Recommended today

| Need | Recommended surface | Why |
|------|---------------------|-----|
| Conversational local coding with cost and undo visibility | `teaagent chat` | The REPL uses the shared chat controller for result display, cost accounting, and undo journal behavior. |
| Daily cockpit with setup, preflight, runs, and approvals | `teaagent tui --setup --root .` | The TUI is useful for status and operations, with unified cost tracking via ChatSessionController. |
| Non-interactive autonomous task | `teaagent agent run "<task>"` | Best when you want audit logs, approval gates, and a run summary without a live chat loop. |
| Resume/review a known run | `teaagent agent interactive-review <run_id>` | This is the currently reliable inspection path for suspended/background-style work. |

## Solid today

- Approval governance, audit logging, plan-before-write gates, and run summaries remain the strongest parts of the project.
- `teaagent chat` prints successful task answers and no longer marks successful tasks as failures.
- `teaagent chat` `/cost` and `/budget` are wired to real session cost.
- `teaagent chat` `/undo` uses the undo journal and preserves unrelated manual edits.
- TUI setup, preflight, runs, session listing, and approval commands provide useful operational coverage.
- TUI `/cost` now accumulates via ChatSessionController (CG-11 fixed).
- TUI has adopted ChatSessionController for unified execution semantics (CG-12 fixed).
- Exception swallowing removed from ChatSessionController (CG-13 fixed).
- Failure-card matching has stopword filtering and relevance threshold (TASK-DD2-012 fixed).
- Memory and run store corruption warnings surfaced in preflight/daily (TASK-DD2-011 fixed).

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

Use [plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md](plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md)
when choosing what to implement next. It ranks the active work by user value, risk
reduction, feasibility, strategic leverage, and ROI.

## Latest project-level cross-review

The newest project-level review layer fact-checks the broad "late-P0 / early-P1"
assessment and turns it into Phase 0 trust-repair work:

- Fact check: [analysis/project-state-cross-review-fact-check-2026-06-04.md](analysis/project-state-cross-review-fact-check-2026-06-04.md)
- Critical questioning: [reviews/project-state-critical-questioning-2026-06-04.md](reviews/project-state-critical-questioning-2026-06-04.md)
- Trust repair brief: [security/phase-0-trust-repair-risk-brief-2026-06-04.md](security/phase-0-trust-repair-risk-brief-2026-06-04.md)
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

## Known issues

| Issue | Practical impact | Tracking |
|-------|------------------|----------|
| Full REPL-originated suspend→resume rehydration is still open. | Users should inspect suspended REPL sessions with `teaagent agent interactive-review <run_id>`; real CLI resume remains Phase 2 work. | AG-03 / TICKET-16 Phase 2 |

## Recently fixed

| Fix | What changed | Tracking |
|-----|-------------|----------|
| Explicit `--root` no longer overwritten by saved TUI state. | `_load_tui_state` condition was inverted (checked `'root' not in data` instead of finding saved root). Root restoration now guarded by `_root_explicit` flag, set by CLI entry points via `run_tui()`. | TASK-DD2-002 |
| TUI undo now uses `ChatSessionController.undo_last_run()` with checkpoint fallback. | TUI `/undo` first tries undo journal (file-level restore), falls back to git-stash checkpoint. | CG-15 / TICKET-12 |
| TUI cost display now reads from `ChatSessionController` session state (source of truth). | `_handle_cost` uses `controller.get_session_cost()` with local fallback. | CG-11 / TICKET-12 |
| Exception swallowing removed from `ChatSessionController`. | `try/except (AttributeError, TypeError): pass` blocks removed from `execute_task`. Fault-injection test added. | CG-13 / TICKET-13 |
| Redundant `audit_trail` field removed from suspension data. | `audit_trail` key removed from `suspend_to_background` and reference in `_agent.py` commented out. | CG-14 / TICKET-15 |
| TUI `/cost` and budget display now show real session cost. | TUI migrated to use `ChatSessionController` for unified cost tracking. Headless TUI path tests verify accumulation. | TASK-DD2-003 / TASK-DD2-013 |
| Failure-card matching has stopword filtering and relevance threshold. | Matching requires 2+ significant words in common to avoid false positives from unrelated tasks. | TASK-DD2-012 |
| Memory and run store corruption warnings surfaced. | `health_report()` methods track corrupt entries; preflight/daily show warnings for degraded state. | TASK-DD2-011 |
| Headless TUI path tests hardened. | Tests now drive through actual command paths (cost, root, initial task, undo, approvals) rather than helper functions. | TASK-DD2-013 |
| REPL `/background` suspend output made honest. | `suspend_to_background()` now prints the working `teaagent agent interactive-review <run_id>` path and no longer advertises broken `teaagent resume` or `--detach` hints. | TICKET-16 Phase 1 |
| TUI `session clear` now clears persisted chat messages. | The command empties the active session's `messages` list, saves it, and reports an error when no active session exists. | TUI session UX |
| Run evidence summaries surfaced in agent mode payload. | `run_evidence` field added to agent run output with commands, tests, approvals, gaps. | — |
| Updated daily-driver status docs. | Removed stale known issues, added recently-fixed section. | — |

## Do not rely on yet

- Do not use `teaagent agent run --background <run_id>` to resume; it can treat the id as a new task argument.
- Do not treat a successful docs-only check as proof that active runtime paths were tested.
- Do not treat newly landed stop-gaps as release-ready until the active command path is tested.

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
