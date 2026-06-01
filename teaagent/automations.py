from __future__ import annotations

import builtins
import contextlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.storage import atomic_write_text, file_lock

_SCHEDULE_EVERY_RE = re.compile(r'^every\s+(\d+)([mh])$')
_SCHEDULE_DAILY_RE = re.compile(r'^daily\s+(\d{2}):(\d{2})$')


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(frozen=True)
class AutomationSpec:
    automation_id: str
    name: str
    task: str
    schedule: str
    provider: Optional[str] = None
    model: Optional[str] = None
    permission_mode: str = 'read-only'
    context_profile: str = 'balanced'
    enabled: bool = True
    max_iterations: int = 10
    max_tool_calls: int = 10
    next_run_at: Optional[str] = None
    last_run_id: Optional[str] = None
    last_status: Optional[str] = None
    running_background_id: Optional[str] = None
    auto_propose_skill: bool = False
    selected_skills: tuple[str, ...] = ()
    acceptance_criteria: str = ''
    collector_command: str = ''
    collector_command_digest: str = ''
    no_agent: bool = False
    allowed_toolsets: tuple[str, ...] = ()
    requires_subagent: bool = False
    max_cost_cents: int = 0
    max_runtime_seconds: int = 0
    delivery: str = 'background_log'
    context_from: str = ''
    provenance_digest: str = ''
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'AutomationSpec':
        return cls(
            automation_id=str(payload.get('automation_id', '')).strip(),
            name=str(payload.get('name', '')).strip(),
            task=str(payload.get('task', '')).strip(),
            schedule=str(payload.get('schedule', '')).strip(),
            provider=(
                str(payload.get('provider')).strip()
                if payload.get('provider') is not None
                else None
            ),
            model=(
                str(payload.get('model')).strip()
                if payload.get('model') is not None
                else None
            ),
            permission_mode=str(payload.get('permission_mode', 'read-only')),
            context_profile=str(payload.get('context_profile', 'balanced')),
            enabled=bool(payload.get('enabled', True)),
            max_iterations=int(payload.get('max_iterations', 10)),
            max_tool_calls=int(payload.get('max_tool_calls', 10)),
            next_run_at=(
                str(payload.get('next_run_at')).strip()
                if payload.get('next_run_at') is not None
                else None
            ),
            last_run_id=(
                str(payload.get('last_run_id')).strip()
                if payload.get('last_run_id') is not None
                else None
            ),
            last_status=(
                str(payload.get('last_status')).strip()
                if payload.get('last_status') is not None
                else None
            ),
            running_background_id=(
                str(payload.get('running_background_id')).strip()
                if payload.get('running_background_id') is not None
                else None
            ),
            auto_propose_skill=bool(payload.get('auto_propose_skill', False)),
            selected_skills=_parse_selected_skills(payload.get('selected_skills')),
            acceptance_criteria=str(payload.get('acceptance_criteria', '')).strip(),
            collector_command=str(payload.get('collector_command', '')).strip(),
            collector_command_digest=str(
                payload.get('collector_command_digest', '')
            ).strip(),
            no_agent=bool(payload.get('no_agent', False)),
            allowed_toolsets=_parse_selected_skills(payload.get('allowed_toolsets')),
            requires_subagent=bool(payload.get('requires_subagent', False)),
            max_cost_cents=int(payload.get('max_cost_cents', 0) or 0),
            max_runtime_seconds=int(payload.get('max_runtime_seconds', 0) or 0),
            delivery=str(payload.get('delivery', 'background_log')).strip()
            or 'background_log',
            context_from=str(payload.get('context_from', '')).strip(),
            provenance_digest=str(payload.get('provenance_digest', '')).strip(),
            created_at=str(payload.get('created_at', '')),
            updated_at=str(payload.get('updated_at', '')),
        )


def _parse_selected_skills(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        return ()
    names = [str(item).strip() for item in raw if str(item).strip()]
    return tuple(names)


def compute_next_run_at(schedule: str, *, now: Optional[datetime] = None) -> str:
    current = now or utc_now()
    normalized = schedule.strip().lower()
    every = _SCHEDULE_EVERY_RE.fullmatch(normalized)
    if every:
        amount = int(every.group(1))
        unit = every.group(2)
        delta = timedelta(minutes=amount) if unit == 'm' else timedelta(hours=amount)
        return iso_utc(current + delta)
    daily = _SCHEDULE_DAILY_RE.fullmatch(normalized)
    if daily:
        hh = int(daily.group(1))
        mm = int(daily.group(2))
        candidate = current.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= current:
            candidate = candidate + timedelta(days=1)
        return iso_utc(candidate)
    raise ValueError(
        "unsupported schedule; use 'every 30m', 'every 2h', or 'daily HH:MM'"
    )


class AutomationStore:
    def __init__(self, root: str | Path = '.', *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.dir = self.root / '.teaagent' / 'automations'
        self.quarantine_dir = self.root / '.teaagent' / 'automations-quarantine'
        self.readonly = readonly
        if not readonly:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _spec_path(self, automation_id: str) -> Path:
        return self.dir / f'{automation_id}.json'

    def _quarantine_path(self, automation_id: str) -> Path:
        return self.quarantine_dir / f'{automation_id}.json'

    def list(self) -> list[AutomationSpec]:
        specs: list[AutomationSpec] = []
        for path in sorted(self.dir.glob('*.json')):
            if path.name.startswith('.'):
                continue
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            spec = AutomationSpec.from_dict(payload)
            if spec.automation_id:
                specs.append(spec)
        return sorted(specs, key=lambda s: s.created_at, reverse=True)

    def show(self, automation_id: str) -> AutomationSpec:
        path = self._spec_path(automation_id)
        if not path.exists():
            raise FileNotFoundError(f"automation '{automation_id}' not found")
        payload = json.loads(path.read_text(encoding='utf-8'))
        return AutomationSpec.from_dict(payload)

    def draft(
        self,
        *,
        name: str,
        task: str,
        schedule: str,
        provider: Optional[str],
        model: Optional[str],
        permission_mode: str,
        context_profile: str,
        max_iterations: int,
        max_tool_calls: int,
        auto_propose_skill: bool = False,
        selected_skills: Optional[builtins.list[str]] = None,
        acceptance_criteria: str = '',
        collector_command: str = '',
        collector_command_digest: str = '',
        no_agent: bool = False,
        allowed_toolsets: Optional[builtins.list[str]] = None,
        requires_subagent: bool = False,
        max_cost_cents: int = 0,
        max_runtime_seconds: int = 0,
        delivery: str = 'background_log',
        context_from: str = '',
        provenance_digest: str = '',
        enabled: bool = True,
    ) -> AutomationSpec:
        if not name.strip():
            raise ValueError('automation name cannot be empty')
        if not task.strip():
            raise ValueError('automation task cannot be empty')
        next_run_at = compute_next_run_at(schedule) if enabled else None
        now = iso_utc(utc_now())
        return AutomationSpec(
            automation_id=uuid4().hex,
            name=name.strip(),
            task=task.strip(),
            schedule=schedule.strip(),
            provider=provider,
            model=model,
            permission_mode=permission_mode,
            context_profile=context_profile,
            enabled=enabled,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            next_run_at=next_run_at,
            auto_propose_skill=auto_propose_skill,
            selected_skills=tuple(selected_skills or ()),
            acceptance_criteria=acceptance_criteria.strip(),
            collector_command=collector_command.strip(),
            collector_command_digest=collector_command_digest.strip(),
            no_agent=no_agent,
            allowed_toolsets=tuple(allowed_toolsets or ()),
            requires_subagent=requires_subagent,
            max_cost_cents=max_cost_cents,
            max_runtime_seconds=max_runtime_seconds,
            delivery=delivery.strip() or 'background_log',
            context_from=context_from.strip(),
            provenance_digest=provenance_digest.strip(),
            created_at=now,
            updated_at=now,
        )

    def create(
        self,
        *,
        name: str,
        task: str,
        schedule: str,
        provider: Optional[str],
        model: Optional[str],
        permission_mode: str,
        context_profile: str,
        max_iterations: int,
        max_tool_calls: int,
        auto_propose_skill: bool = False,
        selected_skills: Optional[builtins.list[str]] = None,
        acceptance_criteria: str = '',
        collector_command: str = '',
        collector_command_digest: str = '',
        no_agent: bool = False,
        allowed_toolsets: Optional[builtins.list[str]] = None,
        requires_subagent: bool = False,
        max_cost_cents: int = 0,
        max_runtime_seconds: int = 0,
        delivery: str = 'background_log',
        context_from: str = '',
        provenance_digest: str = '',
    ) -> AutomationSpec:
        if self.readonly:
            raise RuntimeError('Cannot create automation in readonly mode')
        spec = self.draft(
            name=name,
            task=task,
            schedule=schedule,
            provider=provider,
            model=model,
            permission_mode=permission_mode,
            context_profile=context_profile,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            auto_propose_skill=auto_propose_skill,
            selected_skills=selected_skills,
            acceptance_criteria=acceptance_criteria,
            collector_command=collector_command,
            collector_command_digest=collector_command_digest,
            no_agent=no_agent,
            allowed_toolsets=allowed_toolsets,
            requires_subagent=requires_subagent,
            max_cost_cents=max_cost_cents,
            max_runtime_seconds=max_runtime_seconds,
            delivery=delivery,
            context_from=context_from,
            provenance_digest=provenance_digest,
            enabled=True,
        )
        if spec.collector_command.strip() and not spec.collector_command_digest:
            from teaagent.automation_collector import compute_collector_command_digest

            collector_digest, _errors = compute_collector_command_digest(
                spec.collector_command,
                root=self.root,
            )
            spec = AutomationSpec(
                **{**spec.to_dict(), 'collector_command_digest': collector_digest}
            )
        if not spec.provenance_digest:
            from teaagent.automation_ticket import compute_automation_provenance_digest

            spec = AutomationSpec(
                **{
                    **spec.to_dict(),
                    'provenance_digest': compute_automation_provenance_digest(spec),
                }
            )
        atomic_write_text(
            self._spec_path(spec.automation_id), json.dumps(spec.to_dict())
        )
        return spec

    def create_quarantined(
        self,
        spec: AutomationSpec,
        *,
        provenance: dict[str, Any],
    ) -> AutomationSpec:
        if self.readonly:
            raise RuntimeError('Cannot create quarantined automation in readonly mode')
        payload = {
            **spec.to_dict(),
            'enabled': False,
            'quarantine': True,
            'provenance': provenance,
        }
        atomic_write_text(
            self._quarantine_path(spec.automation_id), json.dumps(payload)
        )
        return spec

    def list_quarantined(self) -> builtins.list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.quarantine_dir.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get('automation_id'):
                rows.append(payload)
        return sorted(
            rows, key=lambda row: str(row.get('created_at', '')), reverse=True
        )

    def show_quarantined(self, automation_id: str) -> dict[str, Any]:
        path = self._quarantine_path(automation_id)
        if not path.exists():
            raise FileNotFoundError(
                f"quarantined automation '{automation_id}' not found"
            )
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError(f"invalid quarantine payload for '{automation_id}'")
        return payload

    def promote_quarantined(
        self,
        automation_id: str,
        *,
        attested: bool = False,
    ) -> AutomationSpec:
        if self.readonly:
            raise RuntimeError('Cannot promote quarantined automation in readonly mode')
        payload = dict(self.show_quarantined(automation_id))
        provenance = payload.pop('provenance', None)
        payload.pop('quarantine', None)
        spec = AutomationSpec.from_dict(payload)
        from teaagent.automation_ticket import compute_automation_provenance_digest

        expected_digest = compute_automation_provenance_digest(spec)
        if spec.provenance_digest and spec.provenance_digest != expected_digest:
            raise ValueError(
                'quarantined automation provenance_digest does not match payload; '
                'review the candidate and recreate it'
            )
        if isinstance(provenance, dict):
            content_digest = str(provenance.get('content_digest', '')).strip()
            if content_digest and content_digest != expected_digest:
                raise ValueError(
                    'quarantined automation provenance content_digest does not match '
                    'payload; review the candidate and recreate it'
                )
            source_kind = str(provenance.get('source_kind', '')).strip()
            if (
                source_kind == 'web_message'
                and not attested
                and not provenance.get('attested')
            ):
                raise ValueError(
                    'quarantined automation from web_message requires '
                    '--i-attest-untrusted-write after human review'
                )
        if self._spec_path(automation_id).exists():
            raise ValueError(
                f"active automation '{automation_id}' already exists; delete it first"
            )
        promoted = AutomationSpec(
            **{
                **spec.to_dict(),
                'enabled': True,
                'next_run_at': compute_next_run_at(spec.schedule),
                'updated_at': iso_utc(utc_now()),
            }
        )
        atomic_write_text(
            self._spec_path(automation_id), json.dumps(promoted.to_dict())
        )
        self._quarantine_path(automation_id).unlink(missing_ok=True)
        return promoted

    def delete(self, automation_id: str) -> None:
        if self.readonly:
            raise RuntimeError('Cannot delete automation in readonly mode')
        path = self._spec_path(automation_id)
        quarantine_path = self._quarantine_path(automation_id)
        if path.exists():
            path.unlink()
            return
        if quarantine_path.exists():
            quarantine_path.unlink(missing_ok=True)
            return
        raise FileNotFoundError(f"automation '{automation_id}' not found")

    def update(self, spec: AutomationSpec) -> AutomationSpec:
        if self.readonly:
            raise RuntimeError('Cannot update automation in readonly mode')
        updated = AutomationSpec(**{**spec.to_dict(), 'updated_at': iso_utc(utc_now())})
        atomic_write_text(
            self._spec_path(spec.automation_id), json.dumps(updated.to_dict())
        )
        return updated

    def set_enabled(self, automation_id: str, enabled: bool) -> AutomationSpec:
        if self.readonly:
            raise RuntimeError('Cannot set enabled in readonly mode')
        spec = self.show(automation_id)
        next_run_at = spec.next_run_at
        if enabled and not next_run_at:
            next_run_at = compute_next_run_at(spec.schedule)
        updated = AutomationSpec(
            **{**spec.to_dict(), 'enabled': enabled, 'next_run_at': next_run_at}
        )
        return self.update(updated)

    def renew_automation(
        self, automation_id: str, *, ttl_seconds: Optional[float] = None
    ) -> AutomationSpec:
        """Renew an automation by updating its next_run_at."""
        if self.readonly:
            raise RuntimeError('Cannot renew in readonly mode')
        spec = self.show(automation_id)
        next_run = compute_next_run_at(spec.schedule)
        updated = AutomationSpec(
            **{**spec.to_dict(), 'next_run_at': next_run, 'updated_at': utc_now()}
        )
        return self.update(updated)

    def expire_automation(self, automation_id: str) -> AutomationSpec:
        """Expire an automation by disabling it and clearing next_run_at."""
        if self.readonly:
            raise RuntimeError('Cannot expire in readonly mode')
        spec = self.show(automation_id)
        updated = AutomationSpec(
            **{
                **spec.to_dict(),
                'enabled': False,
                'next_run_at': None,
                'updated_at': utc_now(),
            }
        )
        return self.update(updated)

    def transfer_ownership(self, automation_id: str, new_owner: str) -> AutomationSpec:
        """Transfer ownership of an automation (adds provenance note)."""
        if self.readonly:
            raise RuntimeError('Cannot transfer ownership in readonly mode')
        spec = self.show(automation_id)
        provenance = spec.provenance_digest or ''
        transfer_note = f'ownership_transfer_to={new_owner};transferred_at={utc_now()}'
        new_provenance = (
            f'{provenance}|{transfer_note}' if provenance else transfer_note
        )
        updated = AutomationSpec(
            **{
                **spec.to_dict(),
                'provenance_digest': new_provenance,
                'updated_at': utc_now(),
            }
        )
        return self.update(updated)

    def review_automation(
        self, automation_id: str, *, review_notes: str = ''
    ) -> AutomationSpec:
        """Add review notes to an automation's acceptance criteria."""
        if self.readonly:
            raise RuntimeError('Cannot review in readonly mode')
        spec = self.show(automation_id)
        current_criteria = spec.acceptance_criteria or ''
        new_criteria = (
            f'{current_criteria}\n\nReview: {review_notes}'
            if review_notes
            else current_criteria
        )
        updated = AutomationSpec(
            **{
                **spec.to_dict(),
                'acceptance_criteria': new_criteria,
                'updated_at': utc_now(),
            }
        )
        return self.update(updated)

    def explain_skip(self, automation_id: str, *, skip_reason: str) -> AutomationSpec:
        """Explain why an automation was skipped (adds to acceptance criteria)."""
        if self.readonly:
            raise RuntimeError('Cannot explain skip in readonly mode')
        spec = self.show(automation_id)
        current_criteria = spec.acceptance_criteria or ''
        skip_note = f'\n\nSkip Reason: {skip_reason} (at {utc_now()})'
        new_criteria = f'{current_criteria}{skip_note}'
        updated = AutomationSpec(
            **{
                **spec.to_dict(),
                'acceptance_criteria': new_criteria,
                'updated_at': utc_now(),
            }
        )
        return self.update(updated)

    def due(self, *, now: Optional[datetime] = None) -> builtins.list[AutomationSpec]:
        current = now or utc_now()
        ready: builtins.list[AutomationSpec] = []
        for spec in self.list():
            if not spec.enabled or not spec.next_run_at:
                continue
            try:
                due_at = parse_utc(spec.next_run_at)
            except ValueError:
                continue
            if due_at <= current:
                ready.append(spec)
        return ready


def build_automation_status(
    root: str | Path,
    *,
    store: Optional[AutomationStore] = None,
    readonly: bool = True,
) -> dict[str, Any]:
    """Summarize automation health for CLI status output."""
    from teaagent.automation_observability import enrich_automation_status_row
    from teaagent.ergonomics.background_run import BackgroundRunStore

    automation_store = store or AutomationStore(root, readonly=readonly)
    bg_store = BackgroundRunStore(root, readonly=readonly)
    rows: list[dict[str, Any]] = []
    for spec in automation_store.list():
        log_tail = ''
        if spec.running_background_id:
            with contextlib.suppress(FileNotFoundError, OSError):
                bg = bg_store.get(spec.running_background_id)
                log_path = bg.get('log_path')
                if isinstance(log_path, str):
                    path = Path(log_path)
                    if path.is_file():
                        lines = path.read_text(
                            encoding='utf-8', errors='replace'
                        ).splitlines()
                        log_tail = '\n'.join(lines[-20:])
        rows.append(enrich_automation_status_row(root, spec, log_tail=log_tail))
    enabled = [row for row in rows if row['enabled']]
    due = automation_store.due()
    running = [row for row in rows if row['running_background_id']]
    quarantined = automation_store.list_quarantined()
    return {
        'automation_count': len(rows),
        'enabled_count': len(enabled),
        'due_count': len(due),
        'running_count': len(running),
        'quarantined_count': len(quarantined),
        'automations': rows,
        'quarantined': quarantined,
    }


class AutomationTickLock:
    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self.path = self.root / '.teaagent' / 'automations' / '.tick'

    def __enter__(self) -> None:
        self._cm = file_lock(self.path)
        self._cm.__enter__()
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._cm.__exit__(exc_type, exc, tb)
