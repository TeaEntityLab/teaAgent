from __future__ import annotations

import os
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Iterator


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+', encoding='utf-8') as handle:
        locked = False
        try:
            try:
                import fcntl
            except ImportError:
                yield
                return

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
            yield
        finally:
            if locked:
                with suppress(Exception):
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_jsonl_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path), path.open('a', encoding='utf-8') as handle:
        handle.write(line.rstrip('\n') + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    with file_lock(path):
        with tmp.open('w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
