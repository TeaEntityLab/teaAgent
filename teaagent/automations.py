from __future__ import annotations

import builtins
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
    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self.dir = self.root / '.teaagent' / 'automations'
        self.dir.mkdir(parents=True, exist_ok=True)

    def _spec_path(self, automation_id: str) -> Path:
        return self.dir / f'{automation_id}.json'

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
    ) -> AutomationSpec:
        if not name.strip():
            raise ValueError('automation name cannot be empty')
        if not task.strip():
            raise ValueError('automation task cannot be empty')
        next_run_at = compute_next_run_at(schedule)
        now = iso_utc(utc_now())
        spec = AutomationSpec(
            automation_id=uuid4().hex,
            name=name.strip(),
            task=task.strip(),
            schedule=schedule.strip(),
            provider=provider,
            model=model,
            permission_mode=permission_mode,
            context_profile=context_profile,
            enabled=True,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            next_run_at=next_run_at,
            auto_propose_skill=auto_propose_skill,
            selected_skills=tuple(selected_skills or ()),
            acceptance_criteria=acceptance_criteria.strip(),
            created_at=now,
            updated_at=now,
        )
        atomic_write_text(
            self._spec_path(spec.automation_id), json.dumps(spec.to_dict())
        )
        return spec

    def delete(self, automation_id: str) -> None:
        path = self._spec_path(automation_id)
        if not path.exists():
            raise FileNotFoundError(f"automation '{automation_id}' not found")
        path.unlink()

    def update(self, spec: AutomationSpec) -> AutomationSpec:
        updated = AutomationSpec(**{**spec.to_dict(), 'updated_at': iso_utc(utc_now())})
        atomic_write_text(
            self._spec_path(spec.automation_id), json.dumps(updated.to_dict())
        )
        return updated

    def set_enabled(self, automation_id: str, enabled: bool) -> AutomationSpec:
        spec = self.show(automation_id)
        next_run_at = spec.next_run_at
        if enabled and not next_run_at:
            next_run_at = compute_next_run_at(spec.schedule)
        updated = AutomationSpec(
            **{**spec.to_dict(), 'enabled': enabled, 'next_run_at': next_run_at}
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
