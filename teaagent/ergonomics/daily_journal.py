from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from teaagent.daily import DailyBrief


def daily_journal_path(root: str | Path, *, day: date | None = None) -> Path:
    day = day or date.today()
    journal_dir = Path(root).resolve() / '.teaagent' / 'daily'
    journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir / f'{day.isoformat()}.md'


def render_daily_journal_markdown(brief: DailyBrief) -> str:
    token = brief.token_budget
    lines = [
        f'# TeaAgent Daily — {date.today().isoformat()}',
        '',
        f'- Ready: **{brief.ready}**',
        f'- Provider: `{brief.provider}`',
        f'- Model: `{brief.model or "default"}`',
        f'- Permission mode: `{brief.permission_mode}`',
        f'- Context profile: `{brief.context_profile.get("name", "balanced")}`',
        f'- Token pressure: **{token.usage_level}** ({token.estimated_input_tokens} in / {token.output_reserve_tokens} reserve)',
        '',
        '## Recommendations',
    ]
    for item in brief.recommendations:
        lines.append(f'- `{item.command}` — {item.reason}')
    lines.extend(['', '## Recent runs', ''])
    for run in brief.recent_runs[:10]:
        lines.append(f'- `{run.run_id}` {run.status}: {run.task[:80]}')
    return '\n'.join(lines) + '\n'


def write_daily_journal(
    brief: DailyBrief, *, root: str | Path, payload: dict[str, Any] | None = None
) -> Path:
    path = daily_journal_path(root)
    path.write_text(render_daily_journal_markdown(brief), encoding='utf-8')
    if payload is not None:
        json_path = path.with_suffix('.json')
        import json

        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'
        )
    return path
