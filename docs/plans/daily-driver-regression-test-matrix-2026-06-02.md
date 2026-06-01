# Daily-Driver Regression Test Matrix
# 2026-06-02

This matrix lists the tests needed to make daily-driver claims durable.

| Risk | Required test | Current expectation |
|------|---------------|--------------------|
| `teaagent chat <task>` drops task | CLI parser/handler test drives positional task through launch. | Missing or incomplete. |
| TUI explicit root overwritten | TUI state-load test with saved stale root and explicit new root. | Missing or incomplete. |
| TUI cost false zero | Headless TUI task execution increments `_session_cost_cents` or shared ledger. | Existing test may be masked. |
| TUI budget display false calm | Budget display reads same ledger as cost. | Needs path-level assertion. |
| REPL/TUI result parity | Same stubbed task returns visible answer in both surfaces. | Needs parity test. |
| REPL/TUI undo parity | Manual edit A plus agent edit B, undo preserves A. | REPL stronger than TUI today. |
| Controller swallows real error | Fake session raises `AttributeError`; test expects classified failure. | Missing. |
| `agent run --background <run_id>` misuse | Command refuses id-shaped argument with hint. | Missing. |
| Suspend stores task context | Suspend then resume rehydrates task and observations. | Missing or failing. |
| Approval empty path | Write/destructive approval with empty path is rejected. | Missing or incomplete. |
| Cost cap zero semantics | Value `0` has one documented behavior. | Needs policy and test. |
| Dry-run hidden writes | Fresh workspace snapshot proves dry-run/read-only side effects. | Newly identified. |
| Context pack read-only label | `readonly` argument is reflected or field renamed. | Newly identified. |
| Pinned file path escape | Absolute, parent, and symlink escape paths are rejected. | Newly identified. |
| Corrupt state hidden | Malformed memory/run JSON appears as degraded health. | Newly identified. |
| Failure-card sticky match | Unrelated tasks with common words do not inject warnings. | Newly identified. |
| Acceptance docs count | Count tests verify headline and markers. | Partially guarded. |
| Headless TUI smoke | Smoke drives real command loop and asserts output/state. | Needs expansion. |

## Test design rules

- Drive public commands or the closest stable facade.
- Avoid direct assignment to the state you claim to prove.
- Assert both user-visible text and backing state for trust-sensitive facts.
- Include one negative test for each lifecycle command that can be misused.
- Pair every docs-known issue with a failing or skipped test that names the ticket.

## Minimal next test batch

1. `test_chat_positional_task_executes_or_rejects`.
2. `test_tui_explicit_root_wins_over_saved_state`.
3. `test_tui_cost_accumulates_after_task_result`.
4. `test_agent_background_run_id_is_rejected`.
5. `test_controller_does_not_swallow_real_attribute_error`.
6. `test_dry_run_does_not_create_state_unless_declared`.
7. `test_pinned_file_rejects_path_escape`.

## Manual smoke mapping

Automated tests should cover regressions, but the manual smoke checklist remains required
for:

- Terminal rendering.
- Prompt wording.
- Approval comprehension.
- Undo confidence.
- Resume/review flow clarity.
