#!/usr/bin/env python3
"""ADR-0031 exit criterion 1: prepare the H4 shadow-denial evidence packet.

Deterministic, offline extraction of ``h4_governance_shadow`` denials into an
owner-adjudication worklist plus per-surface weekly observation coverage. This
prepares the 30-day zero-false-positive window evidence for the 2026-09-12 H4
promotion decision. It classifies nothing: ``owner_verdict`` stays null for every
candidate (promotion spec section 3.1 — agents prepare the list, never the
verdicts). Running it changes no governance mode and wires nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.h4_evidence import (  # noqa: E402
    build_h4_evidence_report,
    discover_audit_logs,
    load_events_from_paths,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--root',
        default='.',
        help='Workspace root to scan for .teaagent audit logs (default: .)',
    )
    parser.add_argument(
        '--audit-log',
        action='append',
        default=[],
        help='Explicit audit JSONL path(s); repeatable. Overrides --root discovery.',
    )
    parser.add_argument(
        '--since',
        default=None,
        help='ISO date/datetime lower bound (inclusive) for the observation window.',
    )
    parser.add_argument(
        '--until',
        default=None,
        help='ISO date/datetime upper bound (inclusive) for the observation window.',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Write the JSON evidence report here instead of stdout.',
    )
    args = parser.parse_args(argv)

    if args.audit_log:
        paths = [Path(p) for p in args.audit_log]
    else:
        paths = discover_audit_logs(args.root)

    if not paths:
        print(
            'No audit logs found. Pass --audit-log PATH or run from a workspace '
            'with .teaagent/audit.jsonl.',
            file=sys.stderr,
        )
        return 1

    events = load_events_from_paths(paths)
    try:
        report = build_h4_evidence_report(events, since=args.since, until=args.until)
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + '\n', encoding='utf-8')
        print(
            f'H4 evidence packet: {report.observed_events} observed events, '
            f'{len(report.candidates)} denial candidate(s) -> {out}'
        )
    else:
        print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
