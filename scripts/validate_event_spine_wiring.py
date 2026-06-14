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

Three checks enforce this:

  A. Taxonomy closure — every RunEventType maps to an audit event type and back
     (no orphaned typed event that cannot reach the audit record).
  B. No orphaned event bus — any class exposing a high-signal lifecycle-event
     delivery method, OR the ``subscribe``+``emit`` pub/sub pair, must be in the
     curated allowlist below. A *new* competing lifecycle-event bus fails the
     gate, forcing a conscious architecture decision rather than silent drift.
  C. Evidence-extractor type coverage (review F2) — every audit ``event_type``
     the evidence extractors read (run_evidence.py, proof_of_use.py) must be in
     RunEventType, else the M6 FOLD-T002 cutover would silently drop it from
     production evidence.

     LIMITATION (heuristic, not a proof): checks B and C are AST/name-based. B
     keys on specific method names plus the subscribe+emit pair; a bus using
     entirely novel naming could still evade it. C resolves ``==``/``in`` against
     string literals and module-level frozenset/set constants; exotic dynamic
     event-type lookups are out of scope. Both catch the shapes that actually
     occur and force a conscious decision for them.

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
    'teaagent.integration.event_stream:RunEventStream': (
        'normalized stream pub/sub contract (unwired in production)'
    ),
}

# A class defining BOTH of these is a pub/sub event bus (the RunEventStream
# shape) even though the individual names (subscribe/emit) are too generic to be
# high-signal on their own. Detecting the *pair* closes the F3 evasion gap
# without flagging skill-writer/marketplace ``publish`` or token-streaming
# ``emit`` (none of which define both).
LIFECYCLE_BUS_PAIR: frozenset[str] = frozenset({'subscribe', 'emit'})


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
            signals = set(methods & LIFECYCLE_BUS_SIGNALS)
            if methods >= LIFECYCLE_BUS_PAIR:
                signals |= LIFECYCLE_BUS_PAIR
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


# Modules whose extractors read audit events by ``event_type`` and feed the
# evidence bundle. After the M6 FOLD-T002 cutover these reads are served by the
# typed reader, which drops unmapped types — so each type they compare against
# must be in RunEventType or it is silently lost from production evidence.
_EVIDENCE_EXTRACTOR_MODULES: tuple[str, ...] = (
    'teaagent/run_evidence.py',
    'teaagent/proof_of_use.py',
)


def _is_event_type_access(node: ast.expr) -> bool:
    """True if ``node`` reads the ``event_type`` key (``.get('event_type')`` or
    ``[...]['event_type']``)."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'get'
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == 'event_type'
    ):
        return True
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == 'event_type'
    )


def _string_elts(node: ast.expr) -> set[str]:
    """Return the string constants in a set/list/tuple literal."""
    out: set[str] = set()
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.add(elt.value)
    return out


def find_evidence_extractor_event_types(repo_root: Path) -> set[str]:
    """AST-discover the audit ``event_type`` literals the evidence extractors read.

    Handles the patterns actually used: ``event_type == 'x'`` / ``!= 'x'``,
    ``event_type in {'a', 'b'}`` (inline), and ``event_type in NAME`` where
    ``NAME`` is a module-level ``frozenset``/``set``/literal of strings (e.g.
    ``_HOOK_AUDIT_TYPES``). ``event_type`` may be a local bound from an
    event-type access or the access itself. Exotic/dynamic lookups are out of
    scope (documented limitation, like the orphan-bus tripwire).
    """
    found: set[str] = set()
    for rel in _EVIDENCE_EXTRACTOR_MODULES:
        found |= event_types_in_source((repo_root / rel).read_text(encoding='utf-8'))
    return found


def event_types_in_source(source: str) -> set[str]:
    """Discover event-type literals compared against in one module's source.

    Split out from :func:`find_evidence_extractor_event_types` so the AST logic
    is unit-testable on seeded source strings.
    """
    found: set[str] = set()
    tree = ast.parse(source)

    # Module-level NAME = {str literals} (incl. frozenset(...)/set(...)),
    # covering both plain and annotated assignments.
    named_sets: dict[str, set[str]] = {}
    et_vars: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value: ast.expr | None = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is None:
            continue
        # event_type-bound locals (event_type = e.get('event_type')).
        if _is_event_type_access(value):
            for tgt in targets:
                if isinstance(tgt, ast.Name):
                    et_vars.add(tgt.id)
        # named string sets (_HOOK_AUDIT_TYPES = frozenset({...})).
        if len(targets) == 1 and isinstance(targets[0], ast.Name):
            elts: set[str] = _string_elts(value)
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in ('frozenset', 'set')
                and value.args
            ):
                elts |= _string_elts(value.args[0])
            if elts:
                named_sets[targets[0].id] = elts

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if not (
            (isinstance(left, ast.Name) and left.id in et_vars)
            or _is_event_type_access(left)
        ):
            continue
        for op, comp in zip(node.ops, node.comparators, strict=True):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    found.add(comp.value)
            elif isinstance(op, (ast.In, ast.NotIn)):
                found |= _string_elts(comp)
                if isinstance(comp, ast.Name) and comp.id in named_sets:
                    found |= named_sets[comp.id]
    return found


def check_evidence_extractor_types_typed() -> list[str]:
    """Every audit type the evidence extractors read must be in RunEventType.

    Closes review F2: after the FOLD-T002 cutover, an extractor reading an
    untyped audit type would silently drop it from production evidence.
    """
    from teaagent.runner._events import _AUDIT_EVENT_TO_RUN_EVENT_TYPE

    discovered = find_evidence_extractor_event_types(_REPO_ROOT)
    errors: list[str] = []
    if not discovered:
        errors.append(
            'evidence-extractor event-type discovery found nothing — the AST '
            'scan likely broke; investigate before trusting this gate.'
        )
    for audit_type in sorted(discovered):
        if audit_type not in _AUDIT_EVENT_TO_RUN_EVENT_TYPE:
            errors.append(
                f'evidence extractor reads audit type {audit_type!r} which is '
                f'NOT in RunEventType — the M6 fold would silently drop it. Add '
                f'it to RunEventType + the audit mapper in teaagent/runner/_events.py.'
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
    errors.extend(check_evidence_extractor_types_typed())
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
