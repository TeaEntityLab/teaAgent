from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.cost_tracker import CostTracker


def cost_report_command(args: argparse.Namespace) -> int:
    tracker = CostTracker(args.root)

    last = args.last or '30d'
    days = int(last.rstrip('d')) if last.endswith('d') else 30

    label_filter = args.label
    if args.pr is not None:
        label_filter = f'pr:{args.pr}'

    if label_filter is not None:
        data = tracker.report_by_label(label_filter)
    else:
        data = tracker.report_all(days=days)

    fmt = getattr(args, 'format', 'json')
    if fmt == 'csv':
        print(CostTracker.export_csv(data))
    else:
        print_json(data)
    return 0
