"""Tests for the ADR 0032 M7 event-spine wiring guard.

Covers the realized-architecture invariant: one typed lifecycle path
(EventSpine -> audit consumer -> AuditLogger) with no orphaned/competing event
bus, and every RunEventType losslessly mapped to the audit record.
"""

from pathlib import Path

import pytest

from scripts.validate_event_spine_wiring import (
    EVENT_DELIVERY_ALLOWLIST,
    check_evidence_extractor_types_typed,
    check_orphan_buses,
    check_taxonomy_closure,
    event_types_in_source,
    find_event_delivery_classes,
    validate,
)


def test_repo_is_clean() -> None:
    """The real repository satisfies the event-spine invariant."""
    assert validate() == []


def test_every_detected_surface_is_allowlisted() -> None:
    """No event-delivery surface exists outside the curated allowlist."""
    from scripts.validate_event_spine_wiring import _TEAAGENT_ROOT

    found = find_event_delivery_classes(_TEAAGENT_ROOT)
    # The scan must actually detect the known surfaces (guards a vacuous pass).
    assert 'teaagent.runner._events:EventSpine' in found
    assert 'teaagent.audit:AuditLogger' in found
    assert set(found) <= set(EVENT_DELIVERY_ALLOWLIST)


def test_orphan_bus_is_flagged() -> None:
    """A new event-delivery surface absent from the allowlist is an error."""
    found = {'teaagent.rogue:RogueBus': {'register_consumer', 'on_event'}}
    errors = check_orphan_buses(found, EVENT_DELIVERY_ALLOWLIST)
    assert len(errors) == 1
    assert 'RogueBus' in errors[0]
    assert 'EventSpine' in errors[0]  # remediation hint names the spine


def test_allowlisted_bus_is_not_flagged() -> None:
    """A surface present in the allowlist passes."""
    found = {'teaagent.audit:AuditLogger': {'add_sink'}}
    assert check_orphan_buses(found, EVENT_DELIVERY_ALLOWLIST) == []


def test_find_event_delivery_classes_detects_seeded_signal(tmp_path: Path) -> None:
    """A class defining a high-signal method is detected; a plain class is not."""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    (pkg / 'mod.py').write_text(
        'class Bus:\n'
        '    def register_interceptor(self, fn):\n'
        '        ...\n'
        'class Plain:\n'
        '    def publish(self, x):\n'  # generic publish is intentionally ignored
        '        ...\n',
        encoding='utf-8',
    )
    found = find_event_delivery_classes(tmp_path)
    names = {q.split(':', 1)[1] for q in found}
    assert 'Bus' in names
    assert 'Plain' not in names


def test_taxonomy_closure_clean() -> None:
    """All RunEventType members map losslessly to the audit record."""
    assert check_taxonomy_closure() == []


def test_taxonomy_closure_catches_unmapped_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing an audit mapping makes the typed event orphaned -> error."""
    from teaagent.runner import _events

    some_type = next(iter(_events.RunEventType))
    patched = dict(_events._RUN_EVENT_TO_AUDIT_EVENT_TYPE)
    del patched[some_type]
    monkeypatch.setattr(_events, '_RUN_EVENT_TO_AUDIT_EVENT_TYPE', patched)

    errors = check_taxonomy_closure()
    assert any(some_type.name in e for e in errors)


# --- F3: subscribe+emit pub/sub bus shape is detected -----------------------


def test_subscribe_emit_pair_is_detected_and_allowlisted() -> None:
    """The RunEventStream shape (subscribe+emit) is now caught by the scan and
    is present in the allowlist (review F3)."""
    from scripts.validate_event_spine_wiring import _TEAAGENT_ROOT

    found = find_event_delivery_classes(_TEAAGENT_ROOT)
    qual = 'teaagent.integration.event_stream:RunEventStream'
    assert qual in found
    assert {'subscribe', 'emit'} <= found[qual]
    assert qual in EVENT_DELIVERY_ALLOWLIST


def test_subscribe_emit_seeded_bus_is_flagged(tmp_path) -> None:
    """A new subscribe+emit class outside the allowlist is an orphan."""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    (pkg / 'mod.py').write_text(
        'class Stream:\n'
        '    def subscribe(self, s):\n        ...\n'
        '    def emit(self, e):\n        ...\n',
        encoding='utf-8',
    )
    found = find_event_delivery_classes(tmp_path)
    assert any(q.endswith(':Stream') for q in found)
    assert check_orphan_buses(found, EVENT_DELIVERY_ALLOWLIST)


# --- F2: evidence-extractor event-type coverage -----------------------------


def test_evidence_extractor_types_all_typed() -> None:
    """Every event_type the evidence extractors read is in RunEventType."""
    assert check_evidence_extractor_types_typed() == []


def test_event_types_in_source_handles_real_patterns() -> None:
    """The discovery handles ==, inline `in {...}`, and `in NAMED_FROZENSET`
    (including annotated module-level constants like _HOOK_AUDIT_TYPES)."""
    src = (
        "FOO: frozenset[str] = frozenset({'aud_named'})\n"
        'def extract(events):\n'
        '    for e in events:\n'
        "        et = e.get('event_type')\n"
        "        if et == 'aud_eq':\n"
        '            pass\n'
        "        if et in {'aud_in_a', 'aud_in_b'}:\n"
        '            pass\n'
        '        if et not in FOO:\n'
        '            continue\n'
        "        if e.get('event_type') != 'aud_direct':\n"
        '            pass\n'
    )
    found = event_types_in_source(src)
    assert found == {'aud_eq', 'aud_in_a', 'aud_in_b', 'aud_named', 'aud_direct'}


def test_evidence_discovery_finds_hook_types() -> None:
    """Non-vacuous: the discovery actually picks up the hook-activity reads
    (which use an annotated module-level frozenset)."""
    from scripts.validate_event_spine_wiring import (
        _REPO_ROOT,
        find_evidence_extractor_event_types,
    )

    found = find_evidence_extractor_event_types(_REPO_ROOT)
    assert 'tool_hook_vetoed' in found
    assert 'tool_use' in found
