#!/usr/bin/env python3
"""Guard the ADR 0032 event-spine invariant: one typed lifecycle path, no orphans.

This validator backs the ADR-0032 M7 invariant. The migration did **not** end
with "everything emits through the spine and consumers serialize audit/webhook/
context" — on assessment that was a regression (webhook is an audit sink already
fed transitively by the spine's audit consumer) or vacuous (ContextBus and the
integration RunEventStream are unwired in production). The realized, sound
architecture is:

  EventSpine.emit  --(register_audit_consumer, M1)-->  AuditLogger.record
                                                              |
                                       add_sink fan-out: webhook, OTel, ...

  * EventSpine (teaagent.runner._events) is THE typed run-lifecycle path.
  * AuditLogger (teaagent.audit) is the complete event record AND the sink hub;
    since M1 it is a spine *consumer*. Governance events that stay inline
    (approval, budget, hooks) are written via audit.record directly — that IS
    the record, not redundant inline eventing.
  * Webhook / OTel are audit *sinks*, not direct spine consumers (a direct
    consumer would only see the spine-emitted subset — a coverage regression).

Two checks enforce this:

  A. Taxonomy closure — every RunEventType maps to an audit event type and back
     (no orphaned typed event that cannot reach the audit record).
  B. No orphaned event bus — any class exposing a high-signal lifecycle-event
     delivery method must be in the curated allowlist below. A *new* competing
     lifecycle-event bus fails the gate, forcing a conscious architecture
     decision rather than silent drift.

Run: python3 scripts/validate_event_spine_wiring.py
Exit code 0 when clean, 1 on any violation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEAAGENT_ROOT = _REPO_ROOT / 'teaagent'

# High-signal, event-specific method names. Deliberately excludes generic
# ``publish`` / ``emit`` (used by skill-writer, marketplace registry, and token
# streaming, none of which are lifecycle-event buses) to keep the scan precise
# and non-noisy.
LIFECYCLE_BUS_SIGNALS: frozenset[str] = frozenset(
    {
        'register_interceptor',
        'register_consumer',
        'add_sink',
        'publish_delta',
        'subscribe_deltas',
        'on_event',
    }
)

# The sanctioned event-delivery surfaces and their architectural role. A class
# caught by the scan that is NOT here is an orphaned/competing event bus.
EVENT_DELIVERY_ALLOWLIST: dict[str, str] = {
    'teaagent.runner._events:EventSpine': (
        'THE typed run-lifecycle spine (interceptors + consumers)'
    ),
    'teaagent.audit:AuditLogger': (
        'complete audit record + sink hub; spine consumer since M1'
    ),
    'teaagent.context_bus:ContextBus': (
        'context-delta store (unwired in production; not a lifecycle bus)'
    ),
    'teaagent.integration.event_stream:RunEventSubscriber': (
        'normalized stream subscriber protocol (unwired in production)'
    ),
}


def find_event_delivery_classes(root: Path) -> dict[str, set[str]]:
    """Scan ``root`` for classes defining any high-signal lifecycle-bus method.

    Returns a mapping of ``module:ClassName`` to the set of signal methods it
    defines. Module names are resolved relative to ``root.parent`` so the scan
    is portable (works on the real ``teaagent/`` tree and on test fixtures).
    Pure over the filesystem so callers/tests can diff against the allowlist.
    """
    base = root.parent
    found: dict[str, set[str]] = {}
    for py in sorted(root.rglob('*.py')):
        if '__pycache__' in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = '.'.join(py.relative_to(base).with_suffix('').parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            signals = methods & LIFECYCLE_BUS_SIGNALS
            if signals:
                found[f'{module}:{node.name}'] = signals
    return found


def check_orphan_buses(
    found: dict[str, set[str]], allowlist: dict[str, str]
) -> list[str]:
    """Return one error per event-delivery class missing from the allowlist."""
    errors: list[str] = []
    for qualname in sorted(found):
        if qualname not in allowlist:
            signals = ', '.join(sorted(found[qualname]))
            errors.append(
                f'orphaned event-delivery surface {qualname!r} (defines '
                f'{signals}); route lifecycle events through EventSpine + the '
                f'audit consumer, or add it to EVENT_DELIVERY_ALLOWLIST with a '
                f'documented role.'
            )
    return errors


def check_taxonomy_closure() -> list[str]:
    """Return errors if any RunEventType lacks a lossless audit mapping."""
    from teaagent.runner._events import (
        _AUDIT_EVENT_TO_RUN_EVENT_TYPE,
        _RUN_EVENT_TO_AUDIT_EVENT_TYPE,
        RunEventType,
        audit_event_to_run_event_type,
        run_event_to_audit_event_type,
    )

    errors: list[str] = []
    for event_type in RunEventType:
        try:
            audit_type = run_event_to_audit_event_type(event_type)
        except ValueError:
            errors.append(
                f'RunEventType.{event_type.name} has no audit mapping — it '
                f'cannot reach the audit record (orphaned typed event).'
            )
            continue
        if audit_event_to_run_event_type(audit_type) is not event_type:
            errors.append(
                f'RunEventType.{event_type.name} does not round-trip through '
                f'the audit mapping (maps to {audit_type!r}).'
            )
    if len(_RUN_EVENT_TO_AUDIT_EVENT_TYPE) != len(RunEventType):
        errors.append(
            'forward mapping size != RunEventType size — an event type is '
            'unmapped or duplicated.'
        )
    if len(_AUDIT_EVENT_TO_RUN_EVENT_TYPE) != len(RunEventType):
        errors.append(
            'inverse mapping size != RunEventType size — two event types share '
            'one audit string (lossy).'
        )
    return errors


def validate() -> list[str]:
    """Run all checks against the real repository; return all errors."""
    errors: list[str] = []
    errors.extend(check_taxonomy_closure())
    found = find_event_delivery_classes(_TEAAGENT_ROOT)
    errors.extend(check_orphan_buses(found, EVENT_DELIVERY_ALLOWLIST))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print('Event-spine wiring check FAILED:', file=sys.stderr)
        for err in errors:
            print(f'  - {err}', file=sys.stderr)
        return 1
    print('Event-spine wiring check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
