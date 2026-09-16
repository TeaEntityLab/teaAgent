# test-type: behavior
"""Pin dogfood finding G31 (R3): ``agent run --background`` must forward the
plan flags (``--from-plan``/``--require-plan``/``--skip-plan-check``) so a
workspace-write background run does not die on ``PLAN_GATE``, and must never
append a literal ``None`` task to the worker argv when ``--from-plan`` supplies
the task.
"""

from __future__ import annotations

from argparse import Namespace

from teaagent.cli import build_parser
from teaagent.ergonomics.background_run import build_agent_run_command


def _base_ns(**overrides: object) -> Namespace:
    fields: dict[str, object] = {
        'provider': 'fake',
        'task': 'do something',
        'root': '.',
        'from_plan': None,
        'allow_external_plan': False,
        'require_plan': False,
        'skip_plan_check': False,
    }
    fields.update(overrides)
    return Namespace(**fields)


def test_plan_flags_forwarded_when_set() -> None:
    """Falsifier: fails if --from-plan/--require-plan/--skip-plan-check are dropped."""
    argv = build_agent_run_command(
        _base_ns(from_plan='/x/plan.md', require_plan=True, skip_plan_check=True),
        'do something',
    )
    assert '--from-plan' in argv
    assert argv[argv.index('--from-plan') + 1] == '/x/plan.md'
    assert '--require-plan' in argv
    assert '--skip-plan-check' in argv


def test_plan_flags_absent_when_unset() -> None:
    """Falsifier: fails if plan flags leak into argv when the args are unset."""
    argv = build_agent_run_command(_base_ns(), 'do something')
    assert '--from-plan' not in argv
    assert '--require-plan' not in argv
    assert '--skip-plan-check' not in argv


def test_from_plan_without_task_omits_positional_and_round_trips() -> None:
    """Falsifier: fails if a literal None/empty task is appended or from_plan is lost."""
    argv = build_agent_run_command(
        _base_ns(task=None, from_plan='/x/plan.md'),
        None,
    )
    assert 'None' not in argv
    assert None not in argv

    # Worker argv minus ``sys.executable -m teaagent.cli`` must parse cleanly
    # with the real top-level parser and round-trip --from-plan.
    inner = argv[3:]
    parser = build_parser()
    ns = parser.parse_args(inner)
    assert ns.from_plan == '/x/plan.md'
