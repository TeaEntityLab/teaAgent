"""Durable run liveness files for background and cross-surface status."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.run_store import safe_run_id
from teaagent.storage import atomic_write_text

DEFAULT_LIVENESS_STALE_SECONDS = 90.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def liveness_path(root: str | Path, run_id: str) -> Path:
    return (
        Path(root).resolve() / '.teaagent' / 'liveness' / f'{safe_run_id(run_id)}.json'
    )


def touch_liveness(
    root: str | Path,
    run_id: str,
    *,
    tick: int,
    interval_seconds: float,
) -> None:
    """Persist a heartbeat tick for observers that cannot rely on PID liveness."""
    path = liveness_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'run_id': run_id,
        'tick': tick,
        'interval_seconds': interval_seconds,
        'updated_at': _utc_now(),
    }
    atomic_write_text(path, json.dumps(payload, sort_keys=True))


def clear_liveness(root: str | Path, run_id: str) -> None:
    path = liveness_path(root, run_id)
    if path.is_file():
        path.unlink()


def liveness_snapshot(
    root: str | Path,
    run_id: str,
    *,
    stale_after_seconds: float = DEFAULT_LIVENESS_STALE_SECONDS,
) -> dict[str, Any] | None:
    path = liveness_path(root, run_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    updated_raw = data.get('updated_at')
    if not isinstance(updated_raw, str):
        return None
    try:
        updated = datetime.fromisoformat(updated_raw)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    age_seconds = (datetime.now(timezone.utc) - updated).total_seconds()
    return {
        'updated_at': updated_raw,
        'tick': data.get('tick'),
        'interval_seconds': data.get('interval_seconds'),
        'age_seconds': round(age_seconds, 3),
        'stale': age_seconds > stale_after_seconds,
    }
