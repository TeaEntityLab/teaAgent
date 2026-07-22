#!/usr/bin/env python3
"""Build the ADR-0031 H4 owner-review decision packet.

Aggregates agent-completable evidence for criteria 1, 2, 3, and 5. Criterion 4
remains human sign-off. This command does not flip H4 modes or claim promotion
readiness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.h4_decision_packet import (  # noqa: E402
    build_h4_decision_packet,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='Workspace root (default: .)')
    parser.add_argument('--audit-log', action='append', default=[])
    parser.add_argument('--since', default=None)
    parser.add_argument('--until', default=None)
    parser.add_argument('--matrix', default=None)
    parser.add_argument('--policy-count', type=int, default=25)
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--threshold-ms', type=float, default=50.0)
    parser.add_argument('--output', default=None)
    args = parser.parse_args(argv)

    audit_logs = [Path(path) for path in args.audit_log] if args.audit_log else None
    try:
        packet = build_h4_decision_packet(
            args.root,
            audit_logs=audit_logs,
            since=args.since,
            until=args.until,
            matrix_path=args.matrix,
            policy_count=args.policy_count,
            iterations=args.iterations,
            threshold_ms=args.threshold_ms,
        )
    except (RuntimeError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    rendered = json.dumps(packet.to_dict(), indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + '\n', encoding='utf-8')
        print(
            f'H4 decision packet: {packet.agent_prepared_criteria} prepared criterion(s), '
            f'{packet.human_required_criteria} human-required -> {output}'
        )
    else:
        print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
