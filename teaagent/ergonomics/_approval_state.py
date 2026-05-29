from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from teaagent.ergonomics._approval_grants import (
    APPROVAL_TTL_HOURS,
    POLICY_ORDER,
    ApprovalDecision,
    ApprovalGrant,
    GrantScope,
    ScopedApprovalRecord,
    _command_matches,
    _compute_argument_digest,
    _compute_expires_at,
    _grant_expired,
    _new_grant_id,
    _new_record_id,
    _parse_grant,
    _path_matches,
    _stable_grant_id,
)
from teaagent.ergonomics._approval_persistence import ApprovalPersistence
from teaagent.storage import file_lock

_RootType = Union[ApprovalPersistence, str, Path]


class ApprovalPresetStore:
    def __init__(self, root: _RootType, *, readonly: bool = False) -> None:
        if isinstance(root, ApprovalPersistence):
            self._persist = root
        else:
            self._persist = ApprovalPersistence(root, readonly=readonly)

    @property
    def root(self) -> Path:
        return self._persist.root

    @property
    def readonly(self) -> bool:
        return self._persist.readonly

    @property
    def path(self) -> Path:
        return self._persist.path

    def _load(self) -> dict[str, Any]:
        return self._persist._load()

    def _save(self, data: dict[str, Any]) -> None:
        self._persist._save(data)

    def _get_workspace_secret(self) -> bytes:
        return self._persist._get_workspace_secret()

    def _get_workspace_key_id(self) -> str:
        return self._persist._get_workspace_key_id()

    def repair_store(self, *, reset_healthy: bool = False) -> dict[str, Any]:
        return self._persist.repair_store(reset_healthy=reset_healthy)

    def _migrate_missing_grant_ids(self) -> None:
        self._persist._migrate_missing_grant_ids()

    def audit_tail(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._persist.audit_tail(limit)

    def check_security_health(self, *, fix_permissions: bool = False) -> dict[str, Any]:
        return self._persist.check_security_health(fix_permissions=fix_permissions)

    def list_grants(self) -> list[ApprovalGrant]:
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
        return self._load()['approved_call_ids']

    def list_all_scoped_approvals(self) -> list[dict[str, Any]]:
        data = self._load()
        records = []
        now = datetime.now(timezone.utc)
        for item in data.get('scoped_approvals', []):
            if not isinstance(item, dict):
                continue
            rec = dict(item)
            if rec.get('consumed_at'):
                rec['status'] = 'consumed'
            elif rec.get('expires_at'):
                try:
                    expires = datetime.fromisoformat(rec['expires_at'])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if now >= expires:
                        rec['status'] = 'expired'
                    else:
                        rec['status'] = 'active'
                except ValueError:
                    rec['status'] = 'active'
            else:
                rec['status'] = 'active'
            records.append(rec)
        return records

    def prune_scoped_approvals(self) -> int:
        data = self._load()
        now = datetime.now(timezone.utc)

        pruned = []
        keep = []
        for item in data.get('scoped_approvals', []):
            if not isinstance(item, dict):
                continue
            should_prune = False
            if item.get('consumed_at'):
                should_prune = True
            elif item.get('expires_at'):
                try:
                    expires = datetime.fromisoformat(item['expires_at'])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if now >= expires:
                        should_prune = True
                except ValueError:
                    should_prune = True

            if should_prune:
                pruned.append(item.get('record_id', 'unknown'))
            else:
                keep.append(item)

        if len(pruned) > 0:
            data['scoped_approvals'] = keep
            data['audit'].append(
                {
                    'action': 'prune_scoped_approvals',
                    'pruned_record_ids': pruned,
                    'created_at': now.isoformat(),
                }
            )
            self._save(data)
        return len(pruned)

    def clear_legacy_approved_call_ids(self) -> int:
        data = self._load()
        original_ids = data.get('approved_call_ids', [])
        count = len(original_ids)
        if count > 0:
            data['approved_call_ids'] = []
            data['audit'].append(
                {
                    'action': 'clear_legacy_approved_call_ids',
                    'cleared_call_ids': list(original_ids),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }
            )
            self._save(data)
        return count

    def add_scoped_approval(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        ttl_hours: float | None = None,
        argument_digest: Optional[str] = None,
    ) -> ScopedApprovalRecord:
        now = datetime.now(timezone.utc).isoformat()
        expires_at = None
        if ttl_hours is None:
            ttl_hours = APPROVAL_TTL_HOURS
        if ttl_hours > 0:
            created = datetime.fromisoformat(now)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            expires_at = (created + timedelta(hours=ttl_hours)).isoformat()

        if argument_digest is None:
            secret = self._get_workspace_secret()
            argument_digest = _compute_argument_digest(arguments, secret)

        key_id = (
            self._get_workspace_key_id()
            if argument_digest and len(argument_digest) == 64
            else None
        )

        record = ScopedApprovalRecord(
            record_id=_new_record_id(),
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            argument_digest=argument_digest,
            created_at=now,
            expires_at=expires_at,
            key_id=key_id,
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
        data = self._load()
        records: list[ScopedApprovalRecord] = []
        for item in data.get('scoped_approvals', []):
            if not isinstance(item, dict):
                continue
            if item.get('run_id') != run_id:
                continue
            if item.get('consumed_at'):
                continue
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
                    key_id=item.get('key_id'),
                )
            )
        return records

    def consume_scoped_approval(self, record_id: str) -> bool:
        with file_lock(self.path):
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

    def try_consume_scoped_approval(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Atomically match and consume a scoped approval under file lock."""
        secret = self._get_workspace_secret()
        argument_digest_v2 = _compute_argument_digest(arguments, secret)
        argument_digest_v1 = _compute_argument_digest(arguments)
        with file_lock(self.path):
            data = self._load()
            now = datetime.now(timezone.utc)
            for item in data.get('scoped_approvals', []):
                if not isinstance(item, dict):
                    continue
                if item.get('run_id') != run_id:
                    continue
                if item.get('consumed_at'):
                    continue
                if item.get('expires_at'):
                    try:
                        expires = datetime.fromisoformat(item['expires_at'])
                        if expires.tzinfo is None:
                            expires = expires.replace(tzinfo=timezone.utc)
                        if now >= expires:
                            continue
                    except ValueError:
                        continue
                if (
                    item.get('call_id') == call_id
                    and item.get('tool_name') == tool_name
                    and item.get('argument_digest')
                    in (argument_digest_v2, argument_digest_v1)
                ):
                    item['consumed_at'] = now.isoformat()
                    data['audit'].append(
                        {
                            'action': 'consume_scoped_approval',
                            'record_id': item.get('record_id'),
                            'consumed_at': item['consumed_at'],
                        }
                    )
                    self._save(data)
                    return True
            return False

    def check_scoped_approval(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ScopedApprovalRecord | None:
        secret = self._get_workspace_secret()
        argument_digest_v2 = _compute_argument_digest(arguments, secret)
        argument_digest_v1 = _compute_argument_digest(arguments)
        for record in self.list_scoped_approvals_for_run(run_id):
            if (
                record.call_id == call_id
                and record.tool_name == tool_name
                and record.argument_digest in (argument_digest_v2, argument_digest_v1)
            ):
                return record
        return None

    def check_scoped_approval_digest(
        self,
        run_id: str,
        call_id: str,
        tool_name: str,
        argument_digest: str,
    ) -> ScopedApprovalRecord | None:
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
        self._migrate_missing_grant_ids()
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
            all_grants = self.list_grants()
            tool_grants = [g for g in all_grants if g.tool_name == tool_name]
            evaluated = self._evaluate_grant_rows(
                tool_grants, permission_mode=permission_mode, arguments=arguments
            )
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


__all__ = ['ApprovalPresetStore']
