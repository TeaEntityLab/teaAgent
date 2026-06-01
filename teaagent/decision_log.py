"""Persistent Decision Log for TeaAgent workspaces.

Stores structured decisions in .teaagent/decisions.md for later injection
into agent system prompts as decision summaries.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List


class DecisionLog:
    """Reads and writes a persistent decision log in .teaagent/decisions.md.

    Format::

        ## 2026-05-31
        **Decision:** Use JSONL for audit log, not SQLite
        **Reason:** Single-writer per workspace; SQLite requires migration for multi-host
        **Do not reverse without:** Reading ADR 0008

    """

    _DATE_HEADER = re.compile(r'^## (\d{4}-\d{2}-\d{2})$')

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._path = self._root / '.teaagent' / 'decisions.md'

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ public

    def add(self, decision: str, reason: str, do_not_reverse: str = '') -> None:
        """Append a decision entry to the log."""
        self._ensure_dir()
        today = date.today().isoformat()
        entry = f'\n## {today}\n**Decision:** {decision}\n**Reason:** {reason}\n'
        if do_not_reverse:
            entry += f'**Do not reverse without:** {do_not_reverse}\n'
        with self._path.open('a', encoding='utf-8') as handle:
            handle.write(entry)

    def list(self) -> List[Dict[str, Any]]:
        """Return all decisions as a list of dicts."""
        decisions: List[Dict[str, Any]] = self._parse().get('decisions', [])
        return decisions

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the *limit* most recent decisions."""
        all_decisions = self.list()
        return list(reversed(all_decisions))[:limit]

    def inject_summary(self, limit: int = 10, max_chars: int | None = 1400) -> str:
        """Return a markdown summary suitable for system-prompt injection.

        Truncates each decision field to keep total output under *max_chars*
        (roughly 500 tokens for typical english prose).  Pass ``max_chars=None``
        to disable truncation.
        """
        recent = self.recent(limit=limit)
        if not recent:
            return ''
        lines: list[str] = ['## Recent Decisions']
        for d in recent:
            lines.append('')
            lines.append(f'**Decision:** {_truncate(d.get("decision", ""))}')
            lines.append(f'**Reason:** {_truncate(d.get("reason", ""))}')
            dnr = d.get('do_not_reverse', '')
            if dnr:
                lines.append(f'**Do not reverse without:** {_truncate(dnr)}')
            lines.append(f'*Logged: {d.get("date", "")}*')
        summary = '\n'.join(lines)
        if max_chars is not None and len(summary) > max_chars:
            summary = summary[:max_chars].rsplit('\n', 1)[0] + '\n*(truncated)*'
        return summary

    # ----------------------------------------------------------------- internal

    def _parse(self) -> dict[str, Any]:
        if not self._path.exists():
            return {'decisions': []}
        raw = self._path.read_text(encoding='utf-8')
        decisions: list[dict[str, Any]] = []
        current_date = ''
        current: dict[str, Any] = {}
        in_entry = False

        for line in raw.splitlines():
            m = self._DATE_HEADER.match(line)
            if m:
                if in_entry and current.get('decision'):
                    current['date'] = current_date
                    decisions.append(current)
                current_date = m.group(1)
                current = {}
                in_entry = True
                continue

            decision_m = re.match(r'\*\*Decision:\*\*\s+(.*)', line)
            if decision_m:
                current['decision'] = decision_m.group(1).strip()
                continue

            reason_m = re.match(r'\*\*Reason:\*\*\s+(.*)', line)
            if reason_m:
                current['reason'] = reason_m.group(1).strip()
                continue

            dnr_m = re.match(r'\*\*Do not reverse without:\*\*\s+(.*)', line)
            if dnr_m:
                current['do_not_reverse'] = dnr_m.group(1).strip()
                continue

        # Flush final entry
        if in_entry and current.get('decision'):
            current['date'] = current_date
            decisions.append(current)

        return {'decisions': decisions}


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + '...'
