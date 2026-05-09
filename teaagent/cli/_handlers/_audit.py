from __future__ import annotations

import argparse
import json
import time
from typing import Any

from teaagent.run_store import RunStore


def audit_list_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def audit_show_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def audit_prune_command(args: argparse.Namespace) -> int:
    if args.days is None and args.keep is None and not args.all:
        print_json(
            {
                'status': 'error',
                'message': 'audit prune requires --days, --keep, or --all',
            }
        )
        return 1
    store = RunStore(args.root)
    cutoff = time.time() - (args.days * 86400) if args.days is not None else None
    run_paths = sorted(
        store.store_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True
    )
    keep = set(run_paths[: args.keep]) if args.keep is not None else set()
    deleted: list[str] = []
    for path in run_paths:
        if path in keep:
            continue
        if cutoff is not None and path.stat().st_mtime >= cutoff:
            continue
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + '.lock').unlink(missing_ok=True)
        deleted.append(path.name)
    print_json({'count': len(deleted), 'deleted': deleted})
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
