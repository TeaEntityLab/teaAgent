"""OAuth subject → tenant mapping helpers for reverse-proxy gateways."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SUBJECT_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$|^[\w.\-:|]+$')


@dataclass(frozen=True)
class OAuthTenantBinding:
    """Maps an IdP subject to a TeaAgent tenant id."""

    subject: str
    tenant_id: str


@dataclass
class OAuthTenantMap:
    """Validated OAuth subject → tenant routing table."""

    bindings: dict[str, str]

    @classmethod
    def from_file(cls, path: Path) -> OAuthTenantMap:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('oauth tenant map must be a JSON object')
        raw = data.get('subject_tenants', data.get('bindings', {}))
        if not isinstance(raw, dict):
            raise ValueError('subject_tenants must be an object')
        bindings: dict[str, str] = {}
        for subject, tenant in raw.items():
            subj = str(subject).strip()
            tid = str(tenant).strip()
            if not subj or not tid:
                raise ValueError('empty subject or tenant in map')
            if not _SUBJECT_RE.match(subj):
                raise ValueError(f'invalid subject format: {subj!r}')
            bindings[subj] = tid
        if not bindings:
            raise ValueError('subject_tenants must not be empty')
        return cls(bindings=bindings)

    def tenant_for_subject(self, subject: str) -> str | None:
        return self.bindings.get(subject.strip())

    def to_nginx_map_snippet(
        self, *, map_var: str = '$http_x_auth_request_email'
    ) -> str:
        """Emit an nginx ``map`` block for auth_request-injected subjects."""
        lines = [f'map {map_var} $teaagent_tenant {{', '    default "";']
        for subject, tenant in sorted(self.bindings.items()):
            lines.append(f'    "{subject}" "{tenant}";')
        lines.append('}')
        return '\n'.join(lines)
