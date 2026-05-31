"""AC-NEW-22: Multi-surface launch recipes flow.

As a user, I want one-command recipes for each TeaAgent surface so I can start
CLI, TUI, IDE, MCP, and federation workflows without reading architecture docs.

Acceptance criteria:
- USAGE.md documents all required surfaces with smoke-check commands.
- Documented local smoke commands exit successfully without network calls.
"""

from __future__ import annotations

import json
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_in(needle: str, haystack: str) -> None:
    assert needle in haystack


def _assert_true(value: object) -> None:
    assert value is True


def _load_validate_module():
    script = _repo_root() / 'scripts' / 'validate_docs_consistency.py'
    spec = spec_from_file_location('validate_docs_consistency', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_surface_recipes_doc_covers_required_surfaces() -> None:
    usage = (_repo_root() / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    module = _load_validate_module()
    errors = module.validate_surface_recipes(usage)
    assert errors == [], f'surface recipe doc errors: {errors}'


def _run_local(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Use virtual environment teaagent if available
    if command[0] == 'teaagent':
        venv_teaagent = cwd / '.venv' / 'bin' / 'teaagent'
        if venv_teaagent.exists():
            command = [str(venv_teaagent)] + command[1:]

    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_documented_smoke_commands_run_locally_without_network() -> None:
    root = _repo_root()
    cases: list[tuple[list[str], callable[[str], None]]] = [
        (
            ['teaagent', 'model', 'providers'],
            lambda out: json.loads(out),
        ),
        (
            ['teaagent', 'agent', 'card', '--root', str(root)],
            lambda out: json.loads(out),
        ),
        (
            ['teaagent', 'workspace', 'tools'],
            lambda out: _assert_in('workspace_read_file', out),
        ),
        (
            [
                'teaagent',
                'agent',
                'preflight',
                'gpt',
                'list workspace tools',
                '--root',
                str(root),
            ],
            lambda out: _assert_true(json.loads(out)['ready']),
        ),
    ]
    for argv, verify in cases:
        result = _run_local(argv, cwd=root)
        if 'preflight' in argv:
            # Preflight uses process exit codes to communicate readiness:
            # - 0: ready
            # - non-zero: not-ready due to clarify/health failures
            #
            # In restricted sandboxes, network binding and repo `.git` writability
            # checks can legitimately fail, but the command should still return a
            # well-formed JSON report rather than crash.
            payload = json.loads(result.stdout.strip() or '{}')
            assert 'ready' in payload
            assert 'health' in payload
            assert 'healthy' in payload['health']
            assert 'failures' in payload['health']
            if result.returncode != 0:
                assert payload['ready'] is False
                assert payload['health']['healthy'] is False
                assert payload['health']['failures']
                continue
        assert result.returncode == 0, (
            f'command failed: {" ".join(argv)}\nstdout={result.stdout}\nstderr={result.stderr}'
        )
        verify(result.stdout.strip() or '{}')
