"""Spec grounding — repository grounding check for spec-to-plan transitions.

When a spec document is promoted to a plan, this module records which
files were searched and which assumptions were confirmed, so a reviewer
can verify the plan is grounded in the workspace.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.audit import AuditLogger, secure_audit_dir, secure_audit_file, utc_now
from teaagent.goal_record import GoalStore
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)

# ── file reference extraction ────────────────────────────────────────────

_BACKTICK_PATH = re.compile(
    r'`([^`\s]+\.(?:py|ts|tsx|js|jsx|rs|go|java|rb|md|json|yaml|yml|toml|cfg|ini|sh|sql))`'
)
_BRACKET_PATH = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
_PLAIN_PATH = re.compile(r'(?<!\w)(?:\.\/|(?:\w+\/)+)[\w./-]+\.\w+(?!\w)')

_MARKER_COMMENT = re.compile(r'#\s|//\s|--\s|<!--|--!?>|\*/|"""', re.MULTILINE)


def _is_likely_path(raw: str) -> bool:
    """Return True if *raw* looks like a file path rather than a URL or random token."""
    if raw.startswith(('http://', 'https://', 'ftp://')):
        return False
    if raw.startswith(('#', '@', '!')):
        return False
    # Must contain at least one dot and a plausible extension
    if '.' not in raw:
        return False
    suffix = Path(raw).suffix.lower()
    if not suffix or len(suffix) > 10:
        return False
    # Reject pure numbers, version strings, and email addresses
    if re.match(r'^[\d.]+$', raw):
        return False
    return '@' not in raw


def extract_file_refs(text: str) -> list[str]:
    """Extract likely file-path references from unstructured text.

    Looks for backtick-quoted paths, markdown links, and plain path-like
    tokens.  Returns de-duplicated, sorted list.
    """
    refs: set[str] = set()

    # Backtick-quoted file paths (highest precision)
    for match in _BACKTICK_PATH.finditer(text):
        raw = match.group(1).strip()
        if _is_likely_path(raw):
            refs.add(raw)

    # Markdown links [label](path)
    for match in _BRACKET_PATH.finditer(text):
        raw = match.group(2).strip()
        if _is_likely_path(raw):
            refs.add(raw)

    # Plain path-like tokens
    for match in _PLAIN_PATH.finditer(text):
        raw = match.group(0).strip()
        if _is_likely_path(raw):
            refs.add(raw)

    return sorted(refs)


# ── grounding check ──────────────────────────────────────────────────────


@dataclass
class GroundingCheck:
    """Result of a repository grounding check for a spec document."""

    spec_id: str
    files_searched: list[str]
    assumptions_confirmed: list[str]
    grounding_valid: bool
    missing_files: list[str] = field(default_factory=list)
    failed_assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'spec_id': self.spec_id,
            'files_searched': list(self.files_searched),
            'assumptions_confirmed': list(self.assumptions_confirmed),
            'grounding_valid': self.grounding_valid,
            'missing_files': list(self.missing_files),
            'failed_assumptions': list(self.failed_assumptions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundingCheck:
        return cls(
            spec_id=data.get('spec_id', ''),
            files_searched=list(data.get('files_searched', []) or []),
            assumptions_confirmed=list(data.get('assumptions_confirmed', []) or []),
            grounding_valid=bool(data.get('grounding_valid', False)),
            missing_files=list(data.get('missing_files', []) or []),
            failed_assumptions=list(data.get('failed_assumptions', []) or []),
        )


def perform_grounding_check(
    spec_path: Path,
    workspace_root: Path,
    *,
    spec_id: str = '',
    assumptions: list[str] | None = None,
    candidate_files: list[str] | None = None,
) -> GroundingCheck:
    """Validate that a spec document's file references exist in the workspace.

    Parameters
    ----------
    spec_path:
        Path to the spec / task document.
    workspace_root:
        Root directory of the workspace to resolve paths against.
    spec_id:
        Optional spec identifier for the GroundingCheck record.
    assumptions:
        Plain-text assumptions to validate (e.g. from ``_plan_assumptions()``).
    candidate_files:
        Pre-resolved candidate paths from ``ContextPack.candidate_files``.
        When provided these are merged with extracted file refs.

    Returns
    -------
    GroundingCheck
        A dataclass with ``grounding_valid``, ``missing_files``, and
        ``failed_assumptions`` populated.
    """
    ws = workspace_root.resolve()
    spec_text = ''
    if spec_path.is_file():
        spec_text = spec_path.read_text(encoding='utf-8')

    # Files searched: merge pre-resolved candidates + extracted refs
    extracted = extract_file_refs(spec_text)
    if candidate_files:
        merged: set[str] = set(candidate_files)
        merged.update(extracted)
    else:
        merged = set(extracted)

    files_searched = sorted(merged)

    # Validate each referenced file exists in the workspace
    missing_files: list[str] = []
    for raw in files_searched:
        candidate = (
            (ws / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        )
        try:
            candidate.relative_to(ws)
        except ValueError:
            continue  # external paths are not required to exist
        if not candidate.is_file():
            missing_files.append(raw)

    # Validate assumptions (simplistic: assume all are confirmed unless *needs_clarification*)
    confirmed: list[str] = list(assumptions) if assumptions else []
    failed_assumptions: list[str] = []
    if assumptions:
        for assumption in assumptions:
            if _assumption_looks_weak(assumption):
                failed_assumptions.append(assumption)
                confirmed.remove(assumption)

    grounding_valid = len(missing_files) == 0 and len(failed_assumptions) == 0

    return GroundingCheck(
        spec_id=spec_id,
        files_searched=files_searched,
        assumptions_confirmed=confirmed,
        grounding_valid=grounding_valid,
        missing_files=missing_files,
        failed_assumptions=failed_assumptions,
    )


def _assumption_looks_weak(text: str) -> bool:
    """Heuristic: flag assumptions that indicate unresolved ambiguity."""
    weak_markers = (
        'above the clarify threshold',
        'should wait for answers',
        'ambiguit',
        'not sufficiently specified',
    )
    lower = text.lower()
    return any(marker in lower for marker in weak_markers)


# ── SpecBinding ──────────────────────────────────────────────────────────


@dataclass
class SpecBinding:
    """Binding record between a spec and a generated plan.

    Captures what files were searched and assumptions confirmed at the
    moment the spec was promoted to a plan.  Mirrors ``PlanBinding`` from
    ``plan_storage.py``.
    """

    spec_id: str
    spec_hash: str
    plan_id: str
    plan_hash: str
    searched_files: list[str] = field(default_factory=list)
    confirmed_assumptions: list[str] = field(default_factory=list)
    transitioned_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'spec_id': self.spec_id,
            'spec_hash': self.spec_hash,
            'plan_id': self.plan_id,
            'plan_hash': self.plan_hash,
            'searched_files': list(self.searched_files),
            'confirmed_assumptions': list(self.confirmed_assumptions),
            'transitioned_at': self.transitioned_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecBinding:
        return cls(
            spec_id=data.get('spec_id', ''),
            spec_hash=data.get('spec_hash', ''),
            plan_id=data.get('plan_id', ''),
            plan_hash=data.get('plan_hash', ''),
            searched_files=list(data.get('searched_files', []) or []),
            confirmed_assumptions=list(data.get('confirmed_assumptions', []) or []),
            transitioned_at=data.get('transitioned_at', ''),
        )


# ── audit events ─────────────────────────────────────────────────────────


def _hash_text(text: str) -> str:
    return 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def emit_spec_promoted_to_plan(
    audit: AuditLogger,
    binding: SpecBinding,
    run_id: str = 'spec',
) -> None:
    """Record ``spec_promoted_to_plan`` audit event with full binding info."""
    audit.record(
        'spec_promoted_to_plan',
        run_id=run_id,
        spec_id=binding.spec_id,
        spec_hash=binding.spec_hash,
        plan_id=binding.plan_id,
        plan_hash=binding.plan_hash,
        searched_files=binding.searched_files,
        confirmed_assumptions=binding.confirmed_assumptions,
        transitioned_at=binding.transitioned_at,
    )


def emit_spec_grounding_checked(
    audit: AuditLogger,
    check: GroundingCheck,
    run_id: str = 'spec',
) -> None:
    """Record ``spec_grounding_checked`` audit event with full check data."""
    audit.record(
        'spec_grounding_checked',
        run_id=run_id,
        spec_id=check.spec_id,
        files_searched=check.files_searched,
        assumptions_confirmed=check.assumptions_confirmed,
        grounding_valid=check.grounding_valid,
        missing_files=check.missing_files,
        failed_assumptions=check.failed_assumptions,
    )


# ── persistence ──────────────────────────────────────────────────────────


def persist_grounding(
    check: GroundingCheck,
    store: GoalStore,
    *,
    binding: SpecBinding | None = None,
) -> Path:
    """Save grounding check results to the goal store.

    Writes ``<spec_id>_grounding.json`` alongside goal records.  Also
    appends audit events via the goal's own audit log when a goal_id can
    be resolved.

    Returns the path to the written grounding file.
    """
    ground_dir = store._root / 'grounding'
    ground_dir.mkdir(parents=True, exist_ok=True)
    secure_audit_dir(ground_dir)

    doc: dict[str, Any] = {
        'grounding': check.to_dict(),
        'saved_at': utc_now(),
    }
    if binding is not None:
        doc['binding'] = binding.to_dict()

    filename = f'{check.spec_id}_grounding.json'
    path = ground_dir / filename
    atomic_write_text(path, json.dumps(doc, indent=2))
    secure_audit_file(path)
    logger.info('Saved grounding result for spec %s to %s', check.spec_id, path)

    # Append to goal audit log if we have a goal for this spec
    goal_id = _resolve_goal_id(store, check.spec_id)
    if goal_id:
        audit = store.goal_audit_logger(goal_id)
        if binding is not None:
            emit_spec_promoted_to_plan(audit, binding, run_id=goal_id)
        emit_spec_grounding_checked(audit, check, run_id=goal_id)

    return path


def _resolve_goal_id(store: GoalStore, spec_id: str) -> str:
    """Find a goal whose ``spec_id`` matches, otherwise return ''."""
    if not spec_id:
        return ''
    try:
        for goal in store.list():
            if goal.spec_id == spec_id:
                return goal.goal_id
    except OSError:
        pass
    return ''
