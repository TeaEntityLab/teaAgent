from __future__ import annotations

import tempfile
import time
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from teaagent.cockpit import ControlCockpitState, build_control_cockpit

if TYPE_CHECKING:
    from teaagent.tui import TeaAgentTUI


def test_control_cockpit_dataclass_fields() -> None:
    """All fields must exist with expected types/defaults."""
    cc = ControlCockpitState()

    assert cc.spec is None
    assert cc.goal is None
    assert cc.model_route is None
    assert isinstance(cc.memory, dict)
    assert 'total_entries' in cc.memory
    assert 'last_entry_summary' in cc.memory
    assert cc.review is None
    assert isinstance(cc.skill, dict)
    assert 'loaded_count' in cc.skill
    assert 'shadowed_count' in cc.skill
    assert 'candidate_count' in cc.skill
    assert 'governance_status' in cc.skill
    assert isinstance(cc.approval, dict)
    assert 'pending_count' in cc.approval
    assert 'blocked_count' in cc.approval
    assert 'mode' in cc.approval
    assert isinstance(cc.cost, dict)
    assert 'spent_cents' in cc.cost
    assert 'limit_cents' in cc.cost
    assert 'state' in cc.cost
    assert cc.last_updated is None


def test_control_cockpit_dataclass_defaults() -> None:
    """Default values must be sensible."""
    cc = ControlCockpitState()
    assert cc.memory['total_entries'] == 0
    assert cc.memory['last_entry_summary'] == ''
    assert cc.skill['loaded_count'] == 0
    assert cc.skill['shadowed_count'] == 0
    assert cc.skill['candidate_count'] == 0
    assert cc.skill['governance_status'] == {}
    assert cc.approval['pending_count'] == 0
    assert cc.approval['blocked_count'] == 0
    assert cc.approval['mode'] == 'prompt'
    assert cc.cost['spent_cents'] == 0.0
    assert cc.cost['limit_cents'] is None
    assert cc.cost['state'] == 'unavailable'


def test_build_control_cockpit_empty_workspace() -> None:
    """Build from empty tmp_path must not raise."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cockpit = build_control_cockpit(root)

        assert isinstance(cockpit, ControlCockpitState)
        assert cockpit.spec is None
        assert cockpit.goal is None
        assert cockpit.model_route is None
        assert cockpit.memory['total_entries'] == 0
        assert cockpit.memory['last_entry_summary'] == ''
        assert cockpit.review is None
        assert cockpit.skill['loaded_count'] == 0
        assert cockpit.approval['pending_count'] == 0
        assert cockpit.cost['spent_cents'] == 0.0
        assert cockpit.last_updated is not None


def test_build_control_cockpit_with_cost_params() -> None:
    """Cost parameters must be reflected in the cockpit."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cockpit = build_control_cockpit(
            root,
            permission_mode='read-only',
            cost_cents=350.0,
            cost_limit_cents=1000,
            cost_state='actual',
        )

        assert cockpit.cost['spent_cents'] == 350.0
        assert cockpit.cost['limit_cents'] == 1000
        assert cockpit.cost['state'] == 'actual'
        assert cockpit.approval['mode'] == 'read-only'


def test_build_control_cockpit_time_stamp() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = time.time()
        cockpit = build_control_cockpit(root)
        after = time.time()

        assert cockpit.last_updated is not None
        assert cockpit.last_updated >= before
        assert cockpit.last_updated <= after


def test_build_control_cockpit_with_goals() -> None:
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

        assert cockpit.goal is not None
        assert cockpit.goal['goal_id'] == 'g-test-001'
        assert cockpit.goal['objective'] == 'Refactor the auth module'
        assert cockpit.goal['status'] == 'active'
        assert cockpit.goal['blockers'] == ['Need design review']
        assert cockpit.goal['next_gate'] == 'human-review'

        assert cockpit.spec is not None
        assert cockpit.spec['spec_id'] == 'spec-abc'
        assert cockpit.spec['spec_hash'] == 'abc123'
        assert cockpit.spec['spec_exemption'] is None

        assert cockpit.review is not None
        assert cockpit.review['review_ids_count'] == 0


def _render_cockpit(tui: TeaAgentTUI) -> str:
    buffer = StringIO()
    with (
        patch('sys.stdout', buffer),
        patch('shutil.get_terminal_size', return_value=(120, 30)),
    ):
        tui._print_state_panel()
    return buffer.getvalue()


def test_control_cockpit_renders_in_state_panel() -> None:
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

    output = _render_cockpit(tui)

    assert '[Control Cockpit]' in output
    assert 'Goal: active — Test goal' in output
    assert 'Memory: 5 entries' in output
    assert 'Review: 2 reviews, gate=passed' in output
    assert 'Skills: 3 loaded' in output
    assert '1 shadowed' in output
    assert '2 candidates' in output
    assert 'Approval: 1 pending, 0 blocked, mode=prompt' in output
    assert 'Cost: $1.50 / $10.00 (actual)' in output


def test_control_cockpit_long_goal_truncation() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    expected = 'A' * 57 + '...'
    assert f'Goal: active — {expected}' in output
    assert 'A' * 58 not in output


def test_control_cockpit_spec_fallback() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    assert 'Spec: spec-xyz-123' in output


def test_control_cockpit_no_goal_no_spec() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    assert 'Spec/Goal: none' in output


def test_control_cockpit_with_model_route() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    assert 'Model: claude/sonnet-4 (est. $1.20)' in output


def test_control_cockpit_no_model_route() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    assert 'Model: gpt/gpt-4o (no route)' in output


def test_control_cockpit_governance_summary() -> None:
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

    output = _render_cockpit(tui)
    assert '[Control Cockpit]' in output
    assert 'Governance: candidate/external/installed' in output


def test_refresh_control_cockpit_sets_field() -> None:
    from teaagent.tui import TeaAgentTUI

    with tempfile.TemporaryDirectory() as tmp:
        buffer = StringIO()
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=buffer.write,
            root=tmp,
        )
        assert tui._control_cockpit is None
        tui._refresh_control_cockpit()
        assert isinstance(tui._control_cockpit, ControlCockpitState)
        assert tui._control_cockpit.last_updated is not None


def test_refresh_control_cockpit_handles_errors() -> None:
    """_refresh_control_cockpit must not raise even when build fails."""
    from teaagent.tui import TeaAgentTUI

    buffer = StringIO()
    tui = TeaAgentTUI(
        input_fn=lambda _prompt: 'exit',
        output_fn=buffer.write,
    )
    # Simulate a failure in build_control_cockpit
    with patch(
        'teaagent.tui.core.build_control_cockpit',
        side_effect=RuntimeError('simulated failure'),
    ):
        tui._refresh_control_cockpit()

    assert tui._control_cockpit is None
