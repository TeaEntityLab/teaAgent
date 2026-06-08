"""Proof-of-use for skill-backed outputs (CPP-P0-007).

Links each skill-backed tool call to its source artifact, tool call id,
output hash, and verification status.  Produces a ``ProofOfUseBundle`` that
can be attached to ``RunEvidenceBundle`` and ``FinalAnswer.metadata``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from teaagent.skill_lifecycle import SkillLifecycleState, SkillLifecycleTracker


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_output_hash(content: str) -> str:
    """Compute a ``sha256:<hexdigest>`` hash of *content*."""
    return f'sha256:{hashlib.sha256(content.encode("utf-8")).hexdigest()}'


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProofOfUse:
    """Evidence that a skill contributed to a tool-call output.

    Fields
    ------
    source_skill_name:
        Skill name as discovered by the loader (directory name).
    source_artifact_path:
        Filesystem path to the skill artifact (SKILL.md or tool.py).
    tool_call_id:
        Agent-internal call id for the tool invocation.
    tool_name:
        Registered tool name dispatched during the run.
    output_hash:
        ``"sha256:<hexdigest>"`` of the tool-call result content.
    verified:
        ``True`` when the skill reached ``OUTPUT_VERIFIED`` lifecycle state.
    verified_at:
        ISO-8601 UTC timestamp when verification was recorded (or ``""``).
    """

    source_skill_name: str
    source_artifact_path: str
    tool_call_id: str
    tool_name: str
    output_hash: str
    verified: bool = False
    verified_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'source_skill_name': self.source_skill_name,
            'source_artifact_path': self.source_artifact_path,
            'tool_call_id': self.tool_call_id,
            'tool_name': self.tool_name,
            'output_hash': self.output_hash,
            'verified': self.verified,
            'verified_at': self.verified_at,
        }


@dataclass
class ProofOfUseBundle:
    """Collection of proof-of-use records for a single run.

    Fields
    ------
    proofs:
        One record per skill-backed tool call observed during the run.
    final_answer_hash:
        ``"sha256:<hexdigest>"`` of the final answer content.
    final_answer_preview:
        First 200 characters of the final answer (for human inspection).
    """

    proofs: list[ProofOfUse] = field(default_factory=list)
    final_answer_hash: str = ''
    final_answer_preview: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'proofs': [p.to_dict() for p in self.proofs],
            'final_answer_hash': self.final_answer_hash,
            'final_answer_preview': self.final_answer_preview,
        }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def _audit_events_to_dicts(
    events: list[Any],
) -> list[dict[str, Any]]:
    """Normalise audit events (which may be ``AuditEvent`` instances or dicts)
    into plain dicts."""
    result: list[dict[str, Any]] = []
    for ev in events:
        if isinstance(ev, dict):
            result.append(ev)
        elif hasattr(ev, 'event_type') and hasattr(ev, 'payload'):
            result.append(
                {
                    'event_type': ev.event_type,
                    'payload': ev.payload if isinstance(ev.payload, dict) else {},
                    'created_at': getattr(ev, 'created_at', ''),
                }
            )
        else:
            continue
    return result


def _skill_output_verification_time(
    events: list[dict[str, Any]],
    skill_name: str,
) -> tuple[bool, str]:
    """Return ``(verified, verified_at)`` by scanning lifecycle transitions."""
    for ev in events:
        if ev.get('event_type') != 'skill_lifecycle_transition':
            continue
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        if (
            payload.get('skill_name') == skill_name
            and payload.get('to_state') == SkillLifecycleState.OUTPUT_VERIFIED.value
        ):
            verified_at = payload.get('created_at') or ev.get('created_at') or ''
            if not verified_at:
                verified_at = _utc_iso_now()
            return True, str(verified_at)
    return False, ''


def _build_proofs_from_events(  # noqa: C901
    events: list[dict[str, Any]],
) -> list[ProofOfUse]:
    """Scan audit events and return one ``ProofOfUse`` per skill-backed tool-call.

    Heuristic
    ---------
    1. Collect every ``skill_lifecycle_transition`` whose ``to_state`` is
       ``USED_IN_RUN`` or ``OUTPUT_VERIFIED``; record the skill name and
       source path.
    2. For every ``tool_call_completed`` event, if the ``tool_name`` or the
       result content references any known skill name, produce a proof entry.
    3. Mark ``verified=True`` when a matching ``OUTPUT_VERIFIED`` transition
       exists.
    """
    # --- collect skill data from lifecycle transitions ----------------------
    used_skills: dict[str, str] = {}  # skill_name -> source_path
    for ev in events:
        if ev.get('event_type') != 'skill_lifecycle_transition':
            continue
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        to_state = payload.get('to_state', '')
        if to_state in {
            SkillLifecycleState.USED_IN_RUN.value,
            SkillLifecycleState.OUTPUT_VERIFIED.value,
        }:
            name = payload.get('skill_name', '')
            path = payload.get('source_path', '')
            if name:
                used_skills[name] = path

    if not used_skills:
        # Fallback: look for skills whose name appears in any tool-call result
        return _fallback_proofs(events)

    # --- match tool calls to skills -----------------------------------------
    proofs: list[ProofOfUse] = []
    seen_call_ids: set[str] = set()

    for ev in events:
        if ev.get('event_type') != 'tool_call_completed':
            continue
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        call_id = payload.get('call_id', '')
        if call_id in seen_call_ids:
            continue
        tool_name = payload.get('tool_name', '')
        result = payload.get('result')
        result_str = str(result) if result is not None else ''

        # Match: if any known skill name appears in the tool name or result
        matched_skill = ''
        for skill_name, _source_path in used_skills.items():
            if skill_name in tool_name or skill_name in result_str:
                matched_skill = skill_name
                break

        if not matched_skill:
            continue

        verified, verified_at = _skill_output_verification_time(events, matched_skill)
        proofs.append(
            ProofOfUse(
                source_skill_name=matched_skill,
                source_artifact_path=used_skills[matched_skill],
                tool_call_id=call_id,
                tool_name=tool_name,
                output_hash=_compute_output_hash(result_str),
                verified=verified,
                verified_at=verified_at,
            )
        )
        seen_call_ids.add(call_id)

    return proofs


def _fallback_proofs(events: list[dict[str, Any]]) -> list[ProofOfUse]:
    """Build proofs by scanning tool-call results for skill names."""
    proofs: list[ProofOfUse] = []
    seen_call_ids: set[str] = set()

    for ev in events:
        if ev.get('event_type') != 'tool_call_completed':
            continue
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        call_id = payload.get('call_id', '')
        if call_id in seen_call_ids:
            continue
        tool_name = payload.get('tool_name', '')
        result = payload.get('result')
        result_str = str(result) if result is not None else ''

        # Simple heuristic: check if tool_name or result contains common
        # skill-related keywords.
        if 'skill' not in tool_name.lower() and 'skill' not in result_str.lower():
            continue

        proofs.append(
            ProofOfUse(
                source_skill_name='',
                source_artifact_path='',
                tool_call_id=call_id,
                tool_name=tool_name,
                output_hash=_compute_output_hash(result_str),
                verified=False,
                verified_at='',
            )
        )
        seen_call_ids.add(call_id)

    return proofs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_proof_of_use(
    audit_events: list[Any],
    final_answer_content: str,
    *,
    skill_tracker: Optional[SkillLifecycleTracker] = None,
) -> ProofOfUseBundle:
    """Build a ``ProofOfUseBundle`` from audit events and skill lifecycle state.

    Parameters
    ----------
    audit_events:
        Audit events (``AuditEvent`` objects or dicts) from the current run.
    final_answer_content:
        The final answer text produced by the agent.
    skill_tracker:
        Optional :class:`~teaagent.skill_lifecycle.SkillLifecycleTracker`
        used to cross-check lifecycle states against audit events.

    Returns
    -------
    ProofOfUseBundle
        Bundle ready for attachment to ``RunEvidenceBundle`` or
        ``FinalAnswer.metadata``.
    """
    events = _audit_events_to_dicts(audit_events)

    # --- merge skill-tracker state into event list --------------------------
    if skill_tracker is not None:
        for skill_name, state in skill_tracker.all_states().items():
            if state in {
                SkillLifecycleState.USED_IN_RUN.value,
                SkillLifecycleState.OUTPUT_VERIFIED.value,
            }:
                # Synthesise a transition event so the proof builder can find it.
                events.append(
                    {
                        'event_type': 'skill_lifecycle_transition',
                        'payload': {
                            'skill_name': skill_name,
                            'to_state': state,
                            'source_path': '',
                        },
                    }
                )

    proofs = _build_proofs_from_events(events)
    final_answer_hash = _compute_output_hash(final_answer_content)
    preview = final_answer_content[:200]

    return ProofOfUseBundle(
        proofs=proofs,
        final_answer_hash=final_answer_hash,
        final_answer_preview=preview,
    )


def emit_proof_of_use_audit(bundle: ProofOfUseBundle) -> dict[str, Any]:
    """Return the *payload* for a ``proof_of_use_collected`` audit event.

    The caller is responsible for recording the event via
    ``audit_logger.record(...)``.  This function only constructs the
    canonical payload dict.

    Returns
    -------
    dict
        Audit event payload with keys ``proofs``, ``final_answer_hash``,
        ``final_answer_preview``, and ``proof_count``.
    """
    return {
        'proofs': [p.to_dict() for p in bundle.proofs],
        'final_answer_hash': bundle.final_answer_hash,
        'final_answer_preview': bundle.final_answer_preview,
        'proof_count': len(bundle.proofs),
    }
