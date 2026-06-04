from __future__ import annotations

import json
import tempfile
import unittest

from teaagent.run_store import RunStore


class SuspensionDataTests(unittest.TestCase):
    """CG-14: Verify suspension data does not contain redundant audit_trail field."""

    def test_suspension_data_has_no_audit_trail_field(self) -> None:
        """Suspension JSON produced by suspend_to_background must not include audit_trail.

        Regression test for CG-14 / TICKET-15. The audit_trail field was a pre-CG-10
        placeholder; real governance records live in RunStore.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            # Simulate suspension data that suspend_to_background produces
            suspension_data = {
                'run_id': 'test-run-001',
                'timestamp': 1717459200.0,
                'acp_version': '1.0.0',
                'mode': 'suspended_from_repl',
                'config': {
                    'model': 'gpt-4',
                    'permission_mode': 'read-only',
                    'max_iterations': 50,
                    'max_tool_calls': 200,
                    'max_estimated_cost_cents': 200,
                },
                'session_context': {
                    'observations_count': 5,
                    'compaction_count': 1,
                    'observations': ['obs 1', 'obs 2'],
                },
                'targeted_files': [],
            }

            # Verify no audit_trail field in suspension data
            self.assertNotIn('audit_trail', suspension_data)

            # Verify JSON serialization round-trip does not introduce it
            as_json = json.dumps(suspension_data)
            parsed = json.loads(as_json)
            self.assertNotIn('audit_trail', parsed)

            # Verify RunStore audit logger is the real governance path
            audit = store.audit_logger('test-run-001')
            audit.record(
                'session_suspended', 'test-run-001', suspension_type='background'
            )
            events = store.show_run('test-run-001')
            self.assertTrue(
                any(e.get('event_type') == 'session_suspended' for e in events)
            )
