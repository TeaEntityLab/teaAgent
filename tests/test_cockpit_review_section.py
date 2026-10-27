from __future__ import annotations

# test-type: behavior
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from teaagent.cockpit import ControlCockpitState, build_control_cockpit
from teaagent.goal_record import GoalRecord, GoalStore
from teaagent.tui import TeaAgentTUI


def test_goal_without_review_source_reports_review_unavailable() -> None:
    """No recorded review source exists, so the review section must be None.

    Previously a goal produced ``{'review_ids_count': 0, 'latest_review_status':
    'unknown'}`` because the cockpit read a ``review_ids`` key that is never
    written into the goal dict. That reads as "0 reviews" and is not real data.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        GoalStore(root).save(
            GoalRecord(goal_id='g-review-1', objective='Ship the cockpit fix')
        )

        cockpit = build_control_cockpit(root)

        assert cockpit.goal is not None
        assert cockpit.review is None


def test_tui_renders_unavailable_review_section() -> None:
    """A None review section renders as explicitly unavailable, not as zero reviews."""
    tui = TeaAgentTUI(
        input_fn=lambda _prompt: 'exit',
        output_fn=lambda _: None,
    )
    tui._control_cockpit = ControlCockpitState(
        goal={
            'goal_id': 'g-1',
            'objective': 'Review rendering',
            'status': 'active',
            'blockers': [],
        },
        review=None,
        last_updated=0.0,
    )

    buffer = StringIO()
    with (
        patch('sys.stdout', buffer),
        patch('shutil.get_terminal_size', return_value=(120, 30)),
    ):
        tui._print_state_panel()
    output = buffer.getvalue()

    assert 'Review: unavailable' in output
    assert 'reviews, gate=' not in output
