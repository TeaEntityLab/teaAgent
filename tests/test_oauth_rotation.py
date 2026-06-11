from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.oauth21._store import OAuthKeyRing
from teaagent.oauth21._types import JWTError


def _ring(**kwargs) -> OAuthKeyRing:
    return OAuthKeyRing(
        active_kid='v1',
        keys={'v1': b'key-v1-secret-123456', 'v2': b'key-v2-secret-123456'},
        **kwargs,
    )


def test_rotate_changes_active_kid() -> None:
    ring = _ring()
    rotated = ring.rotate('v2')
    assert rotated.active_kid == 'v2'


def test_rotate_marks_old_kid_deprecated_at() -> None:
    now = 1_000_000.0
    ring = _ring()
    rotated = ring.rotate('v2', now=now)
    assert rotated.deprecated_at['v1'] == pytest.approx(now)


def test_rotate_preserves_all_keys() -> None:
    ring = _ring()
    rotated = ring.rotate('v2')
    assert 'v1' in rotated.keys
    assert 'v2' in rotated.keys


def test_rotate_preserves_rotation_window() -> None:
    ring = _ring(rotation_window_seconds=300)
    rotated = ring.rotate('v2')
    assert rotated.rotation_window_seconds == 300


def test_rotate_unknown_kid_raises() -> None:
    ring = _ring()
    with pytest.raises(ValueError):
        ring.rotate('v99')


def test_rotate_is_immutable_original_unchanged() -> None:
    ring = _ring()
    ring.rotate('v2')
    assert ring.active_kid == 'v1'
    assert ring.deprecated_at == {}


def test_active_kid_always_valid() -> None:
    ring = _ring(rotation_window_seconds=60)
    key = ring.key_for_validation('v1')
    assert key == b'key-v1-secret-123456'


def test_non_active_kid_valid_within_window() -> None:
    now = time.time()
    ring = _ring(
        rotation_window_seconds=300,
        deprecated_at={'v1': now - 60},  # deprecated 60s ago, window=300s
    ).rotate('v2', now=now)
    # v1 deprecated at now, window=300 — still valid
    key = ring.key_for_validation('v1', now=now + 10)
    assert key == b'key-v1-secret-123456'


def test_non_active_kid_rejected_outside_window() -> None:
    now = 1_000_000.0
    ring = _ring(rotation_window_seconds=300)
    rotated = ring.rotate('v2', now=now)
    # 400s later — outside 300s window
    with pytest.raises(JWTError) as ctx:
        rotated.key_for_validation('v1', now=now + 400)
    assert 'rotation window' in str(ctx.value)


def test_no_window_zero_never_enforces_expiry() -> None:
    now = 1_000_000.0
    ring = _ring(rotation_window_seconds=0)
    rotated = ring.rotate('v2', now=now)
    # rotation_window_seconds=0 → no enforcement
    key = rotated.key_for_validation('v1', now=now + 999_999)
    assert key == b'key-v1-secret-123456'


def test_non_active_kid_without_deprecated_at_always_valid() -> None:
    # Key in ring but no deprecated_at entry → treated as always valid
    ring = OAuthKeyRing(
        active_kid='v2',
        keys={'v1': b'key-v1-secret-123456', 'v2': b'key-v2-secret-123456'},
        rotation_window_seconds=60,
    )
    key = ring.key_for_validation('v1', now=time.time() + 999_999)
    assert key == b'key-v1-secret-123456'


def test_unknown_kid_falls_back_to_active() -> None:
    ring = _ring()
    key = ring.key_for_validation('v99')
    assert key == ring.active_key


def test_rotation_window_accepted_on_serve() -> None:
    from teaagent.cli import main

    with (
        tempfile.TemporaryDirectory() as tmp,
        patch('teaagent.cli.serve_mcp_http', return_value=0),
    ):
        key_ring_path = Path(tmp) / 'kr.json'
        key_ring_path.write_text(
            json.dumps(
                {
                    'active_kid': 'v1',
                    'keys': {'v1': 'signing-secret-key-at-least-32-chars'},
                }
            ),
            encoding='utf-8',
        )
        exit_code = main(
            [
                'mcp',
                'serve',
                '--http',
                '--root',
                tmp,
                '--oauth-issuer',
                'https://issuer.test',
                '--oauth-signing-key',
                'signing-secret-key-at-least-32-chars',
                '--oauth-key-ring-file',
                str(key_ring_path),
                '--oauth-rotation-window',
                '300',
            ]
        )
    assert exit_code == 0


def test_rotation_window_zero_is_default() -> None:
    from teaagent.cli import main

    with (
        tempfile.TemporaryDirectory() as tmp,
        patch('teaagent.cli.serve_mcp_http', return_value=0),
    ):
        key_ring_path = Path(tmp) / 'kr.json'
        key_ring_path.write_text(
            json.dumps(
                {
                    'active_kid': 'v1',
                    'keys': {'v1': 'signing-secret-key-at-least-32-chars'},
                }
            ),
            encoding='utf-8',
        )
        exit_code = main(
            [
                'mcp',
                'serve',
                '--http',
                '--root',
                tmp,
                '--oauth-issuer',
                'https://issuer.test',
                '--oauth-signing-key',
                'signing-secret-key-at-least-32-chars',
                '--oauth-key-ring-file',
                str(key_ring_path),
            ]
        )
    assert exit_code == 0
