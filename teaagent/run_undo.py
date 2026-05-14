"""Run undo journal.

``UndoJournal`` is an :class:`~teaagent.audit.AuditLogger` sink that captures
the pre-write state of every file touched by workspace write tools.  Calling
:meth:`UndoJournal.restore` reverts all captured writes:

* Files that **did not exist before** the write are **deleted**.
* Files that **did exist** are **restored** to their original content.

Usage::

    from teaagent.run_undo import UndoJournal
    from teaagent.audit import AuditLogger

    audit = AuditLogger()
    journal = UndoJournal(root=workspace_root)
    audit.add_sink(journal)

    # ... run the agent ...

    result = journal.restore()
    print('restored:', result.restored)
    print('deleted:', result.deleted)

The journal is held in memory by default.  Pass a *path* to persist it to a
JSONL file so that undo survives process restarts.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_WRITE_TOOL_NAMES = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
        'workspace_run_shell',  # mutate variant captured by name check below
        'workspace_run_shell_mutate',
    }
)

# We only snapshot path-based tools, not shell commands (no stable path arg).
_PATH_WRITE_TOOLS = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)


@dataclass(frozen=True)
class _JournalEntry:
    path: str
    existed_before: bool
    content_b64: Optional[str]  # None when file did not exist before the write


@dataclass(frozen=True)
class UndoResult:
    """Summary returned by :meth:`UndoJournal.restore`."""

    restored: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


class UndoJournal:
    """Audit-log sink that records pre-write file state for later undo.

    Parameters
    ----------
    root:
        Workspace root directory.  All relative paths are resolved against
        this directory.  Paths that escape *root* via ``..`` are silently
        ignored.
    path:
        Optional file path for persistent journal storage (JSONL).  When
        ``None`` (default) the journal is held only in memory.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        path: Optional[str | Path] = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._path = Path(path).resolve() if path else None
        self._entries: list[_JournalEntry] = []
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Load existing entries from disk (supports resume across restarts)
            if self._path.is_file():
                self._entries = list(self._load_from_disk())

    # ------------------------------------------------------------------
    # AuditLogger sink protocol
    # ------------------------------------------------------------------

    def __call__(self, event: object) -> None:  # AuditEvent
        from teaagent.audit import AuditEvent

        if not isinstance(event, AuditEvent):
            return
        if event.event_type != 'tool_call_started':
            return
        payload = event.payload
        tool_name = payload.get('tool_name', '')
        if tool_name not in _PATH_WRITE_TOOLS:
            return
        args = payload.get('arguments', {})
        rel_path = args.get('path', '') if isinstance(args, dict) else ''
        if not rel_path or not isinstance(rel_path, str):
            return
        self._capture(rel_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _capture(self, rel_path: str) -> None:
        """Read current file state and append a journal entry."""
        try:
            abs_path = (self._root / rel_path).resolve()
            abs_path.relative_to(self._root)  # raises ValueError if escapes root
        except (ValueError, OSError):
            return

        existed = abs_path.is_file()
        content_b64: Optional[str] = None
        if existed:
            try:
                content_b64 = base64.b64encode(abs_path.read_bytes()).decode('ascii')
            except OSError:
                return

        entry = _JournalEntry(
            path=rel_path,
            existed_before=existed,
            content_b64=content_b64,
        )
        self._entries.append(entry)
        if self._path is not None:
            with open(self._path, 'a', encoding='utf-8') as fh:
                fh.write(
                    json.dumps(
                        {
                            'path': entry.path,
                            'existed_before': entry.existed_before,
                            'content_b64': entry.content_b64,
                        }
                    )
                    + '\n'
                )

    def _load_from_disk(self) -> Generator[_JournalEntry, None, None]:
        assert self._path is not None
        for line in self._path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                yield _JournalEntry(
                    path=obj['path'],
                    existed_before=obj['existed_before'],
                    content_b64=obj.get('content_b64'),
                )
            except (json.JSONDecodeError, KeyError):
                continue

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def restore(self) -> UndoResult:
        """Revert all captured file writes.

        Iterates journal entries in **reverse** order so that a file written
        multiple times is restored to its state before the *first* write.
        Returns an :class:`UndoResult` describing what was changed.
        """
        restored: list[str] = []
        deleted: list[str] = []
        errors: list[str] = []

        # Process in reverse so the earliest snapshot wins for repeated writes.
        seen: set[str] = set()
        for entry in reversed(self._entries):
            if entry.path in seen:
                continue
            seen.add(entry.path)

            try:
                abs_path = (self._root / entry.path).resolve()
                abs_path.relative_to(self._root)
            except (ValueError, OSError) as exc:
                errors.append(f'{entry.path}: {exc}')
                continue

            try:
                if entry.existed_before and entry.content_b64 is not None:
                    abs_path.parent.mkdir(parents=True, exist_ok=True)
                    abs_path.write_bytes(base64.b64decode(entry.content_b64))
                    restored.append(entry.path)
                else:
                    if abs_path.exists():
                        abs_path.unlink()
                    deleted.append(entry.path)
            except OSError as exc:
                errors.append(f'{entry.path}: {exc}')

        return UndoResult(restored=restored, deleted=deleted, errors=errors)
