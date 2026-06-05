"""Skill lifecycle state machine and tracking (DSK-P0-001).

Defines the ``SkillLifecycleState`` vocabulary and a ``SkillLifecycleTracker``
that records state transitions via audit events.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class SkillLifecycleState(str, Enum):
    """DSK-P0-001 minimum lifecycle state vocabulary for skills.

    Each state represents a stage in the skill's journey from discovery
    through activation to potential supersession or blocking.
    """

    DISCOVERED = 'discovered'
    INDEXED = 'indexed'
    SELECTED = 'selected'
    ACTIVATED = 'activated'
    RESOURCE_READ = 'resource_read'
    CANDIDATE_PROPOSED = 'candidate_proposed'
    CANDIDATE_EVAL_PASSED = 'candidate_eval_passed'
    REVIEW_PASSED = 'review_passed'
    INSTALLED = 'installed'
    USED_IN_RUN = 'used_in_run'
    OUTPUT_VERIFIED = 'output_verified'
    SUPERSEDED = 'superseded'
    BLOCKED = 'blocked'

    def __str__(self) -> str:
        return self.value


class AuditRecorder(Protocol):
    """Protocol for audit loggers that accept ``record(event_type, run_id, **payload)``."""

    def record(self, event_type: str, run_id: str, **payload: Any) -> Any: ...


class SkillLifecycleTracker:
    """Tracks skill state transitions in-memory and optionally via audit events.

    Parameters
    ----------
    audit_logger:
        Optional audit logger. When provided, every state transition is
        recorded as a ``skill_lifecycle_transition`` audit event.
    run_id:
        Run identifier used in audit events. Required when ``audit_logger``
        is provided.
    """

    _EVENT_TYPE = 'skill_lifecycle_transition'

    def __init__(
        self,
        audit_logger: AuditRecorder | None = None,
        run_id: str = '',
    ) -> None:
        self._audit: AuditRecorder | None = audit_logger
        self._run_id: str = run_id
        self._states: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition(
        self,
        skill_name: str,
        to_state: str,
        *,
        reason: str = '',
        source_path: str = '',
    ) -> None:
        """Record a state transition.

        Parameters
        ----------
        skill_name:
            Name of the skill.
        to_state:
            Target lifecycle state (one of ``SkillLifecycleState`` values).
        reason:
            Human-readable reason for the transition.
        source_path:
            Filesystem path where the skill was discovered.
        """
        from_state = self._states.get(skill_name, 'unknown')
        self._states[skill_name] = to_state
        if self._audit is not None:
            self._audit.record(
                self._EVENT_TYPE,
                self._run_id,
                skill_name=skill_name,
                from_state=from_state,
                to_state=to_state,
                reason=reason,
                source_path=source_path,
            )

    def current_state(self, skill_name: str) -> str:
        """Return the current lifecycle state for *skill_name*.

        Returns ``'unknown'`` when no state has been recorded.
        """
        return self._states.get(skill_name, 'unknown')

    def all_states(self) -> dict[str, str]:
        """Return a copy of all tracked skill states."""
        return dict(self._states)

    def set_state(
        self,
        skill_name: str,
        state: str,
        *,
        reason: str = '',
        source_path: str = '',
    ) -> None:
        """Set the current state without recording a transition event.

        Useful for initialising state from a bulk load (e.g. all discovered
        skills) without emitting numerous audit entries.
        """
        self._states[skill_name] = state


# ---------------------------------------------------------------------------
# Governance classification helpers (DSK-P0-006)
# ---------------------------------------------------------------------------

# Project-relative primary skill dirs (candidate workflow capable).
_PRIMARY_PROJECT_RELS = frozenset({
    '.config/agent/skills',
    '.opencode/skill',
})

# Project-relative compatibility dirs (Claude / OpenCode plural aliases).
_COMPAT_PROJECT_RELS = frozenset({
    '.claude/skills',
    '.opencode/skills',
})

# User primary dirs (resolved absolute paths).
_USER_PRIMARY_PATHS: frozenset[str] = frozenset({
    str(Path.home() / '.config' / 'agent' / 'skills'),
    str(Path.home() / '.config' / 'opencode' / 'skills'),
})

# User compatibility dirs.
_USER_COMPAT_PATHS: frozenset[str] = frozenset({
    str(Path.home() / '.claude' / 'skills'),
})


def classify_governance_status(
    skill_dir: Path,
    source_dir: Path,
    root: Path,
) -> str:
    """Classify the governance status of a loaded skill.

    Parameters
    ----------
    skill_dir:
        The skill package directory (e.g. ``…/.config/agent/skills/my-skill``).
    source_dir:
        The search directory that contained *skill_dir* (e.g. ``…/.config/agent/skills``).
    root:
        The workspace root path.

    Returns
    -------
    str
        One of ``'candidate_installed'``, ``'direct_write'``,
        ``'compatibility_path'``, ``'unmanaged'``.
    """
    # --- candidate provenance check ---------------------------------------
    from teaagent.skill_candidate_artifacts import REQUIRED_CANDIDATE_ARTIFACTS

    provenance_path = skill_dir / 'provenance.json'
    if provenance_path.is_file():
        try:
            import json

            provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
            if provenance.get('installed_via') == 'candidate' or (
                provenance.get('install_scope') in {'project', 'personal'}
                and all(
                    (skill_dir / name).is_file()
                    for name in REQUIRED_CANDIDATE_ARTIFACTS
                )
            ):
                return 'candidate_installed'
        except (OSError, json.JSONDecodeError):
            pass

    # --- source-dir classification ----------------------------------------
    source_str = str(source_dir.resolve())

    # Primary project dirs.
    for rel in _PRIMARY_PROJECT_RELS:
        if source_str == str((root / rel).resolve()):
            return 'direct_write'

    # Compatibility project dirs.
    for rel in _COMPAT_PROJECT_RELS:
        if source_str == str((root / rel).resolve()):
            return 'compatibility_path'

    # User primary dirs.
    if source_str in _USER_PRIMARY_PATHS:
        return 'direct_write'

    # User compatibility dirs.
    if source_str in _USER_COMPAT_PATHS:
        return 'compatibility_path'

    # Everything else (extra, custom, extended dirs).
    return 'unmanaged'
