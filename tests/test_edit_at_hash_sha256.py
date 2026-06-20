"""Tests for S-P1-3: SHA-256 line-hash format with CRC migration."""

from __future__ import annotations

import hashlib
import zlib

import pytest

from teaagent.workspace_tools._helpers import (
    _crc32_hex,
    _legacy_crc8_hex,
    _sha256_hex,
    compute_line_hash,
    format_hash_line,
)


@pytest.fixture(autouse=True)
def _clear_hash_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ``TEAAGENT_EDIT_HASH_FORMAT`` is unset (defaults to sha256)."""
    monkeypatch.delenv('TEAAGENT_EDIT_HASH_FORMAT', raising=False)


# ---------------------------------------------------------------------------
# (a) New anchors use SHA-256
# ---------------------------------------------------------------------------


def test_default_format_is_sha256() -> None:
    """With no env var set, the hash is a 64-char SHA-256 hex digest."""
    h = compute_line_hash(1, 'Hello\n')
    assert len(str(h)) == 64
    assert str(h) == hashlib.sha256(b'1:Hello').hexdigest()


def test_format_hash_line_uses_sha256_by_default() -> None:
    """Wire-format output contains the SHA-256 digest."""
    line = format_hash_line(1, 'Hello\n')
    expected_hash = hashlib.sha256(b'1:Hello').hexdigest()
    assert line == f'1#{expected_hash}|Hello\n'


def test_explicit_sha256_format() -> None:
    """Explicitly setting ``TEAAGENT_EDIT_HASH_FORMAT=sha256``."""
    import os

    os.environ['TEAAGENT_EDIT_HASH_FORMAT'] = 'sha256'
    try:
        h = compute_line_hash(5, 'world\n')
        assert str(h) == hashlib.sha256(b'5:world').hexdigest()
    finally:
        del os.environ['TEAAGENT_EDIT_HASH_FORMAT']


# ---------------------------------------------------------------------------
# (c) The config flag selects the format
# ---------------------------------------------------------------------------


def test_crc32_format_selected_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TEAAGENT_EDIT_HASH_FORMAT=crc32`` produces 32-bit CRC hex."""
    monkeypatch.setenv('TEAAGENT_EDIT_HASH_FORMAT', 'crc32')
    h = compute_line_hash(1, 'Hello\n')
    expected = f'{zlib.crc32(b"1:Hello") & 0xFFFFFFFF:08X}'
    assert str(h) == expected
    assert len(str(h)) == 8


def test_crc32_format_hash_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire-format output with crc32 uses the 32-bit CRC."""
    monkeypatch.setenv('TEAAGENT_EDIT_HASH_FORMAT', 'crc32')
    line = format_hash_line(1, 'Hello\n')
    expected_hash = f'{zlib.crc32(b"1:Hello") & 0xFFFFFFFF:08X}'
    assert line == f'1#{expected_hash}|Hello\n'


def test_unknown_format_falls_back_to_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognised format value defaults to sha256."""
    monkeypatch.setenv('TEAAGENT_EDIT_HASH_FORMAT', 'md5')
    h = compute_line_hash(1, 'Hello\n')
    assert str(h) == hashlib.sha256(b'1:Hello').hexdigest()


# ---------------------------------------------------------------------------
# (b) Old CRC anchors are still readable when the migration flag is set
# ---------------------------------------------------------------------------


def test_legacy_crc8_anchor_matches_sha256_hash() -> None:
    """An old 8-bit CRC anchor compares equal to the new SHA-256 hash.

    This is the core migration guarantee: ``compute_line_hash`` returns a
    ``str`` subclass whose ``__eq__`` also accepts the legacy 8-bit CRC
    value, so ``edit_at_hash`` in ``_files.py`` (which does
    ``expected_hash != args['hash']``) accepts old anchors unchanged.
    """
    h = compute_line_hash(1, 'Hello\n')  # sha256 by default
    legacy = _legacy_crc8_hex(1, 'Hello\n')
    assert h == legacy  # migration: old anchor still matches


def test_legacy_crc8_anchor_matches_crc32_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy 8-bit CRC anchors also match when crc32 format is selected."""
    monkeypatch.setenv('TEAAGENT_EDIT_HASH_FORMAT', 'crc32')
    h = compute_line_hash(1, 'Hello\n')
    legacy = _legacy_crc8_hex(1, 'Hello\n')
    assert h == legacy


def test_ne_operator_with_legacy_anchor() -> None:
    """The ``!=`` operator returns False for a matching legacy anchor."""
    h = compute_line_hash(1, 'Hello\n')
    legacy = _legacy_crc8_hex(1, 'Hello\n')
    assert (h != legacy) is False


def test_wrong_legacy_anchor_does_not_match() -> None:
    """A stale 8-bit CRC value that doesn't correspond to the line must
    not match (otherwise the hash provides no integrity)."""
    h = compute_line_hash(1, 'Hello\n')
    # '00' is almost certainly not the correct 8-bit CRC for '1:Hello'
    if _legacy_crc8_hex(1, 'Hello\n') == '00':
        pytest.skip('coincidental collision with 00')
    assert h != '00'


# ---------------------------------------------------------------------------
# Sanity: internal helpers produce expected values
# ---------------------------------------------------------------------------


def test_sha256_hex_helper() -> None:
    assert _sha256_hex(1, 'Hello\n') == hashlib.sha256(b'1:Hello').hexdigest()


def test_crc32_hex_helper() -> None:
    assert _crc32_hex(1, 'Hello\n') == f'{zlib.crc32(b"1:Hello") & 0xFFFFFFFF:08X}'


def test_legacy_crc8_hex_helper() -> None:
    assert _legacy_crc8_hex(1, 'Hello\n') == f'{zlib.crc32(b"1:Hello") & 0xFF:02X}'
