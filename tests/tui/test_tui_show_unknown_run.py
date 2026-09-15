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


def test_handle_command_survives_handler_raise(tmp_path) -> None:
    """A raising handler must not kill the REPL — handle_command guards all."""
    from teaagent.tui.core import TeaAgentTUI

    seen: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=seen.append, root=tmp_path)

    def boom(_t: object, _a: list[str]) -> bool:
        raise RuntimeError('synthetic failure')

    import teaagent.tui._commands as cmds

    orig = cmds._COMMAND_DISPATCH.get('show')
    cmds._COMMAND_DISPATCH['show'] = boom
    try:
        assert tui.handle_command('show x') is True
    finally:
        if orig is not None:
            cmds._COMMAND_DISPATCH['show'] = orig
    assert seen and seen[0].startswith('error: command failed')


def test_show_missing_arg_prints_usage_and_returns_true() -> None:
    tui = _FakeTUI()
    assert _cmd_show(tui, []) is True
    assert tui.lines == ['error: show requires a run id']
