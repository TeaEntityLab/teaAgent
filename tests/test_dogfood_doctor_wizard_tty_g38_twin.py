# test-type: behavior
"""G38 twin: `doctor ... --wizard` must not crash or pollute stdout on non-TTY.

The five doctor wizards prompt with ``input()``/``getpass``, which echo the
prompt to stdout — and the wizard's own result is JSON on stdout. On piped or
headless stdin those reads previously ``EOFError``ed into the generic
``Unexpected error`` (rc 1) — the same first-run crash class removed for
``init``/``setup`` in G23/G38, and reachable straight from ``init``'s own
``next_steps`` (``teaagent doctor mcp --wizard``). Each wizard must now fail
fast with a classified ``{"ok": false, "error": ...}`` *before* prompting, so
the JSON stdout stays clean. Provided input on a real TTY still works, so the
existing wizard tests (which declare a TTY and mock ``input``/``getpass``) keep
passing.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from teaagent.cli import main
from teaagent.cli._handlers._doctor._wizard_io import guard_wizard_eof


@pytest.mark.parametrize(
    'argv',
    [
        ['doctor', 'mcp', '--wizard'],
        ['doctor', 'project', '--wizard'],
        ['doctor', 'providers', '--wizard'],
        ['doctor', 'aigateway', '--wizard'],
        ['doctor', 'model', 'gpt', '--wizard'],
    ],
    ids=['mcp', 'project', 'providers', 'aigateway', 'model'],
)
def test_doctor_wizard_non_tty_is_classified_error(argv: list[str], tmp_path) -> None:
    """Non-TTY -> rc 1 + clean classified JSON, no prompt echoed, no crash."""
    output = io.StringIO()
    with patch('sys.stdin.isatty', return_value=False), redirect_stdout(output):
        exit_code = main([*argv, '--root', str(tmp_path)])

    assert exit_code == 1
    raw = output.getvalue()
    assert 'Unexpected error' not in raw
    # The classified error must be the whole of stdout — no echoed prompt prefix.
    payload = json.loads(raw)
    assert payload['ok'] is False
    assert 'interactive' in payload['error']


def test_require_wizard_tty_allows_a_tty() -> None:
    """Happy path passes through unchanged on a TTY, with no added output.

    Successor to the removed ``require_wizard_tty`` isatty check: the wizard
    guard is now the ``guard_wizard_eof`` decorator, which must leave a
    successful call on an interactive stdin untouched.
    """
    output = io.StringIO()

    @guard_wizard_eof('teaagent doctor demo --wizard')
    def _ok(_args: object) -> int:
        return 0

    with patch('sys.stdin.isatty', return_value=True), redirect_stdout(output):
        assert _ok(object()) == 0
    assert output.getvalue() == ''


def test_guard_wizard_eof_converts_eof_to_classified_error() -> None:
    """On a TTY that still hits end-of-input, EOFError -> classified error, rc 1."""
    output = io.StringIO()

    @guard_wizard_eof('teaagent doctor demo --wizard')
    def _boom(_args: object) -> int:
        raise EOFError

    with patch('sys.stdin.isatty', return_value=True), redirect_stdout(output):
        rc = _boom(object())

    assert rc == 1
    payload = json.loads(output.getvalue())
    assert payload['ok'] is False
    assert 'interactive' in payload['error']
