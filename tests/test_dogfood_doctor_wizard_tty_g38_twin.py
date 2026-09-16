# test-type: behavior
"""G38 twin: `doctor ... --wizard` must not crash on exhausted stdin.

The five doctor wizards prompt with ``input()``/``getpass``. On piped/headless
stdin those raised ``EOFError`` and surfaced as the generic ``Unexpected
error`` (rc 1, empty/opaque message) — the same first-run crash class removed
for ``init``/``setup`` in G23/G38, and reachable straight from ``init``'s own
``next_steps`` (``teaagent doctor mcp --wizard``). Each wizard must now fail
fast with a classified ``{"ok": false, "error": ...}``. Provided/piped answers
still work (the guard only catches EOF), so the existing wizard tests that mock
``input``/``getpass`` keep passing.
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
    """Each wizard on exhausted stdin -> rc 1 + classified error, never a crash."""
    output = io.StringIO()
    with (
        patch('teaagent.cli._handlers._doctor.model.input', side_effect=EOFError),
        patch('teaagent.cli._handlers._doctor.project.input', side_effect=EOFError),
        patch('getpass.getpass', side_effect=EOFError),
        redirect_stdout(output),
    ):
        exit_code = main([*argv, '--root', str(tmp_path)])

    assert exit_code == 1
    raw = output.getvalue()
    assert 'Unexpected error' not in raw
    payload = json.loads(raw)
    assert payload['ok'] is False
    assert 'interactive' in payload['error']


def test_require_wizard_tty_allows_a_tty() -> None:
    """Happy path passes through unchanged, no output.

    Successor to the removed ``require_wizard_tty`` isatty check: the wizard
    guard is now the ``guard_wizard_eof`` decorator, which must leave a
    successful (non-EOF) call untouched — the same "allowed path is not
    blocked" guarantee, now covering provided/piped input, not just a TTY.
    """
    output = io.StringIO()

    @guard_wizard_eof('teaagent doctor demo --wizard')
    def _ok(_args: object) -> int:
        return 0

    with redirect_stdout(output):
        assert _ok(object()) == 0
    assert output.getvalue() == ''


def test_guard_wizard_eof_converts_eof_to_classified_error() -> None:
    """An EOFError inside the wizard becomes a classified error and rc 1."""
    output = io.StringIO()

    @guard_wizard_eof('teaagent doctor demo --wizard')
    def _boom(_args: object) -> int:
        raise EOFError

    with redirect_stdout(output):
        rc = _boom(object())

    assert rc == 1
    payload = json.loads(output.getvalue())
    assert payload['ok'] is False
    assert 'interactive' in payload['error']
