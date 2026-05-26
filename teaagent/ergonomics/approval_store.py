from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

GrantScope = Literal['once', 'session', 'always', 'deny']

SESSION_TTL_HOURS = 8.0

_PATH_ARGUMENT_KEYS = ('path', 'file_path', 'target_path', 'file')
_COMMAND_ARGUMENT_KEYS = ('command', 'cmd')


@dataclass(frozen=True)
class ApprovalGrant:
    tool_name: str
    scope: GrantScope
    permission_mode: str | None = None
    created_at: str = ''
    path_globs: tuple[str, ...] = ()
    command_prefixes: tuple[str, ...] = ()
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'tool_name': self.tool_name,
            'scope': self.scope,
            'permission_mode': self.permission_mode,
            'created_at': self.created_at,
        }
        if self.path_globs:
            payload['path_globs'] = list(self.path_globs)
        if self.command_prefixes:
            payload['command_prefixes'] = list(self.command_prefixes)
        if self.expires_at:
            payload['expires_at'] = self.expires_at
        return payload


def _parse_grant(item: dict[str, Any]) -> ApprovalGrant:
    path_globs = item.get('path_globs') or []
    command_prefixes = item.get('command_prefixes') or []
    return ApprovalGrant(
        tool_name=str(item['tool_name']),
        scope=item.get('scope', 'once'),  # type: ignore[arg-type]
        permission_mode=item.get('permission_mode'),
        created_at=str(item.get('created_at', '')),
        path_globs=tuple(str(g) for g in path_globs if g),
        command_prefixes=tuple(str(p) for p in command_prefixes if p),
        expires_at=item.get('expires_at'),
    )


def _grant_expired(grant: ApprovalGrant) -> bool:
    if not grant.expires_at:
        return False
    try:
        expires = datetime.fromisoformat(grant.expires_at)
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires


def _path_matches(path_globs: tuple[str, ...], arguments: dict[str, Any]) -> bool:
    if not path_globs:
        return True
    path_value: str | None = None
    for key in _PATH_ARGUMENT_KEYS:
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            path_value = raw.replace('\\', '/')
            break
    if path_value is None:
        return False
    for pattern in path_globs:
        normalized = pattern.replace('\\', '/')
        if fnmatch.fnmatch(path_value, normalized):
            return True
        if fnmatch.fnmatch(path_value, f'**/{normalized.lstrip("/")}'):
            return True
    return False


def _command_matches(
    command_prefixes: tuple[str, ...], arguments: dict[str, Any]
) -> bool:
    if not command_prefixes:
        return True
    command_value: str | None = None
    for key in _COMMAND_ARGUMENT_KEYS:
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            command_value = raw.strip()
            break
    if command_value is None:
        return False
    return any(command_value.startswith(prefix) for prefix in command_prefixes)


def _compute_expires_at(
    *,
    scope: GrantScope,
    created_at: str,
    ttl_hours: float | None,
) -> str | None:
    if scope in {'deny', 'always'}:
        return None
    hours = ttl_hours
    if hours is None and scope == 'session':
        hours = SESSION_TTL_HOURS
    if hours is None or hours <= 0:
        return None
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        created = datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (created + timedelta(hours=hours)).isoformat()


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
        grants: list[ApprovalGrant] = []
        for item in self._load().get('grants', []):
            if isinstance(item, dict) and item.get('tool_name'):
                grants.append(_parse_grant(item))
        return grants

    def grant(
        self,
        tool_name: str,
        *,
        scope: GrantScope = 'session',
        permission_mode: str | None = None,
        path_globs: Sequence[str] | None = None,
        command_prefixes: Sequence[str] | None = None,
        ttl_hours: float | None = None,
    ) -> ApprovalGrant:
        now = datetime.now(timezone.utc).isoformat()
        expires_at = _compute_expires_at(
            scope=scope, created_at=now, ttl_hours=ttl_hours
        )
        entry = ApprovalGrant(
            tool_name=tool_name,
            scope=scope,
            permission_mode=permission_mode,
            created_at=now,
            path_globs=tuple(path_globs or ()),
            command_prefixes=tuple(command_prefixes or ()),
            expires_at=expires_at,
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

    def is_allowed(
        self,
        tool_name: str,
        *,
        permission_mode: str,
        arguments: dict[str, Any] | None = None,
    ) -> bool:
        args = arguments or {}
        for grant in self.list_grants():
            if grant.tool_name != tool_name:
                continue
            if _grant_expired(grant):
                continue
            if grant.scope == 'deny':
                return False
            if grant.scope == 'always':
                if _path_matches(grant.path_globs, args) and _command_matches(
                    grant.command_prefixes, args
                ):
                    return True
                continue
            if (
                grant.scope == 'session'
                and (
                    grant.permission_mode is None
                    or grant.permission_mode == permission_mode
                )
                and _path_matches(grant.path_globs, args)
                and _command_matches(grant.command_prefixes, args)
            ):
                return True
        return False

    def audit_tail(self, limit: int = 20) -> list[dict[str, Any]]:
        audit = self._load().get('audit', [])
        if not isinstance(audit, list):
            return []
        return [item for item in audit[-limit:] if isinstance(item, dict)]
