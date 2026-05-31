from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class CommandResult:
    cmd: str
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'cmd': self.cmd,
            'exit_code': self.exit_code,
            'duration_seconds': round(self.duration_seconds, 3),
            'stdout': self.stdout,
            'stderr': self.stderr,
        }


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int = 600,
) -> CommandResult:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    ended = time.monotonic()
    cmd = ' '.join(shlex.quote(part) for part in argv)
    return CommandResult(
        cmd=cmd,
        exit_code=proc.returncode,
        duration_seconds=ended - started,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_pytest_counts(*, python: str, cwd: Path) -> dict[str, Any]:
    def _parse_count(text: str) -> Optional[int]:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.endswith('tests collected') or ' tests collected' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'tests' and i > 0 and parts[i + 1] == 'collected':
                        try:
                            return int(parts[i - 1])
                        except ValueError:
                            return None
                if parts and parts[0].isdigit():
                    return int(parts[0])
        return None

    acceptance = _run(
        [python, '-m', 'pytest', 'tests/acceptance', '--collect-only', '-q'],
        cwd=cwd,
        timeout_seconds=300,
    )
    suite = _run(
        [python, '-m', 'pytest', '--collect-only', '-q'],
        cwd=cwd,
        timeout_seconds=300,
    )
    return {
        'acceptance_collected': _parse_count(
            acceptance.stdout + '\n' + acceptance.stderr
        ),
        'suite_collected': _parse_count(suite.stdout + '\n' + suite.stderr),
        'collect_commands': [acceptance.to_dict(), suite.to_dict()],
    }


def build_release_evidence_bundle(
    *,
    repo_root: Path,
    output_path: Path,
    run_profile: str = 'release',
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    started_at = datetime.now(timezone.utc).isoformat()

    python = sys.executable
    results: list[CommandResult] = []

    # Minimal, reproducible set of gates. Keep this conservative to avoid
    # network or privileged operations inside sandboxed runners.
    if run_profile in {'release', 'full'}:
        results.append(
            _run(['pre-commit', 'run', '-a'], cwd=repo_root, timeout_seconds=900)
        )
        results.append(
            _run(
                [python, 'scripts/run_acceptance_tier.py', '--tier', 'all'],
                cwd=repo_root,
                timeout_seconds=900,
            )
        )
        results.append(
            _run(
                [python, 'scripts/refresh_competitive_docs.py', '--check'],
                cwd=repo_root,
                timeout_seconds=900,
            )
        )

    pytest_counts = _collect_pytest_counts(python=python, cwd=repo_root)

    git_head = _run(['git', 'rev-parse', 'HEAD'], cwd=repo_root, timeout_seconds=30)
    git_branch = _run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_root, timeout_seconds=30
    )
    git_status = _run(
        ['git', 'status', '--porcelain'], cwd=repo_root, timeout_seconds=30
    )

    artifacts = []
    for rel in (
        'docs/acceptance.md',
        'docs/use-case-matrix.md',
        'docs/use-case-matrix.html',
        'docs/ergonomics-kpi.json',
    ):
        path = repo_root / rel
        if path.is_file():
            artifacts.append(
                {
                    'path': rel,
                    'sha256': _sha256(path),
                    'bytes': path.stat().st_size,
                }
            )

    payload: dict[str, Any] = {
        'ok': all(r.exit_code == 0 for r in results),
        'created_at': started_at,
        'repo_root': str(repo_root),
        'run_profile': run_profile,
        'platform': {
            'python': sys.version.split()[0],
            'executable': python,
            'os': platform.platform(),
        },
        'git': {
            'branch': git_branch.stdout.strip(),
            'commit': git_head.stdout.strip(),
            'dirty': bool(git_status.stdout.strip()),
        },
        'pytest_counts': pytest_counts,
        'commands': [r.to_dict() for r in results],
        'artifacts': artifacts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate a release evidence bundle JSON.'
    )
    parser.add_argument('--root', default='.', help='Repo root to run in.')
    parser.add_argument(
        '--output', default='docs/release-evidence.json', help='Output JSON path.'
    )
    parser.add_argument(
        '--profile',
        default='release',
        choices=('release', 'full', 'counts-only'),
        help='Which gates to execute as part of the bundle.',
    )
    args = parser.parse_args()
    root = Path(args.root)
    output = Path(args.output)
    profile = args.profile
    if profile == 'counts-only':
        profile = 'counts-only'
    build_release_evidence_bundle(
        repo_root=root, output_path=output, run_profile=profile
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
