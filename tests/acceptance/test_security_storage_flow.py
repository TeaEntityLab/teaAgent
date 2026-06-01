"""Acceptance: storage helpers for atomic writes and JSONL appends.

Security boundary: append_jsonl_line must fsync; atomic_write_text must not corrupt.
Happy path: round-trip write → read preserves content.
Edge case: empty content; concurrent writes via file_lock (best-effort on macOS)."""

from __future__ import annotations

import json

from teaagent.storage import append_jsonl_line, atomic_write_text, file_lock


class TestFileLock:
    def test_lock_context_does_not_raise(self, tmp_path):
        p = tmp_path / 'data.txt'
        p.write_text('hi')
        with file_lock(p):
            pass

    def test_lock_creates_parent_dir(self, tmp_path):
        p = tmp_path / 'sub' / 'nested.txt'
        with file_lock(p):
            pass
        assert p.parent.is_dir()


class TestAppendJsonlLine:
    def test_writes_and_reads_lines(self, tmp_path):
        path = tmp_path / 'events.jsonl'
        append_jsonl_line(path, json.dumps({'event': 'a'}))
        append_jsonl_line(path, json.dumps({'event': 'b'}))

        lines = path.read_text(encoding='utf-8').strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])['event'] == 'a'
        assert json.loads(lines[1])['event'] == 'b'

    def test_empty_line_is_still_stored(self, tmp_path):
        path = tmp_path / 'empty.jsonl'
        append_jsonl_line(path, '')
        content = path.read_text(encoding='utf-8')
        assert content == '\n'

    def test_creates_parent_directory(self, tmp_path):
        path = tmp_path / 'sub' / 'log.jsonl'
        append_jsonl_line(path, '{"x":1}')
        assert path.is_file()


class TestAtomicWriteText:
    def test_write_and_read_round_trip(self, tmp_path):
        path = tmp_path / 'config.json'
        atomic_write_text(path, '{"key": "value"}')
        assert path.read_text(encoding='utf-8') == '{"key": "value"}'

    def test_overwrite_preserves_content(self, tmp_path):
        path = tmp_path / 'data.txt'
        atomic_write_text(path, 'first')
        atomic_write_text(path, 'second')
        assert path.read_text(encoding='utf-8') == 'second'

    def test_empty_content(self, tmp_path):
        path = tmp_path / 'empty.txt'
        atomic_write_text(path, '')
        assert path.read_text(encoding='utf-8') == ''

    def test_creates_parent_directory(self, tmp_path):
        path = tmp_path / 'deep' / 'nested' / 'file.txt'
        atomic_write_text(path, 'hello')
        assert path.is_file()
