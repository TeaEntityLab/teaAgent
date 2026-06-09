"""SURF-001: shared run-state schema across surfaces."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.run_state import (
    RUN_STATE_SCHEMA_VERSION,
    build_run_state_snapshot,
)
from teaagent.run_store import RunStore
from teaagent.tui import TeaAgentTUI


class RunStateContractTests(unittest.TestCase):
    def test_build_run_state_includes_git_sandbox_and_cost(self) -> None:
        events = [
            {
                'event_type': 'run_started',
                'payload': {'task': 't', 'permission_mode': 'read-only'},
            },
            {
                'event_type': 'git_sandbox_started',
                'payload': {
                    'success': True,
                    'auto_stash': True,
                    'branch_name': 'teaagent-sandbox-run1',
                    'original_branch': 'main',
                    'stash_id': 'stash@{0}',
                },
            },
            {
                'event_type': 'heartbeat',
                'created_at': '2026-06-09T00:00:00Z',
                'payload': {'tick': 2},
            },
            {
                'event_type': 'git_sandbox_resolved',
                'payload': {'resolution': 'merge', 'success': True},
            },
            {
                'event_type': 'run_completed',
                'payload': {'answer': 'ok', 'cost_cents': 42.5},
            },
        ]
        snapshot = build_run_state_snapshot(events, 'run1', undo_available=True)
        payload = snapshot.to_dict()

        self.assertEqual(payload['schema_version'], RUN_STATE_SCHEMA_VERSION)
        self.assertEqual(payload['status'], 'completed')
        self.assertEqual(payload['cost_cents'], 42.5)
        self.assertEqual(payload['permission_mode'], 'read-only')
        self.assertTrue(payload['undo_available'])
        self.assertIsNotNone(payload['git_sandbox'])
        self.assertEqual(payload['git_sandbox']['resolution'], 'merge')

    def test_cli_and_tui_status_return_identical_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger('parity-run')
            audit.record('run_started', 'parity-run', task='parity')
            audit.record('heartbeat', 'parity-run', tick=1, interval_seconds=0.1)
            audit.record(
                'git_sandbox_started',
                'parity-run',
                success=True,
                auto_stash=False,
                branch_name='teaagent-sandbox-parity-run',
                original_branch='main',
            )
            audit.record('run_completed', 'parity-run', answer='done', cost_cents=10.0)

            cli_out = io.StringIO()
            with redirect_stdout(cli_out):
                code = main(['agent', 'status', 'parity-run', '--root', tmp])
            self.assertEqual(code, 0)
            cli_payload = json.loads(cli_out.getvalue())

            tui_out: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=tui_out.append,
            )
            self.assertTrue(tui.handle_command('status parity-run'))
            tui_payload = json.loads(tui_out[-1])

            self.assertEqual(cli_payload, tui_payload)
            self.assertEqual(cli_payload['schema_version'], RUN_STATE_SCHEMA_VERSION)
            self.assertIn('git_sandbox', cli_payload)


if __name__ == '__main__':
    unittest.main()
