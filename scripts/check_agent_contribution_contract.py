#!/usr/bin/env python3
"""Agent contribution contract gate: validate agent-authored commits.

Implements V4-a from the intent verification delta: ensures agent-authored
commits comply with the contribution contract defined in docs/agent-contribution-contract.md.

This gate checks:
1. Required commit trailers are present (Agent, Agent-Session)
2. Claim-bearing files have passing gates
3. Docs consistency validation passes

NO SELF-SERVICE BYPASS (V4-c fix): Agents cannot bypass their own governance gate.
Bypass attempts via trailer or environment variable are treated as CRITICAL errors.
Manual bypass requires human intervention via GitHub UI only.

Usage:
  python3 scripts/check_agent_contribution_contract.py                 # check HEAD commit
  python3 scripts/check_agent_contribution_contract.py --commit <sha>  # check specific commit
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = _REPO_ROOT / '.venv' / 'bin' / 'python'

# Required trailers for agent-authored commits
_REQUIRED_TRAILERS = frozenset({'Agent', 'Agent-Session'})

# Files that claim governance-relevant data and require gate validation
_CLAIM_BEARING_FILES = frozenset(
    {
        'docs/acceptance.md',
        'README.md',
        'docs/architecture.md',
        'docs/roadmap-status.md',
        'docs/governance-compliance.md',
        'docs/generated/suite-summary.json',
    }
)


def _get_commit_message(commit_sha: str = 'HEAD') -> str:
    """Get the full commit message for a given commit."""
    result = subprocess.run(
        ['git', 'log', '-1', '--pretty=format:B', commit_sha],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Failed to get commit message for {commit_sha}')
    return result.stdout


def _parse_trailers(commit_message: str) -> dict[str, str]:
    """Parse git trailers from commit message."""
    trailers: dict[str, str] = {}
    for line in commit_message.splitlines():
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            # Trailer format: Key: Value
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                trailers[key] = value
    return trailers


def _get_changed_files(commit_sha: str = 'HEAD') -> set[str]:
    """Get list of files changed in the commit."""
    result = subprocess.run(
        ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_sha],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Failed to get changed files for {commit_sha}')
    return set(result.stdout.strip().splitlines()) if result.stdout.strip() else set()


def _check_docs_consistency() -> list[str]:
    """Run docs consistency validation."""
    # Prefer the repo venv for consistency with the acceptance count gate
    python = str(_VENV_PYTHON if _VENV_PYTHON.exists() else sys.executable)

    # First, try to regenerate docs inventory to avoid staleness from multi-agent concurrent edits
    inventory_script = _REPO_ROOT / 'scripts' / 'generate_docs_inventory.py'
    if inventory_script.exists():
        subprocess.run(
            [python, str(inventory_script)],
            capture_output=True,
            text=True,
            check=False,
            cwd=_REPO_ROOT,
        )

    result = subprocess.run(
        [python, 'scripts/validate_docs_consistency.py', '--test-quality-mode', 'off'],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    errors: list[str] = []
    if result.returncode != 0:
        errors.append(f'Docs consistency validation failed:\n{result.stderr}')
    return errors


def _check_agent_contract(commit_sha: str = 'HEAD') -> list[str]:
    """Validate agent contribution contract compliance."""
    errors: list[str] = []

    # Get commit metadata
    commit_message = _get_commit_message(commit_sha)
    trailers = _parse_trailers(commit_message)
    changed_files = _get_changed_files(commit_sha)

    # NO BYPASS ALLOWED: agents cannot bypass their own governance gate
    # If a bypass is attempted, treat it as a critical error
    if 'Bypass-agent-contract' in trailers:
        errors.append(
            f'CRITICAL: Agent attempted self-service bypass via trailer. '
            f'This violates the agent contribution contract purpose. '
            f'Reason given: {trailers["Bypass-agent-contract"]}'
        )
        return errors  # Fail immediately

    # Check if this appears to be an agent-authored commit
    # (has Agent trailer or appears to be automated)
    is_agent_commit = 'Agent' in trailers or 'Agent-Session' in trailers

    if is_agent_commit:
        # Check required trailers
        missing_trailers = _REQUIRED_TRAILERS - set(trailers.keys())
        if missing_trailers:
            errors.append(
                f'Missing required trailers for agent-authored commit: {", ".join(missing_trailers)}'
            )

    # Check if claim-bearing files were modified
    modified_claim_files = _CLAIM_BEARING_FILES & changed_files
    if modified_claim_files:
        # Run docs consistency gate
        docs_errors = _check_docs_consistency()
        errors.extend(docs_errors)

        if docs_errors:
            errors.append(
                f'Claim-bearing files modified ({", ".join(modified_claim_files)}) but docs consistency gate failed'
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate agent contribution contract compliance'
    )
    parser.add_argument(
        '--commit',
        default='HEAD',
        help='Commit SHA to check (default: HEAD)',
    )
    args = parser.parse_args()

    # NO ENVIRONMENT BYPASS: agents cannot bypass their own governance gate
    # If bypass is attempted, treat it as a critical error
    if os.getenv('ALLOW_AGENT_CONTRACT_BYPASS') == '1':
        print(
            '::error::CRITICAL: Agent attempted self-service bypass via environment variable. '
            'This violates the agent contribution contract purpose.',
            file=sys.stderr,
        )
        return 1

    try:
        errors = _check_agent_contract(args.commit)
    except Exception as e:
        print(f'Error checking agent contract: {e}', file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f'::error::{error}', file=sys.stderr)
        return 1

    print('Agent contribution contract check passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
