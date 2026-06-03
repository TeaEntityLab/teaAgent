# Daily-Driver Current Status
# As of 2026-06-02

This page is the short daily-use entry point for TeaAgent's TUI, TUI chat, and
agent mode. It is intentionally more practical than the audit corpus.

## Recommended today

| Need | Recommended surface | Why |
|------|---------------------|-----|
| Conversational local coding with cost and undo visibility | `teaagent chat` | The REPL uses the shared chat controller for result display, cost accounting, and undo journal behavior. |
| Daily cockpit with setup, preflight, runs, and approvals | `teaagent tui --setup --root .` | The TUI is useful for status and operations, but some chat counters still lag runtime truth. |
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

## Document governance

Use these when you need the rules behind status, risk, or document ownership:

- Canonical states: [governance/document-state-model.md](governance/document-state-model.md)
- Risk to ticket to roadmap flow: [governance/risk-issue-roadmap-workflow.md](governance/risk-issue-roadmap-workflow.md)
- Document taxonomy and ownership: [governance/doc-taxonomy-and-ownership.md](governance/doc-taxonomy-and-ownership.md)
- Maintenance entry point: [governance/doc-maintenance-policy-2026-06-02.md](governance/doc-maintenance-policy-2026-06-02.md)
- Markdown corpus review: [analysis/markdown-status-review-2026-06-02.md](analysis/markdown-status-review-2026-06-02.md)

## Known issues

| Issue | Practical impact | Tracking |
|-------|------------------|----------|
| `teaagent chat <task>` was recently wired into the TUI initial-task path. | Treat as verify/close until parser, handler, and TUI tests prove it. | TASK-DD2-001 |
| Suspend/resume wording is ahead of implementation in some paths. | A user can try a printed command that does not rehydrate the run. | AG-01..AG-04 / TICKET-16 |
| Controller swallows real errors as "mock" detection. | Production errors may be silently ignored. | CG-13 / TICKET-13 |
| Redundant `audit_trail` JSON field in suspension data. | Wasted space, potential confusion. | CG-14 / TICKET-15 |

## Recently fixed

| Fix | What changed | Tracking |
|-----|-------------|----------|
| Explicit `--root` no longer overwritten by saved TUI state. | `_load_tui_state` condition was inverted (checked `'root' not in data` instead of finding saved root). Root restoration now guarded by `_root_explicit` flag, set by CLI entry points via `run_tui()`. | TASK-DD2-002 |
| TUI undo now uses `ChatSessionController.undo_last_run()` with checkpoint fallback. | TUI `/undo` first tries undo journal (file-level restore), falls back to git-stash checkpoint. | CG-15 / TICKET-15 |
| TUI cost display now reads from `ChatSessionController` session state (source of truth). | `_handle_cost` uses `controller.get_session_cost()` with local fallback. | CG-03 |
| Run evidence summaries surfaced in agent mode payload. | `run_evidence` field added to agent run output with commands, tests, approvals, gaps. | — |
| Updated daily-driver status docs. | Removed stale known issues, added recently-fixed section. | — |

## Do not rely on yet

- Do not assume TUI `/undo` has the same scope as `teaagent chat` `/undo` until the TUI controller migration lands.
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
- Full review index: [analysis/daily-driver-review-INDEX-2026-06-01.md](analysis/daily-driver-review-INDEX-2026-06-01.md)
