# Daily-Driver Risk Register Refresh

Date: 2026-06-01

This register refreshes earlier June 1 risk documents after current-code review and
parallel read-only audits.

## Risk Register

| ID | Severity | Risk | Evidence | Mitigation | Verification |
|---|---|---|---|---|---|
| R-001 | High | `teaagent chat <task>` accepts a task but does not execute it. | Parser accepts chat task; `chat_command` delegates to `run_tui` without initial task support. | Add initial task support to TUI/chat entry point or reject positional task with a clear error. | Behavioral test invoking CLI handler with task and mocked agent result. |
| R-002 | High | TUI cost/budget display is false or stale. | `_run_agent_task` receives `result.cost_cents`; `_session_cost_cents` is not incremented. | Route TUI through `ChatSessionController` or update ledger in one shared helper. | Test real TUI run updates `/cost` and `/budget`. |
| R-003 | High | Agent mode changes git branch despite `--git-sandbox` looking opt-in. | `GitBranchSandbox` starts whenever available under current consent logic. | Decide product contract: either make flag truly opt-in or rename/docs/test auto-sandbox. | Non-interactive clean-repo test with and without flag. |
| R-004 | High | Runtime and tests cover different chat surfaces. | Tests emphasize `chat_repl.py` and controller; runtime `chat_command` lives in `_chat.py` and TUI direct path. | Collapse to one controller-backed entry point. | Import/path test proving CLI command reaches same controller as TUI chat. |
| R-005 | Medium | Background/suspension wording creates false expectations. | `suspend_to_background` creates checkpoint; caller says converted to background task. | Rename command or copy: `/suspend` for checkpoint, `/background` only for active detached work. | Snapshot tests for help and command output. |
| R-006 | Medium | Undo semantics are fragmented. | TUI help lists journal undo and checkpoint undo; CLI exposes preview elsewhere. | Define one recovery decision tree and align help, parser, TUI, docs. | Tests for help text plus TUI undo behavior. |
| R-007 | Medium | Stale duplicate REPL code can reintroduce fixed defects. | `_chat.py` still contains older REPL implementation and stale fallback logic. | Delete, quarantine, or mark dead code with failing guard after import audit. | Coverage proving no runtime imports depend on stale function. |
| R-008 | Medium | Remote MCP annotations can understate destructive behavior. | Adapter infers read-only/destructive behavior from server-provided annotations. | Default unknown remote tools to prompt/high caution; require local trust policy for relaxed mode. | MCP registration tests with missing/lying annotations. |
| R-009 | Medium | Permission fatigue pushes users to broad authority. | Prompt options include path/tool/session outcomes; docs teach pre-approval. | Add permission-mode onboarding and show blast radius before broad approval. | UX copy tests for approval prompts and no-path fallback. |
| R-010 | Medium | Acceptance docs overstate readiness. | `validate_docs_consistency` reported count mismatch against pytest collection. | Generate counts or update docs in the same PR as tests. | `python3 scripts/validate_docs_consistency.py` passes. |
| R-011 | Low | TUI cockpit promise outruns implementation. | README/docs promote TUI daily loop; tests mostly assert line output/no-throw. | Write a TUI cockpit contract and back it with headless smoke scenarios. | Headless TUI scenarios for status, cost, undo, approvals. |
| R-012 | Low | Older same-day docs are easy to misread as current truth. | Previous docs mark completed items that current audit still finds active. | Keep this refresh and index supersession note first in read order. | Index links current truth docs before historical docs. |

## Human Review Gates

Human review is required before:

- Changing branch/sandbox defaults.
- Relaxing or broadening permission approvals.
- Deleting duplicate chat implementation paths.
- Changing undo behavior.
- Claiming daily-driver readiness in README or release notes.

## Rollback Strategy

- Cost-ledger and help-text fixes are local and reversible.
- Controller unification should be guarded by tests before deleting old paths.
- Git-sandbox default changes need a compatibility note and a fast revert path.
- MCP trust changes should default to stricter prompts; rollback can loosen by config if
  users report too much friction.

## Residual Risk After Mitigation

Even after the high risks are fixed, TeaAgent will remain exposed to normal agent-product
risks: provider outages, model regressions, tool-call loops, noisy approvals, and user
misconfiguration. The daily-driver bar is not "no failures"; it is visible state,
bounded authority, recoverable edits, and honest evidence.

