#!/usr/bin/env python3
"""Check that no single Python module exceeds the god-module line threshold.

Enforces thin-harness rule from tool-capability-review.md §Layer 1.

Usage:
    python3 scripts/check_god_modules.py [--threshold N] [--exempt PATH ...]

Exit codes:
    0 — all modules under threshold
    1 — one or more modules exceed threshold
"""

import argparse
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 800

# Explicit exemptions require an ADR or documented rationale.
DEFAULT_EXEMPTIONS: set[str] = {
    'teaagent/runner/_core.py',
    'teaagent/tui/core.py',
    # Known debt — tracked in the action register for future splitting.
    # See A-P2-2 (CLI handler god modules), A-P0-1 (approval queue), and
    # general architecture-debt items.
    'teaagent/approval/manager.py',  # Approval policy core; migration completed.
    'teaagent/audit.py',  # Core audit infrastructure
    'teaagent/chat_agent.py',  # Library entry point
    'teaagent/cli/__init__.py',  # CLI root dispatch
    'teaagent/cli/_agent_parsers.py',  # A-P2-2 split target
    'teaagent/cli/_handlers/_ergonomics/approval.py',
    'teaagent/cli/_handlers/chat_repl.py',  # A-P2-2 split target
    'teaagent/domain/issue_intake.py',
    'teaagent/external_backends.py',  # A-P1-2 Any reduction target
    'teaagent/llm/_adapters.py',
    'teaagent/memory/catalog.py',
    'teaagent/run_evidence.py',  # A-P1-2 Any reduction target
    'teaagent/sandbox/_git_branch.py',
    'teaagent/skill_loader.py',
    'teaagent/subagents/_approval_queue.py',
    'teaagent/subagents/_approval_queue_redis_store.py',
    'teaagent/swarm.py',
    'teaagent/tui/_commands.py',
}


def count_lines(path: Path) -> int:
    with path.open('rb') as f:
        return sum(1 for _ in f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument('--exempt', action='append', default=[])
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    teaagent_dir = repo_root / 'teaagent'

    exemptions = DEFAULT_EXEMPTIONS | set(args.exempt)
    failures: list[tuple[str, int]] = []

    for py_file in sorted(teaagent_dir.rglob('*.py')):
        relative = py_file.relative_to(repo_root).as_posix()
        if relative in exemptions:
            continue
        lines = count_lines(py_file)
        if lines > args.threshold:
            failures.append((relative, lines))

    if not failures:
        print(
            f'OK: No god modules found (threshold={args.threshold}, '
            f'exemptions={len(exemptions)}).'
        )
        return 0

    print(f'ERROR: {len(failures)} module(s) exceed {args.threshold} lines:')
    for path, line_count in failures:
        print(f'  {path}: {line_count} lines')
    print()
    print(
        f'Split the module(s) above or add an ADR exemption. '
        f'Current exemptions: {", ".join(sorted(exemptions))}'
    )
    return 1


if __name__ == '__main__':
    sys.exit(main())
