from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

GrantScope = Literal['once', 'session', 'always', 'deny']
ApprovalDecision = Literal['allow', 'deny', 'prompt']

SESSION_TTL_HOURS = 8.0
APPROVAL_TTL_HOURS = 24.0  # Scoped approvals expire after 24 hours by default

POLICY_ORDER = [
    'Matching deny grants block the tool call',
    'Matching once, always, or session grants allow',
    'Otherwise HITL prompt is required (no matching preset)',
]

_PATH_ARGUMENT_KEYS = ('path', 'file_path', 'target_path', 'file')
_COMMAND_ARGUMENT_KEYS = ('command', 'cmd')


@dataclass(frozen=True)
class ApprovalGrant:
    grant_id: str
    tool_name: str
    scope: GrantScope
    permission_mode: str | None = None
    created_at: str = ''
    path_globs: tuple[str, ...] = ()
    command_prefixes: tuple[str, ...] = ()
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'grant_id': self.grant_id,
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


@dataclass(frozen=True)
class ScopedApprovalRecord:
    """Run-scoped approval record for exact tool call matching."""

    record_id: str
    run_id: str
    call_id: str
    tool_name: str
    argument_digest: str
    created_at: str
    expires_at: str | None = None
    consumed_at: str | None = None
    key_id: str | None = None  # first 16 hex chars of the HMAC secret at creation time

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'record_id': self.record_id,
            'run_id': self.run_id,
            'call_id': self.call_id,
            'tool_name': self.tool_name,
            'argument_digest': self.argument_digest,
            'created_at': self.created_at,
        }
        if self.expires_at:
            payload['expires_at'] = self.expires_at
        if self.consumed_at:
            payload['consumed_at'] = self.consumed_at
        if self.key_id:
            payload['key_id'] = self.key_id
        return payload


def _new_grant_id() -> str:
    return uuid4().hex[:12]


def _new_record_id() -> str:
    return uuid4().hex[:12]


def _compute_argument_digest(
    arguments: dict[str, Any], secret: Optional[bytes] = None
) -> str:
    """Compute stable digest of arguments for exact matching."""
    normalized = json.dumps(arguments, sort_keys=True, separators=(',', ':'))
    if secret is not None:
        import hmac

        return hmac.new(secret, normalized.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _stable_grant_id(item: dict[str, Any]) -> str:
    """Deterministic id for legacy grants missing grant_id (safe to persist)."""
    fingerprint = {
        'tool_name': item.get('tool_name'),
        'scope': item.get('scope', 'once'),
        'permission_mode': item.get('permission_mode'),
        'created_at': item.get('created_at', ''),
        'path_globs': sorted(str(g) for g in (item.get('path_globs') or []) if g),
        'command_prefixes': sorted(
            str(p) for p in (item.get('command_prefixes') or []) if p
        ),
        'expires_at': item.get('expires_at'),
    }
    digest = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()[:12]
    return f'leg-{digest}'


def _parse_grant(item: dict[str, Any]) -> ApprovalGrant:
    path_globs = item.get('path_globs') or []
    command_prefixes = item.get('command_prefixes') or []
    grant_id = item.get('grant_id')
    return ApprovalGrant(
        grant_id=str(grant_id) if grant_id else _stable_grant_id(item),
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


def _normalize_and_validate_path(
    path_value: str, workspace_root: str | Path
) -> str | None:
    """Normalize and validate a path is within workspace bounds.

    Returns normalized path if valid, None if:
    - Path is None or empty
    - Path contains parent traversal (..)
    - Path is absolute and outside workspace
    - Path is a symlink escaping workspace

    This prevents approval widening through path manipulation.
    """
    if not path_value or not isinstance(path_value, str):
        return None

    # Normalize backslashes and resolve
    normalized = path_value.replace('\\', '/')

    # Reject parent traversal
    if '../' in normalized or normalized.startswith('..'):
        return None

    # Resolve against workspace root
    try:
        root_path = Path(workspace_root).resolve()
        abs_path = root_path / normalized

        # Resolve to catch symlinks
        resolved = abs_path.resolve()

        # Check if resolved path is within workspace
        try:
            resolved.relative_to(root_path)
        except ValueError:
            # Path escapes workspace
            return None

        # Return relative path from workspace root
        return str(resolved.relative_to(root_path)).replace('\\', '/')
    except (OSError, ValueError):
        return None


def _path_matches(
    path_globs: tuple[str, ...],
    arguments: dict[str, Any],
    workspace_root: str | Path = '.',
) -> bool:
    """Check if tool call path arguments match approved path globs.

    Enhanced with workspace containment validation to prevent
    path traversal and approval widening.
    """
    if not path_globs:
        return True

    path_value: str | None = None
    for key in _PATH_ARGUMENT_KEYS:
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            # Normalize and validate path against workspace
            normalized = _normalize_and_validate_path(raw, workspace_root)
            if normalized:
                path_value = normalized
                break

    if path_value is None:
        return False

    for pattern in path_globs:
        normalized_pattern = pattern.replace('\\', '/')
        if fnmatch.fnmatch(path_value, normalized_pattern):
            return True
        if fnmatch.fnmatch(path_value, f'**/{normalized_pattern.lstrip("/")}'):
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


__all__ = [
    'APPROVAL_TTL_HOURS',
    'POLICY_ORDER',
    'SESSION_TTL_HOURS',
    'ApprovalDecision',
    'ApprovalGrant',
    'GrantScope',
    'ScopedApprovalRecord',
    '_command_matches',
    '_compute_argument_digest',
    '_compute_expires_at',
    '_grant_expired',
    '_new_grant_id',
    '_new_record_id',
    '_normalize_and_validate_path',
    '_parse_grant',
    '_path_matches',
    '_stable_grant_id',
]
