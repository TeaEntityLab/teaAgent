# test-type: contract
"""Executable specification for the ADR-0029 consensus-validation hold.

Companion to docs/specs/consensus-validation-disposition-spec-2026-07-11.md
(ADR-0029 expiry review 2026-12-10: wire behind approval queue OR
delete/quarantine).

Two guard tests make the hold executable (no production imports; wiring
validator watch-list entry). The remaining tests pin behavioral quirks the
disposition decision depends on — notably the SUPERMAJORITY
threshold-over-cast-votes semantics, which is a wire-blocker for any
destructive-action gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from teaagent.consensus.consensus_validation import (
    ConsensusRule,
    ConsensusRuleType,
    ConsensusStatus,
    ConsensusValidator,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_DOTTED = 'teaagent.consensus.consensus_validation'
_LEGACY_DOTTED = 'teaagent.consensus_validation'
# Files allowed to reference the module: itself, and the deprecation shim
# (which maps the legacy dotted path as a plain string, not an import).
_ALLOWED_FILES = {
    _REPO_ROOT / 'teaagent' / 'consensus' / 'consensus_validation.py',
    _REPO_ROOT / 'teaagent' / '_compat_modules.py',
}


def _production_importers() -> list[str]:
    """Return production files whose import statements name the module."""
    importers: list[str] = []
    for path in sorted((_REPO_ROOT / 'teaagent').rglob('*.py')):
        if path in _ALLOWED_FILES:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith(_MODULE_DOTTED) or name.startswith(_LEGACY_DOTTED):
                    importers.append(str(path.relative_to(_REPO_ROOT)))
    return importers


def test_consensus_validation_has_no_production_imports() -> None:
    """ADR-0029 clause 1: the module stays experimental and unwired.

    Scans every production module's import statements (AST, not text) for the
    current or legacy dotted path. A failure means someone wired
    consensus_validation into production: ADR-0029 requires that to be the
    deliberate 2026-12-10 expiry decision — execute the disposition spec's
    section 3.1 (including the SUPERMAJORITY quorum fix) and update the ADR
    in the same change.
    """
    assert _production_importers() == []


def test_wiring_validator_watchlist_names_module() -> None:
    """ADR-0029 clause 3: the wiring-validator watch-list tracks the module.

    WDA-006 acceptance is 'this ADR plus the wiring validator watch-list';
    silently dropping the watch-list entry would dissolve the acceptance
    without a decision.
    """
    validator_source = (_REPO_ROOT / 'scripts' / 'validate_wiring.py').read_text(
        encoding='utf-8'
    )
    assert _MODULE_DOTTED in validator_source


def test_n_of_m_rejects_only_when_approval_impossible() -> None:
    """N_OF_M flips to REJECTED exactly when N approvals become unreachable.

    Boundary pair for required_approvals=2 of total_voters=3: one rejection
    leaves approval possible (PENDING); two rejections make two approvals
    impossible (REJECTED). The disposition decision needs this exact
    semantics to evaluate queue-hold release timing under Option W.
    """
    rule = ConsensusRule(
        rule_id='nofm-boundary',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )
    assert rule.check_consensus({'a': True, 'b': False}) is ConsensusStatus.PENDING
    assert (
        rule.check_consensus({'a': True, 'b': False, 'c': False})
        is ConsensusStatus.REJECTED
    )


def test_supermajority_threshold_is_over_cast_votes_not_total() -> None:
    """SUPERMAJORITY approves at 2/3 of votes CAST, ignoring total_voters.

    Quirk pin (disposition spec section 3.1 wire-blocker 1): with
    total_voters=5, a single YES vote already satisfies 1 >= (2*1)/3, so the
    request approves with one vote cast. Safe while the module is unwired;
    unacceptable quorum semantics for a destructive-action gate. If this test
    fails, the semantics changed — update the disposition spec's wire-blocker
    list accordingly.
    """
    rule = ConsensusRule(
        rule_id='supermajority-quirk',
        rule_type=ConsensusRuleType.SUPERMAJORITY,
        required_approvals=4,
        total_voters=5,
    )
    assert rule.check_consensus({'solo': True}) is ConsensusStatus.APPROVED


def test_add_vote_overwrites_prior_vote_silently() -> None:
    """A voter's second vote replaces the first with no error or trace.

    Quirk pin (wire-blocker 2): dict-assignment revote is fine for advisory
    use but a destructive gate would need audited revotes. The pin documents
    the current contract so Option W scoping is honest about the gap.
    """
    rule = ConsensusRule(
        rule_id='revote',
        rule_type=ConsensusRuleType.UNANIMOUS,
        required_approvals=2,
        total_voters=2,
    )
    votes = {'a': False, 'b': True}
    assert rule.check_consensus(votes) is ConsensusStatus.REJECTED
    votes['a'] = True
    assert rule.check_consensus(votes) is ConsensusStatus.APPROVED


def test_cast_vote_lifecycle_guards(tmp_path: Path) -> None:
    """cast_vote refuses unknown and terminal requests; votes drive status.

    Baseline for the Option W event contract: unknown request raises
    ValueError; a request that reached a terminal status refuses further
    votes (ValueError); votes on a live request advance it to APPROVED.
    """
    validator = ConsensusValidator(tmp_path)
    rule = validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=1,
        total_voters=2,
        description='disposition baseline',
    )
    request = validator.request_consensus(
        rule.rule_id, 'delete_branch', {'branch': 'main'}, 'requester-1'
    )

    with pytest.raises(ValueError, match='Request not found'):
        validator.cast_vote('missing-request', 'a', True)

    updated = validator.cast_vote(request.request_id, 'a', True)
    assert updated.status is ConsensusStatus.APPROVED
    assert validator.get_consensus_status(request.request_id) is (
        ConsensusStatus.APPROVED
    )

    with pytest.raises(ValueError, match='not pending'):
        validator.cast_vote(request.request_id, 'b', False)
