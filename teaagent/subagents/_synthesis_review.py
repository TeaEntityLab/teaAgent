"""SCL-P0-006 / CPP-P0-004 — Synthesis review artifact minimum schema.

Defines the review data model that sits above patch-centric subagent reviews:
- ``ReviewFindingState`` — seven-state lifecycle for individual findings
- ``ReviewFinding`` — evidence-backed review finding with state tracking
- ``ResidualRisk`` — accepted risk carried forward from review
- ``SynthesisReviewArtifact`` — aggregate review across files, commands, tests
- ``build_synthesis_review()`` — factory from subagent review + findings
- ``close_synthesis_review()`` — validates evidence paths before allowing close
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ReviewFindingState — SCL-P0-006 state machine
# ---------------------------------------------------------------------------

VALID_FINDING_STATES = frozenset(
    {
        'proposed',
        'verified',
        'rejected',
        'false_positive',
        'needs_human',
        'fixed',
        'superseded',
    }
)

VALID_FINDING_TRANSITIONS: dict[str, frozenset[str]] = {
    'proposed': frozenset({'verified', 'rejected', 'false_positive', 'needs_human'}),
    'verified': frozenset({'superseded', 'fixed'}),
    'rejected': frozenset({'proposed'}),
    'false_positive': frozenset({'proposed'}),
    'needs_human': frozenset({'verified', 'rejected', 'false_positive', 'fixed'}),
    'fixed': frozenset({'verified'}),
    'superseded': frozenset(),
}


class ReviewFindingState(str, Enum):
    """SCL-P0-006 minimum finding state vocabulary.

    Lifecycle: proposed → verified / rejected / false_positive / needs_human.
    Terminal: fixed, superseded.
    """

    PROPOSED = 'proposed'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    FALSE_POSITIVE = 'false_positive'
    NEEDS_HUMAN = 'needs_human'
    FIXED = 'fixed'
    SUPERSEDED = 'superseded'

    def __str__(self) -> str:
        return self.value

    def can_transition_to(self, target: ReviewFindingState) -> bool:
        """Check if transitioning from *self* to *target* is allowed."""
        return target.value in VALID_FINDING_TRANSITIONS.get(self.value, frozenset())


# ---------------------------------------------------------------------------
# ReviewFinding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewFinding:
    """Evidence-backed review finding with lifecycle state.

    Each finding must carry a ``evidence_path`` — a reference to the concrete
    artifact that supports the finding. This can be a file path, an audit
    event ID (``run_id:event_index``), or an artifact path under ``.teaagent/``.
    """

    finding_id: str
    state: ReviewFindingState
    severity: str  # critical | high | medium | low
    category: str  # functional | security | performance | style | completeness
    message: str
    evidence_path: str
    superseded_by: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        d: dict[str, Any] = {
            'finding_id': self.finding_id,
            'state': self.state.value,
            'severity': self.severity,
            'category': self.category,
            'message': self.message,
            'evidence_path': self.evidence_path,
        }
        if self.superseded_by is not None:
            d['superseded_by'] = self.superseded_by
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewFinding:
        """Deserialize from a plain dict."""
        state_raw = data.get('state', 'proposed')
        if state_raw not in VALID_FINDING_STATES:
            raise ValueError(f'Invalid finding state: {state_raw!r}')
        return cls(
            finding_id=data.get('finding_id', ''),
            state=ReviewFindingState(state_raw),
            severity=data.get('severity', 'low'),
            category=data.get('category', 'functional'),
            message=data.get('message', ''),
            evidence_path=data.get('evidence_path', ''),
            superseded_by=data.get('superseded_by'),
        )


# ---------------------------------------------------------------------------
# ResidualRisk
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResidualRisk:
    """Risk that remains after review — consciously accepted, not unresolved."""

    description: str
    severity: str  # critical | high | medium | low
    mitigation: str
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'description': self.description,
            'severity': self.severity,
            'mitigation': self.mitigation,
            'accepted': self.accepted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResidualRisk:
        return cls(
            description=data.get('description', ''),
            severity=data.get('severity', 'low'),
            mitigation=data.get('mitigation', ''),
            accepted=bool(data.get('accepted', False)),
        )


# ---------------------------------------------------------------------------
# SynthesisReviewArtifact
# ---------------------------------------------------------------------------

VALID_GATE_STATES = frozenset({'approve', 'reject', 'request_changes'})


@dataclass
class SynthesisReviewArtifact:
    """Aggregate synthesis review produced after subagent review + analysis.

    This artifact wraps one or more subagent reviews, collected findings,
    and a recommended gate decision. Unlike ``SubagentReviewArtifact``
    (patch-centric, no findings), this type carries the full review record.
    """

    review_id: str
    target_run_id: str
    target_goal_id: str
    reviewer_role: str  # subagent | oracle | human
    model_route_id: str = ''
    files_reviewed: list[str] = field(default_factory=list)
    commands_reviewed: list[str] = field(default_factory=list)
    tests_reviewed: list[str] = field(default_factory=list)
    findings: list[ReviewFinding] = field(default_factory=list)
    residual_risk: list[ResidualRisk] = field(default_factory=list)
    recommended_gate_state: str = 'request_changes'
    created_at: str = ''

    def __post_init__(self) -> None:
        if self.recommended_gate_state not in VALID_GATE_STATES:
            raise ValueError(
                f'Invalid gate state {self.recommended_gate_state!r}. '
                f'Must be one of: {", ".join(sorted(VALID_GATE_STATES))}'
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON persistence."""
        return {
            'review_id': self.review_id,
            'target_run_id': self.target_run_id,
            'target_goal_id': self.target_goal_id,
            'reviewer_role': self.reviewer_role,
            'model_route_id': self.model_route_id,
            'files_reviewed': list(self.files_reviewed),
            'commands_reviewed': list(self.commands_reviewed),
            'tests_reviewed': list(self.tests_reviewed),
            'findings': [f.to_dict() for f in self.findings],
            'residual_risk': [r.to_dict() for r in self.residual_risk],
            'recommended_gate_state': self.recommended_gate_state,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SynthesisReviewArtifact:
        """Deserialize from a plain dict."""
        findings = [ReviewFinding.from_dict(f) for f in (data.get('findings') or [])]
        risks = [ResidualRisk.from_dict(r) for r in (data.get('residual_risk') or [])]
        return cls(
            review_id=data.get('review_id', ''),
            target_run_id=data.get('target_run_id', ''),
            target_goal_id=data.get('target_goal_id', ''),
            reviewer_role=data.get('reviewer_role', 'subagent'),
            model_route_id=data.get('model_route_id', ''),
            files_reviewed=list(data.get('files_reviewed', []) or []),
            commands_reviewed=list(data.get('commands_reviewed', []) or []),
            tests_reviewed=list(data.get('tests_reviewed', []) or []),
            findings=findings,
            residual_risk=risks,
            recommended_gate_state=data.get(
                'recommended_gate_state', 'request_changes'
            ),
            created_at=data.get('created_at', ''),
        )


# ---------------------------------------------------------------------------
# Evidence path validation
# ---------------------------------------------------------------------------


def _validate_evidence_path(evidence_path: str, workspace_root: Path) -> bool:
    """Check that *evidence_path* can be resolved to an existing artifact.

    Accepts:
    - File paths (relative or absolute within workspace)
    - Audit event references (``run_id:event_index``)
    - Artifact paths (``.teaagent/...``)
    """
    if not evidence_path or not evidence_path.strip():
        return False

    ep = evidence_path.strip()

    # Audit event ID format: run_id:event_index (event_index is integer)
    if ':' in ep and not ep.startswith('/') and not ep.startswith('.'):
        parts = ep.rsplit(':', 1)
        if len(parts) == 2 and parts[1].isdigit():
            # Cannot fully resolve without a run store, but format is valid
            return True

    # Check as filesystem path
    resolved = workspace_root / ep
    if resolved.exists():
        return True

    # Absolute path
    abs_path = Path(ep)
    return bool(abs_path.is_absolute() and abs_path.exists())


# ---------------------------------------------------------------------------
# Factory: build_synthesis_review
# ---------------------------------------------------------------------------


def build_synthesis_review(
    *,
    subagent_review: Optional[dict[str, Any]] = None,
    target_run_id: str = '',
    target_goal_id: str = '',
    reviewer_role: str = 'subagent',
    model_route_id: str = '',
    supplemental_findings: Optional[list[ReviewFinding]] = None,
    files_reviewed: Optional[list[str]] = None,
    commands_reviewed: Optional[list[str]] = None,
    tests_reviewed: Optional[list[str]] = None,
    residual_risk: Optional[list[ResidualRisk]] = None,
    recommended_gate_state: str = 'request_changes',
) -> SynthesisReviewArtifact:
    """Build a ``SynthesisReviewArtifact`` from a subagent review + findings.

    Parameters
    ----------
    subagent_review:
        Existing ``SubagentReviewArtifact`` dict (optional). When provided,
        ``target_run_id``, ``files_reviewed``, and the review_id prefix are
        derived from it.
    target_run_id:
        The run being reviewed (defaults to ``subagent_review['child_run_id']``).
    target_goal_id:
        The goal the run belongs to.
    reviewer_role:
        Who is performing the synthesis review (subagent, oracle, human).
    model_route_id:
        Model routing decision that produced this review, if any.
    supplemental_findings:
        Additional findings beyond what the subagent review discovered.
    files_reviewed:
        Files covered by the review.
    commands_reviewed:
        Commands reviewed during synthesis.
    tests_reviewed:
        Tests reviewed during synthesis.
    residual_risk:
        Risks accepted or carried forward.
    recommended_gate_state:
        Gate recommendation (approve, reject, request_changes).
    """
    findings: list[ReviewFinding] = []
    if supplemental_findings:
        findings.extend(supplemental_findings)

    review_id = str(uuid4())
    run_id = target_run_id
    flist = list(files_reviewed or [])

    if subagent_review is not None:
        review_prefix = subagent_review.get('review_id', '')
        if review_prefix:
            review_id = f'{review_prefix}-synthesis'
        if not run_id:
            run_id = str(subagent_review.get('child_run_id', ''))
        if not flist:
            flist = list(subagent_review.get('changed_files', []))

    return SynthesisReviewArtifact(
        review_id=review_id,
        target_run_id=run_id,
        target_goal_id=target_goal_id,
        reviewer_role=reviewer_role,
        model_route_id=model_route_id,
        files_reviewed=flist,
        commands_reviewed=list(commands_reviewed or []),
        tests_reviewed=list(tests_reviewed or []),
        findings=findings,
        residual_risk=list(residual_risk or []),
        recommended_gate_state=recommended_gate_state,
    )


# ---------------------------------------------------------------------------
# close_synthesis_review — evidence gate
# ---------------------------------------------------------------------------


def close_synthesis_review(
    review: SynthesisReviewArtifact,
    *,
    workspace_root: Optional[Path] = None,
) -> list[str]:
    """Validate that all findings have valid evidence paths before closing.

    Returns a list of validation errors. An empty list means the review can
    be closed. A non-empty list means the review is blocked — the caller
    must fix or reject the findings with missing/invalid evidence paths.

    Evidence paths are validated against *workspace_root* when provided.
    Otherwise, only format validity is checked.
    """
    errors: list[str] = []
    root = workspace_root or Path('.').resolve()

    for finding in review.findings:
        if not finding.evidence_path:
            errors.append(f"Finding '{finding.finding_id}' has no evidence_path")
            continue

        if not _validate_evidence_path(finding.evidence_path, root):
            errors.append(
                f"Finding '{finding.finding_id}' evidence_path "
                f'{finding.evidence_path!r} cannot be resolved'
            )

    # Gate state must be explicit
    if review.recommended_gate_state not in VALID_GATE_STATES:
        errors.append(
            f'Invalid recommended_gate_state: {review.recommended_gate_state!r}'
        )

    # Every finding should have a valid state
    for finding in review.findings:
        if finding.state.value not in VALID_FINDING_STATES:
            errors.append(
                f"Finding '{finding.finding_id}' has invalid state: "
                f'{finding.state.value!r}'
            )

    if errors:
        logger.warning(
            'Synthesis review %s cannot be closed: %d error(s)',
            review.review_id,
            len(errors),
        )
    else:
        logger.info('Synthesis review %s passed evidence validation', review.review_id)

    return errors


# ---------------------------------------------------------------------------
# Audit event helpers
# ---------------------------------------------------------------------------


def record_review_finding_proposed(
    audit_logger: Any,
    run_id: str,
    finding: ReviewFinding,
) -> None:
    """Emit ``review_finding_proposed`` audit event."""
    audit_logger.record(
        'review_finding_proposed',
        run_id,
        finding_id=finding.finding_id,
        severity=finding.severity,
        category=finding.category,
        message=finding.message,
        evidence_path=finding.evidence_path,
    )


def record_review_finding_verified(
    audit_logger: Any,
    run_id: str,
    finding: ReviewFinding,
) -> None:
    """Emit ``review_finding_verified`` audit event."""
    audit_logger.record(
        'review_finding_verified',
        run_id,
        finding_id=finding.finding_id,
        state=finding.state.value,
        severity=finding.severity,
        category=finding.category,
        evidence_path=finding.evidence_path,
    )


def record_review_closed(
    audit_logger: Any,
    run_id: str,
    review: SynthesisReviewArtifact,
    *,
    error_count: int = 0,
) -> None:
    """Emit ``review_closed`` audit event with summary."""
    audit_logger.record(
        'review_closed',
        run_id,
        review_id=review.review_id,
        target_run_id=review.target_run_id,
        target_goal_id=review.target_goal_id,
        reviewer_role=review.reviewer_role,
        finding_count=len(review.findings),
        residual_risk_count=len(review.residual_risk),
        recommended_gate_state=review.recommended_gate_state,
        error_count=error_count,
    )


# ---------------------------------------------------------------------------
# CPP-P1-001 — Repeat suppression
# ---------------------------------------------------------------------------


def find_repeated_findings(
    existing_findings: list[ReviewFinding],
    new_findings: list[ReviewFinding],
) -> dict[str, str]:
    """Map new finding IDs to supersede action.

    A new finding is considered a *repeat* (and thus a superseder) when it
    shares the same ``(category, evidence_path)`` tuple with an existing
    finding.  Only the first existing match is recorded (first-wins).

    Returns:
        dict mapping each *new* finding_id to one of:

        * ``'superseded'`` — this new finding supersedes an existing one
        * ``'still_active'`` — this finding has no matching existing finding
    """
    # Build index: (category, evidence_path) → existing finding_id
    existing_index: dict[tuple[str, str], str] = {}
    for f in existing_findings:
        key = (f.category, f.evidence_path)
        if key not in existing_index:
            existing_index[key] = f.finding_id

    result: dict[str, str] = {}
    for f in new_findings:
        key = (f.category, f.evidence_path)
        if key in existing_index:
            result[f.finding_id] = 'superseded'
        else:
            result[f.finding_id] = 'still_active'

    return result


def _build_superseded_map(
    existing_findings: list[ReviewFinding],
    new_findings: list[ReviewFinding],
) -> dict[str, str]:
    """Return {existing_finding_id: new_finding_id} for superseding pairs."""
    existing_index: dict[tuple[str, str], str] = {}
    for f in existing_findings:
        key = (f.category, f.evidence_path)
        if key not in existing_index:
            existing_index[key] = f.finding_id

    superseded_map: dict[str, str] = {}
    for f in new_findings:
        key = (f.category, f.evidence_path)
        matched_existing_id = existing_index.get(key)
        if matched_existing_id is not None:
            superseded_map[matched_existing_id] = f.finding_id

    return superseded_map


def suppress_repeated(
    synthesis_review: SynthesisReviewArtifact,
    existing_reviews: list[SynthesisReviewArtifact],
) -> SynthesisReviewArtifact:
    """Detect and record repeat findings against prior reviews.

    This is a convenience wrapper around ``find_repeated_findings``.  It
    collects existing findings from *existing_reviews*, runs repeat
    detection, and returns *synthesis_review* unchanged.

    The caller should use ``find_repeated_findings`` (or the returned
    review's ``findings`` list) to decide which existing findings to
    mark as ``SUPERSEDED`` and which new findings carry a
    ``superseded_by`` link.
    """
    existing_findings: list[ReviewFinding] = []
    for review in existing_reviews:
        existing_findings.extend(review.findings)

    _ = find_repeated_findings(existing_findings, synthesis_review.findings)

    logger.debug(
        'suppress_repeated: %d new findings checked against %d existing',
        len(synthesis_review.findings),
        len(existing_findings),
    )
    return synthesis_review
