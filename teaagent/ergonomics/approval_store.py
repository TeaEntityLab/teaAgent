from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Sequence
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
        return payload


def _new_grant_id() -> str:
    return uuid4().hex[:12]


def _new_record_id() -> str:
    return uuid4().hex[:12]


def _compute_argument_digest(arguments: dict[str, Any]) -> str:
    """Compute stable digest of arguments for exact matching."""
    normalized = json.dumps(arguments, sort_keys=True, separators=(',', ':'))
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
            return {
                'grants': [],
                'audit': [],
                'approved_call_ids': [],
                'scoped_approvals': [],
            }
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {
                'grants': [],
                'audit': [],
                'approved_call_ids': [],
                'scoped_approvals': [],
            }
        if not isinstance(data, dict):
            return {
                'grants': [],
                'audit': [],
                'approved_call_ids': [],
                'scoped_approvals': [],
            }
        data.setdefault('grants', [])
        data.setdefault('audit', [])
        data.setdefault('approved_call_ids', [])
        data.setdefault('scoped_approvals', [])
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def _migrate_missing_grant_ids(self) -> None:
        data = self._load()
        changed = False
        now = datetime.now(timezone.utc).isoformat()
        for grant in data.get('grants', []):
            if (
                isinstance(grant, dict)
                and grant.get('tool_name')
                and not grant.get('grant_id')
            ):
                grant['grant_id'] = _stable_grant_id(grant)
                data['audit'].append(
                    {
                        'action': 'migrate_grant_id',
                        'grant_id': grant['grant_id'],
                        'tool_name': grant.get('tool_name'),
                        'scope': grant.get('scope'),
                        'created_at': now,
                    }
                )
                changed = True
        if changed:
            self._save(data)

    def list_grants(self) -> list[ApprovalGrant]:
        self._migrate_missing_grant_ids()
        grants: list[ApprovalGrant] = []
        for item in self._load().get('grants', []):
            if isinstance(item, dict) and item.get('tool_name'):
                grants.append(_parse_grant(item))
        return grants

    def list_policy(self) -> dict[str, Any]:
        return {
            'policy_order': list(POLICY_ORDER),
            'grants': [grant.to_dict() for grant in self.list_grants()],
        }

    def add_approved_call_id(self, call_id: str) -> None:
        data = self._load()
        if call_id not in data['approved_call_ids']:
            data['approved_call_ids'].append(call_id)
            self._save(data)

    def remove_approved_call_id(self, call_id: str) -> None:
        data = self._load()
        if call_id in data['approved_call_ids']:
            data['approved_call_ids'].remove(call_id)
            self._save(data)

    def list_approved_call_ids(self) -> list[str]:
        """Legacy method for backward compatibility. Returns all bare call IDs."""
        return self._load()['approved_call_ids']

    def add_scoped_approval(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        ttl_hours: float | None = None,
    ) -> ScopedApprovalRecord:
        """Add a run-scoped approval record for exact tool call matching."""
        now = datetime.now(timezone.utc).isoformat()
        expires_at = None
        if ttl_hours is None:
            ttl_hours = APPROVAL_TTL_HOURS
        if ttl_hours > 0:
            created = datetime.fromisoformat(now)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            expires_at = (created + timedelta(hours=ttl_hours)).isoformat()

        record = ScopedApprovalRecord(
            record_id=_new_record_id(),
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            argument_digest=_compute_argument_digest(arguments),
            created_at=now,
            expires_at=expires_at,
        )

        data = self._load()
        data['scoped_approvals'].append(record.to_dict())
        data['audit'].append(
            {
                'action': 'scoped_approval',
                'record_id': record.record_id,
                'run_id': run_id,
                'call_id': call_id,
                'tool_name': tool_name,
                'created_at': now,
            }
        )
        self._save(data)
        return record

    def list_scoped_approvals_for_run(self, run_id: str) -> list[ScopedApprovalRecord]:
        """List all scoped approval records for a specific run."""
        data = self._load()
        records: list[ScopedApprovalRecord] = []
        for item in data.get('scoped_approvals', []):
            if not isinstance(item, dict):
                continue
            if item.get('run_id') != run_id:
                continue
            # Skip consumed records
            if item.get('consumed_at'):
                continue
            # Skip expired records
            if item.get('expires_at'):
                try:
                    expires = datetime.fromisoformat(item['expires_at'])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) >= expires:
                        continue
                except ValueError:
                    continue
            records.append(
                ScopedApprovalRecord(
                    record_id=str(item['record_id']),
                    run_id=str(item['run_id']),
                    call_id=str(item['call_id']),
                    tool_name=str(item['tool_name']),
                    argument_digest=str(item['argument_digest']),
                    created_at=str(item['created_at']),
                    expires_at=item.get('expires_at'),
                    consumed_at=item.get('consumed_at'),
                )
            )
        return records

    def consume_scoped_approval(self, record_id: str) -> bool:
        """Mark a scoped approval as consumed (one-time use)."""
        data = self._load()
        found = False
        for item in data.get('scoped_approvals', []):
            if not isinstance(item, dict):
                continue
            if item.get('record_id') == record_id and not item.get('consumed_at'):
                item['consumed_at'] = datetime.now(timezone.utc).isoformat()
                data['audit'].append(
                    {
                        'action': 'consume_scoped_approval',
                        'record_id': record_id,
                        'consumed_at': item['consumed_at'],
                    }
                )
                found = True
                break
        if found:
            self._save(data)
        return found

    def check_scoped_approval(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ScopedApprovalRecord | None:
        """Check if there's a matching scoped approval for this exact tool call."""
        argument_digest = _compute_argument_digest(arguments)
        for record in self.list_scoped_approvals_for_run(run_id):
            if (
                record.call_id == call_id
                and record.tool_name == tool_name
                and record.argument_digest == argument_digest
            ):
                return record
        return None

    def revoke(self, grant_id: str) -> bool:
        self._migrate_missing_grant_ids()
        before = len(self.list_grants())
        self._remove_grant(grant_id)
        if len(self.list_grants()) >= before:
            return False
        data = self._load()
        data['audit'].append(
            {
                'action': 'revoke',
                'grant_id': grant_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save(data)
        return True

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
            grant_id=_new_grant_id(),
            tool_name=tool_name,
            scope=scope,
            permission_mode=permission_mode,
            created_at=now,
            path_globs=tuple(path_globs or ()),
            command_prefixes=tuple(command_prefixes or ()),
            expires_at=expires_at,
        )
        self._migrate_missing_grant_ids()
        data = self._load()
        grants = [g for g in data['grants'] if isinstance(g, dict)]
        grants.append(entry.to_dict())
        data['grants'] = grants
        data['audit'].append({'action': 'grant', **entry.to_dict()})
        self._save(data)
        return entry

    def deny(
        self,
        tool_name: str,
        *,
        path_globs: Sequence[str] | None = None,
        command_prefixes: Sequence[str] | None = None,
    ) -> ApprovalGrant:
        return self.grant(
            tool_name,
            scope='deny',
            path_globs=path_globs,
            command_prefixes=command_prefixes,
        )

    def _remove_grant(self, grant_id: str) -> None:
        data = self._load()

        def _should_remove(grant: object) -> bool:
            if not isinstance(grant, dict):
                return False
            if grant.get('grant_id') == grant_id:
                return True
            return not grant.get('grant_id') and _stable_grant_id(grant) == grant_id

        data['grants'] = [
            grant for grant in data['grants'] if not _should_remove(grant)
        ]
        self._save(data)

    def _grant_matches(
        self,
        grant: ApprovalGrant,
        *,
        permission_mode: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if _grant_expired(grant):
            return False, 'expired'
        if (
            grant.permission_mode is not None
            and grant.permission_mode != permission_mode
        ):
            return False, 'permission_mode_mismatch'
        path_ok = _path_matches(grant.path_globs, arguments)
        command_ok = _command_matches(grant.command_prefixes, arguments)
        if not path_ok and not command_ok:
            return False, 'path_glob_and_command_prefix_mismatch'
        if not path_ok:
            return False, 'path_glob_mismatch'
        if not command_ok:
            return False, 'command_prefix_mismatch'
        return True, None

    def _active_grants_for(
        self, tool_name: str, *, permission_mode: str
    ) -> list[ApprovalGrant]:
        active: list[ApprovalGrant] = []
        for grant in self.list_grants():
            if grant.tool_name != tool_name or _grant_expired(grant):
                continue
            if (
                grant.permission_mode is not None
                and grant.permission_mode != permission_mode
            ):
                continue
            active.append(grant)
        return active

    def _build_arguments(
        self,
        arguments: dict[str, Any] | None,
        *,
        path: str | None = None,
        command: str | None = None,
    ) -> dict[str, Any]:
        args = dict(arguments or {})
        if path is not None:
            args['path'] = path
        if command is not None:
            args['command'] = command
        return args

    def _evaluate_grant_rows(
        self,
        active: list[ApprovalGrant],
        *,
        permission_mode: str,
        arguments: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for grant in active:
            matched, reason = self._grant_matches(
                grant, permission_mode=permission_mode, arguments=arguments
            )
            rows.append(
                {
                    'grant_id': grant.grant_id,
                    'scope': grant.scope,
                    'permission_mode': grant.permission_mode,
                    'matched': matched,
                    'reason': reason,
                    'path_globs': list(grant.path_globs),
                    'command_prefixes': list(grant.command_prefixes),
                }
            )
        return rows

    def _resolve_decision(
        self,
        tool_name: str,
        *,
        permission_mode: str,
        arguments: dict[str, Any],
        include_inactive: bool = False,
    ) -> tuple[ApprovalDecision, ApprovalGrant | None, list[dict[str, Any]]]:
        if include_inactive:
            # For explain, include all grants (including expired/mode-mismatched)
            all_grants = self.list_grants()
            tool_grants = [g for g in all_grants if g.tool_name == tool_name]
            evaluated = self._evaluate_grant_rows(
                tool_grants, permission_mode=permission_mode, arguments=arguments
            )
            # Decision logic still only considers active grants
            active = self._active_grants_for(tool_name, permission_mode=permission_mode)
        else:
            active = self._active_grants_for(tool_name, permission_mode=permission_mode)
            evaluated = self._evaluate_grant_rows(
                active, permission_mode=permission_mode, arguments=arguments
            )
        for grant in active:
            matched, _reason = self._grant_matches(
                grant, permission_mode=permission_mode, arguments=arguments
            )
            if grant.scope == 'deny' and matched:
                return 'deny', grant, evaluated
        for grant in active:
            matched, _reason = self._grant_matches(
                grant, permission_mode=permission_mode, arguments=arguments
            )
            if grant.scope == 'once' and matched:
                return 'allow', grant, evaluated
            matched, _reason = self._grant_matches(
                grant, permission_mode=permission_mode, arguments=arguments
            )
            if grant.scope == 'always' and matched:
                return 'allow', grant, evaluated
            matched, _reason = self._grant_matches(
                grant, permission_mode=permission_mode, arguments=arguments
            )
            if grant.scope == 'session' and matched:
                return 'allow', grant, evaluated
        return 'prompt', None, evaluated

    def check(
        self,
        tool_name: str,
        *,
        permission_mode: str,
        arguments: dict[str, Any] | None = None,
        path: str | None = None,
        command: str | None = None,
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        args = self._build_arguments(arguments, path=path, command=command)
        decision, matched, evaluated = self._resolve_decision(
            tool_name,
            permission_mode=permission_mode,
            arguments=args,
            include_inactive=include_inactive,
        )
        payload: dict[str, Any] = {
            'tool_name': tool_name,
            'permission_mode': permission_mode,
            'arguments': args,
            'allowed': decision == 'allow',
            'decision': decision,
            'policy_order': list(POLICY_ORDER),
            'evaluated_grants': evaluated,
            'matched_grant': matched.to_dict() if matched else None,
        }
        if matched is not None and matched.scope == 'once' and decision == 'allow':
            payload['note'] = (
                'once grants are consumed when the tool actually runs; '
                'check does not remove them'
            )
        return payload

    def is_allowed(
        self,
        tool_name: str,
        *,
        permission_mode: str,
        arguments: dict[str, Any] | None = None,
    ) -> bool:
        args = arguments or {}
        decision, matched, _evaluated = self._resolve_decision(
            tool_name, permission_mode=permission_mode, arguments=args
        )
        if decision == 'deny':
            return False
        if decision == 'allow' and matched is not None:
            if matched.scope == 'once':
                self._remove_grant(matched.grant_id)
                data = self._load()
                data['audit'].append(
                    {
                        'action': 'consume_once',
                        'grant_id': matched.grant_id,
                        'tool_name': matched.tool_name,
                        'created_at': datetime.now(timezone.utc).isoformat(),
                    }
                )
                self._save(data)
            return True
        return False

    def audit_tail(self, limit: int = 20) -> list[dict[str, Any]]:
        audit = self._load().get('audit', [])
        if not isinstance(audit, list):
            return []
        return [item for item in audit[-limit:] if isinstance(item, dict)]
