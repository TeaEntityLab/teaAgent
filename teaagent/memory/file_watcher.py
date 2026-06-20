"""File system watcher for live context synchronization.

This module provides:
- File watching using watchdog library
- Event debouncing to avoid rapid-fire refreshes
- Background thread operation
- Graceful shutdown handling
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Callable, Optional, Set

logger = logging.getLogger(__name__)


def _import_watchdog() -> tuple[bool, object, object, object, object, object, object]:
    """Return (available, Observer, ... event types)."""
    try:
        from watchdog.events import (
            DirDeletedEvent,
            DirModifiedEvent,
            FileDeletedEvent,
            FileModifiedEvent,
            FileSystemEventHandler,
        )
        from watchdog.observers import Observer

        return (
            True,
            Observer,
            DirDeletedEvent,
            DirModifiedEvent,
            FileDeletedEvent,
            FileModifiedEvent,
            FileSystemEventHandler,
        )
    except ImportError:

        class _DummyObserver:
            def schedule(self, *args: object, **kwargs: object) -> None:
                pass

            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

            def join(self, timeout: Optional[float] = None) -> None:
                pass

        return (False, _DummyObserver, object, object, object, object, object)


(
    WATCHDOG_AVAILABLE,
    Observer,
    DirDeletedEvent,
    DirModifiedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
) = _import_watchdog()


class FileChangeHandler(FileSystemEventHandler):  # type: ignore[valid-type,misc]
    """Handler for file system change events."""

    def __init__(
        self,
        callback: Callable[[str, str], None],
        watched_files: Set[str],
        debounce_ms: int = 500,
    ) -> None:
        super().__init__()
        self.callback = callback
        self.watched_files = watched_files
        self.debounce_ms = debounce_ms
        self.last_event_time: dict[str, float] = {}
        self.lock = threading.Lock()

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:  # type: ignore[valid-type]
        if event.is_directory:  # type: ignore[union-attr]
            return

        try:
            src_path_str = (
                event.src_path  # type: ignore[union-attr]
                if isinstance(event.src_path, str)  # type: ignore[union-attr]
                else event.src_path.decode('utf-8')  # type: ignore[union-attr]
            )
            src_path = Path(src_path_str)
            # This will be resolved in the watcher setup
            file_path = str(src_path)
        except Exception:
            logger.exception('modified event parse failed')
            return

        # Check if this is a watched file
        if file_path not in self.watched_files:
            return

        # Debounce the event
        current_time = time.time()
        with self.lock:
            last_time = self.last_event_time.get(file_path, 0)
            if current_time - last_time < (self.debounce_ms / 1000):
                return
            self.last_event_time[file_path] = current_time

        # Call the callback
        with suppress(Exception):
            self.callback(file_path, 'modified')

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:  # type: ignore[valid-type]
        if event.is_directory:  # type: ignore[union-attr]
            return

        try:
            src_path_str = (
                event.src_path  # type: ignore[union-attr]
                if isinstance(event.src_path, str)  # type: ignore[union-attr]
                else event.src_path.decode('utf-8')  # type: ignore[union-attr]
            )
            src_path = Path(src_path_str)
            file_path = str(src_path)
        except Exception:
            logger.exception('deleted event parse failed')
            return

        # Check if this is a watched file
        if file_path not in self.watched_files:
            return

        # Call the callback immediately (no debounce for deletion)
        with suppress(Exception):
            self.callback(file_path, 'deleted')


class FileWatcher:
    """File system watcher for pinned files."""

    def __init__(
        self,
        root: Path,
        callback: Callable[[str, str], None],
        debounce_ms: int = 500,
    ) -> None:
        """Initialize file watcher.

        Args:
            root: The workspace root directory
            callback: Function to call when a watched file changes (file_path, event_type)
            debounce_ms: Debounce time in milliseconds
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                'watchdog library is required for file watching. '
                'Install with: pip install teaagent[file-watching]'
            )
        self.root = Path(root).resolve()
        self.callback = callback
        self.debounce_ms = debounce_ms
        self.observer = Observer()  # type: ignore[operator]
        self.watched_files: Set[str] = set()
        self.handler: Optional[FileChangeHandler] = None
        self.running = False
        self.lock = threading.Lock()

    def update_watched_files(self, file_paths: Set[str]) -> None:
        """Update the set of files to watch.

        Args:
            file_paths: Set of file paths to watch (relative to workspace root)
        """
        with self.lock:
            self.watched_files = set(file_paths)
            if self.handler:
                self.handler.watched_files = self.watched_files

    def start(self) -> None:
        """Start the file watcher in a background thread."""
        with self.lock:
            if self.running:
                return

            self.handler = FileChangeHandler(
                callback=self.callback,
                watched_files=self.watched_files,
                debounce_ms=self.debounce_ms,
            )

            # Watch the entire root directory
            self.observer.schedule(self.handler, str(self.root), recursive=True)
            self.observer.start()
            self.running = True

    def stop(self) -> None:
        """Stop the file watcher and clean up."""
        with self.lock:
            if not self.running:
                return

            self.observer.stop()
            self.observer.join(timeout=5)
            self.running = False

    def is_running(self) -> bool:
        """Check if the watcher is running.

        Returns:
            True if running, False otherwise
        """
        with self.lock:
            return self.running
