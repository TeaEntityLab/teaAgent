from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.memory import MemoryCatalog


def memory_add_command(args: argparse.Namespace) -> int:
    entry = MemoryCatalog(args.root).add(args.content, tags=tuple(args.tag))
    print_json(entry.to_dict())
    return 0


def memory_list_command(args: argparse.Namespace) -> int:
    print_json(
        [entry.to_dict() for entry in MemoryCatalog(args.root).list(limit=args.limit)]
    )
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json(
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root).search(args.query, limit=args.limit)
        ]
    )
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    print_json(MemoryCatalog(args.root).show(args.memory_id).to_dict())
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
