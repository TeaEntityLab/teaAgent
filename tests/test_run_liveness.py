"""Tests for durable run liveness files."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.ergonomics.run_liveness import (
    clear_liveness,
    liveness_snapshot,
    touch_liveness,
)
from teaagent.heartbeat import Heartbeat
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


class RunLivenessTests(unittest.TestCase):
    def test_touch_and_snapshot_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            touch_liveness(tmp, 'run-live', tick=1, interval_seconds=5.0)
            snap = liveness_snapshot(tmp, 'run-live', stale_after_seconds=90.0)
            assert snap is not None
            self.assertEqual(snap['tick'], 1)
            self.assertFalse(snap['stale'])

    def test_heartbeat_writes_liveness_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLogger()
            beat = Heartbeat(
                audit,
                'run-hb',
                interval_seconds=0.02,
                liveness_root=Path(tmp),
            )
            with beat:
                time.sleep(0.08)
            snap = liveness_snapshot(tmp, 'run-hb')
            self.assertIsNotNone(snap)
            self.assertGreaterEqual(int(snap['tick']), 1)

    def test_run_state_includes_liveness_when_file_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            touch_liveness(tmp, 'state-run', tick=2, interval_seconds=5.0)
            store = RunStore(tmp)
            audit = store.audit_logger('state-run')
            audit.record('run_started', 'state-run', task='t')
            audit.record('heartbeat', 'state-run', tick=2, interval_seconds=5.0)

            payload = store.heartbeat_for_run('state-run')
            self.assertIsNotNone(payload.get('liveness_updated_at'))
            self.assertFalse(payload['liveness_stale'])

    def test_background_get_enriches_liveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            touch_liveness(tmp, 'bg-run', tick=1, interval_seconds=30.0)
            bg_dir = Path(tmp) / '.teaagent' / 'background'
            bg_dir.mkdir(parents=True)
            log_path = bg_dir / 'bg01.log'
            log_path.write_text(
                '{"run_id":"bg-run","status":"running"}\n', encoding='utf-8'
            )
            (bg_dir / 'bg01.json').write_text(
                json.dumps(
                    {
                        'background_id': 'bg01',
                        'pid': 2_147_483_647,
                        'command': ['noop'],
                        'started_at': '2026-06-09T00:00:00+00:00',
                        'log_path': str(log_path),
                        'run_id': 'bg-run',
                    }
                ),
                encoding='utf-8',
            )
            shown = BackgroundRunStore(tmp).get('bg01')
            self.assertEqual(shown['run_id'], 'bg-run')
            self.assertIn('liveness_updated_at', shown)
            self.assertFalse(shown['liveness_stale'])

    def test_clear_liveness_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            touch_liveness(tmp, 'gone', tick=1, interval_seconds=1.0)
            clear_liveness(tmp, 'gone')
            self.assertIsNone(liveness_snapshot(tmp, 'gone'))


if __name__ == '__main__':
    unittest.main()
