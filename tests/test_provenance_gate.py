from __future__ import annotations

from teaagent.provenance_gate import (
    PersistenceSubstrate,
    ProvenanceSourceKind,
    canonical_content_digest,
    evaluate_persistent_write,
    parse_source_kind,
)


def test_local_source_allows_automation_write() -> None:
    gate = evaluate_persistent_write(
        substrate=PersistenceSubstrate.AUTOMATION,
        payload={'name': 'watch', 'task': 'check repo', 'schedule': 'every 30m'},
        source_kind=ProvenanceSourceKind.LOCAL,
    )
    assert gate.allowed
    assert not gate.quarantine


def test_web_message_quarantines_without_attestation() -> None:
    gate = evaluate_persistent_write(
        substrate=PersistenceSubstrate.AUTOMATION,
        payload={'name': 'slack', 'task': 'summarize thread', 'schedule': 'every 1h'},
        source_kind=ProvenanceSourceKind.WEB_MESSAGE,
    )
    assert gate.quarantine
    assert gate.content_digest.startswith('sha256:')


def test_web_message_allows_with_attestation() -> None:
    gate = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': 'note from discord', 'tags': []},
        source_kind=ProvenanceSourceKind.WEB_MESSAGE,
        attested=True,
    )
    assert gate.allowed
    assert gate.attested


def test_canonical_digest_is_stable() -> None:
    payload = {'task': 'x', 'name': 'n'}
    first = canonical_content_digest(
        substrate=PersistenceSubstrate.AUTOMATION, payload=payload
    )
    second = canonical_content_digest(
        substrate=PersistenceSubstrate.AUTOMATION, payload=payload
    )
    assert first == second


def test_parse_source_kind_accepts_aliases() -> None:
    assert parse_source_kind('web-message') == ProvenanceSourceKind.WEB_MESSAGE
