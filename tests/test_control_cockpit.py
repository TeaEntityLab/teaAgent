from __future__ import annotations

import unittest
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from teaagent.cockpit import ControlCockpitState, build_control_cockpit

if TYPE_CHECKING:
    from teaagent.tui import TeaAgentTUI


class ControlCockpitDataclassTests(unittest.TestCase):
    def test_control_cockpit_dataclass_fields(self) -> None:
        """All fields must exist with expected types/defaults."""
        cc = ControlCockpitState()

        self.assertIsNone(cc.spec)
        self.assertIsNone(cc.goal)
        self.assertIsNone(cc.model_route)
        self.assertIsInstance(cc.memory, dict)
        self.assertIn('total_entries', cc.memory)
        self.assertIn('last_entry_summary', cc.memory)
        self.assertIsNone(cc.review)
        self.assertIsInstance(cc.skill, dict)
        self.assertIn('loaded_count', cc.skill)
        self.assertIn('shadowed_count', cc.skill)
        self.assertIn('candidate_count', cc.skill)
        self.assertIn('governance_status', cc.skill)
        self.assertIsInstance(cc.approval, dict)
        self.assertIn('pending_count', cc.approval)
        self.assertIn('blocked_count', cc.approval)
        self.assertIn('mode', cc.approval)
        self.assertIsInstance(cc.cost, dict)
        self.assertIn('spent_cents', cc.cost)
        self.assertIn('limit_cents', cc.cost)
        self.assertIn('state', cc.cost)
        self.assertIsNone(cc.last_updated)

    def test_control_cockpit_dataclass_defaults(self) -> None:
        """Default values must be sensible."""
        cc = ControlCockpitState()
        self.assertEqual(cc.memory['total_entries'], 0)
        self.assertEqual(cc.memory['last_entry_summary'], '')
        self.assertEqual(cc.skill['loaded_count'], 0)
        self.assertEqual(cc.skill['shadowed_count'], 0)
        self.assertEqual(cc.skill['candidate_count'], 0)
        self.assertEqual(cc.skill['governance_status'], {})
        self.assertEqual(cc.approval['pending_count'], 0)
        self.assertEqual(cc.approval['blocked_count'], 0)
        self.assertEqual(cc.approval['mode'], 'prompt')
        self.assertEqual(cc.cost['spent_cents'], 0.0)
        self.assertIsNone(cc.cost['limit_cents'])
        self.assertEqual(cc.cost['state'], 'unavailable')


class BuildControlCockpitTests(unittest.TestCase):
    def test_build_control_cockpit_empty_workspace(self) -> None:
        """Build from empty tmp_path must not raise."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cockpit = build_control_cockpit(root)

            self.assertIsInstance(cockpit, ControlCockpitState)
            self.assertIsNone(cockpit.spec)
            self.assertIsNone(cockpit.goal)
            self.assertIsNone(cockpit.model_route)
            self.assertEqual(cockpit.memory['total_entries'], 0)
            self.assertEqual(cockpit.memory['last_entry_summary'], '')
            self.assertIsNone(cockpit.review)
            self.assertEqual(cockpit.skill['loaded_count'], 0)
            self.assertEqual(cockpit.approval['pending_count'], 0)
            self.assertEqual(cockpit.cost['spent_cents'], 0.0)
            self.assertIsNotNone(cockpit.last_updated)

    def test_build_control_cockpit_with_cost_params(self) -> None:
        """Cost parameters must be reflected in the cockpit."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cockpit = build_control_cockpit(
                root,
                permission_mode='read-only',
                cost_cents=350.0,
                cost_limit_cents=1000,
                cost_state='actual',
            )

            self.assertEqual(cockpit.cost['spent_cents'], 350.0)
            self.assertEqual(cockpit.cost['limit_cents'], 1000)
            self.assertEqual(cockpit.cost['state'], 'actual')
            self.assertEqual(cockpit.approval['mode'], 'read-only')

    def test_build_control_cockpit_time_stamp(self) -> None:
        import tempfile
        import time

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = time.time()
            cockpit = build_control_cockpit(root)
            after = time.time()

            self.assertIsNotNone(cockpit.last_updated)
            self.assertGreaterEqual(cockpit.last_updated, before)
            self.assertLessEqual(cockpit.last_updated, after)

    def test_build_control_cockpit_with_goals(self) -> None:
        import tempfile

        from teaagent.goal_record import GoalRecord, GoalStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GoalStore(root)
            goal = GoalRecord(
                goal_id='g-test-001',
                objective='Refactor the auth module',
                status='active',
                spec_id='spec-abc',
                spec_hash='abc123',
                task_ids=['t1', 't2'],
                run_ids=['r1'],
                cost_cents=500.0,
                blockers=['Need design review'],
                next_gate='human-review',
            )
            store.save(goal)

            cockpit = build_control_cockpit(root)

            self.assertIsNotNone(cockpit.goal)
            assert cockpit.goal is not None
            self.assertEqual(cockpit.goal['goal_id'], 'g-test-001')
            self.assertEqual(cockpit.goal['objective'], 'Refactor the auth module')
            self.assertEqual(cockpit.goal['status'], 'active')
            self.assertEqual(cockpit.goal['blockers'], ['Need design review'])
            self.assertEqual(cockpit.goal['next_gate'], 'human-review')

            self.assertIsNotNone(cockpit.spec)
            assert cockpit.spec is not None
            self.assertEqual(cockpit.spec['spec_id'], 'spec-abc')
            self.assertEqual(cockpit.spec['spec_hash'], 'abc123')
            self.assertIsNone(cockpit.spec['spec_exemption'])

            self.assertIsNotNone(cockpit.review)
            assert cockpit.review is not None
            self.assertEqual(cockpit.review['review_ids_count'], 0)


class ControlCockpitRenderingTests(unittest.TestCase):
    def _render_cockpit(self, tui: TeaAgentTUI) -> str:
        buffer = StringIO()
        with (
            patch('sys.stdout', buffer),
            patch('shutil.get_terminal_size', return_value=(120, 30)),
        ):
            tui._print_state_panel()
        return buffer.getvalue()

    def test_control_cockpit_renders_in_state_panel(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            goal={
                'goal_id': 'g-1',
                'objective': 'Test goal',
                'status': 'active',
                'blockers': [],
            },
            model_route=None,
            memory={'total_entries': 5, 'last_entry_summary': 'test memory'},
            review={'review_ids_count': 2, 'latest_review_status': 'passed'},
            skill={
                'loaded_count': 3,
                'shadowed_count': 1,
                'candidate_count': 2,
                'governance_status': {'skill-1': 'installed', 'skill-2': 'candidate'},
            },
            approval={'pending_count': 1, 'blocked_count': 0, 'mode': 'prompt'},
            cost={'spent_cents': 150.0, 'limit_cents': 1000, 'state': 'actual'},
            last_updated=0.0,
        )

        output = self._render_cockpit(tui)

        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Goal: active — Test goal', output)
        self.assertIn('Memory: 5 entries', output)
        self.assertIn('Review: 2 reviews, gate=passed', output)
        self.assertIn('Skills: 3 loaded', output)
        self.assertIn('1 shadowed', output)
        self.assertIn('2 candidates', output)
        self.assertIn('Approval: 1 pending, 0 blocked, mode=prompt', output)
        self.assertIn('Cost: $1.50 / $10.00 (actual)', output)

    def test_control_cockpit_long_goal_truncation(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            goal={
                'goal_id': 'g-1',
                'objective': 'A' * 80,
                'status': 'active',
                'blockers': [],
            },
            model_route=None,
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        expected = 'A' * 57 + '...'
        self.assertIn(f'Goal: active — {expected}', output)
        self.assertNotIn('A' * 58, output)

    def test_control_cockpit_spec_fallback(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            spec={
                'spec_id': 'spec-xyz-123',
                'spec_hash': 'deadbeef',
                'spec_exemption': None,
            },
            goal=None,
            model_route=None,
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Spec: spec-xyz-123', output)

    def test_control_cockpit_no_goal_no_spec(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            goal=None,
            spec=None,
            model_route=None,
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Spec/Goal: none', output)

    def test_control_cockpit_with_model_route(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            goal=None,
            spec=None,
            model_route={
                'provider': 'claude',
                'model': 'sonnet-4',
                'estimated_cost_cents': 120,
            },
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Model: claude/sonnet-4 (est. $1.20)', output)

    def test_control_cockpit_no_model_route(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
            provider='gpt',
            model='gpt-4o',
        )
        tui._control_cockpit = ControlCockpitState(
            goal=None,
            spec=None,
            model_route=None,
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Model: gpt/gpt-4o (no route)', output)

    def test_control_cockpit_governance_summary(self) -> None:
        from teaagent.tui import TeaAgentTUI

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=lambda _: None,
        )
        tui._control_cockpit = ControlCockpitState(
            goal=None,
            spec=None,
            model_route=None,
            skill={
                'loaded_count': 4,
                'shadowed_count': 0,
                'candidate_count': 1,
                'governance_status': {
                    'a': 'installed',
                    'b': 'installed',
                    'c': 'candidate',
                    'd': 'external',
                },
            },
        )

        output = self._render_cockpit(tui)
        self.assertIn('[Control Cockpit]', output)
        self.assertIn('Governance: candidate/external/installed', output)

    def test_refresh_control_cockpit_sets_field(self) -> None:
        import tempfile
        from io import StringIO

        from teaagent.tui import TeaAgentTUI

        with tempfile.TemporaryDirectory() as tmp:
            buffer = StringIO()
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: 'exit',
                output_fn=buffer.write,
                root=tmp,
            )
            self.assertIsNone(tui._control_cockpit)
            tui._refresh_control_cockpit()
            self.assertIsInstance(tui._control_cockpit, ControlCockpitState)
            self.assertIsNotNone(tui._control_cockpit.last_updated)

    def test_refresh_control_cockpit_handles_errors(self) -> None:
        """_refresh_control_cockpit must not raise even when build fails."""
        from io import StringIO
        from unittest.mock import patch

        from teaagent.tui import TeaAgentTUI

        buffer = StringIO()
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=buffer.write,
        )
        # Simulate a failure in build_control_cockpit
        with patch(
            'teaagent.tui.build_control_cockpit',
            side_effect=RuntimeError('simulated failure'),
        ):
            tui._refresh_control_cockpit()

        self.assertIsNone(tui._control_cockpit)


if __name__ == '__main__':
    unittest.main()
