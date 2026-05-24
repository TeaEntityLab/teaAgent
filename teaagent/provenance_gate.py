"""Canonical provenance gate for persistent substrate writes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional

GateAction = Literal['allow', 'quarantine']


class ProvenanceSourceKind(str, Enum):
    LOCAL = 'local'
    AGENT_RUN = 'agent_run'
    WEB_MESSAGE = 'web_message'


class PersistenceSubstrate(str, Enum):
    MEMORY = 'memory'
    SKILL_CANDIDATE = 'skill_candidate'
    AUTOMATION = 'automation'
    FILESYSTEM = 'filesystem'


@dataclass(frozen=True)
class ProvenanceGateResult:
    action: GateAction
    content_digest: str
    source_kind: ProvenanceSourceKind
    substrate: PersistenceSubstrate
    reason: str = ''
    attested: bool = False

    @property
    def allowed(self) -> bool:
        return self.action == 'allow'

    @property
    def quarantine(self) -> bool:
        return self.action == 'quarantine'

    def to_dict(self) -> dict[str, Any]:
        return {
            'action': self.action,
            'content_digest': self.content_digest,
            'source_kind': self.source_kind.value,
            'substrate': self.substrate.value,
            'reason': self.reason,
            'attested': self.attested,
        }


def parse_source_kind(value: Optional[str]) -> ProvenanceSourceKind:
    if not value:
        return ProvenanceSourceKind.LOCAL
    normalized = value.strip().lower().replace('-', '_')
    for kind in ProvenanceSourceKind:
        if kind.value == normalized:
            return kind
    raise ValueError(
        f"unknown write source '{value}'; use local, agent_run, or web_message"
    )


def canonical_content_digest(
    *,
    substrate: PersistenceSubstrate,
    payload: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {'substrate': substrate.value, 'payload': payload},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return f'sha256:{digest}'


def evaluate_persistent_write(
    *,
    substrate: PersistenceSubstrate,
    payload: dict[str, Any],
    source_kind: ProvenanceSourceKind,
    attested: bool = False,
) -> ProvenanceGateResult:
    """Decide whether a durable write may proceed or must stay in quarantine."""
    digest = canonical_content_digest(substrate=substrate, payload=payload)
    if source_kind == ProvenanceSourceKind.LOCAL:
        return ProvenanceGateResult(
            action='allow',
            content_digest=digest,
            source_kind=source_kind,
            substrate=substrate,
        )
    if source_kind == ProvenanceSourceKind.AGENT_RUN:
        if substrate == PersistenceSubstrate.SKILL_CANDIDATE:
            return ProvenanceGateResult(
                action='allow',
                content_digest=digest,
                source_kind=source_kind,
                substrate=substrate,
                reason='skill candidates are always stored in quarantine',
            )
        return ProvenanceGateResult(
            action='allow',
            content_digest=digest,
            source_kind=source_kind,
            substrate=substrate,
        )
    if attested:
        return ProvenanceGateResult(
            action='allow',
            content_digest=digest,
            source_kind=source_kind,
            substrate=substrate,
            attested=True,
            reason='owner attestation recorded for untrusted source',
        )
    return ProvenanceGateResult(
        action='quarantine',
        content_digest=digest,
        source_kind=source_kind,
        substrate=substrate,
        reason=(
            f'untrusted source {source_kind.value} requires quarantine or '
            '--i-attest-untrusted-write after human review'
        ),
    )
