"""SURF-011: surface capability explain handlers."""

from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.integration.surface_parity import (
    build_surface_explain,
    format_surface_explain_human,
)


def surfaces_explain_command(args: argparse.Namespace) -> int:
    payload = build_surface_explain()
    if getattr(args, 'human', False):
        print(format_surface_explain_human(payload), end='')
    else:
        print_json(payload)
    return 0
