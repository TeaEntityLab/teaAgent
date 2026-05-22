from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from teaagent.llm import estimate_cost_preflight
from teaagent.run_store import RunStore


def estimate_run_cost_cents(events: list[dict[str, Any]]) -> float:
    """Rough same-day cost rollup from audit events (preflight estimate per run)."""
    provider = 'gpt'
    model = 'default'
    for event in events:
        payload = event.get('payload') or {}
        if event.get('event_type') == 'run_started':
            if isinstance(payload.get('provider'), str):
                provider = payload['provider']
            if isinstance(payload.get('model'), str) and payload.get('model'):
                model = payload['model']
    try:
        return float(
            estimate_cost_preflight(
                provider,
                model,
                approx_input_chars=12_000,
                max_output_tokens=2048,
            )
        )
    except Exception:
        return 0.0


def daily_spend_cents(root: str | Path) -> float:
    store = RunStore(root)
    today = date.today()
    total = 0.0
    for summary in store.list_runs(limit=100):
        try:
            day = date.fromisoformat(summary.created_at[:10])
        except ValueError:
            continue
        if day != today:
            continue
        events = store.show_run(summary.run_id)
        total += estimate_run_cost_cents(events)
    return total


def check_daily_cost_cap(root: str | Path, cap_cents: int) -> None:
    if cap_cents <= 0:
        return
    spent = daily_spend_cents(root)
    if spent >= cap_cents:
        raise SystemExit(
            f'daily cost cap exceeded: spent ~{spent:.0f}c / cap {cap_cents}c '
            '(set daily_cost_cap_cents in .teaagent/config.toml or TEAAGENT_DAILY_COST_CAP_CENTS)'
        )
