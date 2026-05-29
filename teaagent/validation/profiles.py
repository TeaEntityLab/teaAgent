"""Validation profiles for post-run checks."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

ValidationProfileName = Literal['fast', 'standard', 'strict']

PROFILE_NAMES: tuple[ValidationProfileName, ...] = ('fast', 'standard', 'strict')


@dataclass
class ProfileCommandResult:
    name: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class ProfileValidationReport:
    profile: ValidationProfileName
    passed: bool
    results: list[ProfileCommandResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            'profile': self.profile,
            'passed': self.passed,
            'results': [
                {
                    'name': r.name,
                    'command': r.command,
                    'exit_code': r.exit_code,
                    'skipped': r.skipped,
                    'skip_reason': r.skip_reason,
                    'stdout_excerpt': (r.stdout or r.stderr)[:500],
                }
                for r in self.results
            ],
        }


def _commands_for_profile(profile: ValidationProfileName) -> list[tuple[str, list[str]]]:
    if profile == 'fast':
        return [('ruff', ['ruff', 'check', '--quiet'])]
    if profile == 'standard':
        return [
            ('ruff', ['ruff', 'check']),
            ('mypy', ['mypy', '.']),
        ]
    return [
        ('ruff', ['ruff', 'check']),
        ('mypy', ['mypy', '.']),
        ('pytest', ['python', '-m', 'pytest', 'tests/', '-q', '--maxfail=1']),
    ]


def run_profile_validation(
    root: str | Path,
    profile: ValidationProfileName,
    *,
    timeout: int = 120,
) -> ProfileValidationReport:
    """Run workspace validation commands for *profile*."""
    workspace = Path(root).resolve()
    results: list[ProfileCommandResult] = []
    passed = True

    for name, command in _commands_for_profile(profile):
        executable = command[0]
        if shutil.which(executable) is None:
            results.append(
                ProfileCommandResult(
                    name=name,
                    command=command,
                    exit_code=0,
                    stdout='',
                    stderr='',
                    skipped=True,
                    skip_reason=f'{executable} not installed',
                )
            )
            continue
        proc = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ok = proc.returncode == 0
        passed = passed and ok
        results.append(
            ProfileCommandResult(
                name=name,
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        )

    return ProfileValidationReport(profile=profile, passed=passed, results=results)
