from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

GrantScope = Literal['once', 'session', 'always', 'deny']


@dataclass(frozen=True)
class ApprovalGrant:
    tool_name: str
    scope: GrantScope
    permission_mode: str | None = None
    created_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'tool_name': self.tool_name,
            'scope': self.scope,
            'permission_mode': self.permission_mode,
            'created_at': self.created_at,
        }


class ApprovalPresetStore:
    def __init__(self, root: str | Path) -> None:
        self.path = Path(root).resolve() / '.teaagent' / 'approvals.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {'grants': [], 'audit': []}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {'grants': [], 'audit': []}
        if not isinstance(data, dict):
            return {'grants': [], 'audit': []}
        data.setdefault('grants', [])
        data.setdefault('audit', [])
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def list_grants(self) -> list[ApprovalGrant]:
        grants = []
        for item in self._load().get('grants', []):
            if isinstance(item, dict) and item.get('tool_name'):
                grants.append(
                    ApprovalGrant(
                        tool_name=str(item['tool_name']),
                        scope=item.get('scope', 'once'),  # type: ignore[arg-type]
                        permission_mode=item.get('permission_mode'),
                        created_at=str(item.get('created_at', '')),
                    )
                )
        return grants

    def grant(
        self,
        tool_name: str,
        *,
        scope: GrantScope = 'session',
        permission_mode: str | None = None,
    ) -> ApprovalGrant:
        now = datetime.now(timezone.utc).isoformat()
        entry = ApprovalGrant(
            tool_name=tool_name,
            scope=scope,
            permission_mode=permission_mode,
            created_at=now,
        )
        data = self._load()
        grants = [
            g
            for g in data['grants']
            if not (isinstance(g, dict) and g.get('tool_name') == tool_name)
        ]
        grants.append(entry.to_dict())
        data['grants'] = grants
        data['audit'].append({'action': 'grant', **entry.to_dict()})
        self._save(data)
        return entry

    def deny(self, tool_name: str) -> ApprovalGrant:
        return self.grant(tool_name, scope='deny')

    def is_allowed(self, tool_name: str, *, permission_mode: str) -> bool:
        for grant in self.list_grants():
            if grant.tool_name != tool_name:
                continue
            if grant.scope == 'deny':
                return False
            if grant.scope == 'always':
                return True
            if grant.scope == 'session' and (
                grant.permission_mode is None
                or grant.permission_mode == permission_mode
            ):
                return True
        return False

    def audit_tail(self, limit: int = 20) -> list[dict[str, Any]]:
        audit = self._load().get('audit', [])
        if not isinstance(audit, list):
            return []
        return [item for item in audit[-limit:] if isinstance(item, dict)]
