from __future__ import annotations

import contextlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.ergonomics._approval_grants import _stable_grant_id

# Trust boundary: owner-only permissions on all .teaagent runtime state files
_TEAAGENT_DIR_MODE = 0o700
_TEAAGENT_FILE_MODE = 0o600


class ApprovalPersistence:
    def __init__(self, root: str | Path, *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.readonly = readonly

        teaagent_dir = self.root / '.teaagent'
        if not readonly:
            teaagent_dir.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(
                OSError
            ):  # best-effort; may fail on network/read-only fs
                teaagent_dir.chmod(_TEAAGENT_DIR_MODE)
        self.path = teaagent_dir / 'approvals.json'

    def _get_workspace_secret(self) -> bytes:
        """Load or generate the workspace-local HMAC secret.

        Raises IOError if the secret file exists but cannot be read or parsed,
        or if a newly-generated secret cannot be persisted to disk.  This
        prevents silent fall-through to ephemeral digests that would break
        subsequent resume exact-match checks.

        In readonly mode, only reads existing secret; raises IOError if missing.
        """
        import secrets

        secret_path = self.root / '.teaagent' / 'secret'
        if secret_path.is_file():
            try:
                secret_hex = secret_path.read_text(encoding='utf-8').strip()
            except OSError as exc:
                raise IOError(
                    f'Cannot read workspace secret from {secret_path}: {exc}. '
                    'Check file permissions or delete the file to regenerate.'
                ) from exc
            if len(secret_hex) != 64:
                raise IOError(
                    f'Workspace secret at {secret_path} is invalid '
                    f'(expected 64-hex, got {len(secret_hex)} chars). '
                    'Delete the file to regenerate a fresh secret.'
                )
            try:
                return bytes.fromhex(secret_hex)
            except ValueError as exc:
                raise IOError(
                    f'Workspace secret at {secret_path} is corrupt: {exc}. '
                    'Delete the file to regenerate.'
                ) from exc
        if self.readonly:
            raise IOError(
                f'Workspace secret does not exist at {secret_path} and store is in readonly mode. '
                'Cannot perform v2 scoped approval checks without a secret.'
            )
        # Generate and persist a fresh secret
        secret = secrets.token_bytes(32)
        try:
            secret_path.write_text(secret.hex(), encoding='utf-8')
            secret_path.chmod(_TEAAGENT_FILE_MODE)
        except OSError as exc:
            raise IOError(
                f'Cannot persist workspace secret to {secret_path}: {exc}. '
                'Ensure .teaagent/ is writable. Without a persistent secret, '
                'resume exact-match approval will not work across sessions.'
            ) from exc
        return secret

    def _get_workspace_key_id(self) -> str:
        """Return a stable 16-hex identifier derived from the first 8 bytes of the
        workspace secret.  Used to detect whether a scoped approval was signed with
        the same secret that is currently in use — without storing the secret itself
        or requiring the original arguments to re-derive the digest.
        """
        return self._get_workspace_secret().hex()[:16]

    def _load(self) -> dict[str, Any]:
        """Load approvals.json with fail-closed behavior.

        Raises IOError if the file is corrupt or unreadable. This prevents silent
        data loss and ensures explicit repair is required.
        """
        if not self.path.is_file():
            return {
                'grants': [],
                'audit': [],
                'approved_call_ids': [],
                'scoped_approvals': [],
            }
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise IOError(
                f'Cannot read approvals.json: {exc}. '
                'File is corrupt or unreadable. Use --repair-store to rebuild from backup.'
            ) from exc
        if not isinstance(data, dict):
            raise IOError(
                f'approvals.json has invalid structure (expected dict, got {type(data).__name__}). '
                'Use --repair-store to rebuild from backup.'
            )
        data.setdefault('grants', [])
        data.setdefault('audit', [])
        data.setdefault('approved_call_ids', [])
        data.setdefault('scoped_approvals', [])
        return data

    def repair_store(self, *, reset_healthy: bool = False) -> dict[str, Any]:
        """Explicitly rebuild the approvals.json store from a corrupt state.

        This method validates the store first and only repairs if corrupt or invalid.
        ``reset_healthy`` is reserved for explicit operator-requested resets of a
        validated store. It still backs up the current file and records a distinct
        audit action so healthy-store resets are reviewable after the fact.

        Args:
            reset_healthy: Rebuild a validated store only after the caller has
                received an explicit reset command from the user.

        Returns:
            dict with 'backup_path' (str | None), 'repaired' (bool), and 'status' (str)
        """
        # Validate store health first
        is_corrupt = False
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    is_corrupt = True
                else:
                    # Check required keys are lists
                    for key in (
                        'grants',
                        'audit',
                        'approved_call_ids',
                        'scoped_approvals',
                    ):
                        if key in data and not isinstance(data[key], list):
                            is_corrupt = True
                            break
            except (OSError, json.JSONDecodeError):
                is_corrupt = True

        if not is_corrupt and not reset_healthy:
            return {
                'backup_path': None,
                'repaired': False,
                'status': 'noop',
                'message': 'Store is healthy, no repair needed. Use --force-reset-store only for an explicit operator reset.',
            }

        backup_path = None
        if self.path.is_file():
            backup_path = str(
                self.path.with_suffix(
                    f'.json.backup.{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}.{time.time_ns()}'
                )
            )
            try:
                shutil.copy2(self.path, backup_path)
            except OSError as exc:
                raise IOError(
                    f'Cannot backup approvals.json to {backup_path}: {exc}. '
                    'Repair aborted.'
                ) from exc

        audit_action = (
            'store_operator_reset'
            if reset_healthy and not is_corrupt
            else 'store_repaired'
        )
        status = 'reset' if audit_action == 'store_operator_reset' else 'repaired'
        # Create fresh empty store
        fresh_data = {
            'grants': [],
            'audit': [
                {
                    'action': audit_action,
                    'backup_path': backup_path,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }
            ],
            'approved_call_ids': [],
            'scoped_approvals': [],
        }
        self._save(fresh_data)
        return {'backup_path': backup_path, 'repaired': True, 'status': status}

    def _save(self, data: dict[str, Any]) -> None:
        if self.readonly:
            raise IOError('Cannot save: ApprovalPresetStore is in readonly mode')

        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        with contextlib.suppress(
            OSError
        ):  # best-effort; permissions may already be correct
            self.path.chmod(_TEAAGENT_FILE_MODE)

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

    def audit_tail(self, limit: int = 20) -> list[dict[str, Any]]:
        audit = self._load().get('audit', [])
        if not isinstance(audit, list):
            return []
        return [item for item in audit[-limit:] if isinstance(item, dict)]

    def check_security_health(self, *, fix_permissions: bool = False) -> dict[str, Any]:
        """Run comprehensive security health checks on .teaagent runtime state.

        Args:
            fix_permissions: When True, attempt to apply the correct chmod values
                to any paths whose modes are wrong before reporting.  Equivalent
                to the ``approval doctor --fix-security`` flag.

        Returns a dict with 'ok' (bool), 'fixed_count' (int), 'verified_count' (int),
        and 'checks' list where each entry has:
          - name: str
          - ok: bool
          - severity: 'error' | 'warning' | 'info'
          - message: str
        """
        checks: list[dict[str, Any]] = []
        fixed_count = 0
        verified_count = 0
        teaagent_dir = self.root / '.teaagent'
        secret_path = teaagent_dir / 'secret'

        # 1. Check .teaagent directory permissions
        if teaagent_dir.exists():
            try:
                mode = teaagent_dir.stat().st_mode & 0o777
                if mode != _TEAAGENT_DIR_MODE:
                    if fix_permissions:
                        with contextlib.suppress(OSError):
                            teaagent_dir.chmod(_TEAAGENT_DIR_MODE)
                        mode = teaagent_dir.stat().st_mode & 0o777
                    if mode != _TEAAGENT_DIR_MODE:
                        checks.append(
                            {
                                'name': 'teaagent_dir_mode',
                                'ok': False,
                                'severity': 'error',
                                'message': (
                                    f'.teaagent/ has mode {oct(mode)}; expected {oct(_TEAAGENT_DIR_MODE)}. '
                                    f'Run: chmod {oct(_TEAAGENT_DIR_MODE)} {teaagent_dir}'
                                ),
                            }
                        )
                    else:
                        checks.append(
                            {
                                'name': 'teaagent_dir_mode',
                                'ok': True,
                                'severity': 'info',
                                'message': f'.teaagent/ fixed to {oct(mode)}',
                            }
                        )
                        fixed_count += 1
                else:
                    checks.append(
                        {
                            'name': 'teaagent_dir_mode',
                            'ok': True,
                            'severity': 'info',
                            'message': f'.teaagent/ has correct mode {oct(mode)}',
                        }
                    )
                    verified_count += 1
            except OSError as exc:
                checks.append(
                    {
                        'name': 'teaagent_dir_mode',
                        'ok': False,
                        'severity': 'error',
                        'message': f'Cannot stat .teaagent/: {exc}',
                    }
                )
        else:
            checks.append(
                {
                    'name': 'teaagent_dir_mode',
                    'ok': True,
                    'severity': 'info',
                    'message': '.teaagent/ does not exist yet (will be created on first use)',
                }
            )

        # 2. Check secret file
        if secret_path.exists():
            try:
                mode = secret_path.stat().st_mode & 0o777
                if mode != _TEAAGENT_FILE_MODE:
                    if fix_permissions:
                        with contextlib.suppress(OSError):
                            secret_path.chmod(_TEAAGENT_FILE_MODE)
                        mode = secret_path.stat().st_mode & 0o777
                    if mode != _TEAAGENT_FILE_MODE:
                        checks.append(
                            {
                                'name': 'secret_file_mode',
                                'ok': False,
                                'severity': 'error',
                                'message': (
                                    f'.teaagent/secret has mode {oct(mode)}; expected {oct(_TEAAGENT_FILE_MODE)}. '
                                    f'Run: chmod {oct(_TEAAGENT_FILE_MODE)} {secret_path}'
                                ),
                            }
                        )
                    else:
                        checks.append(
                            {
                                'name': 'secret_file_mode',
                                'ok': True,
                                'severity': 'info',
                                'message': f'.teaagent/secret fixed to {oct(mode)}',
                            }
                        )
                        fixed_count += 1
                else:
                    checks.append(
                        {
                            'name': 'secret_file_mode',
                            'ok': True,
                            'severity': 'info',
                            'message': f'.teaagent/secret has correct mode {oct(mode)}',
                        }
                    )
                    verified_count += 1
            except OSError as exc:
                checks.append(
                    {
                        'name': 'secret_file_mode',
                        'ok': False,
                        'severity': 'error',
                        'message': f'Cannot stat .teaagent/secret: {exc}',
                    }
                )
            # Validate secret content
            try:
                secret_hex = secret_path.read_text(encoding='utf-8').strip()
                if len(secret_hex) == 64:
                    try:
                        bytes.fromhex(secret_hex)
                        checks.append(
                            {
                                'name': 'secret_content',
                                'ok': True,
                                'severity': 'info',
                                'message': '.teaagent/secret is valid (64-hex HMAC key)',
                            }
                        )
                    except ValueError:
                        checks.append(
                            {
                                'name': 'secret_content',
                                'ok': False,
                                'severity': 'error',
                                'message': '.teaagent/secret contains non-hex data. Delete it to regenerate.',
                            }
                        )
                else:
                    checks.append(
                        {
                            'name': 'secret_content',
                            'ok': False,
                            'severity': 'error',
                            'message': (
                                f'.teaagent/secret has {len(secret_hex)} chars (expected 64). '
                                'Delete it to regenerate.'
                            ),
                        }
                    )
            except OSError as exc:
                checks.append(
                    {
                        'name': 'secret_content',
                        'ok': False,
                        'severity': 'error',
                        'message': f'Cannot read .teaagent/secret: {exc}',
                    }
                )
        else:
            checks.append(
                {
                    'name': 'secret_file_mode',
                    'ok': True,
                    'severity': 'info',
                    'message': '.teaagent/secret does not exist yet (will be created on first destructive approval)',
                }
            )
            checks.append(
                {
                    'name': 'secret_content',
                    'ok': True,
                    'severity': 'info',
                    'message': '.teaagent/secret not yet created',
                }
            )

        # 3. Check approvals.json permissions
        if self.path.exists():
            try:
                mode = self.path.stat().st_mode & 0o777
                if mode != _TEAAGENT_FILE_MODE:
                    if fix_permissions:
                        with contextlib.suppress(OSError):
                            self.path.chmod(_TEAAGENT_FILE_MODE)
                        mode = self.path.stat().st_mode & 0o777
                    if mode != _TEAAGENT_FILE_MODE:
                        checks.append(
                            {
                                'name': 'approvals_file_mode',
                                'ok': False,
                                'severity': 'error',
                                'message': (
                                    f'approvals.json has mode {oct(mode)}; expected {oct(_TEAAGENT_FILE_MODE)}. '
                                    f'Run: chmod {oct(_TEAAGENT_FILE_MODE)} {self.path}'
                                ),
                            }
                        )
                    else:
                        checks.append(
                            {
                                'name': 'approvals_file_mode',
                                'ok': True,
                                'severity': 'info',
                                'message': f'approvals.json fixed to {oct(mode)}',
                            }
                        )
                        fixed_count += 1
                else:
                    checks.append(
                        {
                            'name': 'approvals_file_mode',
                            'ok': True,
                            'severity': 'info',
                            'message': f'approvals.json has correct mode {oct(mode)}',
                        }
                    )
                    verified_count += 1
            except OSError as exc:
                checks.append(
                    {
                        'name': 'approvals_file_mode',
                        'ok': False,
                        'severity': 'error',
                        'message': f'Cannot stat approvals.json: {exc}',
                    }
                )

            # 3b. Check approvals.json content is valid
            try:
                raw = self.path.read_text(encoding='utf-8')
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    checks.append(
                        {
                            'name': 'approvals_file_content',
                            'ok': False,
                            'severity': 'error',
                            'message': (
                                f'approvals.json is not valid JSON: {exc}. '
                                'The file may be corrupt — back it up and delete to reset.'
                            ),
                        }
                    )
                else:
                    if not isinstance(parsed, dict):
                        checks.append(
                            {
                                'name': 'approvals_file_content',
                                'ok': False,
                                'severity': 'error',
                                'message': (
                                    f'approvals.json top-level must be a dict, got {type(parsed).__name__}. '
                                    'The file may be corrupt — back it up and delete to reset.'
                                ),
                            }
                        )
                    else:
                        bad_keys = [
                            k
                            for k in (
                                'grants',
                                'audit',
                                'approved_call_ids',
                                'scoped_approvals',
                            )
                            if k in parsed and not isinstance(parsed[k], list)
                        ]
                        if bad_keys:
                            checks.append(
                                {
                                    'name': 'approvals_file_content',
                                    'ok': False,
                                    'severity': 'error',
                                    'message': (
                                        f'approvals.json has non-list values for keys: {bad_keys}. '
                                        'The file structure is corrupt — back it up and delete to reset.'
                                    ),
                                    'bad_keys': bad_keys,
                                }
                            )
                        else:
                            checks.append(
                                {
                                    'name': 'approvals_file_content',
                                    'ok': True,
                                    'severity': 'info',
                                    'message': 'approvals.json content is structurally valid',
                                }
                            )
            except OSError as exc:
                checks.append(
                    {
                        'name': 'approvals_file_content',
                        'ok': False,
                        'severity': 'error',
                        'message': f'Cannot read approvals.json for content check: {exc}',
                    }
                )
        else:
            checks.append(
                {
                    'name': 'approvals_file_mode',
                    'ok': True,
                    'severity': 'info',
                    'message': 'approvals.json does not exist yet',
                }
            )
            checks.append(
                {
                    'name': 'approvals_file_content',
                    'ok': True,
                    'severity': 'info',
                    'message': 'approvals.json does not exist yet',
                }
            )

        # 4. Check for orphaned v2 approvals using key_id exact match.
        #    Read the secret only after finding active keyed v2 records. This keeps
        #    read-only doctor/check commands non-mutating and avoids warning on a
        #    fresh workspace with no approval state yet.
        try:
            data = self._load()
            now = datetime.now(timezone.utc)
            candidates = []
            for item in data.get('scoped_approvals', []):
                if not isinstance(item, dict):
                    continue
                if item.get('consumed_at'):
                    continue
                expires_at = item.get('expires_at')
                if expires_at:
                    try:
                        exp = datetime.fromisoformat(expires_at)
                        if exp.tzinfo is None:
                            exp = exp.replace(tzinfo=timezone.utc)
                        if now >= exp:
                            continue
                    except ValueError:
                        continue
                digest = item.get('argument_digest', '')
                record_key_id = item.get('key_id')
                if len(digest) == 64 and record_key_id:
                    candidates.append(item)
            current_key_id = self._get_workspace_key_id() if candidates else None
            orphaned = [
                item.get('record_id', '?')
                for item in candidates
                if item.get('key_id') != current_key_id
            ]
            if orphaned:
                checks.append(
                    {
                        'name': 'orphaned_v2_approvals',
                        'ok': False,
                        'severity': 'warning',
                        'message': (
                            f'{len(orphaned)} active v2 scoped approval(s) are orphaned '
                            'because the workspace secret was rotated after they were created. '
                            'They will be blocked on next resume — re-approve via HITL.'
                        ),
                        'orphaned_record_ids': orphaned,
                    }
                )
            else:
                checks.append(
                    {
                        'name': 'orphaned_v2_approvals',
                        'ok': True,
                        'severity': 'info',
                        'message': 'No orphaned v2 scoped approvals detected',
                    }
                )
        except IOError as exc:
            checks.append(
                {
                    'name': 'orphaned_v2_approvals',
                    'ok': False,
                    'severity': 'warning',
                    'message': f'Could not check for orphaned v2 approvals: {exc}',
                }
            )

        errors = [c for c in checks if not c['ok'] and c['severity'] == 'error']
        warnings = [c for c in checks if not c['ok'] and c['severity'] == 'warning']
        return {
            'ok': len(errors) == 0,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'fixed_count': fixed_count,
            'verified_count': verified_count,
            'checks': checks,
        }


__all__ = ['ApprovalPersistence', '_TEAAGENT_DIR_MODE', '_TEAAGENT_FILE_MODE']
