"""Runtime and cost cap enforcement for automation background runs."""

from __future__ import annotations

import os
import signal
from datetime import datetime, timezone
from typing import Any, Optional

from teaagent.automations import AutomationSpec
from teaagent.ergonomics.daily_cost import estimate_run_cost_cents
from teaagent.run_store import RunStore


def _parse_started_at(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except ValueError:
        return None


def background_runtime_seconds(background: dict[str, Any]) -> Optional[float]:
    started_at = background.get('started_at')
    if not isinstance(started_at, str):
        return None
    started = _parse_started_at(started_at)
    if started is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - started).total_seconds())


def terminate_background_pid(pid: int) -> bool:
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError:
        return False
    return True


def enforce_runtime_cap(
    background: dict[str, Any], *, max_runtime_seconds: int
) -> bool:
    """Terminate a live background worker when it exceeds max_runtime_seconds."""
    if max_runtime_seconds <= 0 or not background.get('alive'):
        return False
    elapsed = background_runtime_seconds(background)
    if elapsed is None or elapsed <= max_runtime_seconds:
        return False
    pid = background.get('pid')
    if isinstance(pid, int):
        terminate_background_pid(pid)
    elif isinstance(pid, str) and pid.isdigit():
        terminate_background_pid(int(pid))
    return True


def automation_run_cost_cents(root: str, run_id: str) -> float:
    events = RunStore(root).show_run(run_id)
    return estimate_run_cost_cents(events)


def cost_cap_exceeded(
    root: str,
    spec: AutomationSpec,
    *,
    run_id: str,
) -> bool:
    if spec.max_cost_cents <= 0:
        return False
    spent = automation_run_cost_cents(root, run_id)
    return spent > float(spec.max_cost_cents)
