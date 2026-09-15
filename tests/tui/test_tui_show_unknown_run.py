# test-type: contract
"""TUI `show <unknown-id>` must print an error and stay in the REPL.

Regression for the 2026-09-15 dogfood finding: `show last` raised an
unhandled FileNotFoundError that killed the REPL (exit 1) instead of
returning to the prompt.
"""

from __future__ import annotations

from teaagent.tui._commands import _cmd_show


class _FakeTUI:
    root = '.'

    def __init__(self) -> None:
        self.lines: list[str] = []

    def output_fn(self, msg: str) -> None:
        self.lines.append(msg)

    def _print_json(self, obj: object) -> None:
        self.lines.append('JSON')


def test_show_unknown_run_id_prints_error_and_returns_true() -> None:
    tui = _FakeTUI()
    assert _cmd_show(tui, ['no-such-run-id']) is True
    assert tui.lines == ["error: run 'no-such-run-id' not found"]


def test_show_missing_arg_prints_usage_and_returns_true() -> None:
    tui = _FakeTUI()
    assert _cmd_show(tui, []) is True
    assert tui.lines == ['error: show requires a run id']
