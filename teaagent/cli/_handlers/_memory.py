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
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root, readonly=True).list(limit=args.limit)
        ]
    )
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json(
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root, readonly=True).search(
                args.query, limit=args.limit
            )
        ]
    )
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    try:
        print_json(
            MemoryCatalog(args.root, readonly=True).show(args.memory_id).to_dict()
        )
        return 0
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1


def memory_failures_list_command(args: argparse.Namespace) -> int:
    from teaagent.memory.failure_card import FailureCardStorage

    storage = FailureCardStorage(args.root)
    cards = storage.list_active() if args.active_only else storage.list_all()
    print_json([card.to_dict() for card in cards])
    return 0


def memory_failures_show_command(args: argparse.Namespace) -> int:
    from teaagent.memory.failure_card import FailureCardStorage

    storage = FailureCardStorage(args.root)
    card = storage.get_by_id(args.card_id)
    if card is None:
        print_json(
            {'status': 'error', 'message': f"failure card '{args.card_id}' not found"}
        )
        return 1
    payload = card.to_dict()
    payload['effective_behavior'] = card.effective_behavior()
    payload['active'] = card.is_active()
    print_json(payload)
    return 0


def memory_failures_invalidate_command(args: argparse.Namespace) -> int:
    from teaagent.memory.failure_card import FailureCardStorage

    storage = FailureCardStorage(args.root)
    if not storage.invalidate(args.card_id, reason=args.reason):
        print_json(
            {'status': 'error', 'message': f"failure card '{args.card_id}' not found"}
        )
        return 1
    print_json({'status': 'ok', 'card_id': args.card_id, 'invalidated': True})
    return 0


def memory_failures_prune_command(args: argparse.Namespace) -> int:
    from teaagent.memory.failure_card import FailureCardStorage

    storage = FailureCardStorage(args.root)
    removed = storage.prune_expired()
    print_json({'status': 'ok', 'removed': removed})
    return 0


def memory_failures_auto_invalidate_command(args: argparse.Namespace) -> int:
    from teaagent.memory.failure_card import (
        FailureCardStorage,
        MemoryAutoInvalidationConfig,
    )

    storage = FailureCardStorage(args.root)
    config = MemoryAutoInvalidationConfig.from_workspace_config(args.root)

    if not config.enabled:
        print_json(
            {
                'status': 'skipped',
                'message': 'Auto-invalidation is disabled in workspace configuration',
            }
        )
        return 0

    invalidation_counts = storage.apply_auto_invalidation(config)

    total_invalidated = sum(invalidation_counts.values())
    print_json(
        {
            'status': 'ok',
            'total_invalidated': total_invalidated,
            'by_trigger': invalidation_counts,
        }
    )
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
