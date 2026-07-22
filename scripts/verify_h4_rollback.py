#!/usr/bin/env python3
"""ADR-0031 exit criterion 5: run H4 rollback-to-shadow dry-run evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from teaagent.governance.h4_rollback import run_h4_rollback_dry_run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', default=None, help='Write the JSON report here instead of stdout'
    )
    args = parser.parse_args(argv)

    report = run_h4_rollback_dry_run()
    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + '\n', encoding='utf-8')
        print(f'H4 rollback dry-run: ok={report.ok} -> {output}')
    else:
        print(rendered)
    if not report.ok:
        print('H4 rollback dry-run failed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
