"""SURF-003: cockpit snapshot contract for operator dashboards."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.cockpit_parity import (
    COCKPIT_SNAPSHOT_SCHEMA_VERSION,
    build_cockpit_snapshot,
)


class CockpitSnapshotFlowTests(unittest.TestCase):
    def test_build_cockpit_snapshot_includes_core_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_cockpit_snapshot(tmp)
            self.assertEqual(payload['schema_version'], COCKPIT_SNAPSHOT_SCHEMA_VERSION)
            self.assertIn('control', payload)
            self.assertIn('pending_approvals', payload)
            self.assertIn('stale_workspace', payload)
            self.assertIn('approval', payload['control'])

    def test_cli_cockpit_emits_snapshot_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(['cockpit', '--root', tmp])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload['schema_version'], COCKPIT_SNAPSHOT_SCHEMA_VERSION)


if __name__ == '__main__':
    unittest.main()
