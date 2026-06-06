"""Audit durability and chain health reporting (WS4-003)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.audit_chain import verify_audit_chain


def _event_type(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get('event_type', ''))
    return str(getattr(event, 'event_type', ''))


@dataclass(frozen=True)
class AuditDurabilityHealth:
    disk_write_errors: int
    chain_valid: bool | None
    chain_error: str | None
    cooldown_active: bool
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            'disk_write_errors': self.disk_write_errors,
            'chain_valid': self.chain_valid,
            'chain_error': self.chain_error,
            'cooldown_active': self.cooldown_active,
            'event_count': self.event_count,
        }


def assess_audit_health(
    events: list[dict[str, Any]],
    *,
    log_path: Path | None = None,
    live_logger: AuditLogger | None = None,
) -> AuditDurabilityHealth:
    disk_errors = sum(
        1 for event in events if _event_type(event) == '_disk_write_error'
    )
    chain_valid: bool | None = None
    chain_error: str | None = None
    event_count = len(events)
    if log_path is not None and log_path.is_file():
        result = verify_audit_chain(log_path)
        chain_valid = result.valid
        chain_error = result.error
        event_count = result.event_count

    cooldown_active = live_logger is not None and live_logger.disk_error is not None
    return AuditDurabilityHealth(
        disk_write_errors=disk_errors,
        chain_valid=chain_valid,
        chain_error=chain_error,
        cooldown_active=cooldown_active,
        event_count=event_count,
    )


def format_audit_health(health: AuditDurabilityHealth) -> str:
    lines = ['Audit durability:']
    if health.chain_valid is None:
        lines.append('  Chain: not verified')
    elif health.chain_valid:
        lines.append(f'  Chain: valid ({health.event_count} events)')
    else:
        lines.append(f'  Chain: INVALID — {health.chain_error}')
    if health.disk_write_errors:
        lines.append(f'  Disk write errors recorded: {health.disk_write_errors}')
    if health.cooldown_active:
        lines.append('  Cooldown: active (disk writes suppressed)')
    else:
        lines.append('  Cooldown: inactive')
    return '\n'.join(lines)
