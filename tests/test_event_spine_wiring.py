"""Tests for the ADR 0032 M7 event-spine wiring guard.

Covers the realized-architecture invariant: one typed lifecycle path
(EventSpine -> audit consumer -> AuditLogger) with no orphaned/competing event
bus, and every RunEventType losslessly mapped to the audit record.
"""

from pathlib import Path

import pytest

from scripts.validate_event_spine_wiring import (
    EVENT_DELIVERY_ALLOWLIST,
    check_orphan_buses,
    check_taxonomy_closure,
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
