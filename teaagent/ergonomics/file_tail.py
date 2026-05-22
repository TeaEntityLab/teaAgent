from __future__ import annotations

import json
import select
import struct
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable, Optional

# Linux inotify constants (stdlib has no binding).
_IN_MODIFY = 0x00000002
_IN_CLOSE_WRITE = 0x00000008
_IN_IGNORED = 0x00008000
_EVENT_STRUCT = struct.Struct('iIII')


def _linux_inotify_available() -> bool:
    return sys.platform.startswith('linux')


def _watch_directory_linux(
    directory: Path,
    *,
    poll_timeout: float,
    stop_when: Callable[[], bool],
) -> Iterator[None]:
    """Block until the watched directory may have changed (Linux inotify)."""
    import ctypes

    libc = ctypes.CDLL('libc.so.6', use_errno=True)
    inotify_init = libc.inotify_init
    inotify_init.argtypes = []
    inotify_init.restype = ctypes.c_int
    inotify_add_watch = libc.inotify_add_watch
    inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    inotify_add_watch.restype = ctypes.c_int

    fd = inotify_init()
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'inotify_init')
    watch_descriptor = inotify_add_watch(
        fd,
        str(directory).encode(),
        _IN_MODIFY | _IN_CLOSE_WRITE,
    )
    if watch_descriptor < 0:
        raise OSError(ctypes.get_errno(), 'inotify_add_watch')
    try:
        while not stop_when():
            ready, _, _ = select.select([fd], [], [], poll_timeout)
            if not ready:
                continue
            buffer = ctypes.create_string_buffer(4096)
            length = libc.read(fd, buffer, 4096)
            if length <= 0:
                continue
            offset = 0
            while offset + _EVENT_STRUCT.size <= length:
                _wd, mask, _cookie, name_len = _EVENT_STRUCT.unpack_from(
                    buffer.raw, offset
                )
                offset += _EVENT_STRUCT.size + name_len
                if mask & _IN_IGNORED:
                    continue
                if mask & (_IN_MODIFY | _IN_CLOSE_WRITE):
                    yield
    finally:
        libc.close(fd)


def _wait_for_growth(
    path: Path,
    position: int,
    *,
    follow: bool,
    poll_interval: float,
    stop_when: Callable[[], bool],
    use_inotify: bool,
) -> Iterator[None]:
    last_size = path.stat().st_size if path.exists() else 0
    directory = path.parent
    inotify = use_inotify and _linux_inotify_available() and directory.is_dir()
    wake: Iterator[None]
    if inotify:
        try:
            wake = _watch_directory_linux(
                directory, poll_timeout=poll_interval, stop_when=stop_when
            )
        except OSError:
            inotify = False
            wake = iter(())
    else:
        wake = iter(())

    pending_sleep = poll_interval

    while not stop_when():
        if path.exists():
            size = path.stat().st_size
            if size > position:
                pending_sleep = min(poll_interval, 0.05)
                yield
                last_size = size
                continue
            if not follow and size == last_size:
                return
            last_size = size

        try:
            next(wake)
            pending_sleep = min(poll_interval, 0.05)
            continue
        except StopIteration:
            wake = iter(())

        time.sleep(pending_sleep)
        if not follow:
            return


def iter_jsonl_tail(
    path: Path,
    *,
    follow: bool = False,
    poll_interval: float = 0.5,
    stop_when: Optional[Callable[[], bool]] = None,
    use_inotify: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield JSON objects appended to a JSONL file, optionally following new lines."""
    done = stop_when or (lambda: False)
    position = 0
    if path.exists():
        existing = path.read_text(encoding='utf-8')
        position = len(existing)
        for line in existing.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed

    if not follow:
        return

    while not path.exists() and not done():
        for _ in _wait_for_growth(
            path,
            position,
            follow=True,
            poll_interval=poll_interval,
            stop_when=done,
            use_inotify=use_inotify,
        ):
            break

    while not done():
        with path.open('r', encoding='utf-8') as handle:
            handle.seek(position)
            advanced = False
            while True:
                line = handle.readline()
                if not line:
                    break
                position = handle.tell()
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    advanced = True
                    yield parsed

        if done():
            return
        if advanced:
            continue

        for _ in _wait_for_growth(
            path,
            position,
            follow=True,
            poll_interval=poll_interval,
            stop_when=done,
            use_inotify=use_inotify,
        ):
            break
