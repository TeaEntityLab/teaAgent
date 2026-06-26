"""Contract tests for harness-first signal and documentation policy."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.test_type('contract')

_ROOT = Path(__file__).resolve().parents[1]


def _read_doc(path: str) -> str:
    return (_ROOT / path).read_text(encoding='utf-8')


def test_signal_to_acceptance_gap_documents_harness_first_gate() -> None:
    text = _read_doc('docs/processes/signal-to-acceptance-gap.md')

    assert '## Harness-First Routing Gate' in text
    assert '**Adopt**' in text
    assert '**Hypothesis**' in text
    assert '**Defer**' in text
    assert '**ADR Required**' in text
    assert 'authority, audit, rollback, cost, and evidence semantics' in text
    assert (
        'Feature-parity signals must not bypass the harness-first routing gate.' in text
    )


def test_evidence_policy_limits_competitor_survey_documents() -> None:
    text = _read_doc('docs/governance/evidence-to-principle-policy.md')

    assert 'Treat competitor surveys as intake, not default new docs' in text
    assert 'Competitor surveys and community feedback are evidence intake.' in text
    assert 'quarterly refresh or publication-triggered re-verification' in text
    assert 'release-blocking eval gate or official ecosystem change' in text
    assert 'a competitor signal is only an unvalidated UX hypothesis' in text


def test_operator_friction_log_preserves_owner_evidence_boundary() -> None:
    text = _read_doc('docs/work-log/operator-friction-log.md')
    collapsed = ' '.join(text.split())

    assert 'Owner-written entries are evidence.' in text
    assert 'competitor or community entries are hypotheses' in collapsed
    assert '[hypothesis: source, date]' in text
    assert (
        'Agents may add only competitor-derived or community-derived hypothesis entries.'
        in text
    )
    assert "must not answer them on the owner's behalf" in collapsed
    assert 'Signal-to-Acceptance-Gap Process' in text
