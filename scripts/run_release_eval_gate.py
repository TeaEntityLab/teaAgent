#!/usr/bin/env python3
"""Run release eval gate (WDA-004 / WDD-001)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from teaagent.governance.release_eval import (  # noqa: E402
    format_gate_summary,
    run_release_eval_gate,
    should_block_release,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='Workspace/repo root')
    parser.add_argument(
        '--seed-failure',
        action='store_true',
        help='Force a failing regression output to verify the gate blocks release.',
    )
    parser.add_argument(
        '--report',
        default='',
        help='Optional path to write JSON gate report.',
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report) if args.report else None
    result = run_release_eval_gate(
        args.root,
        seed_failure=args.seed_failure,
        report_path=report_path,
    )
    print(format_gate_summary(result))
    return 1 if should_block_release(result) else 0


if __name__ == '__main__':
    raise SystemExit(main())
