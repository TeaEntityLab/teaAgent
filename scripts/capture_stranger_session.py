#!/usr/bin/env python3
"""Capture simulated stranger-session pilot evidence (WDH-002 tooling)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.stranger_session import (  # noqa: E402
    run_pilot_battery,
    write_session_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output',
        default='docs/analysis/external-user-sessions-pilot-2026-06-10.json',
    )
    args = parser.parse_args(argv)
    records = run_pilot_battery()
    write_session_report(records, args.output)
    print(f'Captured {len(records)} pilot sessions: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
