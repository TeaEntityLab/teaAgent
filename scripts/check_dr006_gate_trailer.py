#!/usr/bin/env python3
"""DR-006 T1 gate trailer check.

Mechanically enforces DR-006 falsifier 1: a ``feat:`` commit that touches
``teaagent/`` must cite its scheduling gate in a ``Gate:`` or ``Constraint:``
trailer whose value contains one of the accepted DR-006 gate tokens.

Usage:
    python3 scripts/check_dr006_gate_trailer.py --commit-msg <path>
    python3 scripts/check_dr006_gate_trailer.py --base <sha>
    python3 scripts/check_dr006_gate_trailer.py --commit <sha>

Exit codes:
    0 — all relevant commits cite an accepted gate.
    1 — at least one relevant ``feat:`` commit touching ``teaagent/`` does not.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Accepted DR-006 scheduling gate tokens. The value of the Gate:/Constraint:
# trailer must contain one of these verbatim.
_ACCEPTED_GATES: tuple[str, ...] = (
    'friction-driven',
    'governance-gap',
    'owner-override',
)

_ACCEPTED_VALUES_TEXT = ', '.join(_ACCEPTED_GATES)

_SUBJECT_PATTERN = re.compile(r'^feat(?:\([^)]*\))?:', re.IGNORECASE)
_GATE_TOKEN_PATTERN = re.compile(
    r'\b(?:friction-driven|governance-gap|owner-override)\b',
    re.IGNORECASE,
)
_TRAILER_PATTERN = re.compile(
    r'^(Gate|Constraint):\s*(.*?)\s*$',
    re.MULTILINE | re.IGNORECASE,
)

_TEAAGENT_PREFIX = 'teaagent/'


def _run_git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a git subcommand and return its completed process."""
    result = subprocess.run(
        ['git', *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result


def _get_commit_message(commit_sha: str) -> str:
    """Return the full commit message for *commit_sha*."""
    result = _run_git('log', '-1', '--pretty=format:%B', commit_sha)
    if result.returncode != 0:
        raise RuntimeError(
            f'Failed to read commit message for {commit_sha}: {result.stderr}'
        )
    return result.stdout


def _get_changed_files(commit_sha: str) -> list[str]:
    """Return the list of files changed in *commit_sha*."""
    result = _run_git('diff-tree', '--no-commit-id', '--name-only', '-r', commit_sha)
    if result.returncode != 0:
        raise RuntimeError(
            f'Failed to list changed files for {commit_sha}: {result.stderr}'
        )
    return [line for line in result.stdout.splitlines() if line]


def _get_staged_files() -> list[str]:
    """Return the list of files currently staged for commit."""
    result = _run_git('diff', '--cached', '--name-only')
    if result.returncode != 0:
        raise RuntimeError(f'Failed to list staged files: {result.stderr}')
    return [line for line in result.stdout.splitlines() if line]


def _get_commits_in_range(rev_range: str) -> list[str]:
    """Return the commit SHAs in *rev_range* in chronological order."""
    result = _run_git('rev-list', '--reverse', rev_range)
    if result.returncode != 0:
        raise RuntimeError(f'Failed to list commits in {rev_range}: {result.stderr}')
    return [line for line in result.stdout.splitlines() if line]


def _is_feat_subject(subject: str) -> bool:
    """Return True when *subject* is a ``feat:`` or ``feat(scope):`` subject."""
    return bool(_SUBJECT_PATTERN.match(subject))


def _touches_teaagent(files: list[str]) -> bool:
    """Return True when any path in *files* starts with ``teaagent/``."""
    return any(file_path.startswith(_TEAAGENT_PREFIX) for file_path in files)


def _has_gate_trailer(message: str) -> bool:
    """Return True when *message* cites an accepted gate in a trailer."""
    for _, value in _TRAILER_PATTERN.findall(message):
        if _GATE_TOKEN_PATTERN.search(value):
            return True
    return False


def _format_error(commit_sha: str, subject: str) -> str:
    """Return an actionable error message for an offending commit."""
    return (
        f'ERROR: DR-006 gate missing on ``feat:`` commit touching teaagent/.\n'
        f'  Commit: {commit_sha} {subject}\n'
        f'  Accepted gate values: {_ACCEPTED_VALUES_TEXT}\n'
        f'  Add a trailer such as ``Gate: governance-gap`` or '
        f'``Constraint: DR-006 governance-gap only`` to the commit message.'
    )


def _read_commit_msg(path: str) -> str:
    """Read the commit message from *path*."""
    return Path(path).read_text(encoding='utf-8')


def _check_commit(commit_sha: str) -> str | None:
    """Check a single commit; return an error string if it fails the gate."""
    message = _get_commit_message(commit_sha)
    subject = message.splitlines()[0] if message else ''
    if not _is_feat_subject(subject):
        return None
    if _touches_teaagent(_get_changed_files(commit_sha)) and not _has_gate_trailer(
        message
    ):
        return _format_error(commit_sha, subject)
    return None


def main() -> int:
    """Parse arguments and run the DR-006 gate trailer check."""
    parser = argparse.ArgumentParser(
        description=(
            'DR-006 T1 gate trailer check: '
            'feat commits touching teaagent/ must cite a gate.'
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        '--commit-msg',
        help='Path to the commit message file (pre-commit commit-msg stage).',
    )
    mode.add_argument(
        '--base',
        help='Base git SHA for CI mode (iterates base..HEAD).',
    )
    mode.add_argument(
        '--commit',
        help='Single commit SHA to check (verification mode).',
    )
    args = parser.parse_args()

    if args.commit_msg is not None:
        message = _read_commit_msg(args.commit_msg)
        subject = message.splitlines()[0] if message else ''
        if (
            _is_feat_subject(subject)
            and _touches_teaagent(_get_staged_files())
            and not _has_gate_trailer(message)
        ):
            print(
                _format_error('<commit-msg>', subject),
                file=sys.stderr,
            )
            return 1
        return 0

    if args.commit is not None:
        error = _check_commit(args.commit)
        if error:
            print(error, file=sys.stderr)
            return 1
        return 0

    # --base mode
    rev_range = args.base if '..' in args.base else f'{args.base}..HEAD'
    commits = _get_commits_in_range(rev_range)
    errors: list[str] = []
    for commit_sha in commits:
        error = _check_commit(commit_sha)
        if error:
            errors.append(error)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
