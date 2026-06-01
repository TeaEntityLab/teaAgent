# Daily-Driver Advice And Recommendation Ledger
# 2026-06-02

This is the June 2 "log everything advised/suggested/recommended/thought" ledger. It
continues the June 1 thought log and focuses on actions that make TeaAgent useful for
daily TUI, TUI chat, and agent-mode work.

## Source boundary

Evidence comes from repository docs and local code-grounded review artifacts already in
this workspace. No new web/forum research was performed for this layer.

## Priority classes

| Class | Meaning |
|-------|---------|
| P0 | Trust or data-loss risk. Fix before broad daily-driver recommendation. |
| P1 | Daily-use friction or stability gap. Fix soon. |
| P2 | Maintainability, documentation, or polish. Fix opportunistically. |

## Advice log

| ID | Priority | Advice | Reason |
|----|----------|--------|--------|
| ADV-001 | P0 | Execute or explicitly reject `teaagent chat <task>`. | Accepting a task and dropping it is a trust failure. |
| ADV-002 | P0 | Make explicit `--root` override saved TUI state. | Users must know which repo the agent is operating in. |
| ADV-003 | P0 | Replace false `$0.00` TUI cost with real ledger or unknown state. | Wrong zero is more misleading than missing data. |
| ADV-004 | P0 | Keep destructive recovery scoped and named by mechanism. | Undo ambiguity can lose manual work. |
| ADV-005 | P0 | Reject approvals with empty or ambiguous path scope for write/destructive tools. | Approval without scope weakens the governance story. |
| ADV-006 | P0 | Preserve run task and observations at suspend time. | Resume cannot be real without stored context. |
| ADV-007 | P0 | Remove or correct commands that imply background work when none continues. | Lifecycle wording must match runtime state. |
| ADV-008 | P1 | Complete TUI migration to `ChatSessionController`. | One controller reduces surface drift. |
| ADV-009 | P1 | Stop swallowing `AttributeError`/`TypeError` as mock-detection behavior. | Real production errors can be hidden. |
| ADV-010 | P1 | Make tests drive active user paths. | Helper-only tests can pass while live UX fails. |
| ADV-011 | P1 | Add a regression test for TUI cost accumulation through task execution. | Guards CG-11 and prevents decorative state. |
| ADV-012 | P1 | Add a regression test for explicit root persistence precedence. | Guards TASK-DD2-002. |
| ADV-013 | P1 | Add a regression test for positional chat task execution or rejection. | Guards TASK-DD2-001. |
| ADV-014 | P1 | Split "background", "suspend", "resume", and "review" into separate UX terms. | Users should infer state from words correctly. |
| ADV-015 | P1 | Update docs whenever a finding changes from active to fixed or stale. | Historical docs are useful only when supersession is clear. |
| ADV-016 | P1 | Keep a short current-status page ahead of the audit corpus. | Daily users need guidance before archaeology. |
| ADV-017 | P1 | Maintain a troubleshooting page by symptom, not by internal finding id. | Operators search by what went wrong. |
| ADV-018 | P1 | Make run evidence distinguish claimed, observed, verified, and not-tested. | Prevents final-answer overtrust. |
| ADV-019 | P1 | Treat manual smoke as required for interactive surfaces. | CI has already missed interactive drift. |
| ADV-020 | P1 | Keep TUI approval commands and CLI approval commands semantically aligned. | Governance should not vary by surface. |
| ADV-021 | P1 | Add a test that `agent run --background <run_id>` refuses with a helpful hint. | Prevents accidental new tasks from ids. |
| ADV-022 | P1 | Store approval continuity across suspend/resume. | A resumed run should not launder old authority. |
| ADV-023 | P2 | Introduce `TUIConfig` once parameter growth blocks safe changes. | Avoids 16-argument drift without premature abstraction. |
| ADV-024 | P2 | Retire or quarantine stale `_chat.py` paths after migration. | Reduces future tests against dead code. |
| ADV-025 | P2 | Keep ADR-0025 marked partial until TUI parity is proven. | Architecture records should not overclaim. |
| ADV-026 | P2 | Keep ticket plans small and separately reviewable. | Risky UX fixes are easier to validate in slices. |
| ADV-027 | P2 | Prefer existing governance primitives over a new agent framework. | Project rules say harness stays thin. |
| ADV-028 | P2 | Track docs saturation as a risk. | More docs can hide the next implementation step. |
| ADV-029 | P2 | Add doc consistency checks for new daily-driver indexes. | Keeps the large corpus navigable. |
| ADV-030 | P2 | Add "known broken path" labels directly in user-facing guides. | Honest caveats preserve trust. |
| ADV-031 | P1 | Reclassify newly patched findings as verify/close instead of active implementation. | The working tree now forwards chat positional tasks and has a TUI cost stop-gap. |
| ADV-032 | P1 | Add a dry-run invariant: read-only/dry-run commands must not create `.teaagent` state unless explicitly documented. | Preflight/daily paths can initialize state through memory/run helpers. |
| ADV-033 | P1 | Make `ContextPack.read_only` reflect the caller argument or rename it. | Evidence labels should not imply no side effects when builders can write. |
| ADV-034 | P0 | Enforce workspace containment for pinned files. | Absolute paths and `..` should not escape the project root. |
| ADV-035 | P1 | Surface corrupt memory/run JSON as degraded health. | Silent omission makes daily cockpit state look cleaner than it is. |
| ADV-036 | P2 | Bound failure-card matching with stopwords, scoring thresholds, and redaction. | Sticky irrelevant memories can bias later daily tasks. |

## Repeated thoughts

- The most valuable next code movement is still small trust repair, not broad redesign.
- The strongest product story is governance plus evidence; do not dilute it with misleading UI.
- TUI daily usefulness depends on being boringly accurate.
- Agent mode daily usefulness depends on run ids being durable continuity handles.
- Tests must prove the path the user actually drives.
- A newly patched line is not the same thing as a verified release behavior.

## Human review required

Human review is recommended before:

- Changing default git sandbox behavior.
- Broadening approval scopes.
- Deleting stale chat paths.
- Changing cost cap semantics.
- Rewording lifecycle commands in ways that affect documented workflows.
- Claiming TUI/REPL parity.

## Follow-up docs created in this layer

- [../daily-driver-current-status.md](../daily-driver-current-status.md)
- [../tui-daily-driver-guide.md](../tui-daily-driver-guide.md)
- [../tui-chat-reference.md](../tui-chat-reference.md)
- [../agent-mode-operator-guide.md](../agent-mode-operator-guide.md)
- [../recovery-and-continuity-guide.md](../recovery-and-continuity-guide.md)
- [../operator-trust-model.md](../operator-trust-model.md)
- [../permission-and-approval-playbook.md](../permission-and-approval-playbook.md)
- [../daily-driver-troubleshooting.md](../daily-driver-troubleshooting.md)
- [../run-evidence-and-audit-guide.md](../run-evidence-and-audit-guide.md)
- [../ux-stability-contract.md](../ux-stability-contract.md)
