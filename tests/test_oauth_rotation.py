from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from teaagent.oauth21._store import OAuthKeyRing
from teaagent.oauth21._types import JWTError


class OAuthKeyRingRotationTests(unittest.TestCase):
    def _ring(self, **kwargs) -> OAuthKeyRing:
        return OAuthKeyRing(
            active_kid='v1',
            keys={'v1': b'key-v1-secret-123456', 'v2': b'key-v2-secret-123456'},
            **kwargs,
        )

    # --- rotate() ---

    def test_rotate_changes_active_kid(self) -> None:
        ring = self._ring()
        rotated = ring.rotate('v2')
        self.assertEqual(rotated.active_kid, 'v2')

    def test_rotate_marks_old_kid_deprecated_at(self) -> None:
        now = 1_000_000.0
        ring = self._ring()
        rotated = ring.rotate('v2', now=now)
        self.assertAlmostEqual(rotated.deprecated_at['v1'], now)

    def test_rotate_preserves_all_keys(self) -> None:
        ring = self._ring()
        rotated = ring.rotate('v2')
        self.assertIn('v1', rotated.keys)
        self.assertIn('v2', rotated.keys)

    def test_rotate_preserves_rotation_window(self) -> None:
        ring = self._ring(rotation_window_seconds=300)
        rotated = ring.rotate('v2')
        self.assertEqual(rotated.rotation_window_seconds, 300)

    def test_rotate_unknown_kid_raises(self) -> None:
        ring = self._ring()
        with self.assertRaises(ValueError):
            ring.rotate('v99')

    def test_rotate_is_immutable_original_unchanged(self) -> None:
        ring = self._ring()
        ring.rotate('v2')
        self.assertEqual(ring.active_kid, 'v1')
        self.assertEqual(ring.deprecated_at, {})

    # --- key_for_validation() ---

    def test_active_kid_always_valid(self) -> None:
        ring = self._ring(rotation_window_seconds=60)
        key = ring.key_for_validation('v1')
        self.assertEqual(key, b'key-v1-secret-123456')

    def test_non_active_kid_valid_within_window(self) -> None:
        now = time.time()
        ring = self._ring(
            rotation_window_seconds=300,
            deprecated_at={'v1': now - 60},  # deprecated 60s ago, window=300s
        ).rotate('v2', now=now)
        # v1 deprecated at now, window=300 — still valid
        key = ring.key_for_validation('v1', now=now + 10)
        self.assertEqual(key, b'key-v1-secret-123456')

    def test_non_active_kid_rejected_outside_window(self) -> None:
        now = 1_000_000.0
        ring = self._ring(rotation_window_seconds=300)
        rotated = ring.rotate('v2', now=now)
        # 400s later — outside 300s window
        with self.assertRaises(JWTError) as ctx:
            rotated.key_for_validation('v1', now=now + 400)
        self.assertIn('rotation window', str(ctx.exception))

    def test_no_window_zero_never_enforces_expiry(self) -> None:
        now = 1_000_000.0
        ring = self._ring(rotation_window_seconds=0)
        rotated = ring.rotate('v2', now=now)
        # rotation_window_seconds=0 → no enforcement
        key = rotated.key_for_validation('v1', now=now + 999_999)
        self.assertEqual(key, b'key-v1-secret-123456')

    def test_non_active_kid_without_deprecated_at_always_valid(self) -> None:
        # Key in ring but no deprecated_at entry → treated as always valid
        ring = OAuthKeyRing(
            active_kid='v2',
            keys={'v1': b'key-v1-secret-123456', 'v2': b'key-v2-secret-123456'},
            rotation_window_seconds=60,
        )
        key = ring.key_for_validation('v1', now=time.time() + 999_999)
        self.assertEqual(key, b'key-v1-secret-123456')

    def test_unknown_kid_falls_back_to_active(self) -> None:
        ring = self._ring()
        key = ring.key_for_validation('v99')
        self.assertEqual(key, ring.active_key)


class OAuthKeyRingCLIRotationWindowTests(unittest.TestCase):
    def test_rotation_window_accepted_on_serve(self) -> None:
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
                        'keys': {'v1': 'signing-secret-key-12345'},
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
                    'signing-secret-key-12345',
                    '--oauth-key-ring-file',
                    str(key_ring_path),
                    '--oauth-rotation-window',
                    '300',
                ]
            )
        self.assertEqual(exit_code, 0)

    def test_rotation_window_zero_is_default(self) -> None:
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
                        'keys': {'v1': 'signing-secret-key-12345'},
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
                    'signing-secret-key-12345',
                    '--oauth-key-ring-file',
                    str(key_ring_path),
                ]
            )
        self.assertEqual(exit_code, 0)


if __name__ == '__main__':
    unittest.main()
