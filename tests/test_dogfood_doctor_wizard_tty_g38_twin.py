# test-type: behavior
"""G38 twin: `doctor ... --wizard` must not crash on non-interactive stdin.

The five doctor wizards prompt with ``input()``/``getpass``. On piped/headless
stdin those raised ``EOFError`` and surfaced as the generic ``Unexpected
error`` (rc 1, empty/opaque message) — the same first-run crash class removed
for ``init``/``setup`` in G23/G38, and reachable straight from ``init``'s own
``next_steps`` (``teaagent doctor mcp --wizard``). Each wizard must now fail
fast with a classified ``{"ok": false, "error": ...}`` naming the TTY need.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from teaagent.cli import main
from teaagent.cli._handlers._doctor._wizard_io import require_wizard_tty


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
    """Each wizard on non-TTY stdin -> rc 1 + classified error, never a crash."""
    output = io.StringIO()
    with (
        patch('sys.stdin.isatty', return_value=False),
        redirect_stdout(output),
    ):
        exit_code = main([*argv, '--root', str(tmp_path)])

    assert exit_code == 1
    raw = output.getvalue()
    assert 'Unexpected error' not in raw
    payload = json.loads(raw)
    assert payload['ok'] is False
    assert 'terminal' in payload['error']


def test_require_wizard_tty_allows_a_tty() -> None:
    """The guard returns True (no output) when stdin is interactive."""
    output = io.StringIO()
    with patch('sys.stdin.isatty', return_value=True), redirect_stdout(output):
        assert require_wizard_tty('teaagent doctor mcp --wizard') is True
    assert output.getvalue() == ''
