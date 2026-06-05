"""Dynamic asset provenance summary (CPP-P0-006).

Captures a snapshot of currently loaded skills and MCP servers together
with their governance status, lifecycle state, revocation status, and
shadowed paths.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

AssetType = Literal['skill', 'mcp_server']
RevocationStatus = Literal['active', 'revoked', 'unknown']


@dataclass(frozen=True)
class ProvenanceRecord:
    """A single asset provenance snapshot.

    Fields
    ------
    asset_type:
        ``skill`` or ``mcp_server``.
    name:
        Asset name (skill name or MCP server identifier).
    source_path:
        Filesystem path where the asset was discovered (skill) or
        endpoint URL / config path (mcp_server).
    governance_status:
        Governance classification from
        :func:`~teaagent.skill_lifecycle.classify_governance_status`
        (e.g. ``candidate_installed``, ``direct_write``,
        ``compatibility_path``, ``unmanaged``). For MCP servers this
        may be ``remote`` or ``local``.
    activation_status:
        Lifecycle state from
        :class:`~teaagent.skill_lifecycle.SkillLifecycleState`. For
        MCP servers this reflects connection state
        (``connected``, ``disconnected``, ``failed``).
    revocation_status:
        Whether the asset is currently ``active``, ``revoked``, or
        ``unknown``.
    shadowed_paths:
        Paths that were shadowed by this asset (only meaningful for
        skills).
    loaded_at:
        Unix epoch timestamp when this record was created.
    """

    asset_type: AssetType
    name: str
    source_path: str = ''
    governance_status: str = 'unknown'
    activation_status: str = 'unknown'
    revocation_status: RevocationStatus = 'unknown'
    shadowed_paths: list[str] = field(default_factory=list)
    loaded_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            'asset_type': self.asset_type,
            'name': self.name,
            'source_path': self.source_path,
            'governance_status': self.governance_status,
            'activation_status': self.activation_status,
            'revocation_status': self.revocation_status,
            'shadowed_paths': list(self.shadowed_paths),
            'loaded_at': self.loaded_at,
        }


@dataclass
class AssetProvenanceBundle:
    """Collection of provenance records captured at a point in time."""

    records: list[ProvenanceRecord] = field(default_factory=list)
    captured_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            'captured_at': self.captured_at,
            'records': [r.to_dict() for r in self.records],
        }


def _revocation_status_for_skill(
    skill_name: str,
    lifecycle_state: str,
) -> RevocationStatus:
    """Derive revocation status from lifecycle state."""
    from teaagent.skill_lifecycle import SkillLifecycleState

    if lifecycle_state in (
        SkillLifecycleState.BLOCKED.value,
        SkillLifecycleState.SUPERSEDED.value,
    ):
        return 'revoked'
    if lifecycle_state in (
        SkillLifecycleState.DISCOVERED.value,
        SkillLifecycleState.INDEXED.value,
        SkillLifecycleState.SELECTED.value,
        SkillLifecycleState.ACTIVATED.value,
        SkillLifecycleState.RESOURCE_READ.value,
        SkillLifecycleState.USED_IN_RUN.value,
        SkillLifecycleState.OUTPUT_VERIFIED.value,
    ):
        return 'active'
    return 'unknown'


def collect_provenance(
    root: str | Path,
    *,
    skill_activation: Any | None = None,
    mcp_servers: Optional[list[dict[str, Any]]] = None,
    lifecycle_tracker: Any | None = None,
) -> AssetProvenanceBundle:
    """Collect provenance snapshot for currently loaded skills and MCP servers.

    Parameters
    ----------
    root:
        Workspace root path.
    skill_activation:
        Optional :class:`~teaagent.skill_loader.SkillActivationExplain`
        from a prior call to
        :func:`~teaagent.skill_loader.explain_skill_activation`.
        When ``None``, no skill records are included.
    mcp_servers:
        Optional list of MCP server descriptors. Each dict may contain
        ``name``, ``endpoint``, ``status``, and ``source_path`` keys.
    lifecycle_tracker:
        Optional :class:`~teaagent.skill_lifecycle.SkillLifecycleTracker`
        used to resolve current lifecycle states. When ``None``,
        lifecycle_state defaults to ``unknown``.

    Returns
    -------
    AssetProvenanceBundle
        Snapshot of all discovered provenance records.
    """
    records: list[ProvenanceRecord] = []

    # --- Skills ------------------------------------------------------------
    if skill_activation is not None:
        from teaagent.skill_loader import SkillActivationExplain

        if isinstance(skill_activation, SkillActivationExplain):
            shadow_map: dict[str, list[str]] = {}
            for shadow in skill_activation.shadowed:
                shadow_map.setdefault(shadow.name, []).append(
                    str(shadow.shadowed_path)
                )

            for loaded in skill_activation.loaded:
                lifecycle_state = loaded.lifecycle_state
                if lifecycle_tracker is not None:
                    try:
                        current = lifecycle_tracker.current_state(loaded.name)
                        if current != 'unknown':
                            lifecycle_state = current
                    except Exception:
                        pass

                records.append(
                    ProvenanceRecord(
                        asset_type='skill',
                        name=loaded.name,
                        source_path=str(loaded.path),
                        governance_status=loaded.governance_status,
                        activation_status=lifecycle_state,
                        revocation_status=_revocation_status_for_skill(
                            loaded.name, lifecycle_state
                        ),
                        shadowed_paths=shadow_map.get(loaded.name, []),
                    )
                )

    # --- MCP servers -------------------------------------------------------
    if mcp_servers is not None:
        for server in mcp_servers:
            name = server.get('name', '')
            endpoint = server.get('endpoint', '')
            source_path = server.get('source_path', endpoint)
            status = server.get('status', 'unknown')

            # Map connection status to activation_status
            activation_status: str = 'unknown'
            if status == 'connected':
                activation_status = 'connected'
            elif status == 'disconnected':
                activation_status = 'disconnected'
            elif status == 'failed':
                activation_status = 'failed'
            else:
                activation_status = status

            # Revocation status for MCP servers
            revocation_status: RevocationStatus
            if status in ('connected', 'initializing'):
                revocation_status = 'active'
            elif status in ('failed', 'revoked', 'disconnected'):
                revocation_status = 'revoked'
            else:
                revocation_status = 'unknown'

            records.append(
                ProvenanceRecord(
                    asset_type='mcp_server',
                    name=name,
                    source_path=source_path,
                    governance_status='remote' if endpoint.startswith(
                        ('http://', 'https://')
                    ) else 'local',
                    activation_status=activation_status,
                    revocation_status=revocation_status,
                    shadowed_paths=[],
                )
            )

    return AssetProvenanceBundle(records=records)
