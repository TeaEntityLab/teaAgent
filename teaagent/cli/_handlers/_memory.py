from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.memory import MemoryCatalog
from teaagent.provenance_gate import (
    PersistenceSubstrate,
    evaluate_persistent_write,
    parse_source_kind,
)


def memory_add_command(args: argparse.Namespace) -> int:
    catalog = MemoryCatalog(args.root)
    source_kind = parse_source_kind(getattr(args, 'write_source', None))
    gate = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': args.content, 'tags': list(args.tag)},
        source_kind=source_kind,
        attested=bool(getattr(args, 'i_attest_untrusted_write', False)),
    )
    if gate.quarantine:
        entry = catalog.add_quarantined(
            args.content,
            tags=tuple(args.tag),
            provenance=gate.to_dict(),
        )
        print_json(
            {
                'status': 'quarantined',
                'memory': entry.to_dict(),
                'provenance': gate.to_dict(),
            }
        )
        return 0
    entry = catalog.add(args.content, tags=tuple(args.tag))
    print_json({'status': 'created', 'memory': entry.to_dict()})
    return 0


def memory_list_command(args: argparse.Namespace) -> int:
    print_json(
        [entry.to_dict() for entry in MemoryCatalog(args.root, readonly=True).list(limit=args.limit)]
    )
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json(
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root, readonly=True).search(args.query, limit=args.limit)
        ]
    )
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    try:
        print_json(MemoryCatalog(args.root, readonly=True).show(args.memory_id).to_dict())
        return 0
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
