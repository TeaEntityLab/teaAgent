from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_measure_time_to_first_run_under_budget() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(repo_root / 'scripts' / 'measure_time_to_first_run.py')],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"seconds"' in proc.stdout
    seconds = float(json.loads(proc.stdout)['seconds'])
    assert seconds < 30.0
