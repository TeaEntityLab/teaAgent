#!/usr/bin/env python3
"""Measure seconds from project init to first providerless daily dry-run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def measure(*, repo_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='teaagent-kpi-') as tmp:
        root = Path(tmp)
        init = subprocess.run(
            [
                sys.executable,
                '-m',
                'teaagent.cli',
                'init',
                '--root',
                str(root),
                '--provider',
                'gpt',
                '--api-key',
                'kpi-test',
                '--permission-mode',
                'read-only',
                '--context-profile',
                'lean',
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0:
            raise RuntimeError(init.stderr or init.stdout)
        daily = subprocess.run(
            [
                sys.executable,
                '-m',
                'teaagent.cli',
                'daily',
                'readiness',
                '--root',
                str(root),
                '--dry-run',
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if daily.returncode != 0:
            raise RuntimeError(daily.stderr or daily.stdout)
    elapsed = time.perf_counter() - started
    return {
        'seconds': round(elapsed, 3),
        'path': 'pip install -e . → teaagent init → teaagent daily --dry-run',
        'ok': True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--write',
        default=None,
        metavar='PATH',
        help='Write JSON KPI artifact (e.g. docs/ergonomics-kpi.json).',
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    payload = measure(repo_root=repo_root)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.write:
        Path(args.write).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
