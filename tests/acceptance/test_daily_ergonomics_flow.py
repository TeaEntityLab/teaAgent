from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, '-m', 'teaagent.cli', *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_daily_ergonomics_smoke(tmp_path: Path) -> None:
    init = _run(
        'init',
        '--root',
        str(tmp_path),
        '--provider',
        'gpt',
        '--api-key',
        'test',
        '--permission-mode',
        'read-only',
        '--context-profile',
        'lean',
        cwd=tmp_path,
    )
    assert init.returncode == 0, init.stderr
    guidance = _run('guidance', '--root', str(tmp_path), cwd=tmp_path)
    assert guidance.returncode == 0
    recipes = _run('recipes', 'list', cwd=tmp_path)
    assert recipes.returncode == 0
    payload = json.loads(recipes.stdout)
    names = {item['name'] for item in payload}
    required = {
        'review-staged',
        'fix-failing-test',
        'summarize-repo',
        'map-architecture',
        'safe-cleanup',
        'write-tests',
        'release-check',
        'docs-drift',
        'security-pass',
    }
    assert required <= names
    recipe_run = _run(
        'recipes',
        'run',
        'summarize-repo',
        '--print-only',
        '--root',
        str(tmp_path),
        cwd=tmp_path,
    )
    assert recipe_run.returncode == 0
    recipe_payload = json.loads(recipe_run.stdout)
    assert recipe_payload['permission_mode'] == 'read-only'
    assert recipe_payload['context_profile'] == 'lean'
    approval = _run('approval', 'list', '--root', str(tmp_path), cwd=tmp_path)
    assert approval.returncode == 0
    recall = _run('recall', '--root', str(tmp_path), '--limit', '3', cwd=tmp_path)
    assert recall.returncode == 0
    session = _run('session', 'list', '--root', str(tmp_path), cwd=tmp_path)
    assert session.returncode == 0
    daily = _run(
        'daily',
        'readiness check',
        '--root',
        str(tmp_path),
        '--dry-run',
        cwd=tmp_path,
    )
    assert daily.returncode == 0, daily.stderr
    run_dry = _run(
        'run',
        'smoke task',
        '--root',
        str(tmp_path),
        '--dry-run',
        cwd=tmp_path,
    )
    assert run_dry.returncode == 0, run_dry.stderr
    journal = _run('journal', '--root', str(tmp_path), '--task', 'note', cwd=tmp_path)
    assert journal.returncode == 0, journal.stderr
    caps = _run(
        'model', 'capabilities', '--per-model', '--provider', 'gpt', cwd=tmp_path
    )
    assert caps.returncode == 0
    assert 'gpt' in caps.stdout
    background = _run('background', 'list', '--root', str(tmp_path), cwd=tmp_path)
    assert background.returncode == 0
