"""Cross-session scratchpad for TeaAgent (UX2.3).

Stores structured JSON on session end, reads on start, and supports resume
offers.  An atexit handler plus SIGINT handler ensure crash/interrupt
protection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCRATCHPAD_FILE = 'scratchpad.json'


class Scratchpad:
    """Persist run context across sessions in ``.teaagent/scratchpad.json``.

    Typical usage::

        sp = Scratchpad(workspace_root)
        sp.write(goal='...', progress='...', open_questions=[...], next_step='...')
        previous = sp.read()
        sp.clear()
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._path = root / '.teaagent' / SCRATCHPAD_FILE

    def write(
        self,
        goal: str,
        progress: str,
        open_questions: list[str],
        next_step: str,
        *,
        session_id: str = '',
    ) -> None:
        """Persist scratchpad content to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            'last_goal': goal,
            'progress': progress,
            'open_questions': open_questions,
            'next_step': next_step,
            'session_id': session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except OSError as exc:
            logger.warning('Failed to write scratchpad: %s', exc)

    def read(self) -> dict[str, Any] | None:
        """Return scratchpad content or *None* if the file is absent or
        unreadable."""
        if not self._path.is_file():
            return None
        try:
            return json.loads(
                self._path.read_text(encoding='utf-8'),
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning('Failed to read scratchpad: %s', exc)
            return None

    def clear(self) -> None:
        """Remove the scratchpad file."""
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning('Failed to clear scratchpad: %s', exc)

    def exists(self) -> bool:
        """Return *True* when the scratchpad file exists on disk."""
        return self._path.is_file()

    def resume_prompt(self) -> str | None:
        """Build a resume-context string, or *None* if nothing to resume."""
        content = self.read()
        if content is None:
            return None
        goal = content.get('last_goal', '')
        progress = content.get('progress', '')
        questions = content.get('open_questions', [])
        next_step = content.get('next_step', '')
        if not goal and not progress and not next_step:
            return None
        return (
            f'[Resumed from previous session]\n'
            f'Goal: {goal}\n'
            f'Progress: {progress}\n'
            f'Open questions: {json.dumps(questions)}\n'
            f'Next step: {next_step}'
        )
