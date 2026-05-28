"""File system watcher for live context synchronization.

This module provides:
- File watching using watchdog library
- Event debouncing to avoid rapid-fire refreshes
- Background thread operation
- Graceful shutdown handling
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Callable, Optional, Set

try:
    from watchdog.events import (
        FileDeletedEvent,
        FileModifiedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class FileChangeHandler(FileSystemEventHandler):
    """Handler for file system change events."""

    def __init__(
        self,
        callback: Callable[[str, str], None],
        watched_files: Set[str],
        debounce_ms: int = 500,
    ) -> None:
        """Initialize file change handler.

        Args:
            callback: Function to call when a file changes (file_path, event_type)
            watched_files: Set of file paths to watch (relative to workspace root)
            debounce_ms: Debounce time in milliseconds
        """
        super().__init__()
        self.callback = callback
        self.watched_files = watched_files
        self.debounce_ms = debounce_ms
        self.last_event_time: dict[str, float] = {}
        self.lock = threading.Lock()

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modified event.

        Args:
            event: The file modified event
        """
        if event.is_directory:
            return

        # Get relative path
        try:
            src_path = Path(event.src_path)
            # This will be resolved in the watcher setup
            file_path = str(src_path)
        except Exception:
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

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """Handle file deleted event.

        Args:
            event: The file deleted event
        """
        if event.is_directory:
            return

        # Get relative path
        try:
            src_path = Path(event.src_path)
            file_path = str(src_path)
        except Exception:
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
        self.observer = Observer()
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
