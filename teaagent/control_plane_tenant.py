"""Multi-tenant control plane state and registry."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

_TENANT_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$')


def sanitize_tenant_id(raw: str, *, default: str = 'default') -> str:
    """Normalize tenant identifiers from headers or URL paths."""
    value = (raw or '').strip()
    if not value:
        return default
    if not _TENANT_RE.match(value):
        raise ValueError(f'invalid tenant id: {raw!r}')
    return value


@dataclass
class JitDiffRecord:
    """Prompt or patch diff surfaced for dashboard review."""

    request_id: str
    agent_name: str
    old_text: str
    new_text: str
    unified_diff: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            'request_id': self.request_id,
            'agent_name': self.agent_name,
            'old_text': self.old_text,
            'new_text': self.new_text,
            'unified_diff': self.unified_diff,
            'created_at': self.created_at,
        }


@dataclass
class ControlPlaneState:
    """Mutable snapshots streamed to the HTML dashboard."""

    workflow: dict[str, Any] | None = None
    focus: dict[str, Any] | None = None
    jit_diffs: list[JitDiffRecord] = field(default_factory=list)
    polish_notes: str = ''
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_workflow(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.workflow = payload

    def set_focus(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.focus = payload

    def set_polish_notes(self, notes: str) -> None:
        with self._lock:
            self.polish_notes = notes

    def publish_jit_diff(
        self,
        request_id: str,
        agent_name: str,
        old_text: str,
        new_text: str,
        unified_diff: str,
    ) -> JitDiffRecord:
        record = JitDiffRecord(
            request_id=request_id,
            agent_name=agent_name,
            old_text=old_text,
            new_text=new_text,
            unified_diff=unified_diff,
        )
        with self._lock:
            self.jit_diffs.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                'workflow': self.workflow,
                'focus': self.focus,
                'jit_diffs': [item.to_dict() for item in self.jit_diffs],
                'polish_notes': self.polish_notes,
            }


@dataclass
class ControlPlaneRegistry:
    """Map tenant IDs to isolated workflow/focus/JIT snapshot state."""

    default_tenant: str = 'default'
    _tenants: dict[str, ControlPlaneState] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def list_tenants(self) -> list[str]:
        with self._lock:
            return sorted(self._tenants.keys())

    def get_or_create(self, tenant_id: str) -> ControlPlaneState:
        tid = sanitize_tenant_id(tenant_id, default=self.default_tenant)
        with self._lock:
            state = self._tenants.get(tid)
            if state is None:
                state = ControlPlaneState()
                self._tenants[tid] = state
            return state

    def seed(self, tenant_id: str, state: ControlPlaneState) -> None:
        tid = sanitize_tenant_id(tenant_id, default=self.default_tenant)
        with self._lock:
            self._tenants[tid] = state
