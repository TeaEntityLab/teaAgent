# TUI Module Inspection

## Inspect these paths

- `teaagent/tui/__init__.py`
- `tests/test_tui.py`
- `docs/tui-daily-driver-guide.md`
- `docs/tui-chat-reference.md`

## Inspection questions

- Does startup preserve explicit root?
- Does saved state restore only non-explicit preferences?
- Does chat initial task execute or fail visibly?
- Does cost increment from real run result?
- Does budget display read the same source?
- Does undo tell the user which mechanism is active?
- Does approval prompt show exact scope?
- Do tests drive `_run_agent_task()` or only helper formatters?

## Evidence to collect

- Command entered.
- Visible prompt/root.
- Run id.
- Cost before/after.
- Approval prompt text.
- Git status before/after undo.
- Test names that cover the active path.
