"""Team-shared memory stored in a workspace Markdown file.

The team memory file lives at ``<root>/.teaagent/team-memory.md`` and
supports append-only entries plus prompt injection for agent context.
"""

from __future__ import annotations

from pathlib import Path


class TeamMemory:
    """Read/write team-shared memory persisted as a Markdown file.

    Entries are appended in chronological order with timestamps.
    The file is human-readable and can be edited directly between agents.
    """

    def __init__(self, root: str | Path = '.') -> None:
        self._root = Path(root).resolve()
        self._tea_dir = self._root / '.teaagent'
        self._path = self._tea_dir / 'team-memory.md'

    def add(self, entry: str) -> str:
        """Append a timestamped entry to the team memory file.

        Returns the full line that was written, including the timestamp.
        """
        from datetime import datetime, timezone

        self._tea_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        line = f'- {timestamp} — {entry}\n'
        with self._path.open('a', encoding='utf-8') as f:
            f.write(line)
        return line.rstrip('\n')

    def list(self) -> list[str]:
        """Return all entries (raw lines) from the team memory file."""
        if not self._path.is_file():
            return []
        return [
            line.rstrip('\n')
            for line in self._path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]

    def inject_prompt(self, limit_tokens: int = 2048) -> str:
        """Return a prompt snippet of recent team memory entries.

        The snippet is capped at approximately ``limit_tokens``, keeping
        the most recent entries first.  Token estimation is a rough
        heuristic (4 chars ≈ 1 token).
        """
        entries = self.list()
        if not entries:
            return '[team-memory] No shared team context available.'

        lines: list[str] = []
        char_budget = limit_tokens * 4
        for entry in reversed(entries):
            if len('\n'.join(lines)) + len(entry) > char_budget:
                break
            lines.insert(0, entry)

        snippet = '\n'.join(lines)
        return (
            f'[team-memory] Shared team context ({len(lines)} entries):\n'
            f'{snippet}'
        )
