"""AC-NEW: mtime read-before-write concurrent modification guard.

Verifies that workspace_write_file rejects overwrites when the file was
modified between the read and the write, preventing silent data loss from
concurrent modifications (a mainstream standard pioneered by OpenCode and
Codex).

Acceptance criteria:
- workspace_read_file returns an mtime field in its output.
- workspace_write_file with expected_mtime rejects the write if the file
  was externally modified after the read (mtime mismatch).
- workspace_write_file without expected_mtime succeeds unconditionally
  (backward compatible).
- workspace_write_file with expected_mtime succeeds when the file was NOT
  modified (mtime matches within tolerance).
"""

from __future__ import annotations

import time

from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools._files import (
    read_file,
    write_file,
)


def _config(tmp_path) -> WorkspaceToolConfig:
    return WorkspaceToolConfig.from_root(str(tmp_path))


def test_read_file_returns_mtime(tmp_path):
    (tmp_path / 'hello.txt').write_text('hello', encoding='utf-8')
    config = _config(tmp_path)
    result = read_file(config, {'path': 'hello.txt'})
    assert 'mtime' in result, (
        'read_file must return mtime for concurrent modification detection'
    )
    assert isinstance(result['mtime'], float)
    assert result['mtime'] > 0


def test_write_includes_mtime_on_success(tmp_path):
    (tmp_path / 'hello.txt').write_text('hello', encoding='utf-8')
    config = _config(tmp_path)
    result = write_file(config, {'path': 'hello.txt', 'content': 'world'})
    assert 'mtime' in result, 'write_file must return mtime on success'
    assert isinstance(result['mtime'], float)


def test_write_without_mtime_succeeds_unconditionally(tmp_path):
    (tmp_path / 'hello.txt').write_text('hello', encoding='utf-8')
    config = _config(tmp_path)
    (tmp_path / 'hello.txt').write_text('external edit', encoding='utf-8')
    result = write_file(config, {'path': 'hello.txt', 'content': 'new'})
    assert result['bytes_written'] > 0


def test_write_blocked_on_mtime_mismatch(tmp_path):
    (tmp_path / 'hello.txt').write_text('hello', encoding='utf-8')
    config = _config(tmp_path)
    read_result = read_file(config, {'path': 'hello.txt'})
    read_mtime = read_result['mtime']

    time.sleep(0.05)
    (tmp_path / 'hello.txt').write_text('external edit', encoding='utf-8')
    import pytest

    with pytest.raises(ValueError, match='was modified since last read'):
        write_file(
            config,
            {
                'path': 'hello.txt',
                'content': 'new content',
                'expected_mtime': read_mtime,
            },
        )


def test_write_succeeds_when_mtime_matches(tmp_path):
    (tmp_path / 'hello.txt').write_text('hello', encoding='utf-8')
    config = _config(tmp_path)
    read_result = read_file(config, {'path': 'hello.txt'})
    read_mtime = read_result['mtime']
    result = write_file(
        config,
        {
            'path': 'hello.txt',
            'content': 'new content',
            'expected_mtime': read_mtime,
        },
    )
    assert result['bytes_written'] > 0


def test_mtime_guard_new_file_creation(tmp_path):
    config = _config(tmp_path)
    result = write_file(
        config,
        {'path': 'new_file.txt', 'content': 'fresh', 'create_dirs': True},
    )
    assert result['bytes_written'] > 0
