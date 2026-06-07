from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Callable],
) -> None:
    cost = subparsers.add_parser(
        'cost',
        help='Cost attribution and reporting from audit logs.',
        description='Report cost by label, day, or model from run audit logs.',
    )
    subs = cost.add_subparsers(dest='cost_command', required=True)

    report = subs.add_parser('report', help='Generate cost report.')
    report.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    report.add_argument(
        '--last',
        default='30d',
        help='Time window (e.g. 7d, 30d, 90d). Defaults to 30d.',
    )
    report.add_argument(
        '--label',
        default=None,
        help='Filter by label (e.g. "feature:rate-limiting").',
    )
    report.add_argument(
        '--pr',
        type=int,
        default=None,
        help='Filter by PR number (matches labels like "pr:42").',
    )
    report.add_argument(
        '--format',
        choices=['json', 'csv'],
        default='json',
        help='Output format. Defaults to json.',
    )
    report.set_defaults(func=handlers['cost_report'])
