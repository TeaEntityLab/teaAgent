from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from teaagent.run_store import RunStore, RunSummary


def _parse_day(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except ValueError:
        return None


def list_yesterday_runs(root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    target = date.today() - timedelta(days=1)
    store = RunStore(root, readonly=True)
    results: list[dict[str, Any]] = []
    for summary in store.list_runs(limit=200):
        day = _parse_day(summary.created_at)
        if day == target:
            results.append(_enrich_summary(store, summary))
        if len(results) >= limit:
            break
    return results


def list_recall_runs(root: str | Path, *, limit: int = 5) -> list[dict[str, Any]]:
    store = RunStore(root, readonly=True)
    return [_enrich_summary(store, summary) for summary in store.list_runs(limit=limit)]


def _enrich_summary(store: RunStore, summary: RunSummary) -> dict[str, Any]:
    payload = summary.to_dict()
    try:
        payload['pending_approval'] = store.pending_approval_for_run(summary.run_id)
    except Exception:
        payload['pending_approval'] = None
    return payload
