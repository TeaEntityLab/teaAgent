"""External-user stranger session capture helpers (WDH-002)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.governance.conversation_ux import (
    ADVANCED_CONCEPTS,
    CORE_ONBOARDING_CONCEPTS,
    progressive_disclosure_sections,
    stranger_concept_count,
)


@dataclass(frozen=True)
class StrangerSessionRecord:
    participant_id: str
    participant_type: str
    concepts_before_first_success: list[str]
    happy_path_concept_count: int
    advanced_disclosed: bool
    completed_happy_path: bool
    notes: str = ''
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            'participant_id': self.participant_id,
            'participant_type': self.participant_type,
            'concepts_before_first_success': self.concepts_before_first_success,
            'happy_path_concept_count': self.happy_path_concept_count,
            'advanced_disclosed': self.advanced_disclosed,
            'completed_happy_path': self.completed_happy_path,
            'notes': self.notes,
            'captured_at': self.captured_at,
        }


def concepts_in_copy(text: str) -> list[str]:
    """Return canonical concepts mentioned in user-facing copy."""
    lowered = text.lower()
    found: list[str] = []
    for concept in (*CORE_ONBOARDING_CONCEPTS, *ADVANCED_CONCEPTS):
        if concept in lowered and concept not in found:
            found.append(concept)
    return found


def run_simulated_happy_path_session(
    *,
    participant_id: str,
    include_advanced: bool = False,
) -> StrangerSessionRecord:
    """Pilot session using progressive-disclosure copy (maintainer simulation)."""
    sections = progressive_disclosure_sections(include_advanced=include_advanced)
    concepts = concepts_in_copy('\n'.join(sections))
    happy_path = [c for c in concepts if c in CORE_ONBOARDING_CONCEPTS]
    return StrangerSessionRecord(
        participant_id=participant_id,
        participant_type='simulated_pilot',
        concepts_before_first_success=concepts,
        happy_path_concept_count=len(happy_path),
        advanced_disclosed=include_advanced,
        completed_happy_path=len(happy_path) <= 3,
        notes='Automated pilot using onboarding copy; not a non-maintainer session.',
    )


def run_pilot_battery() -> list[StrangerSessionRecord]:
    """Three simulated pilot sessions for WDH-002 tooling evidence."""
    return [
        run_simulated_happy_path_session(participant_id='pilot-01'),
        run_simulated_happy_path_session(participant_id='pilot-02'),
        run_simulated_happy_path_session(
            participant_id='pilot-03-advanced',
            include_advanced=True,
        ),
    ]


def write_session_report(
    records: list[StrangerSessionRecord],
    path: str,
) -> None:
    payload = {
        'session_type': 'simulated_pilot',
        'target_happy_path_concepts': list(CORE_ONBOARDING_CONCEPTS),
        'baseline_concept_count': stranger_concept_count(include_advanced=False),
        'records': [record.to_dict() for record in records],
    }
    out = Path(path) if isinstance(path, str) else path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
