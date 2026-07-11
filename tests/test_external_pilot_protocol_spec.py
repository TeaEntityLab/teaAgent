# test-type: contract
"""Executable specification for the WDH-002 external-pilot boundary.

Companion to docs/specs/wdh-002-external-pilot-protocol-2026-07-11.md.
The current helper is simulation-only and contributes zero real participants.
These tests pin that truth label and its record format; the designed skip
activates when a separate privacy-capable ExternalPilotRecord is implemented.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

import teaagent.governance.stranger_session as stranger_session_module
from teaagent.governance.conversation_ux import CORE_ONBOARDING_CONCEPTS
from teaagent.governance.stranger_session import (
    StrangerSessionRecord,
    concepts_in_copy,
    run_simulated_happy_path_session,
    write_session_report,
)

_SIMULATED_RECORD_FIELDS = {
    'participant_id',
    'participant_type',
    'concepts_before_first_success',
    'happy_path_concept_count',
    'advanced_disclosed',
    'completed_happy_path',
    'notes',
    'captured_at',
}

_REAL_RECORD_FIELDS = {
    'schema_version',
    'participant_id',
    'participant_type',
    'consent_obtained',
    'captured_at',
    'task_completed',
    'time_to_first_success_seconds',
    'doc_lookup_count',
    'concepts_before_first_success',
    'friction_observations',
    'participant_quotes',
    'facilitator_interventions',
    'evidence_status',
    'exclusion_reason',
}


def test_simulated_record_schema_is_pinned() -> None:
    """StrangerSessionRecord keeps the exact eight-field simulation schema.

    The helper lacks consent, timing, lookup, intervention, and evidence-status
    fields by design; silently adding those would tempt callers to reuse it for
    human research. The protocol requires a separate ExternalPilotRecord.
    """
    assert {field.name for field in fields(StrangerSessionRecord)} == (
        _SIMULATED_RECORD_FIELDS
    )
    record = StrangerSessionRecord(
        participant_id='pilot-spec',
        participant_type='simulated_pilot',
        concepts_before_first_success=['ask'],
        happy_path_concept_count=1,
        advanced_disclosed=False,
        completed_happy_path=True,
    )
    assert set(record.to_dict()) == _SIMULATED_RECORD_FIELDS


def test_simulated_session_is_labeled_non_evidence() -> None:
    """The deterministic pilot advertises simulation in type and notes.

    WDH-002 needs real non-maintainer humans. This test prevents a later docs
    pass from treating a convenient harness result as external evidence.
    """
    record = run_simulated_happy_path_session(participant_id='pilot-contract')
    assert record.participant_type == 'simulated_pilot'
    assert 'not a non-maintainer session' in record.notes
    assert record.completed_happy_path is True
    assert record.advanced_disclosed is False
    assert record.happy_path_concept_count == len(CORE_ONBOARDING_CONCEPTS)
    assert set(record.concepts_before_first_success) == set(CORE_ONBOARDING_CONCEPTS)


def test_simulated_report_roundtrip_preserves_truth_label(tmp_path: Path) -> None:
    """write_session_report emits valid JSON explicitly typed simulated_pilot.

    The hardcoded report label is a safety property, not missing flexibility:
    future real-human capture must use the distinct schema in protocol §3.4.
    """
    records = [
        run_simulated_happy_path_session(participant_id='pilot-a'),
        run_simulated_happy_path_session(
            participant_id='pilot-b', include_advanced=True
        ),
    ]
    report_path = tmp_path / 'simulated-report.json'
    write_session_report(records, str(report_path))

    payload = json.loads(report_path.read_text(encoding='utf-8'))
    assert set(payload) == {
        'session_type',
        'target_happy_path_concepts',
        'baseline_concept_count',
        'records',
    }
    assert payload['session_type'] == 'simulated_pilot'
    assert payload['target_happy_path_concepts'] == list(CORE_ONBOARDING_CONCEPTS)
    assert len(payload['records']) == 2
    assert all(
        set(record_payload) == _SIMULATED_RECORD_FIELDS
        for record_payload in payload['records']
    )
    assert all(
        record_payload['participant_type'] == 'simulated_pilot'
        for record_payload in payload['records']
    )


def test_concept_detection_contract_and_substring_limit() -> None:
    """Core labels are found case-insensitively; matching is substring-based.

    The known `undoable` -> `undo` result is intentional characterization, not
    endorsement. It proves why arbitrary participant transcripts must not be
    auto-scored with concepts_in_copy; the protocol limits it to UI-copy linting.
    """
    text = 'ASK for a change, Approve it, then Undo it.'
    assert concepts_in_copy(text) == list(CORE_ONBOARDING_CONCEPTS)
    assert concepts_in_copy('plain neutral copy') == []
    assert concepts_in_copy('This operation is undoable.') == ['undo']


_HAS_REAL_RECORD = hasattr(stranger_session_module, 'ExternalPilotRecord')


@pytest.mark.skipif(
    not _HAS_REAL_RECORD,
    reason=(
        'privacy-capable real-human record is not implemented; see '
        'docs/specs/wdh-002-external-pilot-protocol-2026-07-11.md §3.4'
    ),
)
def test_real_external_record_schema_activates() -> None:
    """Activation hook for the distinct, versioned real-human record schema.

    Once implemented, exact fields enforce consent, privacy, timing, intervention,
    and owner-adjudication requirements. Reusing StrangerSessionRecord must not
    satisfy this test.
    """
    record_type = vars(stranger_session_module)['ExternalPilotRecord']
    assert {field.name for field in fields(record_type)} == _REAL_RECORD_FIELDS
