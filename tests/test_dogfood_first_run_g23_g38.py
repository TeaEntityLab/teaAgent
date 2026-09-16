# test-type: behavior
"""Behavior tests for dogfood findings G23, G24, G29, G30, G38 (R2 first-run).

These pin the first-run reliability repairs:
- G30: the offline ``fake`` provider skips connectivity checks (no DNS/socket).
- G23: ``init --provider fake`` never prompts for a key it does not need, and no
  ``getpass`` runs when stdin is not a TTY.
- G38: non-interactive ``init``/``setup`` without a provider fail with a
  classified error before writing config, instead of raising ``EOFError``.
- G24: ``init --permission-mode workspace-write`` next-steps explain the plan
  gate (``agent plan`` then ``--from-plan``) and never recommend
  ``--skip-plan-check``.
- G29: ``init`` gitignores ``.teaagent/`` in a git repo (added/present/skipped/
  not-a-git-repo), non-destructively.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from teaagent.cli import main
from teaagent.preflight import check_provider_connectivity


def _run_init(argv: list[str], *, tty: bool) -> tuple[int, dict]:
    output = io.StringIO()
    with patch('sys.stdin.isatty', return_value=tty), redirect_stdout(output):
        exit_code = main(argv)
    return exit_code, json.loads(output.getvalue())


def test_fake_provider_skips_connectivity_without_network() -> None:
    """G30: fake readiness must not touch DNS/sockets and stays ready offline."""
    with (
        patch('socket.getaddrinfo', side_effect=AssertionError('DNS was called')),
        patch(
            'socket.create_connection',
            side_effect=AssertionError('socket was opened'),
        ),
    ):
        ready, message = check_provider_connectivity('fake')
    assert ready is True
    assert 'no network' in message


def test_init_fake_non_tty_writes_config_without_prompting(tmp_path: Path) -> None:
    """G23: fake needs no key; init writes config and never calls getpass on non-TTY."""
    with patch(
        'teaagent.cli._handlers._misc.getpass.getpass',
        side_effect=AssertionError('getpass must not run for fake / non-TTY'),
    ):
        exit_code, payload = _run_init(
            ['init', '--root', str(tmp_path), '--provider', 'fake'], tty=False
        )
    assert exit_code == 0
    assert payload['ok'] is True
    assert payload['provider'] == 'fake'
    assert (tmp_path / '.teaagent' / 'config.json').exists()


def test_init_without_provider_on_non_tty_is_classified_error(tmp_path: Path) -> None:
    """G38: non-interactive init without --provider errors before writing config."""
    exit_code, payload = _run_init(['init', '--root', str(tmp_path)], tty=False)
    assert exit_code == 1
    assert payload['ok'] is False
    assert 'non-interactive' in payload['message']
    assert not (tmp_path / '.teaagent' / 'config.json').exists()


def test_init_workspace_write_next_steps_explain_plan_gate(tmp_path: Path) -> None:
    """G24: workspace-write next-steps teach the plan gate, never --skip-plan-check."""
    exit_code, payload = _run_init(
        [
            'init',
            '--root',
            str(tmp_path),
            '--provider',
            'fake',
            '--api-key',
            'x',
            '--permission-mode',
            'workspace-write',
        ],
        tty=False,
    )
    assert exit_code == 0
    steps = payload['next_steps']
    plan_idx = next(i for i, s in enumerate(steps) if 'agent plan' in s)
    from_plan_idx = next(i for i, s in enumerate(steps) if '--from-plan' in s)
    assert plan_idx < from_plan_idx
    assert not any('--skip-plan-check' in s for s in steps)


def test_init_adds_teaagent_to_gitignore_in_git_repo(tmp_path: Path) -> None:
    """G29: a fresh git repo gains a non-destructive .teaagent/ ignore, reports added."""
    (tmp_path / '.git').mkdir()
    exit_code, payload = _run_init(
        ['init', '--root', str(tmp_path), '--provider', 'fake'], tty=False
    )
    assert exit_code == 0
    assert payload['gitignore'] == 'added'
    gitignore = (tmp_path / '.gitignore').read_text(encoding='utf-8')
    assert '.teaagent/' in gitignore
    # The scaffold itself is untracked until committed, and the sandbox refuses
    # a dirty worktree: the first next step must say so.
    assert payload['next_steps'][0].startswith('git add .gitignore AGENTS.md')


def test_init_leaves_existing_gitignore_entry_untouched(tmp_path: Path) -> None:
    """G29: an existing .teaagent/ entry is preserved verbatim and reported present."""
    (tmp_path / '.git').mkdir()
    gitignore_path = tmp_path / '.gitignore'
    original = 'node_modules/\n.teaagent/\n'
    gitignore_path.write_text(original, encoding='utf-8')
    exit_code, payload = _run_init(
        ['init', '--root', str(tmp_path), '--provider', 'fake'], tty=False
    )
    assert exit_code == 0
    assert payload['gitignore'] == 'present'
    assert gitignore_path.read_text(encoding='utf-8') == original


def test_init_no_gitignore_flag_opts_out(tmp_path: Path) -> None:
    """G29: --no-gitignore leaves the repo's .gitignore untouched and reports skipped."""
    (tmp_path / '.git').mkdir()
    exit_code, payload = _run_init(
        ['init', '--root', str(tmp_path), '--provider', 'fake', '--no-gitignore'],
        tty=False,
    )
    assert exit_code == 0
    assert payload['gitignore'] == 'skipped'
    assert not (tmp_path / '.gitignore').exists()


def test_init_outside_git_repo_leaves_gitignore_alone(tmp_path: Path) -> None:
    """G29: a non-git directory is never given a .gitignore; reports not-a-git-repo."""
    exit_code, payload = _run_init(
        ['init', '--root', str(tmp_path), '--provider', 'fake'], tty=False
    )
    assert exit_code == 0
    assert payload['gitignore'] == 'not-a-git-repo'
    assert not (tmp_path / '.gitignore').exists()
    assert not any(step.startswith('git add') for step in payload['next_steps'])


def test_setup_without_provider_on_non_tty_is_classified_error(tmp_path: Path) -> None:
    """G38: non-interactive setup without --provider errors cleanly, never EOFError."""
    output = io.StringIO()
    with patch('sys.stdin.isatty', return_value=False), redirect_stdout(output):
        exit_code = main(['setup', '--root', str(tmp_path)])
    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload['ok'] is False
    assert 'non-interactive' in payload['message']
    assert not (tmp_path / '.teaagent' / 'config.json').exists()
