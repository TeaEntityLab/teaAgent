"""SURF-003: operator cockpit snapshot handler."""

from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.ergonomics.cli_output import wants_human_cli
from teaagent.integration.cockpit_parity import build_cockpit_snapshot


def cockpit_show_command(args: argparse.Namespace) -> int:
    payload = build_cockpit_snapshot(
        args.root,
        permission_mode=getattr(args, 'permission_mode', 'prompt'),
    )
    if wants_human_cli(args):
        pending = payload['pending_approvals'].get('queue_depth', 0)
        stale = payload['stale_workspace']
        print(
            'TeaAgent status\n'
            f'  pending approvals: {pending}\n'
            f'  git dirty: {stale.get("dirty_git")}\n'
            f'  branch: {stale.get("branch") or "(unknown)"}\n'
        )
        return 0
    print_json(payload)
    return 0
