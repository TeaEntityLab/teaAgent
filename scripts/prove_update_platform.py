#!/usr/bin/env python3
"""WDA-005: run single-platform update proof and write report artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.update_platform import (  # noqa: E402
    run_update_platform_proof,
    write_proof_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output',
        default='docs/analysis/update-platform-proof-2026-06-10.json',
        help='JSON proof report path',
    )
    parser.add_argument('--platform', default='linux')
    args = parser.parse_args(argv)
    proof = run_update_platform_proof(platform=args.platform)
    out = write_proof_report(proof, Path(args.output))
    print(f'Update platform proof OK: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
