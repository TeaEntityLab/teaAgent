"""Run undo journal.

``UndoJournal`` is an :class:`~teaagent.audit.AuditLogger` sink that captures
the pre-write state of workspace path-based write tools **only after a successful
tool call**.  Pending snapshots taken at ``tool_call_started`` are committed on
``tool_call_completed`` and discarded on ``tool_call_failed``, ``tool_call_blocked``,
or ``tool_call_denied``.

Calling :meth:`UndoJournal.restore` reverts all committed writes:

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
import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.audit import secure_audit_dir, secure_audit_file
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)

# We only snapshot path-based tools, not shell commands (no stable path arg).
_PATH_WRITE_TOOLS = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)

_DISCARD_PENDING_EVENTS = frozenset(
    {
        'tool_call_failed',
        'tool_call_blocked',
        'tool_call_denied',
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
        ``None`` (default) the journal is held only in memory until
        :meth:`save_to` is called.
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
        self._pending: dict[str, _JournalEntry] = {}
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            secure_audit_dir(self._path.parent)
            if self._path.is_file():
                self._entries = list(self._load_from_disk())
                self._validate_journal_health()

    # ------------------------------------------------------------------
    # AuditLogger sink protocol
    # ------------------------------------------------------------------

    def __call__(self, event: object) -> None:  # AuditEvent
        from teaagent.audit import AuditEvent

        if not isinstance(event, AuditEvent):
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        call_id = payload.get('call_id')
        if not isinstance(call_id, str) or not call_id:
            return

        if event.event_type == 'tool_call_started':
            self._on_tool_started(payload)
            return
        if event.event_type == 'tool_call_completed':
            self._on_tool_completed(call_id)
            return
        if event.event_type in _DISCARD_PENDING_EVENTS:
            self._pending.pop(call_id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_tool_started(self, payload: dict[str, object]) -> None:
        tool_name = payload.get('tool_name', '')
        if tool_name not in _PATH_WRITE_TOOLS:
            return
        args = payload.get('arguments', {})
        rel_path = args.get('path', '') if isinstance(args, dict) else ''
        if not isinstance(rel_path, str) or not rel_path:
            return
        call_id = payload.get('call_id')
        if not isinstance(call_id, str) or not call_id:
            return
        entry = self._snapshot(rel_path)
        if entry is not None:
            self._pending[call_id] = entry

    def _on_tool_completed(self, call_id: str) -> None:
        entry = self._pending.pop(call_id, None)
        if entry is None:
            return
        self._entries.append(entry)

    def _snapshot(self, rel_path: str) -> Optional[_JournalEntry]:
        try:
            abs_path = (self._root / rel_path).resolve()
            abs_path.relative_to(self._root)
        except (ValueError, OSError):
            return None

        existed = abs_path.is_file()
        content_b64: Optional[str] = None
        if existed:
            try:
                content_b64 = base64.b64encode(abs_path.read_bytes()).decode('ascii')
            except OSError:
                return None

        return _JournalEntry(
            path=rel_path,
            existed_before=existed,
            content_b64=content_b64,
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

    def _validate_journal_health(self) -> None:
        """Check journal health and log warnings if issues are detected."""
        if not self._entries:
            return

        # Check for potential corruption or incomplete entries
        corrupted_count = 0
        for entry in self._entries:
            if entry.existed_before and entry.content_b64 is None:
                corrupted_count += 1
                logger.warning(
                    f"Journal entry for '{entry.path}' marked as existed but has no content"
                )
            elif not entry.existed_before and entry.content_b64 is not None:
                corrupted_count += 1
                logger.warning(
                    f"Journal entry for '{entry.path}' marked as not existed but has content"
                )

        if corrupted_count > 0:
            logger.warning(
                f'Journal health check found {corrupted_count} potentially corrupted entries '
                f'out of {len(self._entries)} total entries'
            )

        # Check for orphaned pending entries (from crashed runs)
        if self._pending:
            logger.warning(
                f'Found {len(self._pending)} orphaned pending journal entries from previous run. '
                'These will be discarded.'
            )
            self._pending.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def has_entries(self) -> bool:
        return bool(self._entries)

    def changed_paths(self) -> list[str]:
        """Return unique relative paths captured by this journal, in order."""
        seen: set[str] = set()
        paths: list[str] = []
        for entry in self._entries:
            if entry.path in seen:
                continue
            seen.add(entry.path)
            paths.append(entry.path)
        return paths

    def iter_entries(self) -> list[dict[str, Any]]:
        """Return a JSON-serializable view of committed journal entries."""
        return [
            {
                'path': entry.path,
                'existed_before': entry.existed_before,
                'content_b64': entry.content_b64,
            }
            for entry in self._entries
        ]

    def check_health(self) -> dict[str, Any]:
        """Perform health check on the journal and return diagnostic information.

        Returns a dict with keys:
        - 'total_entries': total number of journal entries
        - 'corrupted_entries': number of potentially corrupted entries
        - 'orphaned_pending': number of orphaned pending entries
        - 'healthy': boolean indicating overall health
        """
        corrupted_count = 0
        for entry in self._entries:
            if (
                entry.existed_before
                and entry.content_b64 is None
                or not entry.existed_before
                and entry.content_b64 is not None
            ):
                corrupted_count += 1

        orphaned_pending = len(self._pending)
        healthy = corrupted_count == 0 and orphaned_pending == 0

        return {
            'total_entries': len(self._entries),
            'corrupted_entries': corrupted_count,
            'orphaned_pending': orphaned_pending,
            'healthy': healthy,
        }

    def save_to(self, path: str | Path) -> None:
        """Persist in-memory journal entries to a JSONL file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        secure_audit_dir(target.parent)
        lines = [
            json.dumps(
                {
                    'path': entry.path,
                    'existed_before': entry.existed_before,
                    'content_b64': entry.content_b64,
                }
            )
            for entry in self._entries
        ]
        body = '\n'.join(lines) + ('\n' if lines else '')
        atomic_write_text(target, body)
        secure_audit_file(target)

    def restore(self) -> UndoResult:
        """Revert all captured file writes.

        Iterates journal entries in **forward** order (oldest first) so that
        the pre-write snapshot from the earliest entry is used for each file.
        Returns an :class:`UndoResult` describing what was changed.
        """
        restored: list[str] = []
        deleted: list[str] = []
        errors: list[str] = []

        seen: set[str] = set()
        for entry in self._entries:
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
