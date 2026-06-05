from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.release_evidence import (
    build_release_evidence_bundle,
    write_release_evidence_bundle,
)


def release_evidence_command(args: argparse.Namespace) -> int:
    bundle = build_release_evidence_bundle(
        profile=getattr(args, 'profile', 'release'),
        root=getattr(args, 'root', None),
    )
    write_release_evidence_bundle(bundle, args.output)
    print_json(
        {
            'ok': bundle.ok,
            'output_path': str(args.output),
            'seven_loop_evidence': bundle.seven_loop_evidence,
        }
    )
    return 0 if bundle.ok else 1
