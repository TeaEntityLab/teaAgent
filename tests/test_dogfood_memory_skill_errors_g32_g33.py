# test-type: behavior
"""Behavior tests pinning dogfood findings G32 and G33 (R5).

G32: ``MemoryAutoInvalidationConfig.from_workspace_config`` crashed with
``TypeError: unsupported operand type(s) for /: 'str' and 'str'`` when handed a
str root, because it did ``root / '.teaagent'`` on a raw string. The CLI passes
``args.root`` (a str), so ``memory failures auto-invalidate`` was unusable. It
must accept ``str | Path`` like the sibling ``FailureCardStorage``.

G33: ``skill candidate install <missing>`` raised an uncaught
``FileNotFoundError`` (surfacing as the generic ``Unexpected error:`` catch-all)
while the sibling ``show``/``eval``/``review`` subcommands return the classified
``{"status": "error", "message": "... not found"}`` shape and exit 1.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.cli._handlers._memory import memory_failures_auto_invalidate_command
from teaagent.cli._handlers._skill import skill_candidate_install_command
from teaagent.memory.failure_card import MemoryAutoInvalidationConfig


def test_from_workspace_config_accepts_str_root_and_reads_config(
    tmp_path: Path,
) -> None:
    """G32: str root does not raise TypeError and a real config.json is honored."""
    # Absolute str path with no config present -> defaults, no TypeError.
    cfg = MemoryAutoInvalidationConfig.from_workspace_config('/some/str/path')
    assert cfg.enabled is True
    assert cfg.rules  # default conservative rules present

    # str(tmp_path) pointing at a real config.json that disables auto-invalidation
    # must actually be read (proves the loader resolves the path, not just tolerates
    # the type).
    tea_dir = tmp_path / '.teaagent'
    tea_dir.mkdir()
    (tea_dir / 'config.json').write_text(
        json.dumps({'memory': {'auto_invalidation': {'enabled': False}}}),
        encoding='utf-8',
    )
    disabled = MemoryAutoInvalidationConfig.from_workspace_config(str(tmp_path))
    assert disabled.enabled is False
    assert disabled.rules == []


def test_auto_invalidate_handler_accepts_str_root(
    tmp_path: Path,
    capsys,
) -> None:
    """G32: the CLI handler returns 0 and prints a JSON status with a str root."""
    rc = memory_failures_auto_invalidate_command(argparse.Namespace(root=str(tmp_path)))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'ok'
    assert payload['total_invalidated'] == 0


def test_install_missing_candidate_returns_classified_error(
    tmp_path: Path,
    capsys,
) -> None:
    """G33: install of a missing candidate returns 1 with classified error JSON."""
    rc = skill_candidate_install_command(
        argparse.Namespace(
            root=str(tmp_path),
            candidate_id='nonexistent',
            scope='project',
        )
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'error'
    assert 'not found' in payload['message']
