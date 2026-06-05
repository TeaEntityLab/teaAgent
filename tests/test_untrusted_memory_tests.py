"""CPP-P1-004 — Untrusted-source memory tests.

Every web/tool/MCP output that reaches MEMORY substrate must go through the
quarantine gate before becoming project memory.  This file proves the gate
blocks untrusted sources and that the promote flow requires explicit attestation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.memory.catalog import MemoryCatalog
from teaagent.provenance_gate import (
    PersistenceSubstrate,
    ProvenanceSourceKind,
    evaluate_persistent_write,
)

# ── provenance gate unit tests ──────────────────────────────────────────────


def test_web_message_memory_quarantined() -> None:
    """WEB_MESSAGE + MEMORY → quarantine (no attestation)."""
    result = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': 'untrusted web content', 'tags': ['web']},
        source_kind=ProvenanceSourceKind.WEB_MESSAGE,
    )
    assert result.action == 'quarantine'
    assert not result.allowed
    assert result.quarantine
    assert 'untrusted source' in result.reason


def test_web_message_attested_allowed() -> None:
    """WEB_MESSAGE + MEMORY + attested=True → allow."""
    result = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': 'attested web content', 'tags': ['web']},
        source_kind=ProvenanceSourceKind.WEB_MESSAGE,
        attested=True,
    )
    assert result.action == 'allow'
    assert result.allowed
    assert not result.quarantine
    assert result.attested


def test_agent_run_memory_quarantined() -> None:
    """AGENT_RUN + MEMORY → quarantine (default policy)."""
    result = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': 'agent output', 'tags': ['auto']},
        source_kind=ProvenanceSourceKind.AGENT_RUN,
    )
    assert result.action == 'quarantine'
    assert not result.allowed
    assert result.quarantine
    assert 'agent_created_memory_default_quarantine' in result.reason


def test_local_memory_allowed() -> None:
    """LOCAL + MEMORY → allow (local CLI writes bypass quarantine)."""
    result = evaluate_persistent_write(
        substrate=PersistenceSubstrate.MEMORY,
        payload={'content': 'local memory', 'tags': ['local']},
        source_kind=ProvenanceSourceKind.LOCAL,
    )
    assert result.action == 'allow'
    assert result.allowed
    assert not result.quarantine


# ── quarantine → promote flow tests ────────────────────────────────────────


def test_promote_requires_attestation() -> None:
    """promote_quarantined requires explicit attestation keyword.

    Calling promote_quarantined() without the attestation keyword argument
    must raise TypeError, proving the API enforces the human-review gate.
    """
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(Path(tmp))

        entry = catalog.add_quarantined(
            'content needing review',
            tags=('test',),
            provenance={
                'source_kind': 'web_message',
                'reason': 'untrusted_source',
            },
        )

        # Verify the non-attested path: entry stays quarantined
        assert len(catalog.list(limit=10)) == 0
        quarantined = catalog.list_quarantined(limit=10)
        assert len(quarantined) == 1
        assert quarantined[0].memory_id == entry.memory_id

        # Calling without attestation= is a type error due to the
        # keyword-only parameter contract.
        try:
            catalog.promote_quarantined(entry.memory_id)  # type: ignore[call-arg]
            raise AssertionError('expected TypeError for missing attestation')
        except TypeError:
            pass

        # Entry must still be quarantined (no side-effect from failing call)
        assert len(catalog.list(limit=10)) == 0
        assert len(catalog.list_quarantined(limit=10)) == 1


def test_quarantine_promote_round_trip() -> None:
    """Full quarantine → promote round-trip with explicit attestation.

    Untrusted content:
      1. starts in quarantine,
      2. is absent from main memory,
      3. is promoted only after attestation,
      4. is verified in main memory,
      5. is removed from the quarantine file.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        catalog = MemoryCatalog(root)
        run_id = 'untrusted-round-trip'
        provenance = {
            'source_kind': 'web_message',
            'run_id': run_id,
            'reason': 'web_message_default_quarantine',
            'content_digest': 'sha256:f00bar',
        }

        # 1. Add quarantined entry
        entry = catalog.add_quarantined(
            'Web/tool output that must be reviewed',
            tags=('untrusted', 'web'),
            provenance=provenance,
            run_id=run_id,
        )

        # 2. Verify it is NOT in main memory
        assert len(catalog.list(limit=10)) == 0

        # 3. Verify it IS in quarantine
        quarantined = catalog.list_quarantined(limit=10)
        assert len(quarantined) == 1
        assert quarantined[0].memory_id == entry.memory_id
        assert quarantined[0].content == 'Web/tool output that must be reviewed'
        assert 'untrusted' in quarantined[0].tags

        # 4. Promote with explicit attestation
        promoted = catalog.promote_quarantined(
            entry.memory_id,
            attestation='human-reviewed-and-approved',
        )

        # 5. Verify promoted entry properties
        assert promoted.memory_id == entry.memory_id
        assert promoted.content == 'Web/tool output that must be reviewed'
        assert 'untrusted' in promoted.tags

        # 6. Verify it is NOW in main memory
        main_entries = catalog.list(limit=10)
        assert len(main_entries) == 1
        assert main_entries[0].memory_id == entry.memory_id
        assert main_entries[0].content == 'Web/tool output that must be reviewed'

        # 7. Verify it is REMOVED from quarantine
        assert len(catalog.list_quarantined(limit=10)) == 0
