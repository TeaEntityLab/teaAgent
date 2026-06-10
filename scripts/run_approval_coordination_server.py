#!/usr/bin/env python3
"""Run the HTTP approval coordination server for remote backends."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# ruff: noqa: E402
from teaagent.coordination.approval_backend import FileBackedApprovalBackend
from teaagent.coordination.approval_http_server import ApprovalCoordinationHttpServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--auth-token', default=None)
    args = parser.parse_args(argv)

    backend = FileBackedApprovalBackend(args.workspace.resolve())
    server = ApprovalCoordinationHttpServer(
        backend,
        host=args.host,
        port=args.port,
        auth_token=args.auth_token,
    )
    server.start()
    print(f'Approval coordination server listening on {server.base_url}')

    def _shutdown(_signum: int, _frame: object) -> None:
        server.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    try:
        signal.pause()
    except AttributeError:
        import time

        while True:
            time.sleep(3600)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
