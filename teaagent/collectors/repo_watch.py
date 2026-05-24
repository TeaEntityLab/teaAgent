"""Repo-watch collector for script-first automations."""

from __future__ import annotations

import json
import subprocess


def collect_latest_commit_summary() -> dict[str, object]:
    try:
        completed = subprocess.run(
            ['git', 'log', '-1', '--oneline'],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            'wake_agent': False,
            'summary': f'git log unavailable: {exc}',
        }
    line = completed.stdout.strip()
    if completed.returncode != 0 or not line:
        return {'wake_agent': False, 'summary': 'no commits'}
    return {'wake_agent': True, 'summary': line}


def main() -> int:
    print(json.dumps(collect_latest_commit_summary(), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
