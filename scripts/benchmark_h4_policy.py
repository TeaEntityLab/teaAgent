#!/usr/bin/env python3
"""ADR-0031 exit criterion 3: benchmark H4 policy evaluation performance.

Runs the deterministic scratch-store benchmark for
``PolicyEngine.evaluate_with_explanation`` and emits a JSON evidence report. This
prepares performance evidence only; it does not change H4 modes or certify
promotion readiness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.h4_performance import (  # noqa: E402
    DEFAULT_ITERATIONS,
    DEFAULT_POLICY_COUNT,
    DEFAULT_THRESHOLD_MS,
    measure_policy_evaluation_performance,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy-count', type=int, default=DEFAULT_POLICY_COUNT)
    parser.add_argument('--iterations', type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument('--threshold-ms', type=float, default=DEFAULT_THRESHOLD_MS)
    parser.add_argument(
        '--output', default=None, help='Write the JSON report here instead of stdout'
    )
    args = parser.parse_args(argv)

    try:
        report = measure_policy_evaluation_performance(
            policy_count=args.policy_count,
            iterations=args.iterations,
            threshold_ms=args.threshold_ms,
        )
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + '\n', encoding='utf-8')
        print(
            f'H4 policy performance: median={report.median_ms:.3f}ms, '
            f'threshold={report.threshold_ms:.3f}ms -> {output}'
        )
    else:
        print(rendered)

    if not report.ok:
        print(
            f'H4 policy performance exceeds threshold: median={report.median_ms:.3f}ms '
            f'>= {report.threshold_ms:.3f}ms',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
