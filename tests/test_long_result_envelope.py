"""Tests for LongResultEnvelope helpers."""

import hashlib
from pathlib import Path

import pytest

from teaagent.long_result_envelope import (
    _safe_utf8_truncate,
    readback_artifact,
    store_long_result,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(content: str) -> str:
    return f'sha256:{hashlib.sha256(content.encode("utf-8")).hexdigest()}'


def _large_rss_output() -> str:
    """Build a fake RSS feed result larger than the default 50KB preview."""
    items = []
    for i in range(1, 600):
        items.append(
            f"""<item>
  <title>Blog Post #{i:04d} — Deep Dive Into Some Long Topic That Takes Up Space</title>
  <link>https://example.com/blog/post-{i:04d}</link>
  <description>This is a very long description for post number {i} intended to consume
a significant amount of bytes so that the total RSS output exceeds the default
50KB preview threshold. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad
minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
commodo consequat.</description>
  <pubDate>Mon, {i:02d} Jan 2026 10:00:00 GMT</pubDate>
  <category>Technology</category>
</item>"""
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        '<channel>\n'
        '<title>Example RSS Feed</title>\n' + '\n'.join(items) + '\n</channel>\n</rss>'
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStoreLongResultSmall:
    def test_truncated_false(self, tmp_path: Path):
        content = 'short result'
        envelope = store_long_result(tmp_path, 'run-001', 'call-001', content)
        assert not envelope.truncated
        assert envelope.preview == content
        assert envelope.total_bytes == len(content.encode('utf-8'))
        assert envelope.preview_bytes == len(content.encode('utf-8'))
        assert envelope.content_hash == _sha256(content)
        assert envelope.artifact_path == ''
        assert envelope.cursor == f'offset:{len(content.encode("utf-8"))}'

    def test_no_artifact_file_created(self, tmp_path: Path):
        store_long_result(tmp_path, 'run-001', 'call-001', 'short')
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results'
        assert not artifact_dir.exists()


class TestStoreLongResultLarge:
    def test_truncated_true(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        assert envelope.truncated
        assert envelope.total_bytes == len(content.encode('utf-8'))
        assert envelope.preview_bytes < envelope.total_bytes

    def test_preview_is_truncated_first_chunk(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        expected_data, expected_bytes = _safe_utf8_truncate(
            content.encode('utf-8'), 50000
        )
        assert envelope.preview == expected_data.decode('utf-8')
        assert envelope.preview_bytes == expected_bytes

    def test_artifact_file_exists_and_matches(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        assert envelope.artifact_path
        artifact = tmp_path / envelope.artifact_path
        assert artifact.is_file()
        stored = artifact.read_text(encoding='utf-8')
        assert stored == content

    def test_content_hash(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        assert envelope.content_hash == _sha256(content)

    def test_cursor_reflects_preview_bytes(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        _, expected_offset = _safe_utf8_truncate(content.encode('utf-8'), 50000)
        assert envelope.cursor == f'offset:{expected_offset}'


class TestReadbackArtifact:
    def test_reads_full_artifact(self, tmp_path: Path):
        content = 'hello world'
        # First store a small result (which doesn't write to disk, so we write manually)
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-readback.txt'
        artifact_file.write_text(content, encoding='utf-8')

        result = readback_artifact(
            tmp_path,
            '.teaagent/artifacts/tool-results/run-001/call-readback.txt',
        )
        assert result == content

    def test_reads_large_artifact_via_store_then_readback(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)
        assert envelope.truncated
        assert envelope.artifact_path

        full = readback_artifact(
            tmp_path, envelope.artifact_path, max_bytes=len(content.encode('utf-8')) + 1
        )
        assert full == content

    def test_readback_with_cursor_returns_partial(self, tmp_path: Path):
        content = _large_rss_output()
        envelope = store_long_result(tmp_path, 'run-001', 'call-large', content)

        # Read the first 10000 bytes
        chunk1 = readback_artifact(
            tmp_path, envelope.artifact_path, cursor='offset:0', max_bytes=10000
        )
        content_bytes = content.encode('utf-8')
        expected1, _ = _safe_utf8_truncate(content_bytes[:10000], 10000)
        assert chunk1 == expected1.decode('utf-8')

        # Continue from offset 10000
        chunk2 = readback_artifact(
            tmp_path,
            envelope.artifact_path,
            cursor='offset:10000',
            max_bytes=10000,
        )
        expected2, _ = _safe_utf8_truncate(content_bytes[10000:20000], 10000)
        assert chunk2 == expected2.decode('utf-8')

    def test_readback_with_none_cursor_reads_from_start(self, tmp_path: Path):
        content = 'abc' * 100
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-none-cursor.txt'
        artifact_file.write_text(content, encoding='utf-8')

        result = readback_artifact(
            tmp_path,
            '.teaagent/artifacts/tool-results/run-001/call-none-cursor.txt',
            cursor=None,
        )
        assert result == content

    def test_readback_max_bytes_truncation(self, tmp_path: Path):
        content = 'x' * 100_000
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / 'call-maxbytes.txt'
        artifact_file.write_text(content, encoding='utf-8')

        limited = readback_artifact(
            tmp_path,
            '.teaagent/artifacts/tool-results/run-001/call-maxbytes.txt',
            max_bytes=2000,
        )
        assert len(limited.encode('utf-8')) == 2000
        assert limited.startswith('x' * 2000)

    # ------------------------------------------------------------------
    # Negative-input guards
    # ------------------------------------------------------------------

    def test_negative_max_bytes_zero(self) -> None:
        with pytest.raises(ValueError, match='max_bytes must be positive'):
            readback_artifact(Path('.'), 'any/path', max_bytes=0)

    def test_negative_max_bytes_negative(self) -> None:
        with pytest.raises(ValueError, match='max_bytes must be positive'):
            readback_artifact(Path('.'), 'any/path', max_bytes=-1)

    def test_negative_cursor_offset(self, tmp_path: Path) -> None:
        content = 'hello'
        artifact_dir = tmp_path / '.teaagent' / 'artifacts' / 'tool-results' / 'run-001'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / 'test.txt').write_text(content, encoding='utf-8')

        with pytest.raises(ValueError, match='cursor offset must be >= 0'):
            readback_artifact(
                tmp_path,
                '.teaagent/artifacts/tool-results/run-001/test.txt',
                cursor='offset:-1',
            )
