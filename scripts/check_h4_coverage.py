#!/usr/bin/env python3
"""ADR-0031 exit criterion 2: check H4 policy/RBAC coverage declarations.

Inventories enabled policies and RBAC roles from the workspace, then compares
that inventory to the H4 policy/RBAC section of the claim-to-test traceability
matrix. The check prepares evidence only: it verifies declarations and referenced
test files, but does not run those tests, decide test sufficiency, or flip H4
modes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.h4_coverage import build_h4_coverage_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='Workspace root (default: .)')
    parser.add_argument(
        '--matrix',
        default=None,
        help='Traceability YAML path (default: <root>/docs/architecture/claim-to-test-traceability.yaml)',
    )
    parser.add_argument(
        '--output', default=None, help='Write the JSON report here instead of stdout'
    )
    args = parser.parse_args(argv)

    try:
        report = build_h4_coverage_report(args.root, matrix_path=args.matrix)
    except (RuntimeError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + '\n', encoding='utf-8')
        print(
            f'H4 coverage report: {len(report.policies)} policies, {len(report.roles)} roles, '
            f'{len(report.gaps)} gap(s) -> {output}'
        )
    else:
        print(rendered)

    if report.gaps:
        print(f'H4 coverage check found {len(report.gaps)} gap(s).', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
