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
    assert any(item['name'] == 'review-staged' for item in payload)
    approval = _run('approval', 'list', '--root', str(tmp_path), cwd=tmp_path)
    assert approval.returncode == 0
    recall = _run('recall', '--root', str(tmp_path), '--limit', '3', cwd=tmp_path)
    assert recall.returncode == 0
